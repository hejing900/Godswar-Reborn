"""Compare the capture's NPC placements against the ones the server publishes.

Reads the generated placement table out of the server source and the freshly
decoded capture exports, then reports per map which captured NPCs the server
does not carry and which server rows the capture never saw.

Usage: python tools/diff_server_vs_captured_npcs.py
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

SERVER = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure\WorldContent"
    r"\CapturedNpcPlacements.Generated.cs")
CAPTURE_DIR = pathlib.Path(r"D:\Godswar-Reborn-main\artifacts\npc-port")

ROW = re.compile(
    r'\["(?P<key>[A-Za-z_0-9]+)"\]\s*=\s*new\('
    r'"[^"]+",\s*'
    r'"(?P<template>[^"]+)",\s*'
    r'(?P<object>\d+)u,\s*'
    r'0x(?P<appearance>[0-9A-Fa-f]+)u,\s*'
    r'(?P<x>[-\d.]+)f,\s*'
    r'(?P<z>[-\d.]+)f,\s*'
    r'(?P<facing>[-\d.]+)f\),')


def server_rows():
    """(mapId, npcKey) -> row, using the // map N: banner comments."""
    text = SERVER.read_text(encoding="utf-8")
    rows = {}
    current_map = None
    for line in text.splitlines():
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
                "x": float(found.group("x")),
                "z": float(found.group("z")),
                "facing": float(found.group("facing")),
            }
    return rows


def npc_key_from_template(template: str) -> str:
    """Athens_001_AthenianCivilian1 -> Athens_001; Athens_Newbie_026_FemMale3 -> Athens_Newbie_026."""
    parts = template.split("_")
    # A leading "<Camp>_<n>" segment (Parnitha_1, Marathon_006) is part of the
    # key, so anchor on a 3-digit ordinal instead of the first bare number.
    index = next((i for i, part in enumerate(parts)
                  if len(part) == 3 and part.isdigit()), None)
    return "_".join(parts[:index + 1]) if index is not None else template


def captured_rows():
    rows = {}
    for path in sorted(CAPTURE_DIR.glob("captured-npcs-map*.txt")):
        map_id = int(re.search(r"map(\d+)", path.name).group(1))
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("|")
            if len(parts) != 6:
                continue
            rows[(map_id, npc_key_from_template(parts[1]))] = {
                "template": parts[1],
                "objectId": int(parts[0]),
                "appearance": int(parts[2]),
                "x": float(parts[3]),
                "z": float(parts[4]),
                "facing": float(parts[5]),
            }
    return rows


def main() -> int:
    server = server_rows()
    capture = captured_rows()
    print(f"server placements: {len(server)}   captured placements: {len(capture)}")

    server_maps = collections.Counter(m for m, _ in server)
    capture_maps = collections.Counter(m for m, _ in capture)
    print(f"\n{'map':>4} {'server':>7} {'capture':>8}  status")
    for map_id in sorted(set(server_maps) | set(capture_maps)):
        ours = server_maps.get(map_id, 0)
        theirs = capture_maps.get(map_id, 0)
        status = "ok" if ours == theirs else f"DIFF {theirs - ours:+d}"
        print(f"{map_id:>4} {ours:>7} {theirs:>8}  {status}")

    missing = sorted(set(capture) - set(server))
    extra = sorted(set(server) - set(capture))
    print(f"\ncaptured but absent from server: {len(missing)}")
    for key in missing:
        map_id, npc_key = key
        row = capture[key]
        print(f"    map {map_id:>2}  {npc_key:<24} {row['template']:<40} "
              f"obj={row['objectId']:<6} app=0x{row['appearance']:x}  "
              f"({row['x']},{row['z']})")
    print(f"\nserver rows the capture never saw: {len(extra)}")
    by_map = collections.Counter(m for m, _ in extra)
    print(f"    {dict(sorted(by_map.items()))}")

    print("\nfield drift on shared npcs:")
    drift = collections.Counter()
    samples = []
    for key in sorted(set(server) & set(capture)):
        ours, theirs = server[key], capture[key]
        for field in ("objectId", "appearance", "x", "z", "facing"):
            if abs(ours[field] - theirs[field]) > 1e-6:
                drift[field] += 1
                if len(samples) < 15:
                    samples.append((key, field, ours[field], theirs[field]))
    print(f"    {dict(drift)}")
    for key, field, ours, theirs in samples:
        print(f"    map {key[0]:>2} {key[1]:<24} {field:<10} "
              f"server={ours} capture={theirs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
