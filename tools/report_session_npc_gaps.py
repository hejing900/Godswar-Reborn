"""Compare one capture session's NPC object list against the shipped placements.

Layer 1: opcode 10020 S2C frames of the given session (what the reference sent
         on this map today) - decoded with the layout tools/enum_captured_npc_placements.py
         documents.
Layer 2: src/Godswar.Server/Infrastructure/WorldContent/CapturedNpcPlacements.Generated.cs
         (the capture the server currently ships).
Layer 3: npc_spawn_definitions (what the server published).

Prints, per map: keys the session holds that the shipped file lacks (these are
deleted by CapturedNpcPlacementPolicy.DropAbsentFromCapture), keys where the
object id / appearance / coordinates differ, and published rows that never reach
a client.

Usage:
  python tools/report_session_npc_gaps.py --session <uuid>
"""
from __future__ import annotations

import argparse
import collections
import re
import struct
import subprocess
import sys

PLACEMENTS = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure"
              r"\WorldContent\CapturedNpcPlacements.Generated.cs")

MONSTER_PREFIXES = ("A_", "B_", "C_", "c_")

ROW = re.compile(
    r'\["(?P<key>[A-Za-z_0-9]+)"\]\s*=\s*new\('
    r'"[^"]+",\s*"(?P<template>[^"]+)",\s*(?P<object>\d+)u,\s*'
    r'0x(?P<appearance>[0-9A-Fa-f]+)u,\s*(?P<x>[-\d.]+)f,\s*'
    r'(?P<z>[-\d.]+)f,\s*(?P<facing>[-\d.]+)f\),')


def psql(sql: str) -> list[str]:
    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        sys.stderr.write(done.stderr or "")
        raise SystemExit(1)
    return [l for l in (done.stdout or "").splitlines() if l.strip()]


def npc_key(template: str) -> str:
    parts = template.split("_")
    index = next((i for i, p in enumerate(parts)
                  if len(p) == 3 and p.isdigit()), None)
    return "_".join(parts[:index + 1]) if index is not None else template


def shipped() -> dict[tuple[int, str], dict]:
    rows = {}
    current_map = None
    for line in open(PLACEMENTS, encoding="utf-8"):
        banner = re.match(r"\s*//\s*map\s+(\d+):", line)
        if banner:
            current_map = int(banner.group(1))
            continue
        found = ROW.search(line)
        if found and current_map is not None:
            key = found.group("key")
            rows.setdefault((current_map, key), []).append({
                "template": found.group("template"),
                "objectId": int(found.group("object")),
                "appearance": int(found.group("appearance"), 16),
                "x": float(found.group("x")),
                "z": float(found.group("z")),
                "facing": float(found.group("facing")),
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    args = parser.parse_args()

    rows = psql("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
                f"WHERE opcode = 10020 AND direction = 'S2C' "
                f"AND capture_session_id = '{args.session}' ORDER BY id;")

    live: dict[tuple[int, str], dict] = {}
    monsters: collections.Counter = collections.Counter()
    for blob in rows:
        data = bytes.fromhex(blob)
        offset = 0
        while offset + 4 <= len(data):
            length, op = struct.unpack_from("<HH", data, offset)
            if length < 4 or offset + length > len(data):
                break
            frame = data[offset:offset + length]
            offset += length
            if op != 10020 or len(frame) < 108:
                continue
            object_type = struct.unpack_from("<I", frame, 4)[0]
            map_id = (object_type >> 16) & 0xFFFF
            low = object_type & 0xFFFF
            object_id = struct.unpack_from("<I", frame, 8)[0]
            x = struct.unpack_from("<f", frame, 28)[0]
            z = struct.unpack_from("<f", frame, 36)[0]
            facing = struct.unpack_from("<f", frame, 40)[0]
            tail = frame[44:]
            end = tail.index(b"\0") if b"\0" in tail else len(tail)
            template = tail[:end].decode("ascii", "replace")
            if template.startswith(MONSTER_PREFIXES):
                monsters[map_id] += 1
                continue
            live[(map_id, npc_key(template))] = {
                "objectId": object_id, "template": template, "appearance": low,
                "x": x, "z": z, "facing": facing,
            }

    ship = shipped()
    print(f"session frames: {len(rows)}  decoded npc objects: {len(live)}  "
          f"monsters: {dict(sorted(monsters.items()))}")

    missing = sorted(set(live) - set(ship))
    print(f"\n[A] in this session but NOT shipped: {len(missing)}")
    for key in missing:
        row = live[key]
        print(f"    map {key[0]:>2}  {key[1]:<22} {row['template']:<34} "
              f"obj={row['objectId']:<6} app=0x{row['appearance']:x} "
              f"({row['x']:.2f},{row['z']:.2f},{row['facing']:.2f})")

    print(f"\n[B] shipped keys not in this session: "
          f"{len(set(ship) - set(live))} (informational)")

    drift = []
    for key in sorted(set(live) & set(ship)):
        row = live[key]
        for known in ship[key]:
            if (known["objectId"] != row["objectId"]
                    or known["appearance"] != row["appearance"]):
                drift.append((key, row, known))
    print(f"\n[C] same key, different id/appearance: {len(drift)}")
    for key, row, known in drift:
        print(f"    map {key[0]:>2}  {key[1]:<22} live obj={row['objectId']} "
              f"app=0x{row['appearance']:x}  shipped obj={known['objectId']} "
              f"app=0x{known['appearance']:x}")

    published = {}
    for line in psql("SELECT map_id, npc_key, object_id, interaction_id, "
                     "template_key FROM npc_spawn_definitions ORDER BY 1,2;"):
        parts = line.split("|")
        published.setdefault((int(parts[0]), parts[1]), []).append(
            (int(parts[2]), int(parts[3]), parts[4]))

    dead = sorted(k for k in published if k not in ship)
    print(f"\n[D] published but not shipped (never reach a client): {len(dead)}")
    for key in dead:
        flag = "  <-- IN THIS SESSION" if key in live else ""
        print(f"    map {key[0]:>2}  {key[1]:<22} "
              f"{published[key][0][2]:<34}{flag}")

    unpub = sorted(k for k in live if k not in published)
    print(f"\n[E] in this session but NOT published (invisible): {len(unpub)}")
    for key in unpub:
        row = live[key]
        print(f"    map {key[0]:>2}  {key[1]:<22} {row['template']:<34} "
              f"obj={row['objectId']:<6} app=0x{row['appearance']:x} "
              f"({row['x']:.2f},{row['z']:.2f},{row['facing']:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
