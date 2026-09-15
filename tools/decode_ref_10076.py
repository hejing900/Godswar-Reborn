"""Decode the reference server's captured 10076 frames and compare with ours."""
import subprocess
import struct
import sys

SQL = ("SELECT captured_at, clear_bytes FROM packet_transactions "
       "WHERE opcode = 10076 ORDER BY captured_at;")


def rows():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if "|" not in line:
            continue
        when, blob = line.split("|", 1)
        blob = blob.strip()
        if blob.startswith("\\x"):
            blob = blob[2:]
        yield when, bytes.fromhex(blob)


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def i32(data, offset):
    return struct.unpack_from("<i", data, offset)[0]


def filled_slots(data, start, count):
    filled = []
    for slot in range(count):
        off = start + (slot * 72)
        if off + 36 > len(data):
            break
        item = u32(data, off + 8)
        if item not in (0, 0xFFFFFFFF):
            filled.append(item)
    return filled


def main():
    seen = {}
    for when, data in rows():
        if len(data) < 60:
            continue
        kind = i32(data, 16)
        key = (u32(data, 8), kind, u32(data, 28), i32(data, 44), len(data))
        seen.setdefault(key, [0, when, data])
        seen[key][0] += 1
    print(f"distinct 10076 shapes: {len(seen)}")
    print(f"{'quest':>6} {'kind':>4} {'monster':>7} {'need':>5} {'len':>4} "
          f"{'count':>5}  rewards")
    for (quest, kind, monster, need, length), (count, when, data) in sorted(
            seen.items()):
        rewards = filled_slots(data, 60, 4)
        print(f"{quest:>6} {kind:>4} {monster:>7} {need:>5} {length:>4} "
              f"{count:>5}  {rewards}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
