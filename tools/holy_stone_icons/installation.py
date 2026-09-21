"""Strict four-atlas publication; item and socket metadata remain unchanged."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from holy_suit_tiers.transaction import Change, contained
from level5_forge_icons.common import InstallError, Sprite, SpriteSpec
from level5_forge_icons.png_assets import read_png_rgba
from level5_forge_icons.tga_atlas import make_desired_pixels, validate_generated_atlas
from .catalog import BASELINE_HASHES, CELLS, parse_baseline, read_baselines, read_catalog, sha256


def atlas_name(texture: str) -> str:
    return texture.replace("\\", "/").rsplit("/", 1)[-1]


def coordinates(value: str) -> tuple[int, int] | None:
    try:
        parts = tuple(int(v.strip()) for v in value.split(","))
        return parts if len(parts) == 2 else None
    except ValueError:
        return None


def validate_item_consumers(data: bytes, label: str) -> None:
    try:
        nodes = list(ET.fromstring(data).iter())
    except ET.ParseError as error:
        raise InstallError(f"Invalid item metadata {label}: {error}") from error
    by_id: dict[int, list[ET.Element]] = {}
    for node in nodes:
        item_id = node.get("ID", "")
        if item_id.isdigit():
            by_id.setdefault(int(item_id), []).append(node)
    for item_id, (name, x, y) in CELLS.items():
        owned = by_id.get(item_id, [])
        if len(owned) != 1:
            raise InstallError(f"Expected one existing item {item_id} in {label}")
        node = owned[0]
        if (atlas_name(node.get("Texture", "")), coordinates(node.get("Icon", ""))) != (name, (x, y)):
            raise InstallError(f"Item {item_id} no longer uses its reviewed native cell: {label}")
    for node in nodes:
        xy = coordinates(node.get("Icon", ""))
        if xy is None:
            continue
        name = atlas_name(node.get("Texture", ""))
        for item_id, (owned_name, x, y) in CELLS.items():
            if name == owned_name and x <= xy[0] < x + 36 and y <= xy[1] < y + 36:
                if node.get("ID") != str(item_id):
                    raise InstallError(f"Unrelated item aliases the cell for {item_id}: {label}")


def validate_socket_consumers(data: bytes, label: str) -> None:
    try:
        nodes = list(ET.fromstring(data))
    except ET.ParseError as error:
        raise InstallError(f"Invalid socket metadata {label}: {error}") from error
    for effect_id in range(21, 25):
        matches = [n for n in nodes if n.get("ID") == str(effect_id)]
        if (len(matches) != 1 or atlas_name(matches[0].get("Texture", "")) != "Icon5.gwo"
                or coordinates(matches[0].get("IconPos", "")) != (620, 8)):
            raise InstallError(f"Zephyr effect {effect_id} changed its shared stone crop: {label}")


def verify_release(root: Path) -> dict[str, bytes]:
    entries = read_catalog(root)
    baselines = read_baselines(root)
    release = json.loads((root / "generated/release.json").read_text(encoding="utf-8"))
    if (release.get("schema_version") != 1
            or release.get("manifest_sha256") != sha256((root / "manifest.json").read_bytes())
            or release.get("generation_sha256") != sha256((root / "generation.json").read_bytes())):
        raise InstallError("Prepared Holy Stone release has stale catalog or generation provenance")
    sources = {e["slug"]: e for e in release.get("sources", [])}
    if set(sources) != {e["slug"] for e in entries}:
        raise InstallError("Prepared Holy Stone release is missing source identities")
    output_hashes = release.get("outputs", {})
    outputs = {}
    for filename, record in output_hashes.items():
        if Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise InstallError("Release output path must be a filename")
        data = (root / "generated" / filename).read_bytes()
        if len(data) != record["bytes"] or sha256(data) != record["sha256"]:
            raise InstallError(f"Prepared release output SHA256 mismatch: {filename}")
        outputs[filename] = data
    sprites: dict[str, list[Sprite]] = {name: [] for name in baselines}
    for entry in entries:
        slug = entry["slug"]
        if sha256((root / "source" / f"{slug}.png").read_bytes()) != sources[slug]["source_sha256"]:
            raise InstallError(f"Prepared source changed: {slug}")
        filename = f"{slug}-36.png"
        if filename not in outputs or sha256(outputs[filename]) != sources[slug]["icon_sha256"]:
            raise InstallError(f"Prepared icon is missing or stale: {slug}")
        width, height, rgba = read_png_rgba(root / "generated" / filename)
        if (width, height) != (36, 36):
            raise InstallError(f"Expected native 36px icon: {slug}")
        bgra = bytearray(rgba)
        for offset in range(0, len(bgra), 4):
            bgra[offset], bgra[offset + 2] = bgra[offset + 2], bgra[offset]
        sprites[entry["atlas"]].append(Sprite(
            SpriteSpec(filename, entry["x"], entry["y"]), bytes(bgra), sha256(outputs[filename])))
    for name, data in baselines.items():
        if name not in outputs:
            raise InstallError(f"Prepared atlas is missing: {name}")
        base = parse_baseline(data, name)
        desired, _ = make_desired_pixels(base, tuple(sprites[name]))
        validate_generated_atlas(base, outputs[name], desired, name)
    return {name: outputs[name] for name in baselines}


def accepted_current(current: bytes, desired: bytes, name: str) -> None:
    if current != desired and sha256(current) != BASELINE_HASHES[name]:
        raise InstallError(f"Refusing unknown {name}; expected the exact reviewed baseline or prepared release")


def build_plan(client_root: Path, asset_root: Path) -> list[Change]:
    desired = verify_release(asset_root)
    plan = []
    for locale in ("en_us", "zh_cn"):
        locale_root = contained(client_root, client_root / "Localization" / locale)
        for filename, validator in (("ItemBaseAttribute.xml", validate_item_consumers),
                                    ("EquipStoneInfo.xml", validate_socket_consumers)):
            path = contained(client_root, locale_root / "Settings/Sys" / filename)
            current = path.read_bytes()
            validator(current, str(path))
            # Include prerequisites in the transaction snapshot to catch a
            # concurrent metadata edit, without changing a single XML byte.
            plan.append(Change(path, current, current))
        for name, prepared in desired.items():
            path = contained(client_root, locale_root / "UI/Texture" / name)
            current = path.read_bytes()
            accepted_current(current, prepared, name)
            plan.append(Change(path, current, prepared))
    return plan
