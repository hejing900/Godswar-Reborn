"""Scoped presentation for the existing experience catalyst, item9025."""
from __future__ import annotations

import re

from holy_suit_tiers.text import PatchError, append_lines, replace_rows, unique

NAME = "Ascension Core"
PLURAL = "Ascension Cores"
DESCRIPTION = ("The Master Vestment Forger uses Ascension Cores for RuneSteel, Arcanite, "
               "Seraphite, and Divinium upgrades. Each Core represents 100,000,000 EXP "
               "and is consumed when used.")
NPC_REQUIREMENTS = ("|cffF14187Use the material matching the target Holy Suit tier. Advanced materials "
                    "are RuneSteel Ingot, Arcanite Crystal, Seraphite Core, and Divinium Essence. "
                    "The target level determines quantity. Ascension Cores are required when specified.|cffffffff")
LUA_VALUES = {
    "NF_L0_ZBJY888": "Please enter the number of Ascension Cores.",
    "NF_L0_ZBJY8": NPC_REQUIREMENTS,
    "NF_L0_ZBJY10": "Enter the number of Ascension Cores you want to create. Each Ascension Core "
                    "consumes 100,000,000 EXP.|cffffffff",
    "NF_L0_ZBJY11": "|cffF14187Note: Ensure you have enough EXP to create the specified number of "
                    "Ascension Cores.|cffffffff",
    "NF_L0_ZBJY2100": "|cffF14187Your EXP has successfully been transformed into Ascension Cores.|cffffffff",
    "NF_L0_ZBJY401": "|cffF14187*Create Ascension Cores|cffffffff",
}


def renamed_words(text: str) -> str:
    text = re.sub(r"\b(?:Experience )?Prism(s?)\b",
                  lambda match: PLURAL if match[1] else NAME, text)
    # Stock upgrade tables use the singular item label after every quantity.
    # Keep the quantities exactly while using the proper new plural.
    return re.sub(r"\b(\d+)([ \t]+)Ascension Core\b",
                  lambda match: match[1] + match[2] + (NAME if int(match[1]) == 1 else PLURAL), text)


def patch_names(text: str, newline: str) -> str:
    return replace_rows(text, {"Congregation6": NAME}, newline)


def patch_descriptions(text: str, newline: str) -> str:
    values = {"Congregation6": DESCRIPTION,
              "SuitUpGradeExp": "EXP or Ascension Cores needed for the upgrade"}
    for item_id in range(9014, 9018):
        key = "Shenqi" + str(item_id)
        matches = list(re.finditer(r"^" + key + r"\t([^\r\n]*)", text, re.MULTILINE))
        if not matches and item_id == 9017:
            # The historical repository source omits the published Divinium
            # material. This rename must not invent a second item definition.
            continue
        if len(matches) != 1:
            raise PatchError(f"Missing or duplicate Holy Suit material description: {key}")
        values[key] = renamed_words(matches[0][1])
    return replace_rows(text, values, newline)


def patch_lua(text: str, newline: str) -> str:
    for key, value in LUA_VALUES.items():
        pattern = r"(?m)^([ \t]*" + re.escape(key) + r'[ \t]*=[ \t]*")[^"\r\n]*("[ \t]*;?[ \t]*)'
        matches = list(re.finditer(pattern, text))
        if len(matches) > 1 or (not matches and key == "NF_L0_ZBJY8"):
            raise PatchError(f"Missing or duplicate Ascension Core localization key: {key}")
        if not matches:
            # The stock secondary locale lacks the optional transformation
            # labels. Add only these exact compatibility keys, without routing changes.
            text = append_lines(text, [f'{key} = "{value}"'], newline)
        else:
            match = matches[0]
            text = text[:match.start()] + match[1] + value + match[2] + text[match.end():]
    return text


def patch_help(text: str) -> str:
    for index in (16, 17, 18):
        pattern = r"HelpSystem_Cofig\[" + str(index) + r"\][ \t]*=[ \t]*\{[\s\S]*?\]\][\s\S]*?\}"
        match = unique(pattern, text, f"Holy Suit help entry {index}")
        text = text[:match.start()] + renamed_words(match.group()) + text[match.end():]
    marker = "-- Reborn Holy Suit Divinium help: BEGIN"
    if marker in text:
        match = unique(re.escape(marker) + r"[\s\S]*?-- Reborn Holy Suit Divinium help: END",
                       text, "Divinium help block")
        text = text[:match.start()] + renamed_words(match.group()) + text[match.end():]
    return text
