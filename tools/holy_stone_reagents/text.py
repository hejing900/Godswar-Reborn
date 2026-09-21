"""Lossless item metadata and forward Holy Stone protection instructions."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from holy_suit_tiers.text import (PatchError, append_lines, element, replace_rows,
                                 set_attributes)
from .catalog import ATLAS, ITEMS, TEXTURE

PLATINUM_DESCRIPTION = (
    "Increases the success rate of transforming Level 7 Holy Stones into Level 8 Holy Stones "
    "by 10% and prevents the loss of a level if the upgrade fails.")
LEGACY_DESCRIPTION = (
    "Legacy compatibility item; it is not usable. Level 8+ Holy Stone upgrades have no "
    "rollback-protection item. Combine Holy Stones of the same Grade to upgrade safely.")
LUA_VALUES = {
    "NF_L0_ZBXQ7": "Place 1 Goddess' Stone here at Holy Stone Levels 1-9. A matching "
                   "Evasion Signet is accepted only when the current Holy Stone is Level 4, 5, 6, or 7.",
    "NF_L0_ZBXQ8": "|cffF14187Notes: (1) Level 1 Eclipse Stones have a 90% success rate, "
                   "Level 2 Eclipse Stones 25%, and Level 3 Eclipse Stones 10%. "
                   "(2) A failed upgrade normally lowers the Holy Stone by 1 level. "
                   "A Goddess' Stone adds 10% success at Levels 1-9 but never prevents rollback. "
                   "A matching Evasion Signet adds 10% success and prevents rollback only for "
                   "Level 4->5 (Copper), Level 5->6 (Silver), Level 6->7 (Gold), and Level 7->8 "
                   "(Platinum). Level 8+ upgrades have no rollback-protection item; combine Holy "
                   "Stones of the same Grade to upgrade safely.|cffffffff",
    "NF_L0_ZBXQ2400": "|cffF14187The optional catalyst is missing, stale, or does not match "
                      "this Holy Stone. Evasion Signets protect only Level 4->5 (Copper), "
                      "Level 5->6 (Silver), Level 6->7 (Gold), and Level 7->8 (Platinum).|cffffffff",
    "NF_L0_ZBXQ3400": "|cffF14187Evasion Signets are accepted only for a current Level 4, 5, "
                      "6, or 7 Holy Stone (up to reaching Level 8). Level 8+ upgrades have no "
                      "rollback-protection item and can lose 1 level on failure. Combine Holy "
                      "Stones of the same Grade to upgrade safely.|cffffffff",
}


def patch_items(text: str) -> str:
    try:
        nodes = list(ET.fromstring(text).iter())
    except ET.ParseError as error:
        raise PatchError(f"Malformed item XML: {error}") from error
    owned_ids = {str(item[0]) for item in ITEMS}
    # The dedicated atlas belongs only to these items. Reject any unreviewed
    # consumer before publishing art; original shared atlases stay untouched.
    for node in nodes:
        texture = node.get("Texture", "").replace("\\", "/").rsplit("/", 1)[-1]
        if texture == ATLAS and node.get("ID") not in owned_ids:
            raise PatchError(f"Unrelated item uses the reagent atlas: {node.tag}")
    for index, (item_id, _, _, old_atlas, old_icon) in enumerate(ITEMS):
        tag = "Stone" + str(item_id)
        _, node = element(text, tag)
        if node.get("ID") != str(item_id) or sum(n.get("ID") == str(item_id) for n in nodes) != 1:
            raise PatchError(f"Expected exactly one item {item_id}")
        old_texture = "./Localization/en_us/UI/Texture/" + old_atlas
        desired_icon = f"{index * 36},0"
        if (node.get("Texture"), node.get("Icon")) not in {
                (old_texture, old_icon), (TEXTURE, desired_icon)}:
            raise PatchError(f"Item {item_id} differs from its reviewed old or new icon mapping")
        text = set_attributes(text, tag, {"Texture": TEXTURE, "Icon": desired_icon})
    return text


def patch_names(text: str, newline: str) -> str:
    return replace_rows(text, {"Stone9054": "Platinum Evasion Signet"}, newline)


def patch_descriptions(text: str, newline: str) -> str:
    return replace_rows(text, {"Stone9054": PLATINUM_DESCRIPTION,
                              "Stone9055": LEGACY_DESCRIPTION,
                              "Stone9056": LEGACY_DESCRIPTION}, newline)


def patch_lua(text: str, newline: str) -> str:
    for key, value in LUA_VALUES.items():
        matches = list(re.finditer(r"(?m)^([ \t]*" + re.escape(key) +
                                   r'[ \t]*=[ \t]*")[^"\r\n]*("[ \t]*;?[ \t]*)', text))
        if len(matches) > 1 or (not matches and key != "NF_L0_ZBXQ3400"):
            raise PatchError(f"Missing or duplicate Holy Stone localization key: {key}")
        if matches:
            match = matches[0]
            text = text[:match.start()] + match[1] + value + match[2] + text[match.end():]
        else:
            text = append_lines(text, [f'{key} = "{value}"'], newline)
    return text


def patch_result_branch(text: str, newline: str) -> str:
    header = r"(?m)^[ \t]*elseif SubID / 100 == 34 then[ \t]*\r?$"
    matches = list(re.finditer(header, text))
    body = ("\t\telseif SubID / 100 == 34 then\n"
            "\t\t\tFirstWin_Text1:SetText(NF_L0_ZBXQ3400);\n"
            "\t\t\tFirstWin_Text1:Visible(true);\n"
            "\t\t\tFirstWin_Text1:SetPosition(25,220);\n").replace("\n", newline)
    if matches:
        if len(matches) != 1 or not text[matches[0].start():].startswith(body):
            raise PatchError("Unknown or duplicate Holy Stone protection result branch")
        return text
    # Insert after the exact audited result30 display, preserving surrounding
    # branches and each old line separator. This also supports the zh_cn copy.
    pattern = (r"(?m)^[ \t]*elseif SubID / 100 == 30 then\r?\n"
               r"[ \t]*FirstWin_Text1:SetText\(NF_LO_L05\);\r?\n"
               r"[ \t]*FirstWin_Text1:Visible\(true\);\r?\n"
               r"[ \t]*FirstWin_Text1:SetPosition\(45,100\);\r?\n")
    anchors = list(re.finditer(pattern, text))
    if len(anchors) != 1:
        raise PatchError("Expected one audited Holy Stone result30 display")
    index = anchors[0].end()
    return text[:index] + body + text[index:]
