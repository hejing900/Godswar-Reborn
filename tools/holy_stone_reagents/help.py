"""Replace only the audited Holy Stone upgrade paragraph in both help copies."""
from __future__ import annotations

import re

from holy_suit_tiers.text import PatchError

OLD_UPGRADE_HELP = (
    "3.|cffFFBBFF Holy Stone Upgrade|cffffffff: The Item Mall is a source for obtaining the "
    "Eclipse Stone, which is needed to upgrade Holy Stones. Bring your Holy Stone and Eclipse "
    "Stone to the|cffD5912B Holy Stone Artisan|cffffffff to be upgraded. Upgrade a Holy Stone "
    "from Lv.1 through Lv.4, using a Level 1 Eclipse Stone, Lv.5 through Lv.7 with a Level 2 "
    "Eclipse Stone, and Lv.8 through Lv.10 with a Level 3 Eclipse Stone.\n"
    "Holy Stone upgrades are not guaranteed due to certain tech difficulties. When a Holy Stone "
    "is upgraded unsuccessfully, its level will be reduced by 1. However, if you use an Evasion "
    "Signet when upgrading a Holy Stone, the chance of success will be increased by 10% and "
    "there will be no risk of degradation from a failed upgrade.\n"
    "A Copper Evasion Signet improves the success rate of a Holy Stone upgrade by 10%, and "
    "guarantees there will be no risk of degradation when upgrading to a Lv. 4 or Lv. 5 Holy Stone.\n"
    "A Silver Evasion Signet improves the success rate of a Holy Stone upgrade by 10%, and "
    "guarantees there will be no risk of degradation when upgrading a Lv. 5 or Lv. 6 Holy Stone.\n"
    "A Gold Evasion Signet improves the success rate of a Holy Stone upgrade by 10%, and "
    "guarantees there will be no risk of degradation when upgrading a Lv. 6 or Lv. 7 Holy Stone.\n"
)
UPGRADE_HELP = (
    "3.|cffFFBBFF Holy Stone Upgrade|cffffffff: Bring a Holy Stone and the matching Eclipse "
    "Stone to the|cffD5912B Holy Stone Artisan|cffffffff. A successful attempt raises the Holy Stone "
    "by one level. Use a Level 1 Eclipse Stone at current levels 1-3 (90% base success), a "
    "Level 2 Eclipse Stone at current levels 4-6 (25%), or a Level 3 Eclipse Stone at current "
    "levels 7-9 (10%). A failed upgrade normally lowers the Holy Stone by one level.\n"
    "A Goddess' Stone adds 10 percentage points to the upgrade success rate at current "
    "levels 1-9, but does not prevent the loss of a level on failure.\n"
    "A matching Evasion Signet adds 10 percentage points to the upgrade success rate and "
    "prevents the loss of a level on failure, only for its exact upgrade below.\n"
    "Copper Evasion Signet: current Level 4 -> Level 5.\n"
    "Silver Evasion Signet: current Level 5 -> Level 6.\n"
    "Gold Evasion Signet: current Level 6 -> Level 7.\n"
    "Platinum Evasion Signet: current Level 7 -> Level 8.\n"
    "Current Level 8+ upgrades have no rollback-protection item. Combining four Holy Stones "
    "of the same Grade safely raises the major Holy Stone by one Grade at current Grades 4-9.\n"
)
PREVIOUS_UPGRADE_HELP = UPGRADE_HELP.replace("A successful attempt raises", "Each attempt raises", 1)


def patch_help(text: str, newline: str) -> str:
    sections = list(re.finditer(r"HelpSystem_Cofig\[10\]\s*=\s*\{\s*static_text=\[\[([\s\S]*?)\]\]", text))
    if len(sections) != 1:
        raise PatchError("Expected one Holy Stone help section10")
    section = sections[0]
    body = section[1]
    desired = UPGRADE_HELP.replace("\n", newline)
    if body.count(desired) == 1:
        return text
    previous = (OLD_UPGRADE_HELP.replace("\n", newline),
                PREVIOUS_UPGRADE_HELP.replace("\n", newline))
    accepted = [old for old in previous if body.count(old) == 1]
    if len(accepted) != 1:
        raise PatchError("Holy Stone help differs from the audited old or updated upgrade paragraph")
    updated = body.replace(accepted[0], desired, 1)
    return text[:section.start(1)] + updated + text[section.end(1):]
