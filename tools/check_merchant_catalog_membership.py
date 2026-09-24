"""Check the Athens merchants exist in the authoritative actor catalog.

CapturedNpcPlacementPolicy can only rewrite an npc that NpcActorPlacementCatalog
actually carries: the catalog is what the world content reader loads, and the
policy then applies the capture to it. A merchant missing there is not a mapping
problem, it is absent content.

Usage: python tools/check_merchant_catalog_membership.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

CATALOG = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\State"
    r"\NpcActorPlacementCatalog.cs")

MERCHANTS = {
    5166: "Athens_026", 5167: "Athens_027", 5168: "Athens_028",
    5169: "Athens_029", 5234: "Athens_096", 5237: "Athens_099",
    5240: "Athens_102", 5245: "Athens_107", 5246: "Athens_108",
    5259: "Athens_121", 5260: "Athens_122", 5273: "Athens_135",
    5274: "Athens_136", 5275: "Athens_137",
}


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    text = CATALOG.read_text(encoding="utf-8")
    row = re.compile(
        r'new\((?P<map>\d+),\s*"(?P<key>[A-Za-z_0-9]+)",\s*'
        r'"(?P<template>[^"]+)",\s*(?P<object>\d+)u,\s*'
        r'(?P<x>[-\d.]+)f,\s*(?P<z>[-\d.]+)f,\s*(?P<facing>[-\d.]+)f\)')

    catalog = {}
    for found in row.finditer(text):
        catalog[found.group("key")] = {
            "template": found.group("template"),
            "sourceObjectId": int(found.group("object")),
            "x": float(found.group("x")),
            "z": float(found.group("z")),
        }

    publish = {}
    for line in psql("SELECT npc_key, object_id FROM npc_spawn_definitions "
                     "WHERE map_id = 1;"):
        key, object_id = line.split("|")
        publish[key] = int(object_id)

    capture = {}
    for path in pathlib.Path(
            r"D:\Godswar-Reborn-main\artifacts\npc-port").glob(
                "captured-npcs-map1.txt"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("|")
            if len(parts) == 6:
                capture[int(parts[0])] = (parts[1], float(parts[3]),
                                          float(parts[4]))

    print(f"{'npc':>6} {'npcKey':<14} {'catalog':<9} {'published':<10} "
          f"{'capture':<9} notes")
    absent = []
    for npc_id, key in sorted(MERCHANTS.items()):
        in_catalog = key in catalog
        in_publish = key in publish
        in_capture = npc_id in capture
        note = ""
        if not in_catalog:
            absent.append(key)
            note = "MISSING FROM CATALOG"
        elif not in_publish:
            note = "not in npc_spawn_definitions"
        if in_catalog and in_capture:
            expected = capture[npc_id]
            if not expected[0].startswith(key + "_"):
                note = f"template drift capture={expected[0]}"
            dx = abs(catalog[key]["x"] - expected[1])
            dz = abs(catalog[key]["z"] - expected[2])
            if dx > 1.5 or dz > 1.5:
                note += f" pos drift ({dx:.1f},{dz:.1f})"
        print(f"{npc_id:>6} {key:<14} {str(in_catalog):<9} "
              f"{str(in_publish):<10} {str(in_capture):<9} {note}")

    print(f"\nmissing from NpcActorPlacementCatalog: {len(absent)} {absent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
