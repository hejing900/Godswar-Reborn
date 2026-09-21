"""The four Socket Spell icons, isolated from their shared native scroll cell."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from holy_stone_icons.catalog import json_bytes
from holy_suit_tiers.text import Document, PatchError, element, set_attributes
from holy_suit_tiers.transaction import Change, contained
from isolated_item_artwork import pack_catalog, verify_catalog_release
from level5_forge_icons.common import InstallError

ATLAS = "SocketSpells.gwo"
TEXTURE = "./Localization/en_us/UI/Texture/" + ATLAS
OLD_TEXTURE = "./Localization/en_us/UI/Texture/Icon.gwo"
IDS = (4270, 4271, 4272, 4273)


def expected_manifest() -> dict:
    return {"schema_version": 1, "sprite_size": 36, "atlas_size": 1024,
            "texture": TEXTURE,
            "entries": [{"item_id": item_id, "slug": f"socket-spell-{index + 1}",
                         "name": "Socket Spell " + ("I", "II", "III", "IV")[index],
                         "atlas": ATLAS, "x": index * 36, "y": 0}
                        for index, item_id in enumerate(IDS)]}


def read_catalog(root: Path) -> list[dict]:
    manifest = json.loads((root / "manifest.json").read_bytes())
    if manifest != expected_manifest():
        raise InstallError("Socket Spell manifest differs from the reviewed four-item contract")
    return manifest["entries"]


def pack(root: Path) -> dict[Path, bytes]:
    return pack_catalog(root, read_catalog(root), ATLAS, "Socket Spells I-IV")


def verify_release(root: Path) -> bytes:
    return verify_catalog_release(root, read_catalog(root), ATLAS)


def patch_items(text: str) -> str:
    try:
        nodes = list(ET.fromstring(text).iter())
    except ET.ParseError as error:
        raise PatchError(f"Malformed item XML: {error}") from error
    owned = {str(item_id) for item_id in IDS}
    for node in nodes:
        texture = node.get("Texture", "").replace("\\", "/").rsplit("/", 1)[-1]
        if texture == ATLAS and node.get("ID") not in owned:
            raise PatchError(f"Unrelated item uses the Socket Spell atlas: {node.tag}")
    for index, item_id in enumerate(IDS):
        tag = "Smithing" + str(item_id)
        _, node = element(text, tag)
        if node.get("ID") != str(item_id) or sum(n.get("ID") == str(item_id) for n in nodes) != 1:
            raise PatchError(f"Expected exactly one Socket Spell item {item_id}")
        desired_icon = f"{index * 36},0"
        if (node.get("Texture"), node.get("Icon")) not in {
                (OLD_TEXTURE, "108,900"), (TEXTURE, desired_icon)}:
            raise PatchError(f"Item {item_id} differs from its reviewed old or new Socket Spell icon")
        text = set_attributes(text, tag, {"Texture": TEXTURE, "Icon": desired_icon})
    return text


def build_metadata_plan(client_root: Path, *, repository_source: bool = False) -> list[Change]:
    plan = []
    for locale in (("en_us",) if repository_source else ("en_us", "zh_cn")):
        path = contained(client_root, client_root / "Localization" / locale / "Settings/Sys/ItemBaseAttribute.xml")
        document = Document.read(path)
        plan.append(Change(path, path.read_bytes(), document.encode(patch_items(document.text))))
    return plan


def build_plan(client_root: Path, asset_root: Path, *, repository_source: bool = False) -> list[Change]:
    desired = verify_release(asset_root)
    plan = build_metadata_plan(client_root, repository_source=repository_source)
    if not repository_source:
        for locale in ("en_us", "zh_cn"):
            path = contained(client_root, client_root / "Localization" / locale / "UI/Texture" / ATLAS)
            current = path.read_bytes() if path.exists() else None
            if current is not None and current != desired:
                raise InstallError(f"Refusing to replace an unknown Socket Spell atlas: {path}")
            plan.append(Change(path, current, desired))
    return plan
