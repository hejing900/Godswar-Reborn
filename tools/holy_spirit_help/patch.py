"""Scoped help-only edits with strict predecessor and native navigation checks."""
from __future__ import annotations

import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from holy_suit_tiers.text import Document, PatchError, element, managed_block, unique
from holy_suit_tiers.transaction import Change, contained
from .data import CALLBACK, CHOICES, HELP_KEY, LABEL_KEY, OVERVIEW, page

PREVIOUS = json.loads(Path(__file__).with_name("previous.json").read_text(encoding="utf-8"))
ATTRIBUTES = {"Template": "T_NoTextureButton", "Rectangle": "20,645,120,665",
              "SText": LABEL_KEY, "Font": "CONTAIN2_HELPSYSTEM_TEXTFONT",
              "FontColor": "ORDINARY_INFOCOLOR", "OnClick": CALLBACK + "()"}


def normalized(text: str) -> str:
    return re.sub(r"\r+\n", "\n", text)


def section(text: str, index: int) -> re.Match[str]:
    return unique(r"HelpSystem_Cofig\[" + str(index) + r"\]\s*=\s*\{\s*static_text=\[\[([\s\S]*?)\]\]",
                  text, f"help section {index}")


def approved_replace(text: str, match: re.Match[str], desired: str, previous: str,
                     newline: str, group: int = 0) -> str:
    current = normalized(match[group])
    if current == desired:
        return text
    if current != previous:
        raise PatchError("Holy Spirit help differs from its audited predecessor")
    return text[:match.start(group)] + desired.replace("\n", newline) + text[match.end(group):]


def config(text: str, newline: str) -> str:
    for index, family in ((19, "Fire"), (20, "Water")):
        text = approved_replace(text, section(text, index), "\n" + page(family),
                                PREVIOUS[str(index)], newline, 1)
    match = section(text, 10)
    body = match[1]
    for index, desired in ((2, CHOICES), (4, OVERVIEW)):
        part = unique(r"^" + str(index) + r"\.[\s\S]*?(?=^" + str(index + 1) + r"\.)",
                      body, f"Holy Stone overview subsection {index}")
        body = approved_replace(body, part, desired, PREVIOUS[f"overview{index}"], newline)
    text = text[:match.start(1)] + body + text[match.end(1):]
    marker = "Holy Spirit Zephyr help"
    if HELP_KEY in text and f"-- Reborn {marker}: BEGIN" not in text:
        raise PatchError("Zephyr help key is already allocated")
    body = f'HelpSystem_Cofig["{HELP_KEY}"] = {{\n  static_text=[[\n' + page("Zephyr") + "  ]]\n}"
    return managed_block(text, marker, body, newline)


def proc(text: str, newline: str) -> str:
    marker = "Holy Spirit Zephyr callback"
    if CALLBACK in text and f"-- Reborn {marker}: BEGIN" not in text:
        raise PatchError("Zephyr callback is already allocated")
    body = (f"function {CALLBACK}()\n\tHelpSystem_Initcontainer1();\n"
            f'\tcont1_text:SetText(Get_HelpSystem_Cofig("{HELP_KEY}").static_text);\nend')
    return managed_block(text, marker, body, newline)


def labels(text: str, newline: str) -> str:
    marker = "Holy Spirit Zephyr label"
    if LABEL_KEY in text and f"-- Reborn {marker}: BEGIN" not in text:
        raise PatchError("Zephyr label is already allocated")
    return managed_block(text, marker, f'{LABEL_KEY} = "Zephyr Spirits"', newline)


def layout(text: str, newline: str) -> str:
    container = unique(r"<Container\b[\s\S]*?</Container>", text, "help navigation container")
    body = container[0]
    anchor = unique(r'<StoneBtn\b[^<>]*SText="HS_X0_33"[^<>]*/>', body, "Water Spirits help button")
    if 'Rectangle="20,620,80,640"' not in anchor[0]:
        raise PatchError("Unknown Water Spirits navigation geometry")
    if "<ZephyrSpiritBtn" in text:
        match, node = element(text, "ZephyrSpiritBtn")
        if node.attrib != ATTRIBUTES or not (container.start() < match.start() < container.end()):
            raise PatchError("Zephyr help button has unexpected attributes or parent")
        return text
    # Anchor + exact known following rows prevent overlap or modifying unrelated panels.
    expected = {"PetsystemBtn": "10,645,80,665", "PetsystemBtn1": "20,670,120,700",
                "PetsystemBtn2": "20,695,120,725", "LiveSkillBtn": "10,720,80,750",
                "CreateBtn": "10,745,80,775"}
    for tag, rectangle in expected.items():
        match, node = element(body, tag)
        if node.get("Rectangle") != rectangle or match.start() < anchor.end():
            raise PatchError(f"Unexpected navigation geometry for {tag}")
        shifted = [int(v) for v in rectangle.split(",")]
        shifted[1] += 25
        shifted[3] += 25
        replacement = match[0].replace(f'Rectangle="{rectangle}"',
                                       'Rectangle="' + ",".join(map(str, shifted)) + '"', 1)
        body = body[:match.start()] + replacement + body[match.end():]
    button = "<ZephyrSpiritBtn " + " ".join(f'{k}="{v}"' for k, v in ATTRIBUTES.items()) + "/>"
    body = body[:anchor.end()] + newline + "       " + button + body[anchor.end():]
    return text[:container.start()] + body + text[container.end():]


def validate_navigation(xml: str, callbacks: str, contents: str, tokens: str) -> None:
    root = ET.fromstring(xml)
    buttons = list(root.iter("ZephyrSpiritBtn"))
    if len(buttons) != 1 or buttons[0].attrib != ATTRIBUTES:
        raise PatchError("Zephyr navigation button is missing or differs")
    containers = [n for n in root.iter("Container") if buttons[0] in list(n)]
    if len(containers) != 1 or containers[0].get("Auto") != "1":
        raise PatchError("Zephyr help is outside the scrolling navigation list")
    unique(r"^function " + CALLBACK + r"\(\)[\s\S]*?Get_HelpSystem_Cofig\(\"" + HELP_KEY +
           r'"\)\.static_text\);[\s\S]*?^end', callbacks, "Zephyr callback")
    unique(r'^HelpSystem_Cofig\["' + HELP_KEY + r'"\]\s*=\s*\{\s*static_text=\[\[[\s\S]*?\]\]',
           contents, "Zephyr help body")
    unique(r'^' + LABEL_KEY + r' = "Zephyr Spirits"', tokens, "Zephyr help label")
    # Existing following rows move together, retaining their spacing and scrolling behavior.
    if element(xml, "PetsystemBtn")[1].get("Rectangle") != "10,670,80,690":
        raise PatchError("Zephyr help overlaps the following navigation row")


def build_plan(root: Path) -> list[Change]:
    root = root.resolve()
    plan = []
    for locale in ("en_us", "zh_cn"):
        outputs = {}
        for relative, transform in (("XML/HelpSystemConfig.lua", config), ("XML/HelpSystemProc.lua", proc),
                                    ("XML/HelpSystem.xml", layout), ("Base/text.lua", labels)):
            path = contained(root, root / "Localization" / locale / "UI" / relative)
            doc = Document.read(path)
            after = transform(doc.text, doc.newline)
            if transform(after, doc.newline) != after:
                raise PatchError(f"Non-idempotent help transform: {relative}")
            plan.append(Change(path, path.read_bytes(), doc.encode(after)))
            outputs[relative] = after
        validate_navigation(outputs["XML/HelpSystem.xml"], outputs["XML/HelpSystemProc.lua"],
                            outputs["XML/HelpSystemConfig.lua"], outputs["Base/text.lua"])
    return plan
