"""Summarise the world objects a capture window placed, split NPC vs monster.

Decodes opcode 10020 frames inside a local-time window and reports, per map, the
distinct appearance templates with their object counts, so a window can be
compared against what the server already publishes. Monster templates carry a
rank prefix (A_/B_/C_/c_); NPC templates read "<Scene>_<number>_<Model>".

Usage:
  python tools/summarise_world_objects.py --session <uuid> \
      --from "2026-09-24 23:59:00" --to "2026-09-25 00:10:00"
"""
from __future__ import annotations

import argparse
import collections
import struct
import subprocess
import sys

MONSTER_PREFIXES = ("A_", "B_", "C_", "c_")


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    args = parser.parse_args()

    sql = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
           "WHERE opcode=10020 AND direction='S2C' "
           f"AND capture_session_id='{args.session}' "
           "AND captured_at + interval '8 hours' >= "
           f"timestamp '{args.start}' "
           "AND captured_at + interval '8 hours' < "
           f"timestamp '{args.end}' ORDER BY id;")

    # map -> objectId -> (template, appearance)
    npcs: dict[int, dict[int, tuple[str, int]]] = collections.defaultdict(dict)
    monsters: dict[int, dict[int, tuple[str, int]]] = collections.defaultdict(dict)
    for line in psql(sql):
        data = bytes.fromhex(line)
        if len(data) < 44:
            continue
        object_type = struct.unpack_from("<I", data, 4)[0]
        map_id = (object_type >> 16) & 0xFFFF
        appearance = object_type & 0xFFFF
        object_id = struct.unpack_from("<I", data, 8)[0]
        tail = data[44:]
        end = tail.index(b"\0") if b"\0" in tail else len(tail)
        template = tail[:end].decode("ascii", "replace")
        bucket = monsters if template.startswith(MONSTER_PREFIXES) else npcs
        bucket[map_id][object_id] = (template, appearance)

    print(f"window {args.start} .. {args.end}")
    for label, table in (("NPC", npcs), ("MONSTER", monsters)):
        print(f"\n===== {label}: "
              f"{sum(len(v) for v in table.values())} objects "
              f"on maps {sorted(table)}")
        for map_id in sorted(table):
            rows = table[map_id]
            templates = collections.Counter(t for t, _ in rows.values())
            print(f"  map {map_id}: {len(rows)} objects, "
                  f"{len(templates)} distinct templates")
            for template, count in sorted(templates.items()):
                print(f"      {count:>4}x  {template}")

    # Machine-readable dump for diffing against the server's own content.
    print("\n===== templates by map =====")
    for map_id in sorted(set(npcs) | set(monsters)):
        npc_templates = sorted({t for t, _ in npcs.get(map_id, {}).values()})
        monster_templates = sorted(
            {t for t, _ in monsters.get(map_id, {}).values()})
        print(f"map {map_id}")
        print(f"    npc     : {npc_templates}")
        print(f"    monster : {monster_templates}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
