"""Prepare the complete client content transaction without publishing files."""
from __future__ import annotations

from pathlib import Path
import hashlib
import re
import xml.etree.ElementTree as ET

from level5_forge_icons.tga_atlas import parse_tga
from ascension_core_text import NAME as CORE_NAME, renamed_words

from . import help as help_text
from .badges import badges, patch_bag_control
from .badge_atlas import prepare_badge_atlas
from .material_release import (PREVIOUS_DIVINIUM_DESCRIPTION, PREVIOUS_DIVINIUM_NAME,
                               PREVIOUS_MATERIAL_ATLAS_RELEASES)
from .item_container import add_beside_predecessor
from .policy import (ATLAS_NAME, TIERS, atlas_path, divinium_effect_rows,
                     material_description, material_name)
from .text import (Document, PatchError, add_xml, element, replace_rows, set_attributes, xml_nodes)
from .transaction import Change, contained


def names(text: str, newline: str) -> str:
    values: dict[str, str] = {}
    new: set[str] = {"Shenqi9017"}
    for tier in TIERS:
        values[f"Shenqi{9009 + tier.number}"] = material_name(tier)
        for index, adjective in enumerate(tier.adjectives, 1):
            key = tier.badge_key + str(index)
            values[key] = f"{adjective} {tier.name} Suit"
            if tier.number == 8:
                new.add(key)
    return replace_rows(text, values, newline, frozenset(new),
                        previous_values={"Shenqi9017": PREVIOUS_DIVINIUM_NAME})


def descriptions(text: str, newline: str) -> str:
    # A later item9025 presentation release keeps the same recipes. Preserve
    # that installed name when this older, independently rerunnable tool runs.
    core_installed = re.search(r"^Congregation6\t[^\r\n]*" + re.escape(CORE_NAME), text, re.MULTILINE) is not None
    values: dict[str, str] = {}
    new: set[str] = {"Shenqi9017"}
    for tier in TIERS:
        values[f"Shenqi{9009 + tier.number}"] = material_description(tier)
        for level in range(1, 11):
            key = f"Suit{tier.number * 100 + level}"
            values[key] = f"|cFF{tier.color}Level {level} {tier.name}"
            if tier.number == 8:
                new.add(key)
        for index, adjective in enumerate(tier.adjectives, 1):
            key = tier.badge_key + str(index)
            if tier.number == 8:
                values[key] = (f"{adjective} Divinium Holy Suit. Holy Suit effects increase with "
                               "equipped Holy Suit points.")
                new.add(key)
            else:
                match = re.search(r"^" + key + r"\t([^\r\n]*)", text, re.MULTILINE)
                if match is None:
                    raise PatchError(f"Missing badge description: {key}")
                values[key] = match.group(1).replace(tier.old_name, tier.name)
    values["Congregation6"] = ("The Master Vestment Forger uses Experience Prisms for RuneSteel, Arcanite, "
                                "Seraphite, and Divinium upgrades. Each Prism represents 100,000,000 EXP "
                                "and is consumed when used.")
    if core_installed:
        values = {key: renamed_words(value) for key, value in values.items()}
        # Preserve the intentionally shorter noun within the catalyst tooltip.
        values["Congregation6"] = values["Congregation6"].replace("Each Ascension Core", "Each Core")
    return replace_rows(text, values, newline, frozenset(new),
                        previous_values={"Shenqi9017": PREVIOUS_DIVINIUM_DESCRIPTION})


def items(text: str, newline: str, locale: str) -> str:
    nodes = list(ET.fromstring(text).iter())
    existing = [node for node in nodes if node.get("ID") == "9017"]
    if len(existing) > 1 or any(node.tag != "Shenqi9017" for node in existing):
        raise PatchError("Material item ID9017 is already allocated")
    for tier in TIERS[:3]:
        key = f"Shenqi{9009 + tier.number}"
        _, node = element(text, key)
        if node.get("ID") != str(9009 + tier.number) or node.get("Type") != "consume item":
            raise PatchError(f"Unexpected material identity: {key}")
        text = set_attributes(text, key, {"Texture": atlas_path(locale), "Icon": f"{tier.x},0"})
    _, predecessor = element(text, "Shenqi9016")
    # Copy only the reviewed stock consumable shape, not arbitrary added skills.
    allowed = {"ID", "Type", "Texture", "Icon", "Random", "Distribution", "Money", "Overlap"}
    if set(predecessor.attrib) != allowed or predecessor.get("Overlap") != "99":
        raise PatchError("Unknown Seraphite material template; refusing to clone additional item behavior")
    attrs = {"ID": "9017", "Type": "consume item", "Texture": atlas_path(locale), "Icon": "108,0",
             "Random": "0", "Distribution": "0,0", "Money": "0", "Overlap": "99"}
    return add_beside_predecessor(text, "Shenqi9017", attrs, "Shenqi9016", newline)


def effects(text: str, newline: str) -> str:
    nodes = xml_nodes(text)
    for code in range(801, 811):
        matching = [node for node in nodes if node.get("LvId") == str(code)]
        if len(matching) > 1 or any(node.tag != f"Edivlv{code - 800}" for node in matching):
            raise PatchError(f"Divinium effect code is already allocated: {code}")
    _, terminal = element(text, "Exsslv10")
    if terminal.attrib not in ({"LvId": "710", "Effect": "0.7", "Exp": "999999999", "Fun": "70"},
                              {"LvId": "710", "Effect": "0.7", "Exp": "99", "Fun": "70"}):
        raise PatchError("Unknown tier7 terminal upgrade row")
    text = set_attributes(text, "Exsslv10", {"Exp": "99"})
    for index, attrs in enumerate(divinium_effect_rows(), 1):
        text = add_xml(text, f"Edivlv{index}", attrs, "EquipEff", newline)
    return text


def validate_atlas(data: bytes) -> None:
    try:
        atlas = parse_tga(data, ATLAS_NAME)
    except Exception as error:
        raise PatchError(f"Invalid native Holy Suit atlas: {error}") from error
    # Coordinates are top-origin UI positions. Native TGA stores bottom-origin
    # rows. Gear badges live in HolySuitBadges.gwo; only material cells belong here.
    for x in (0, 36, 72, 108):
        visible = sum(atlas.pixels[((atlas.height - 1 - row) * atlas.width + col) * 4 + 3] > 0
                      for row in range(36) for col in range(x, x + 36))
        if visible < 16:
            raise PatchError(f"Missing material pixels at {x},0")


def build_plan(root: Path, atlas_source: Path, locales: tuple[str, ...] = ("en_us", "zh_cn"),
               badge_atlas_source: Path | None = None) -> list[Change]:
    root = root.resolve()
    if not root.is_dir() or not locales or len(set(locales)) != len(locales) or any(
            locale not in ("en_us", "zh_cn") for locale in locales):
        raise PatchError("Select an existing client root and unique supported locales")
    atlas = atlas_source.read_bytes()
    validate_atlas(atlas)
    badge_atlas_source = badge_atlas_source or (
        Path(__file__).resolve().parents[2] / "assets/holy-suit-badges/generated/HolySuitBadges.gwo")
    changes = prepare_badge_atlas(root, badge_atlas_source, locales)
    for locale in locales:
        directory = root / "Localization" / locale
        operations = {
            "Text/EquipName.dat": names,
            "Text/EquipDescription.dat": descriptions,
            "Settings/Sys/ItemBaseAttribute.xml": lambda text, nl: items(text, nl, locale),
            "Settings/Sys/EquipEffect.xml": effects,
            "Settings/Sys/EquipSuitInfoIni.xml": lambda text, nl: badges(text, nl, locale),
            "UI/XML/EquipSuitInfoIni.xml": lambda text, nl: badges(text, nl, locale),
            "UI/XML/ItemBagsExUI.xml": lambda text, _: patch_bag_control(text, locale),
            "UI/Base/font.lua": help_text.fonts,
            "UI/Base/text.lua": help_text.labels,
            "UI/Base/LuaText.lua": lambda text, _: help_text.npc_text(text),
            "UI/XML/HelpSystemConfig.lua": help_text.help_config,
            "UI/XML/HelpSystemProc.lua": help_text.help_proc,
            "UI/XML/HelpSystem.xml": help_text.help_layout,
        }
        # Texture publication is in the same transaction, before references.
        target = contained(root, directory / "UI" / "Texture" / ATLAS_NAME)
        before = target.read_bytes() if target.exists() else None
        if (before is not None and before != atlas and
                hashlib.sha256(before).hexdigest() not in PREVIOUS_MATERIAL_ATLAS_RELEASES):
            raise PatchError(f"Dedicated atlas is occupied by different content: {target}")
        changes.append(Change(target, before, atlas))
        for relative, operation in operations.items():
            path = contained(root, directory / relative)
            before = path.read_bytes()
            document = Document.read(path)
            try:
                after_text = operation(document.text, document.newline)
            except PatchError as error:
                raise PatchError(f"{locale}/{relative}: {error}") from error
            if path.suffix.lower() == ".xml":
                xml_nodes(after_text)
            changes.append(Change(path, before, document.encode(after_text)))
    return changes
