"""Compare a capture window's monsters against the reviewed spawn baseline.

The monster baseline is exported from monster_spawn_packets, so that table - not
monster_spawn_definitions - is what the server actually publishes. This reports,
per map, which of the window's objects are already in the baseline and which are
new, keyed on the capture's own object id.

Usage:
  python tools/compare_window_monsters.py --session <uuid> \
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
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def window_monsters(session: str, start: str, end: str):
    sql = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
           "WHERE opcode=10020 AND direction='S2C' "
           f"AND capture_session_id='{session}' "
           "AND captured_at + interval '8 hours' >= "
           f"timestamp '{start}' "
           "AND captured_at + interval '8 hours' < "
           f"timestamp '{end}' ORDER BY id;")
    found: dict[int, dict[int, str]] = collections.defaultdict(dict)
    for line in psql(sql):
        data = bytes.fromhex(line)
        if len(data) < 44:
            continue
        object_type = struct.unpack_from("<I", data, 4)[0]
        map_id = (object_type >> 16) & 0xFFFF
        object_id = struct.unpack_from("<I", data, 8)[0]
        tail = data[44:]
        stop = tail.index(b"\0") if b"\0" in tail else len(tail)
        template = tail[:stop].decode("ascii", "replace")
        if template.startswith(MONSTER_PREFIXES):
            found[map_id][object_id] = template
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    args = parser.parse_args()

    window = window_monsters(args.session, args.start, args.end)
    baseline: dict[int, dict[int, str]] = collections.defaultdict(dict)
    for line in psql("SELECT map_id, object_id, template_key "
                     "FROM monster_spawn_packets;"):
        map_id, object_id, template = line.split("|")
        baseline[int(map_id)][int(object_id)] = template

    print(f"window {args.start} .. {args.end}")
    print(f"baseline maps: "
          f"{ {m: len(v) for m, v in sorted(baseline.items())} }")
    total_new = 0
    for map_id in sorted(window):
        rows = window[map_id]
        have = baseline.get(map_id, {})
        new_objects = sorted(set(rows) - set(have))
        total_new += len(new_objects)
        print(f"\n===== map {map_id} =====")
        print(f"  window objects   : {len(rows)}")
        print(f"  baseline objects : {len(have)}")
        print(f"  NEW object ids   : {len(new_objects)}")
        templates = collections.Counter(rows[o] for o in new_objects)
        for template, count in sorted(templates.items()):
            known = sum(1 for t in have.values() if t == template)
            print(f"      {count:>4}x  {template:<32} "
                  f"(baseline already has {known})")
    print(f"\ntotal new monster objects: {total_new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
