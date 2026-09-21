"""Reviewed native cells and strict artwork manifest validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct

from level5_forge_icons.common import InstallError, TgaAtlas
from level5_forge_icons.tga_atlas import parse_tga


BASELINE_HASHES = {
    "Icon2.gwo": "3f7699ada1be4ded4e70c7dea8e29dff345eb9e7bec9d9dd14748ee3b790c94a",
    "Icon5.gwo": "35fe7c805cc6eef1ef326c43a5ce765bfd8e958bfa96b023900b1c5524ee8f1f",
}
CELLS = {
    9030: ("Icon2.gwo", 252, 0), 9031: ("Icon2.gwo", 288, 0),
    9032: ("Icon5.gwo", 612, 0),
    9060: ("Icon2.gwo", 360, 0), 9061: ("Icon2.gwo", 396, 0),
    9062: ("Icon2.gwo", 432, 0), 9063: ("Icon2.gwo", 468, 0),
    9064: ("Icon2.gwo", 504, 0), 9065: ("Icon2.gwo", 540, 0),
    9066: ("Icon2.gwo", 864, 0), 9067: ("Icon2.gwo", 900, 0),
    9068: ("Icon2.gwo", 756, 36), 9069: ("Icon2.gwo", 792, 36),
    9080: ("Icon2.gwo", 576, 0), 9081: ("Icon2.gwo", 612, 0),
    9082: ("Icon2.gwo", 648, 0), 9083: ("Icon2.gwo", 684, 0),
    9084: ("Icon2.gwo", 720, 0), 9085: ("Icon2.gwo", 756, 0),
    9086: ("Icon2.gwo", 792, 0), 9087: ("Icon2.gwo", 828, 0),
    9088: ("Icon2.gwo", 828, 36), 9089: ("Icon2.gwo", 864, 36),
    9090: ("Icon5.gwo", 648, 0), 9091: ("Icon5.gwo", 684, 0),
    9092: ("Icon5.gwo", 720, 0), 9093: ("Icon5.gwo", 756, 0),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_catalog(root: Path) -> list[dict]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("sprite_size") != 36
            or manifest.get("baseline_sha256") != BASELINE_HASHES):
        raise InstallError("Holy Stone manifest differs from the reviewed native contract")
    entries = manifest.get("entries", [])
    if len(entries) != len(CELLS) or {e.get("item_id") for e in entries} != set(CELLS):
        raise InstallError("Holy Stone manifest must cover exactly the 27 existing items")
    slugs = set()
    for entry in entries:
        slug = entry.get("slug", "")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,60}", slug) or slug in slugs:
            raise InstallError(f"Invalid or duplicate artwork slug: {slug}")
        slugs.add(slug)
        if (entry.get("atlas"), entry.get("x"), entry.get("y")) != CELLS[entry["item_id"]]:
            raise InstallError(f"Native item cell changed: {entry['item_id']}")
    return entries


def read_baselines(root: Path) -> dict[str, bytes]:
    result = {}
    for name, expected in BASELINE_HASHES.items():
        data = (root / "base" / name).read_bytes()
        if sha256(data) != expected:
            raise InstallError(f"Native atlas baseline SHA256 mismatch: {name}")
        result[name] = data
    return result


def parse_baseline(data: bytes, name: str) -> TgaAtlas:
    if sha256(data) != BASELINE_HASHES[name]:
        raise InstallError(f"Unreviewed atlas passed as baseline: {name}")
    if name == "Icon2.gwo":
        # An earlier local patch expanded the RLE stream but retained its old
        # footer pointer. Recognize only the exact reviewed release; repair
        # this one pointer before the strict parser validates the container.
        extension = len(data) - 26 - 495
        if extension != 2099511 or struct.unpack_from("<H", data, extension)[0] != 495:
            raise InstallError("Reviewed Icon2 extension moved unexpectedly")
        normalized = bytearray(data)
        struct.pack_into("<I", normalized, len(data) - 26, extension)
        data = bytes(normalized)
    return parse_tga(data, f"baseline {name}")
