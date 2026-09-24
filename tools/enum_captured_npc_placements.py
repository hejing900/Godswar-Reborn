"""Enumerate every NPC world-object the capture holds, grouped by map.

Reads opcode 10020 S2C frames out of ``packet_transactions``. The layout is the
one the existing Sparta/Athens exports were built from: the low half of the
object type is the appearance word, the high half is the map id, and the ASCII
template name follows the 44-byte fixed prefix.

Outputs ``captured-npcs-map{N}.txt`` rows (``objectId|template|appearance|x|z|facing``)
plus a JSON summary, both under artifacts so nothing outside the repo is touched.

Usage:
  python tools/enum_captured_npc_placements.py [out_dir]
"""
from __future__ import annotations

import collections
import json
import os
import struct
import subprocess
import sys

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Godswar-Reborn-main\artifacts\npc-port"

# A map filter keeps a run from rewriting the exports of maps it did not
# re-capture: the generator consumes the whole directory, so a partial export
# would otherwise look like "the capture no longer has those NPCs".
ONLY_MAPS = {int(a) for a in sys.argv[2:]} if len(sys.argv) > 2 else None

# Monster templates carry a rank prefix; NPC appearance templates read
# "<Scene>_<number>_<Model>". Both travel as 10020.
MONSTER_PREFIXES = ("A_", "B_", "C_", "c_")

SQL = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10020 AND direction = 'S2C' ORDER BY id;")


def frames():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        line = line.strip()
        if line:
            yield bytes.fromhex(line)


def decode(data: bytes):
    object_type = struct.unpack_from("<I", data, 4)[0]
    map_id = (object_type >> 16) & 0xFFFF
    low = object_type & 0xFFFF
    object_id = struct.unpack_from("<I", data, 8)[0]
    x = struct.unpack_from("<f", data, 28)[0]
    z = struct.unpack_from("<f", data, 36)[0]
    facing = struct.unpack_from("<f", data, 40)[0]
    tail = data[44:]
    end = tail.index(b"\0") if b"\0" in tail else len(tail)
    template = tail[:end].decode("ascii", "replace")
    return map_id, low, object_id, x, z, facing, template


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    npcs: dict[int, dict[int, tuple]] = collections.defaultdict(dict)
    monsters: dict[int, dict[int, tuple]] = collections.defaultdict(dict)
    malformed = 0

    for data in frames():
        if len(data) < 108:
            malformed += 1
            continue
        map_id, low, object_id, x, z, facing, template = decode(data)
        target = monsters if template.startswith(MONSTER_PREFIXES) else npcs
        target[map_id][object_id] = (template, low, x, z, facing)

    summary = {}
    for map_id in sorted(npcs):
        if ONLY_MAPS is not None and map_id not in ONLY_MAPS:
            continue
        rows = npcs[map_id]
        path = os.path.join(OUT_DIR, f"captured-npcs-map{map_id}.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("# objectId|template|appearance|x|z|facing\n")
            for object_id in sorted(rows):
                template, low, x, z, facing = rows[object_id]
                handle.write(f"{object_id}|{template}|{low}|{x:.4f}|"
                             f"{z:.4f}|{facing:.4f}\n")
        appearances = collections.Counter(low for _, low, _, _, _ in rows.values())
        templates = collections.Counter(t for t, _, _, _, _ in rows.values())
        summary[map_id] = {
            "npcCount": len(rows),
            "monsterCount": len(monsters.get(map_id, {})),
            "appearances": {str(k): v for k, v in sorted(appearances.items())},
            "templates": {k: v for k, v in sorted(templates.items())},
            "file": os.path.basename(path),
        }
        print(f"map {map_id:>3}: {len(rows):>3} NPC  "
              f"{len(monsters.get(map_id, {})):>4} monster  "
              f"appearances={sorted(hex(k) for k in appearances)}")

    with open(os.path.join(OUT_DIR, "captured-npc-placements.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
    print(f"\nmaps with NPC objects: {len(npcs)}  "
          f"malformed frames skipped: {malformed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
