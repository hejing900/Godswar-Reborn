"""Diff the kitbag frames around a wish to see what the wish granted.

The wish's answer (10280) names a player and a number but not obviously an item,
and the client refreshes its kitbag right after - so the granted item is the
difference between the kitbag before the wish and the kitbag after it.
"""
import struct
import subprocess

SQL = ("SELECT captured_at, encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10022 ORDER BY captured_at;")


def items(payload):
    """The kitbag frame's item ids, read as (id, count) pairs where possible."""
    found = []
    for offset in range(0, len(payload) - 8, 4):
        value = struct.unpack_from("<I", payload, offset)[0]
        if 1 <= value <= 20_000:
            found.append((offset, value))
    return found


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    snapshots = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        when, hexed = line.split("|")
        data = bytes.fromhex(hexed)
        snapshots.append((when[:23], data[4:]))
    print(f"kitbag frames in the capture: {len(snapshots)}")
    for when, payload in snapshots[-4:]:
        print(f"  {when} payload={len(payload)}")
    if len(snapshots) < 2:
        print("need two kitbag frames to diff")
        return 0

    # The wish happened at 22:21:12; compare the frame after it with the one before.
    before = next((p for w, p in reversed(snapshots) if w < "2026-09-13 22:21:12"), None)
    after = next((p for w, p in snapshots if w > "2026-09-13 22:21:12"), None)
    if before is None or after is None:
        before, after = snapshots[-2][1], snapshots[-1][1]
    print(f"before {len(before)} bytes, after {len(after)} bytes")
    length = min(len(before), len(after))
    differences = [offset for offset in range(0, length, 4)
                   if before[offset:offset + 4] != after[offset:offset + 4]]
    print(f"differing 4-byte slots: {len(differences)}")
    for offset in differences[:20]:
        old = struct.unpack_from("<I", before, offset)[0]
        new = struct.unpack_from("<I", after, offset)[0]
        print(f"  +{offset:<5} {old:>10} -> {new:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
