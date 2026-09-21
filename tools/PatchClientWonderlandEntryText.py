#!/usr/bin/env python3
"""Correct Wonderland entry notes without changing its client routing or server policy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from holy_suit_tiers.text import Document, PatchError, unique
from holy_suit_tiers.transaction import Change, contained, install

OLD_NOTES = {
    "en_us": " Notes: This instance is only allowed to enter once a day before 23:00! ",
    "zh_cn": "注：该副本每天23:00之前允许进入一次。",
}
WEEKEND_NOTES = {
    "en_us": " Notes: Level 120+. Enter solo or with up to 5 players. 3 free entries per day on "
             "Saturday and Sunday, before 23:00 server time (Asia/Manila). Each run lasts 40 minutes. ",
    "zh_cn": "注：需要120级及以上，可单人或1至5人组队进入。每周六、周日服务器时间（Asia/Manila）"
             "23:00前可免费进入3次，每次限时40分钟。",
}
NOTES = {
    "en_us": " Notes: Level 120+. Enter solo or with up to 5 players. 3 free entries every day, "
             "before 23:00 server time (Asia/Manila). Each run lasts 40 minutes. ",
    "zh_cn": "注：需要120级及以上，可单人或1至5人组队进入。每天服务器时间（Asia/Manila）"
             "23:00前可免费进入3次，每次限时40分钟。",
}
OLD_UNAVAILABLE = {"en_us": "Sorry, it's not Saturday or Sunday yet. ", "zh_cn": "不是星期六或者星期日"}
UNAVAILABLE = {"en_us": "Wonderland is currently unavailable. ", "zh_cn": "飘渺幻境暂时无法进入。"}
SOURCE_NOTES = (" Notes: This instance may be entered up to 3 times per day on Saturday and "
                "Sunday before 23:00! ")


def patch_notes(text: str, locale: str) -> str:
    row = unique(r'^LuaText\.NF_EM_T211[ \t]*=[ \t]*"[^\r\n]*"', text, "Wonderland entry notes")
    note = unique(r"\|cffF14187([\s\S]*?)\|cFFFFFFFF", row.group(), "Wonderland colored notes")
    accepted = (OLD_NOTES[locale], WEEKEND_NOTES[locale], NOTES[locale]) + ((SOURCE_NOTES,) if locale == "en_us" else ())
    if note[1] not in accepted:
        raise PatchError("Wonderland notes differ from the audited existing or corrected wording")
    start, end = row.start() + note.start(1), row.start() + note.end(1)
    return text[:start] + NOTES[locale] + text[end:]


def patch_unavailable(text: str, locale: str) -> str:
    row = unique(r'^(LuaText\.NF_EM_T300[ \t]*=[ \t]*")([^\r\n]*)(")', text,
                 "Wonderland unavailable message")
    if row[2] not in (OLD_UNAVAILABLE[locale], UNAVAILABLE[locale]):
        raise PatchError("Unknown Wonderland unavailable message")
    return text[:row.start(2)] + UNAVAILABLE[locale] + text[row.end(2):]


def build_plan(root: Path, repository_source: bool = False) -> list[Change]:
    changes = []
    for locale in (("en_us",) if repository_source else ("en_us", "zh_cn")):
        path = contained(root, root / "Localization" / locale / "UI/Base/LuaText.lua")
        document = Document.read(path)
        updated = patch_unavailable(patch_notes(document.text, locale), locale)
        changes.append(Change(path, path.read_bytes(), document.encode(updated)))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--repository-source", action="store_true")
    parser.add_argument("--mode", choices=("preview", "apply", "verify"), default="preview")
    args = parser.parse_args()
    try:
        root = args.client_root.resolve()
        plan = build_plan(root, args.repository_source)
        result = {"mode": args.mode, "files": [c.summary(root) for c in plan]}
        if args.mode == "apply":
            result.update(install(root, plan))
            if any(c.changed for c in build_plan(root, args.repository_source)):
                raise PatchError("Wonderland notes readback differs")
        elif args.mode == "verify":
            if any(c.changed for c in plan):
                raise PatchError("Wonderland notes need installation")
            result["status"] = "Verified"
        print(json.dumps(result, indent=2))
        return 0
    except (PatchError, OSError, ValueError) as error:
        print(f"Wonderland entry notes patch failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
