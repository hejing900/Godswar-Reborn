"""Tag NPC dialogue button labels with a self-describing probe marker.

The dialogue chains in docs/NPC对话链路技术文本.md know every number a client script
can draw, but not which number the server answers a click with, and that can only come
from a measurement. This script makes the client say it: every button label used by the
scripted dialogues gains a trailing `#<function>-<subId>` marker, so a screenshot or a
read-aloud identifies the exact number that was clicked, and the page the server answered
with is read back off the same markers on the buttons it drew.

Markers are appended after the whole value, so a trailing colour reset such as
`|cFFFFFFFF` stays intact and the marker renders in the window's default colour.

Dry run by default; pass -Apply to write. A sha256-named backup is taken before the
first write, matching tools/PatchClientAtlantisLevel90Plus.ps1.
"""

import argparse
import collections
import hashlib
import os
import re
import shutil
import sys

CLIENT = r"D:\Godswar Origin"
NPC_DIR = os.path.join(CLIENT, "Localization", "zh_cn", "UI", "XML", "NpcFun")
ZH_TEXT = os.path.join(CLIENT, "Localization", "zh_cn", "UI", "Base", "LuaText.lua")
EN_TEXT = os.path.join(CLIENT, "Localization", "en_us", "UI", "Base", "LuaText.lua")
BACKUP_DIR = os.path.join(CLIENT, "backups")
MAPPING_OUT = r"D:\Godswar-Reborn-main\artifacts\npc-dialogue-probe-tags\mapping.md"

# Every client script that draws buttons is covered, not a hand-picked subset: the
# markers exist so a player can read back what the client was told to draw, and that
# is useful for the older dialogs (wish pool, gear mentor, Zeus, guild pages) just as
# much as for the ones added recently. `NpcFun.lua`'s dispatch decides which script
# answers which function number, so a script it never reaches is skipped.
SCRIPTS = None  # None means: derive from NpcFun.lua's dispatch table.

# A few scripts build the key from the number itself, e.g.
# Button:SetText(LuaText["NF_HF_B" .. SubID]) inside a range test rather than an
# equality test, so the SubID is not visible on that line. Those families are listed
# with the exact numbers the script can reach.
COMPUTED_FAMILIES = {
    "NpcFunHorseFeeder": [("NF_HF_B", range(100, 107))],
    "NpcFunNewYear": [("NF_NY_B", range(100, 106))],
}

# A handful of label keys are missing from the zh_cn text table while the script still
# asks for them, so the client draws an empty button. They are translated here; the
# sidecar keeps the bulk list out of the code. Keys absent from both languages (for
# example NF_L0_GIFTX) are left alone: there is nothing to translate.
TRANSLATIONS = {
    "NF_HF_B106": "|cffFFFF00▽绑定坐骑装备|cFFFFFFFF",
    "NF_HF_T206": ("|cffF14187绑定坐骑装备：请放入未绑定的普通坐骑装备，"
                   "我来为它绑定。|cFFFFFFFF"),
    "NF_L0_QT101": "|cffFFFF00▽领取任务袋|cFFFFFFFF",
}

TRANSLATIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "npc-dialogue-probe-translations.json")
if os.path.exists(TRANSLATIONS_FILE):
    import json
    with open(TRANSLATIONS_FILE, encoding="utf-8") as handle:
        TRANSLATIONS.update(json.load(handle))

# Keys the button scan cannot reach because they are not drawn by `Button:SetText`,
# yet are still needed for a dialogue to render at all. Given as key -> (function,
# page, subId) so they get the same marker shape.
EXTRA_KEYS = {
    "NF_HF_T206": (21, 2, 206),   # the 106 form heading, drawn via FirstWin_Text1
}

MARKER = re.compile(r"#(\d+)-(\d+)-(\d+)")
# A label is authored as `|cffRRGGBB` + text + a trailing `|cffffffff` reset. The
# marker therefore goes BEFORE that trailing colour code: appended after it the
# marker would fall outside the button's own colour and would break the "ends with
# a reset" shape the client's own strings all use.
TRAILING_COLOR = re.compile(r"(\|c[0-9a-fA-F]{6,8})\Z")


def with_marker(value, marker):
    """Place `marker` inside the label's colour span, before any trailing reset."""
    value = MARKER.sub("", value)
    tail = TRAILING_COLOR.search(value)
    if tail:
        return value[:tail.start()] + marker + tail.group(1)
    return value + marker

CJK = re.compile(r"[\u4e00-\u9fff]")
ASSIGN = re.compile(r'^(\s*(?:LuaText\.)?([A-Za-z_]\w*)\s*=\s*)"((?:[^"\\]|\\.)*)"\s*;?\s*(.*)$')


def read_text_lines(path):
    """Return (encoding, newline, lines, had_bom) or None when undecodable.

    The zh_cn text table is UTF-8 with a BOM and CRLF; the en_us copy is UTF-8 with
    bare LF, so both endings are accepted and the one actually found is returned so a
    rewrite can preserve it.
    """
    with open(path, "rb") as handle:
        raw = handle.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    newline = "\r\n" if b"\r\n" in body else "\n"
    return "utf-8", newline, text.split(newline), bom


def flag_by_script():
    """Map each script to (constant name, number) from NpcFun.lua's own dispatch."""
    lines = read_text_lines(os.path.join(NPC_DIR, "NpcFun.lua"))
    if lines is None:
        raise SystemExit("NpcFun.lua is not UTF-8/CRLF as expected; refusing to continue")
    _, _, body, _ = lines
    constant_value = {}
    for line in body:
        match = re.match(r"\s*(NPC_FLAG[A-Za-z_0-9]*)\s*=\s*(\d+)", line)
        if match:
            constant_value[match.group(1)] = int(match.group(2))
    dispatch = {}
    for index, line in enumerate(body):
        match = re.search(r"Type == (NPC_FLAG[A-Za-z_0-9]+)", line)
        if not match:
            continue
        follower = re.search(r"(\w+?)_SetText\(", "\n".join(body[index + 1:index + 5]))
        number = constant_value.get(match.group(1))
        if follower and number is not None:
            dispatch.setdefault(follower.group(1), (match.group(1), number))
    return dispatch


def button_labels(script):
    """Every (key, subId) a script draws as a button label."""
    path = os.path.join(NPC_DIR, script + ".lua")
    if not os.path.exists(path):
        # NpcFun.lua's dispatch name is not always the file name (NpcLevelSeal is
        # drawn by NpcFunLevelSealer.lua), so a missing file is a note, not a stop.
        print(f"note: no such client script file: {script}.lua (skipped)",
              file=sys.stderr)
        return []
    source = open(path, encoding="utf-8-sig", errors="replace").read()
    found = []
    page = sub_id = None
    for line in source.splitlines():
        mi = re.search(r"Index\s*==\s*(\d+)", line)
        if mi:
            page = int(mi.group(1))
        match = re.search(r"SubID\s*==\s*(\d+)", line)
        if match:
            sub_id = int(match.group(1))
        label = re.search(r"Button\w*:SetText\((.*)\)\s*;?\s*$", line)
        if not label:
            continue
        argument = label.group(1).strip()
        direct = re.match(r'(?:LuaText\.)?([A-Za-z_]\w*)$', argument)
        if direct and sub_id is not None:
            found.append((direct.group(1), page, sub_id))
            continue
        computed = re.match(r'LuaText\["([^"]+)"\s*\.\.\s*SubID\s*\]$', argument)
        if computed:
            if sub_id is not None:
                found.append((computed.group(1) + str(sub_id), page, sub_id))
            else:
                for prefix, numbers in COMPUTED_FAMILIES.get(script, []):
                    if prefix == computed.group(1):
                        found.extend((prefix + str(n), page, n) for n in numbers)
    return found


def assignments(lines):
    """key -> (line number, value) for every single-line string assignment."""
    table = {}
    for number, line in enumerate(lines):
        match = ASSIGN.match(line)
        if match and match.group(2) not in table:
            table[match.group(2)] = (number, match.group(3))
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-Apply", action="store_true", help="write the file (default: dry run)")
    parser.add_argument("-Force", action="store_true",
                        help="re-tag values that already carry a marker, from scratch")
    parser.add_argument("-ListMissing", action="store_true",
                        help="dump the label keys with no Chinese and their en_us text, then exit")
    args = parser.parse_args()

    original = read_text_lines(ZH_TEXT)
    if original is None:
        raise SystemExit("LuaText.lua is not UTF-8 with CRLF as expected; refusing to touch it")
    encoding, newline, body, had_bom = original
    english = read_text_lines(EN_TEXT)
    en_table = assignments(english[2]) if english else {}
    zh_table = assignments(body)

    dispatch = flag_by_script()
    wanted = collections.defaultdict(set)
    scripts = SCRIPTS if SCRIPTS is not None else sorted(dispatch)
    for script in scripts:
        if script not in dispatch:
            raise SystemExit(f"{script}: no NPC_FLAG dispatch found in NpcFun.lua")
        constant, function = dispatch[script]
        for key, page, sub_id in button_labels(script):
            wanted[key].add((function, page or 0, sub_id, script, constant))
    for key, (function, page, sub_id) in EXTRA_KEYS.items():
        wanted[key].add((function, page, sub_id, "extra", "NPC_FLAG_PROBE_EXTRA"))

    edits = {}
    created = []
    shared = []
    untranslatable = []
    needs_chinese = []
    for key in sorted(wanted):
        uses = sorted(wanted[key])
        numbers = {(function, page, sub_id) for function, page, sub_id, _, _ in uses}
        if len(numbers) > 1:
            # One label shared by several numbers can only carry one marker, so the
            # marker names the lowest number and the pair is reported for the docs.
            shared.append((key, sorted(numbers)))
        function, page, sub_id, script, constant = uses[0]
        marker = f"#{function}-{page}-{sub_id}"
        bare = re.sub(r"^LuaText\.", "", key)
        if bare in zh_table:
            line_number, value = zh_table[bare]
            if not CJK.search(value):
                # Present but not Chinese (an English leftover): replace the text.
                needs_chinese.append(bare)
                if bare not in TRANSLATIONS:
                    untranslatable.append(bare)
                    continue
                edits[bare] = (line_number,
                               with_marker(TRANSLATIONS[bare], marker))
                continue
            if MARKER.search(value) and not args.Force:
                continue
            edits[bare] = (line_number, with_marker(value, marker))
        elif bare in TRANSLATIONS:
            created.append((bare, with_marker(TRANSLATIONS[bare], marker),
                            uses[0]))
        else:
            needs_chinese.append(bare)
            untranslatable.append(bare)

    if args.ListMissing:
        import json
        report = [{"key": bare, "en_us": en_table.get(bare, (0, ""))[1]}
                  for bare in sorted(set(needs_chinese))]
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0

    tagged = 0
    out = list(body)
    for key, (line_number, new_value) in edits.items():
        line = out[line_number]
        match = ASSIGN.match(line)
        if not match:
            raise SystemExit(f"{key}: assignment line {line_number + 1} no longer parses")
        out[line_number] = f'{match.group(1)}"{new_value}"{match.group(4)}'.rstrip()
        tagged += 1
    if created:
        out.append("")
        out.append("-- Probe tags added for the NPC dialogue measurement")
        for key, value, _ in created:
            out.append(f'{key} = "{value}"')

    print(f"scripts      : {len(scripts)}")
    print(f"label keys   : {len(wanted)}")
    print(f"would tag    : {tagged}")
    print(f"would create : {len(created)}  ({', '.join(k for k, _, _ in created) or '-'})")
    print(f"shared label : {len(shared)}  ({', '.join(k for k, _ in shared) or '-'})")
    print(f"no text at all: {len(untranslatable)}  ({', '.join(untranslatable) or '-'})")

    if not args.Apply:
        print("\ndry run; pass -Apply to write")
        return 0

    if edits or created:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        digest = hashlib.sha256(open(ZH_TEXT, "rb").read()).hexdigest()
        backup = os.path.join(BACKUP_DIR, f"{digest}-LuaText.lua.before")
        if not os.path.exists(backup):
            shutil.copy2(ZH_TEXT, backup)
            print(f"\nbackup       : {backup}")

        current = read_text_lines(ZH_TEXT)
        if current is None or current[2] != body:
            raise SystemExit("LuaText.lua changed after preparation; nothing was written")
        payload = newline.join(out).encode("utf-8")
        with open(ZH_TEXT, "wb") as handle:
            handle.write((b"\xef\xbb\xbf" if had_bom else b"") + payload)
        print(f"written      : {ZH_TEXT}")
    else:
        # The mapping is derived from the file as it now stands, so it still refreshes.
        print("\nnothing to change; the file was left alone and no backup was taken")

    os.makedirs(os.path.dirname(MAPPING_OUT), exist_ok=True)
    with open(MAPPING_OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# NPC 对话按钮探针标记\n\n")
        handle.write("标记格式 `#功能号-页号-SubID`。功能号取自 `NpcFun.lua` 的 "
                     "`NPC_FLAG_SYS_*`，SubID 是对应脚本 `Button:SetText` 所在分支的号。\n\n")
        handle.write("| 标记 | 功能号常量 | 脚本 | 文本键 | 中文标签 |\n|---|---|---|---|---|\n")
        after = assignments(read_text_lines(ZH_TEXT)[2])
        for key in sorted(wanted):
            function, page, sub_id, script, constant = sorted(wanted[key])[0]
            bare = re.sub(r"^LuaText\.", "", key)
            if bare not in after:
                continue  # never tagged (no text to tag), so it gets no row
            value = after[bare][1]
            marker = MARKER.search(value)
            if not marker:
                continue
            label = re.sub(r"\|cff[0-9a-fA-F]{6}|\|cFFFFFFFF", "", value)
            label = MARKER.sub("", label).strip()
            handle.write(f"| `#{function}-{page}-{sub_id}` | `{constant}` | `{script}` "
                         f"| `{key}` | {label} |\n")
        if shared:
            handle.write("\n## 一个标签被多个号共用\n\n")
            handle.write("一个文本键只能带一个标记，所以下列键的标记只写出较小的号；\n"
                         "看到该标记时两个号都可能被点到，必须结合服务端发出的号来判读。\n\n")
            for key, numbers in shared:
                handle.write(f"- `{key}` → {numbers}\n")
    print(f"mapping      : {MAPPING_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
