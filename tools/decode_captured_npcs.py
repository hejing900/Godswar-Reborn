"""Decode the NPC world-object frames a capture holds, per map.

The same decoding that produced Sparta's city NPC data (object id, appearance
word, position, facing, appearance template) from the reference capture. Run it
after a capture session and it writes one row per placed NPC, so a map that has
never been driven by the reference - Athens city, Athens newbie - can be written
exactly the way Sparta's was.

Usage: python tools/decode_captured_npcs.py [out_dir]
"""

import collections
import os
import struct
import subprocess
import sys

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Godswar Origin\npc-translation"

SQL = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10020 ORDER BY captured_at;")

# The client's monster templates are prefixed with their rank; NPC appearance
# templates are "<Scene>_<number>_<Model>". Both travel as opcode 10020, so the
# template name is what separates the two populations.
MONSTER_PREFIXES = ("A_", "B_", "C_", "c_")


def frames():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        line = line.strip()
        if line:
            yield bytes.fromhex(line)


def decode(data):
    object_type = struct.unpack_from("<I", data, 4)[0]
    map_id = (object_type >> 16) & 0xFFFF
    low = object_type & 0xFFFF
    object_id = struct.unpack_from("<I", data, 8)[0]
    x = struct.unpack_from("<f", data, 28)[0]
    z = struct.unpack_from("<f", data, 36)[0]
    facing = struct.unpack_from("<f", data, 40)[0]
    end = data.index(b"\0", 44) if b"\0" in data[44:] else len(data)
    template = data[44:end].decode("ascii", "replace")
    return map_id, low, object_id, x, z, facing, template


def main():
    placed = collections.defaultdict(dict)
    for data in frames():
        if len(data) < 108:
            continue
        map_id, low, object_id, x, z, facing, template = decode(data)
        if template.startswith(MONSTER_PREFIXES):
            continue
        placed[map_id][object_id] = (template, low, x, z, facing)

    if not placed:
        print("the capture holds no NPC object frames yet")
        return 0

    for map_id in sorted(placed):
        rows = placed[map_id]
        path = os.path.join(OUT_DIR, f"captured-npcs-map{map_id}.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# objectId|template|appearance|x|z|facing\n")
            for object_id in sorted(rows):
                template, low, x, z, facing = rows[object_id]
                handle.write(
                    f"{object_id}|{template}|{low}|{x:.4f}|{z:.4f}|"
                    f"{facing:.4f}\n")
        appearances = collections.Counter(
            low for _, low, _, _, _ in rows.values())
        print(f"map {map_id}: {len(rows)} NPC objects -> {path}")
        print(f"    appearance words: "
              f"{ {hex(k): v for k, v in sorted(appearances.items())} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
