"""Copy the probe-tagged Chinese NPC dialogue labels into another locale's text table.

The client renders from `Localization/en_us`, so the Chinese labels and their
`#<function>-<page>-<subId>` markers that live in `Localization/zh_cn` have to be
present in the locale that is actually loaded for them to appear.

Only keys whose zh_cn value carries a probe marker are copied - i.e. exactly the NPC
dialogue button labels this tool was built for - so nothing else in the target locale
changes. The target file's own encoding (BOM or not) and line endings are preserved,
a sha256-named backup is taken before the first write, and the run is a dry run unless
-Apply is given.

    python tools/PatchClientNpcDialogueChineseLocale.py            # dry run
    python tools/PatchClientNpcDialogueChineseLocale.py -Apply     # write
    python tools/PatchClientNpcDialogueChineseLocale.py -Apply -Locale zh_cn
"""

import argparse
import hashlib
import os
import re
import shutil
import sys

CLIENT = r"D:\Godswar Origin"
SOURCE_LOCALE = "zh_cn"
BACKUP_DIR = os.path.join(CLIENT, "backups")

MARKER = re.compile(r"#\d+-\d+-\d+")
ASSIGN = re.compile(r'^(\s*(?:LuaText\.)?)([A-Za-z_]\w*)(\s*=\s*)"((?:[^"\\]|\\.)*)"(\s*)$')


def read(path):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    text = body.decode("utf-8")
    newline = "\r\n" if b"\r\n" in body else "\n"
    return text.split(newline), newline, bom


def path_for(locale):
    return os.path.join(CLIENT, "Localization", locale, "UI", "Base", "LuaText.lua")


def index(lines):
    """key -> (line number, prefix, suffix) for the first assignment of each key."""
    found = {}
    for number, line in enumerate(lines):
        match = ASSIGN.match(line)
        if match and match.group(2) not in found:
            found[match.group(2)] = number
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-Locale", default="en_us", help="locale to receive the Chinese labels")
    parser.add_argument("-Apply", action="store_true")
    args = parser.parse_args()

    target_path = path_for(args.Locale)
    if not os.path.exists(target_path):
        raise SystemExit(f"no such locale text table: {target_path}")

    source_lines, _, _ = read(path_for(SOURCE_LOCALE))
    target_lines, newline, bom = read(target_path)
    target_index = index(target_lines)

    wanted = {}
    for line in source_lines:
        match = ASSIGN.match(line)
        if not match:
            continue
        key, value = match.group(2), match.group(4)
        if MARKER.search(value):
            bare = MARKER.sub("", value)
            if not re.search(r"[\u4e00-\u9fff]", bare):
                continue  # nothing Chinese to copy
            wanted[key] = value

    appended = []
    changed = 0
    out = list(target_lines)
    for key, value in sorted(wanted.items()):
        if key not in target_index:
            appended.append((key, value))
            continue
        number = target_index[key]
        match = ASSIGN.match(out[number])
        if match.group(4) == value:
            continue
        out[number] = f'{match.group(1)}{key}{match.group(3)}"{value}"{match.group(5)}'
        changed += 1

    already = len(wanted) - changed - len(appended)
    print(f"locale        : {args.Locale}")
    print(f"Chinese keys  : {len(wanted)}")
    print(f"to write      : {changed}")
    print(f"already equal : {already}")
    print(f"not in target : {len(appended)}  "
          f"({', '.join(k for k, _ in appended[:6])}{' …' if len(appended) > 6 else ''})")

    if not args.Apply:
        print("\ndry run; pass -Apply to write")
        return 0
    if not changed and not appended:
        print("\nnothing to change; the file was left alone")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    digest = hashlib.sha256(open(target_path, "rb").read()).hexdigest()
    backup = os.path.join(BACKUP_DIR, f"{digest}-LuaText.{args.Locale}.lua.before")
    if not os.path.exists(backup):
        shutil.copy2(target_path, backup)
        print(f"\nbackup        : {backup}")

    again, _, _ = read(target_path)
    if again != target_lines:
        raise SystemExit("the target changed after preparation; nothing was written")

    if appended:
        out.append("")
        out.append("-- NPC dialogue probe labels localised for this locale")
        out.extend(f'{key} = "{value}"' for key, value in appended)

    payload = newline.join(out).encode("utf-8")
    with open(target_path, "wb") as handle:
        handle.write((b"\xef\xbb\xbf" if bom else b"") + payload)
    print(f"written       : {target_path}  (+{len(appended)} new keys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
