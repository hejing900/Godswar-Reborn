"""Backfill monster spawns from the capture stream into the reviewed table.

The capture proxy only writes monster_spawn_packets when it is started with
--monster-map-id, so a session recorded without that flag stores its opcode-10020
frames in packet_transactions and publishes nothing. This replays those frames
through the same validation and the same upsert the proxy performs, so
monster_spawn_packets - the source of MonsterContentBaseline.v1.gz - ends up
exactly as it would have been had the flag been present.

Validation mirrors CapturedMonsterSpawn.Validate and the proxy's
TryParseMonsterSpawn: object type discriminator 0x12, non-zero tier/HP, finite
coordinates, the template must resolve for that map, and the declared frame
length must equal the captured length.

Usage:
  python tools/import_captured_monsters.py --session <uuid>
  python tools/import_captured_monsters.py --session <uuid> --apply
"""
from __future__ import annotations

import argparse
import collections
import math
import struct
import subprocess
import sys

MONSTER_DISCRIMINATOR = 0x12
MIN_PACKET = 108


def psql(sql: str, fetch: bool = True) -> str:
    args = ["docker", "exec", "-i", "godswar-postgres", "psql", "-U", "godswar",
            "-d", "godswar", "-v", "ON_ERROR_STOP=1"]
    if fetch:
        args += ["-t", "-A", "-F", "|"]
    args += ["-c", sql]
    done = subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit((done.stderr or "").strip() or "psql failed")
    return done.stdout or ""


def run_script(sql: str) -> None:
    done = subprocess.run(
        ["docker", "exec", "-i", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-v", "ON_ERROR_STOP=1"],
        input=sql, capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit((done.stderr or "").strip() or "psql script failed")


def templates() -> dict[tuple[int, str], tuple[str, str]]:
    """(map_id, template_key) -> (scene_key, display_name)."""
    out = psql("SELECT source_map_id, template_key, scene_key, display_name "
               "FROM monster_templates WHERE source_map_id IS NOT NULL;")
    table: dict[tuple[int, str], tuple[str, str]] = {}
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 4:
            table[(int(parts[0]), parts[1])] = (parts[2], parts[3])
    return table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--apply", action="store_true",
                        help="write the rows (default: dry run)")
    parser.add_argument("--only-maps", type=int, nargs="*")
    args = parser.parse_args()

    known = templates()
    print(f"monster_templates pairs: {len(known)}")

    rows = psql(
        "SELECT id, to_char(captured_at,'YYYY-MM-DD HH24:MI:SS.MS+00'), "
        "encode(clear_bytes,'hex') FROM packet_transactions "
        "WHERE opcode=10020 AND direction='S2C' "
        f"AND capture_session_id='{args.session}' ORDER BY id;")

    accepted: dict[tuple[int, int], dict] = {}
    rejected = collections.Counter()
    for line in rows.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        _, captured_at, hexed = parts
        data = bytes.fromhex(hexed)
        if len(data) < MIN_PACKET:
            rejected["short"] += 1
            continue
        declared = struct.unpack_from("<H", data, 0)[0]
        opcode = struct.unpack_from("<H", data, 2)[0]
        object_type = struct.unpack_from("<I", data, 4)[0]
        map_id = (object_type >> 16) & 0xFFFF
        object_id = struct.unpack_from("<I", data, 8)[0]
        tier = struct.unpack_from("<I", data, 12)[0]
        current_hp = struct.unpack_from("<I", data, 20)[0]
        maximum_hp = struct.unpack_from("<I", data, 24)[0]
        x = struct.unpack_from("<f", data, 28)[0]
        y = struct.unpack_from("<f", data, 32)[0]
        z = struct.unpack_from("<f", data, 36)[0]
        facing = struct.unpack_from("<f", data, 40)[0]
        tail = data[44:]
        stop = tail.index(b"\0") if b"\0" in tail else len(tail)
        template = tail[:stop].decode("ascii", "replace")

        if (object_type & 0xFF) != MONSTER_DISCRIMINATOR:
            rejected["not-monster"] += 1
            continue
        if args.only_maps and map_id not in args.only_maps:
            continue
        if declared != len(data) or opcode != 10020:
            rejected["bad-frame"] += 1
            continue
        if not template or tier == 0 or current_hp == 0 or maximum_hp == 0:
            rejected["bad-metadata"] += 1
            continue
        if not all(math.isfinite(v) for v in (x, y, z, facing)):
            rejected["bad-coords"] += 1
            continue
        located = known.get((map_id, template))
        if located is None:
            rejected[f"no-template-map{map_id}"] += 1
            continue

        scene_key, display_name = located
        accepted[(map_id, object_id)] = {
            "map_id": map_id,
            "scene_key": scene_key,
            "template_key": template,
            "display_name": display_name,
            "object_id": object_id,
            "x": x,
            "z": z,
            "packet": hexed,
            "captured_at": captured_at,
        }

    per_map = collections.Counter(m for m, _ in accepted)
    print(f"\naccepted: {len(accepted)} spawns  per map: {dict(sorted(per_map.items()))}")
    if rejected:
        print(f"rejected: {dict(rejected)}")

    # Which of the accepted rows are already in the reviewed table?
    existing = set()
    out = psql("SELECT map_id, object_id FROM monster_spawn_packets;")
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 2:
            existing.add((int(parts[0]), int(parts[1])))
    fresh = {k: v for k, v in accepted.items() if k not in existing}
    print(f"already in monster_spawn_packets: {len(accepted) - len(fresh)}")
    print(f"new rows to insert              : {len(fresh)}")
    fresh_per_map = collections.Counter(m for m, _ in fresh)
    print(f"new per map                     : "
          f"{dict(sorted(fresh_per_map.items()))}")

    if not fresh:
        print("\nnothing to do")
        return 0

    if not args.apply:
        print("\n(dry run - pass --apply to write)")
        return 0

    statements = ["BEGIN;"]
    for row in fresh.values():
        statements.append(
            "INSERT INTO monster_spawn_packets (map_id, scene_key, "
            "template_key, display_name, object_id, pos_x, pos_z, clear_bytes, "
            "source, first_seen_at, last_seen_at, capture_count) VALUES ("
            f"{row['map_id']}, '{row['scene_key']}', '{row['template_key']}', "
            f"'{row['display_name'].replace(chr(39), chr(39) * 2)}', "
            f"{row['object_id']}, {row['x']!r}, {row['z']!r}, "
            f"decode('{row['packet']}','hex'), 'capture_proxy', "
            f"'{row['captured_at']}', '{row['captured_at']}', 1) "
            "ON CONFLICT (map_id, object_id) DO UPDATE SET "
            "template_key = EXCLUDED.template_key, "
            "display_name = EXCLUDED.display_name, "
            "pos_x = EXCLUDED.pos_x, pos_z = EXCLUDED.pos_z, "
            "clear_bytes = EXCLUDED.clear_bytes, "
            "last_seen_at = EXCLUDED.last_seen_at, "
            "capture_count = monster_spawn_packets.capture_count + 1;")
    statements.append("COMMIT;")
    run_script("\n".join(statements))
    print(f"\nwrote {len(fresh)} rows")

    out = psql("SELECT map_id, count(*) FROM monster_spawn_packets "
               "GROUP BY map_id ORDER BY map_id;")
    print("\nmonster_spawn_packets now:")
    for line in out.splitlines():
        print(f"    map {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
