"""Keep native bag badge controls and authored gear atlas coordinates aligned."""
from __future__ import annotations

from .policy import CONDITIONS, TIERS, atlas_path
from .text import PatchError, add_xml, element, set_attributes, xml_nodes


# Three established gear cells plus one independently audited unused cell.
BADGE_POSITIONS = ("774,355", "744,355", "714,355", "684,355")
BADGE_ATLAS_NAME = "HolySuitBadges.gwo"
BADGE_ATLAS_PATH = "./Localization/en_us/UI/Texture/" + BADGE_ATLAS_NAME


def main_atlas_path(locale: str) -> str:
    return f"./Localization/{locale}/UI/Texture/main.gwo"


def bag_control_texture(text: str, locale: str) -> str:
    # Origin.exe binds ID110038 to UI+0x278C at0x57334B. Both hover
    # (0x57709B) and normal refresh (0x57901A) update ONLY IcoPos, never
    # the row's MtPath. Both must be changed in the same atlas transaction.
    _, control = element(text, "SuButton")
    expected = {"ID": "110038", "BtnTopRect": "0,0,30,30"}
    # Both installed locales use the English atlas; accept the equivalent
    # reviewed locale-relative form without rewriting the shared UI control.
    if (any(control.get(key) != value for key, value in expected.items()) or
            control.get("BtnTopTexture") not in (main_atlas_path("en_us"), main_atlas_path(locale),
                                                BADGE_ATLAS_PATH)):
        raise PatchError("Unknown native Holy Suit badge control texture/size")
    return control.attrib["BtnTopTexture"]


def patch_bag_control(text: str, locale: str) -> str:
    bag_control_texture(text, locale)
    return set_attributes(text, "SuButton", {"BtnTopTexture": BADGE_ATLAS_PATH})


def badges(text: str, newline: str, locale: str) -> str:
    nodes = xml_nodes(text)
    allowed_new = {"Suitdiv" + str(index) for index in range(1, 5)}
    if any(node.get("Type") == "8" and node.tag not in allowed_new for node in nodes):
        raise PatchError("Holy Suit Type8 is already allocated")
    for tier, position in zip(TIERS, BADGE_POSITIONS):
        for index, condition in enumerate(CONDITIONS, 1):
            key = tier.badge_key + str(index)
            desired = {"MtPath": BADGE_ATLAS_PATH, "Type": str(tier.number),
                       "Conditions": str(condition), "IcoPos": position}
            previous = {**desired, "MtPath": atlas_path(locale), "IcoPos": f"{tier.x},36"}
            restored_position = "804,165" if tier.number == 8 else position
            restored = {**desired, "MtPath": main_atlas_path("en_us"), "IcoPos": restored_position}
            matching = [node for node in nodes if node.tag == key]
            if tier.number == 8 and not matching:
                text = add_xml(text, key, desired, "EquipSuitInfoIni", newline)
                continue
            _, node = element(text, key)
            if tier.number == 8:
                # Permit precisely our previous authored row to migrate. Other
                # Type8 allocations must still fail before any file is changed.
                allowed = (desired, previous, restored)
            else:
                # The stock UI copy used its fallback714,165 for tiers5..7;
                # Settings/Sys contains the actual per-tier colored gear cells.
                allowed = (desired, previous, restored, {**restored, "IcoPos": "714,165"},
                           {**restored, "MtPath": main_atlas_path(locale)},
                           {**restored, "MtPath": main_atlas_path(locale), "IcoPos": "714,165"})
            if node.attrib not in allowed:
                raise PatchError(f"Unknown or occupied Holy Suit badge row: {key}")
            text = set_attributes(text, key, {"MtPath": desired["MtPath"], "IcoPos": position})
    return text
