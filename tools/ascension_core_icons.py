"""Isolated artwork and lossless Ascension Core presentation for existing item9025."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from ascension_core_text import NAME, patch_descriptions, patch_help, patch_lua, patch_names
from holy_stone_icons.catalog import json_bytes
from holy_suit_tiers.text import Document, PatchError, element, set_attributes
from holy_suit_tiers.transaction import Change, contained
from isolated_item_artwork import pack_catalog, verify_catalog_release
from level5_forge_icons.common import InstallError

ATLAS = "ExperienceCatalyst.gwo"
TEXTURE = "./Localization/en_us/UI/Texture/" + ATLAS
OLD_TEXTURE = "./Localization/en_us/UI/Texture/Icon2.gwo"


def expected_manifest() -> dict:
    return {"schema_version": 1, "sprite_size": 36, "atlas_size": 1024,
            "texture": TEXTURE, "entries": [{"item_id": 9025, "slug": "ascension-core",
            "name": NAME, "atlas": ATLAS, "x": 0, "y": 0}]}


def read_catalog(root: Path) -> list[dict]:
    manifest = json.loads((root / "manifest.json").read_bytes())
    if manifest != expected_manifest():
        raise InstallError("Ascension Core manifest differs from the reviewed item9025 contract")
    return manifest["entries"]


def pack(root: Path) -> dict[Path, bytes]:
    return pack_catalog(root, read_catalog(root), ATLAS, NAME)


def verify_release(root: Path) -> bytes:
    return verify_catalog_release(root, read_catalog(root), ATLAS)


def patch_items(text: str) -> str:
    try:
        nodes = list(ET.fromstring(text).iter())
    except ET.ParseError as error:
        raise PatchError(f"Malformed item XML: {error}") from error
    for node in nodes:
        texture = node.get("Texture", "").replace("\\", "/").rsplit("/", 1)[-1]
        if texture == ATLAS and node.get("ID") != "9025":
            raise PatchError(f"Unrelated item uses the Ascension Core atlas: {node.tag}")
    _, item = element(text, "Congregation6")
    if item.get("ID") != "9025" or sum(n.get("ID") == "9025" for n in nodes) != 1:
        raise PatchError("Expected exactly one experience catalyst item9025")
    if (item.get("Texture"), item.get("Icon")) not in {(OLD_TEXTURE, "216,72"), (TEXTURE, "0,0")}:
        raise PatchError("Item9025 differs from its reviewed old or new icon mapping")
    return set_attributes(text, "Congregation6", {"Texture": TEXTURE, "Icon": "0,0"})


def build_metadata_plan(client_root: Path, *, repository_source: bool = False) -> list[Change]:
    plan = []
    for locale in (("en_us",) if repository_source else ("en_us", "zh_cn")):
        base = client_root / "Localization" / locale
        patches = [("Settings/Sys/ItemBaseAttribute.xml", lambda doc: patch_items(doc.text)),
                   ("Text/EquipName.dat", lambda doc: patch_names(doc.text, doc.newline)),
                   ("Text/EquipDescription.dat", lambda doc: patch_descriptions(doc.text, doc.newline)),
                   ("UI/Base/LuaText.lua", lambda doc: patch_lua(doc.text, doc.newline))]
        if not repository_source or (base / "UI/XML/HelpSystemConfig.lua").exists():
            patches.append(("UI/XML/HelpSystemConfig.lua", lambda doc: patch_help(doc.text)))
        for relative, patch in patches:
            path = contained(client_root, base / relative)
            document = Document.read(path)
            plan.append(Change(path, path.read_bytes(), document.encode(patch(document))))
    return plan


def build_plan(client_root: Path, asset_root: Path, *, repository_source: bool = False) -> list[Change]:
    desired = verify_release(asset_root)
    plan = build_metadata_plan(client_root, repository_source=repository_source)
    if not repository_source:
        for locale in ("en_us", "zh_cn"):
            path = contained(client_root, client_root / "Localization" / locale / "UI/Texture" / ATLAS)
            current = path.read_bytes() if path.exists() else None
            if current is not None and current != desired:
                raise InstallError(f"Refusing to replace an unknown Ascension Core atlas: {path}")
            plan.append(Change(path, current, desired))
    return plan
