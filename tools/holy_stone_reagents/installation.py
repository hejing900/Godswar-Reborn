"""Reversible publication of isolated reagent artwork and scoped client text."""
from __future__ import annotations

from pathlib import Path

from holy_suit_tiers.text import Document
from holy_suit_tiers.transaction import Change, contained
from level5_forge_icons.common import InstallError
from isolated_item_artwork import verify_catalog_release
from .catalog import ATLAS, read_catalog
from .help import patch_help
from .text import (patch_descriptions, patch_items, patch_lua, patch_names,
                   patch_result_branch)


def verify_release(root: Path) -> bytes:
    return verify_catalog_release(root, read_catalog(root), ATLAS)

def build_metadata_plan(client_root: Path, *, repository_source: bool = False) -> list[Change]:
    plan = []
    locales = ("en_us",) if repository_source else ("en_us", "zh_cn")
    for locale in locales:
        base = contained(client_root, client_root / "Localization" / locale)
        patches = [
            ("Settings/Sys/ItemBaseAttribute.xml", lambda doc: patch_items(doc.text)),
            ("Text/EquipName.dat", lambda doc: patch_names(doc.text, doc.newline)),
            ("Text/EquipDescription.dat", lambda doc: patch_descriptions(doc.text, doc.newline)),
            ("UI/Base/LuaText.lua", lambda doc: patch_lua(doc.text, doc.newline)),
        ]
        if not repository_source:
            patches.append(("UI/XML/NpcFun/NpcFunEment.lua",
                            lambda doc: patch_result_branch(doc.text, doc.newline)))
            patches.append(("UI/XML/HelpSystemConfig.lua",
                            lambda doc: patch_help(doc.text, doc.newline)))
        elif (base / "UI/XML/HelpSystemConfig.lua").exists():
            patches.append(("UI/XML/HelpSystemConfig.lua",
                            lambda doc: patch_help(doc.text, doc.newline)))
        for relative, patch in patches:
            path = contained(client_root, base / relative)
            doc = Document.read(path)
            plan.append(Change(path, path.read_bytes(), doc.encode(patch(doc))))
    return plan


def build_plan(client_root: Path, asset_root: Path, *, repository_source: bool = False) -> list[Change]:
    desired = verify_release(asset_root)
    plan = build_metadata_plan(client_root, repository_source=repository_source)
    if repository_source:
        return plan
    for locale in ("en_us", "zh_cn"):
        path = contained(client_root, client_root / "Localization" / locale / "UI/Texture" / ATLAS)
        current = path.read_bytes() if path.exists() else None
        if current is not None and current != desired:
            raise InstallError(f"Refusing to replace an unknown dedicated reagent atlas: {path}")
        plan.append(Change(path, current, desired))
    return plan
