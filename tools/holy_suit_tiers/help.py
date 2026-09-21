"""Targeted Lua/help presentation edits; compatibility callbacks keep their names."""
from __future__ import annotations

import re
from ascension_core_text import NAME as CORE_NAME, NPC_REQUIREMENTS, renamed_words

from .material_release import PREVIOUS_DIVINIUM_HELP
from .policy import DIVINIUM_HELP_KEY, DIVINIUM_PERCENTAGES, DIVINIUM_TEXT_KEY, TIERS, material_name
from .text import PatchError, element, managed_block, replace_one, unique


def lua_value(text: str, key: str, value: str, *, optional: bool = False) -> str:
    pattern = r"^" + re.escape(key) + r'[ \t]*=[ \t]*"[^\r\n]*"[ \t]*'
    if optional and not re.search(pattern, text, re.MULTILINE):
        return text
    # Values are authored ASCII, never interpolated untrusted Lua expressions.
    return replace_one(text, pattern, f'{key} = "{value}"', f"Lua token {key}")


def fonts(text: str, newline: str) -> str:
    for key, tier in zip(("MITHRIL_COLOR", "ORICHALCUM_COLOR", "ADAMANTIUM_COLOR"), TIERS):
        r, g, b = (int(tier.color[index:index + 2], 16) for index in (0, 2, 4))
        text = replace_one(text, r"^" + key + r"[ \t]*=[ \t]*\{[^\r\n]*\}",
                           f"{key}={{r={r}, g={g}, b={b}, a=255}}", key)
    if "DIVINIUM_COLOR" in text and "-- Reborn Holy Suit Divinium color: BEGIN" not in text:
        raise PatchError("DIVINIUM_COLOR is already allocated")
    return managed_block(text, "Holy Suit Divinium color", "DIVINIUM_COLOR={r=255, g=248, b=231, a=255}", newline)


def labels(text: str, newline: str) -> str:
    for index, tier in enumerate(TIERS[:3]):
        key = f"HS_X0_{29 + index}"
        if re.search(r"^" + key + r"[ \t]*=", text, re.MULTILINE):
            text = lua_value(text, key, tier.name + " Suit")
        else:
            text = managed_block(text, f"Holy Suit {key} label", f'{key} = "{tier.name} Suit"', newline)
    if DIVINIUM_TEXT_KEY in text and "-- Reborn Holy Suit Divinium label: BEGIN" not in text:
        raise PatchError(f"{DIVINIUM_TEXT_KEY} is already allocated")
    return managed_block(text, "Holy Suit Divinium label", f'{DIVINIUM_TEXT_KEY} = "Divinium Suit"', newline)


def npc_text(text: str) -> str:
    core_installed = re.search(r'^NF_L0_ZBJY8[^\r\n]*' + re.escape(CORE_NAME), text, re.MULTILINE) is not None
    text = lua_value(text, "NF_L0_ZBJY8",
                     "|cffF14187Use the material matching the target Holy Suit tier. Advanced materials are "
                     "RuneSteel Ingot, Arcanite Crystal, Seraphite Core, and Divinium Essence. "
                     "The target level determines quantity. Experience Prisms are required when specified.|cffffffff")
    if core_installed:
        text = lua_value(text, "NF_L0_ZBJY8", NPC_REQUIREMENTS)
    # These two authored advanced-drilling tokens are absent in some stock
    # locales. Updating only present keys preserves the existing UI routing.
    text = lua_value(text, "NF_LO_L01",
                     "|cffFFFF00Advanced Drilling Requirements|cffffffff\\n3rd socket: Lv.140+ gear + Socket Spell III."
                     "\\n4th socket: Lv.140+ gear + Socket Spell IV + Arcanite Lv.1+ + Arcane quality+ + Grade 20+.",
                     optional=True)
    return lua_value(text, "NF_LO_L05",
                     "|cffF14187The equipment does not meet the next socket requirements. Socket 3 needs Level 140+. "
                     "Socket 4 also needs Arcanite Level 1+, Arcane quality+, and Grade 20+.|cffffffff", optional=True)


def help_config(text: str, newline: str) -> str:
    first = unique(r"HelpSystem_Cofig\[16\][ \t]*=[ \t]*\{[\s\S]*?\]\][\s\S]*?\}",
                   text, "Holy Suit help entry 16")
    core_installed = CORE_NAME in first.group()
    for index, tier in enumerate(TIERS[:3], 16):
        pattern = r"HelpSystem_Cofig\[" + str(index) + r"\][ \t]*=[ \t]*\{[\s\S]*?\]\][\s\S]*?\}"
        match = unique(pattern, text, f"Holy Suit help entry {index}")
        block = match.group().replace(tier.old_name, tier.name)
        old_color = ("74DBAB", "BE5BFC", "E26EA1")[index - 16]
        block = re.sub(re.escape(old_color), tier.color, block, flags=re.IGNORECASE)
        if index == 18 and "Level 10-1" not in block:
            closing = unique(r"^[ \t]*\]\]", block, "Seraphite help closing")
            block = block[:closing.start()] + "Level 10-1  |  99 Experience Prism" + newline + block[closing.start():]
        if core_installed:
            block = renamed_words(block)
        text = text[:match.start()] + block + text[match.end():]
    if DIVINIUM_HELP_KEY in text and "-- Reborn Holy Suit Divinium help: BEGIN" not in text:
        raise PatchError("Divinium help key is already allocated")
    rows = [f'HelpSystem_Cofig["{DIVINIUM_HELP_KEY}"] = {{', "  static_text=[[",
            "|cFFFFF8E7Divinium Suit|cFFFFFFFF", "",
            "Divinium increases supported base equipment attributes by 71%-90% across ten levels.",
            "Holy Suit bonus percentages by level:",
            ", ".join(f"{index + 1}: {percent}%" for index, percent in enumerate(DIVINIUM_PERCENTAGES)),
            "", f"Level 10 Seraphite -> Level 1 Divinium: 99 Experience Prisms + 1 {material_name(TIERS[3])}."]
    rows.extend(f"Level {level}-{level + 1}: {99 + level * 3} Experience Prisms + {level + 1} {material_name(TIERS[3])}."
                for level in range(1, 10))
    rows.extend(("Level 10 is the maximum. Appended attributes and Class Suit bonuses are separate.", "  ]]", "}"))
    body = "\n".join(rows)
    if core_installed:
        body = renamed_words(body)
    return managed_block(text, "Holy Suit Divinium help", body, newline,
                         previous_bodies=(PREVIOUS_DIVINIUM_HELP,))


def help_proc(text: str, newline: str) -> str:
    key = "HelpSystem_OnClickDiviniumBtn"
    if key in text and "-- Reborn Holy Suit Divinium callback: BEGIN" not in text:
        raise PatchError("Divinium help callback is already allocated")
    body = (f"function {key}()\n\tHelpSystem_Initcontainer1();\n"
            f'\tcont1_text:SetText(Get_HelpSystem_Cofig("{DIVINIUM_HELP_KEY}").static_text);\nend')
    return managed_block(text, "Holy Suit Divinium callback", body, newline)


def help_layout(text: str, newline: str) -> str:
    attributes = {"Template": "T_NoTextureButton", "Rectangle": "20,545,120,565", "SText": DIVINIUM_TEXT_KEY,
                  "Font": "CONTAIN2_HELPSYSTEM_TEXTFONT", "FontColor": "DIVINIUM_COLOR",
                  "OnClick": "HelpSystem_OnClickDiviniumBtn()"}
    if "<DiviniumBtn" in text:
        _, node = element(text, "DiviniumBtn")
        if node.attrib != attributes:
            raise PatchError("Divinium help button is occupied by unrelated content")
        return text
    container = unique(r"<Container\b[\s\S]*?</Container>", text, "help navigation container")
    body = container.group()
    anchor = unique(r'<StoneBtn\b[^<>]*SText="HS_X0_19"[^<>]*/>', body, "Holy Stone help button")
    if 'Rectangle="10,545,80,565"' not in anchor.group():
        raise PatchError("Unknown Holy Stone help geometry; refusing to overlap another button")
    # Only the first scrolling navigation container is affected. Shift later
    # rows down one slot; preserve the main help panel and all other geometry.
    def shift(match: re.Match[str]) -> str:
        parts = tuple(int(value) for value in match.group(1).split(","))
        if len(parts) != 4:
            raise PatchError("Malformed help rectangle")
        x1, y1, x2, y2 = parts
        return f'Rectangle="{x1},{y1 + 25},{x2},{y2 + 25}"' if y1 >= 545 else match.group()
    tail = re.sub(r'Rectangle="([0-9,]+)"', shift, body[anchor.start():])
    button = "<DiviniumBtn " + " ".join(f'{key}="{value}"' for key, value in attributes.items()) + "/>"
    body = body[:anchor.start()] + button + newline + "       " + tail
    return text[:container.start()] + body + text[container.end():]
