"""What the reference server actually sent for its city NPCs.

Decodes the captured opcode-10020 world-object frames and reports, per placed
map, the NPC templates and the low word of their object type - the flag word the
client reads to decide what an object is. Sparta's city NPCs came from this
capture; the other maps' NPCs are synthesised, so this is the yardstick to
compare them against.
"""
import collections
import struct
import subprocess

SQL = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10020;")


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    by_map = collections.defaultdict(collections.Counter)
    for row in out.splitlines():
        row = row.strip()
        if not row:
            continue
        data = bytes.fromhex(row)
        if len(data) < 108:
            continue
        object_type = struct.unpack_from("<I", data, 4)[0]
        map_id = (object_type >> 16) & 0xFFFF
        low = object_type & 0xFFFF
        try:
            end = data.index(b"\0", 44)
        except ValueError:
            end = len(data)
        template = data[44:end].decode("ascii", "replace")
        by_map[map_id][(template, low)] += 1

    for map_id in sorted(by_map):
        entries = by_map[map_id]
        npcs = [(t, w) for (t, w) in entries if not t.startswith("A_")
                and not t.startswith("B_") and not t.startswith("C_")
                and not t.startswith("c_")]
        print(f"map {map_id}: {len(entries)} templates, "
              f"{len(npcs)} look like NPCs")
        for template, low in sorted(npcs, key=lambda item: item[0]):
            print(f"    {template:<34} low=0x{low:04X} ({low})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
