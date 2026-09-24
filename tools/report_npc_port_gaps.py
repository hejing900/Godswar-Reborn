"""Final work list: what the latest capture holds that the server cannot serve.

Compares three layers and reports only real gaps:
  1. npc_spawn_definitions (what the server published)
  2. CapturedNpcPlacements.Generated.cs (the capture the server already ships)
  3. the freshly decoded capture exports (what the reference actually sent)

Because CapturedNpcPlacementPolicy.DropAbsentFromCapture removes any NPC a
covered map does not have in layer 2, a row present in layer 1 but missing from
layer 2 is dead content - it never reaches the client.

Usage: python tools/report_npc_port_gaps.py
"""
from __future__ import annotations

import collections
import pathlib
import re
import struct
import subprocess
import sys

PLACEMENTS = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure\WorldContent"
    r"\CapturedNpcPlacements.Generated.cs")
CAPTURE_DIR = pathlib.Path(r"D:\Godswar-Reborn-main\artifacts\npc-port")

ROW = re.compile(
    r'\["(?P<key>[A-Za-z_0-9]+)"\]\s*=\s*new\('
    r'"[^"]+",\s*"(?P<template>[^"]+)",\s*(?P<object>\d+)u,\s*'
    r'0x(?P<appearance>[0-9A-Fa-f]+)u,\s*(?P<x>[-\d.]+)f,\s*'
    r'(?P<z>[-\d.]+)f,\s*(?P<facing>[-\d.]+)f\),')


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def npc_key(template: str) -> str:
    parts = template.split("_")
    index = next((i for i, p in enumerate(parts)
                  if len(p) == 3 and p.isdigit()), None)
    return "_".join(parts[:index + 1]) if index is not None else template


def shipped() -> dict[tuple[int, str], dict]:
    rows = {}
    current_map = None
    for line in PLACEMENTS.read_text(encoding="utf-8").splitlines():
        banner = re.match(r"\s*//\s*map\s+(\d+):", line)
        if banner:
            current_map = int(banner.group(1))
            continue
        found = ROW.search(line)
        if found and current_map is not None:
            rows[(current_map, found.group("key"))] = {
                "template": found.group("template"),
                "objectId": int(found.group("object")),
                "appearance": int(found.group("appearance"), 16),
            }
    return rows


def captured() -> dict[tuple[int, str], dict]:
    rows = {}
    for path in sorted(CAPTURE_DIR.glob("captured-npcs-map*.txt")):
        map_id = int(re.search(r"map(\d+)", path.name).group(1))
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("|")
            if len(parts) != 6:
                continue
            rows[(map_id, npc_key(parts[1]))] = {
                "objectId": int(parts[0]),
                "template": parts[1],
                "appearance": int(parts[2]),
                "x": float(parts[3]),
                "z": float(parts[4]),
                "facing": float(parts[5]),
            }
    return rows


def main() -> int:
    ship = shipped()
    cap = captured()

    published = collections.defaultdict(dict)
    for line in psql("SELECT map_id, npc_key, object_id, interaction_id, "
                     "template_key, appearance_type, pos_x, pos_z FROM "
                     "npc_spawn_definitions ORDER BY map_id, npc_key;"):
        parts = line.split("|")
        if len(parts) != 8:
            continue
        published[int(parts[0])][parts[1]] = {
            "objectId": int(parts[2]), "interactionId": int(parts[3]),
            "template": parts[4], "appearance": int(parts[5]),
            "x": float(parts[6]), "z": float(parts[7]),
        }

    # ---- layer 2 vs layer 3: capture content the server ships is missing ----
    missing_from_ship = sorted(set(cap) - set(ship))
    print("=" * 78)
    print(f"capture holds {len(cap)} npcs; server ships {len(ship)}")
    print(f"\n[A] in the latest capture but NOT in the shipped placements: "
          f"{len(missing_from_ship)}")
    print("    -> these are deleted at runtime by DropAbsentFromCapture")
    for key in missing_from_ship:
        row = cap[key]
        print(f"    map {key[0]:>2}  {key[1]:<22} {row['template']:<34} "
              f"obj={row['objectId']:<6} app=0x{row['appearance']:x} "
              f"({row['x']},{row['z']})")

    # ---- layer 1 vs layer 2: published rows that can never reach a client ----
    dead = []
    for map_id, by_key in published.items():
        if not any(k[0] == map_id for k in ship):
            continue  # map not covered by the shipped capture
        for key in by_key:
            if (map_id, key) not in ship:
                dead.append((map_id, key))
    print(f"\n[B] published but absent from the shipped placements: {len(dead)}")
    by_map = collections.Counter(m for m, _ in dead)
    print(f"    per map: {dict(sorted(by_map.items()))}")
    for map_id, key in sorted(dead)[:40]:
        row = published[map_id][key]
        print(f"    map {map_id:>2}  {key:<22} obj={row['objectId']:<6} "
              f"int={row['interactionId']:<6} {row['template']}")

    # ---- shops: is every captured merchant reachable? ----
    shop_ids = set()
    shops_file = CAPTURE_DIR / "shop-catalogs.json"
    if shops_file.exists():
        import json
        shop_ids = {int(k) for k in json.loads(shops_file.read_text("utf-8"))}
    print(f"\n[C] captured merchant npcs: {len(shop_ids)}")
    for npc_id in sorted(shop_ids):
        entry = next(((m, k) for (m, k), v in cap.items()
                      if v["objectId"] == npc_id), None)
        if entry is None:
            print(f"    {npc_id}: no placement in the capture")
            continue
        map_id, key = entry
        status = "placed" if (map_id, key) in ship else "DROPPED by policy"
        pub = published.get(map_id, {}).get(key)
        pub_text = (f"published obj={pub['objectId']} int={pub['interactionId']}"
                    if pub else "NOT published")
        print(f"    {npc_id:>5}  map {map_id}  {key:<22} {status:<18} {pub_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
