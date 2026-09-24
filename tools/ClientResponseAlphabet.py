"""Derive, from the client alone, what each NPC function module may be sent back.

The client calls `<Script>_SetText(Type, Index, BtnID, SubID)` once per number the server
places in a `10070` reply, and draws only what a branch exists for. The set of branches is
therefore the legal answer alphabet for that module, and the arithmetic a branch performs on
`SubID` is the encoding the server must use when it has a number to convey.

For every client script this writes a spec table: function flag, per-Index numbers, which are
buttons versus results, any `EndMessage`, any computed family such as
`SubID % 10 == 6 -> text = L017 + (SubID - 6) / 10 + L018`, and every label key it uses
together with whether the shipped client can actually render it.

Numbers are read literally from the script. Nothing here infers which number a click leads to:
that pairing is not in the client and needs a capture, so the table reports the alphabet and
leaves the ordering to measurement.
"""

import json
import os
import re

NPC_DIR = r"D:\Godswar Origin\Localization\zh_cn\UI\XML\NpcFun"
TEXT = r"D:\Godswar Origin\Localization\zh_cn\UI\Base\LuaText.lua"
OUT = r"D:\Godswar-Reborn-main\artifacts\npc-dialogue-probe-tags\response-alphabet.md"
JSON_OUT = r"D:\Godswar-Reborn-main\artifacts\npc-dialogue-probe-tags\response-alphabet.json"

CJK = re.compile(r"[一-鿿]")
FUNC = re.compile(r"^(\w+?)_SetText\(")
INDEX_TEST = re.compile(r"Index\s*==\s*(\d+)")
SUBID_EQ = re.compile(r"SubID\s*==\s*(\d+)")
SUBID_MOD = re.compile(r"SubID\s*%\s*(\d+)\s*(?:==|>=|<=|>|<)\s*(\d+)")
SUBID_RANGE = re.compile(r"SubID\s*(>=|<=)\s*(\d+)")
KEY = re.compile(r"SetText\(\s*((?:LuaText\.)?[A-Za-z_]\w*)")
CONCAT = re.compile(r"SetText\(\s*([A-Za-z_]\w*)\s*\.\.\s*\(([^)]*)\)(.*?)\)")


def read(path):
    return open(path, encoding="utf-8-sig", errors="replace").read()


def labels():
    table = {}
    for line in read(TEXT).splitlines():
        match = re.match(r'\s*(?:LuaText\.)?([A-Za-z_]\w*)\s*=\s*"((?:[^"\\]|\\.)*)"', line)
        if match and match.group(1) not in table:
            table[match.group(1)] = match.group(2)
    return table


def flags_by_script():
    lines = read(os.path.join(NPC_DIR, "NpcFun.lua")).splitlines()
    values, dispatch = {}, {}
    for line in lines:
        match = re.match(r"\s*(NPC_FLAG[A-Za-z_0-9]*)\s*=\s*(\d+)", line)
        if match:
            values[match.group(1)] = int(match.group(2))
    for index, line in enumerate(lines):
        match = re.search(r"Type == (NPC_FLAG[A-Za-z_0-9]+)", line)
        if not match:
            continue
        follower = re.search(r"(\w+?)_SetText\(", "\n".join(lines[index + 1:index + 6]))
        if follower and match.group(1) in values:
            dispatch.setdefault(follower.group(1), []).append(
                (values[match.group(1)], match.group(1)))
    return dispatch


def analyse(script, text):
    """Collect the branch structure of one script's SetText function."""
    body = read(os.path.join(NPC_DIR, script + ".lua"))
    start = body.find("_SetText(")
    if start < 0:
        return {}
    index = None
    sub = None
    branches = {}
    # Skip the signature line itself; its `SetText(Type, Index, ...)` is
    # not a branch.
    for line in body[start:].splitlines()[1:]:
        found_index = INDEX_TEST.search(line)
        if found_index:
            index = int(found_index.group(1))
        found_sub = SUBID_EQ.search(line)
        found_mod = SUBID_MOD.search(line)
        found_range = SUBID_RANGE.search(line)
        if found_sub:
            sub = int(found_sub.group(1))
            key = f"exact:{sub}"
        elif found_mod:
            sub = None
            key = f"mod{found_mod.group(1)}=={found_mod.group(2)}"
        elif found_range:
            sub = None
            key = f"range{found_range.group(1)}{found_range.group(2)}"
        else:
            key = None
        label = KEY.search(line)
        entry = branches.setdefault(key or f"index{index}-shared",
                                    {"index": index, "numbers": set(), "buttons": set(),
                                     "results": set(), "computed": set(), "keys": set()})
        if key and not key.startswith(("mod", "range")):
            entry["numbers"].add(int(key.split(":")[1]))
            if sub is not None:
                entry["index"] = entry["index"] or index
        if label:
            name = label.group(1).split(".")[-1]
            entry["keys"].add(name)
            value = text.get(name)
            drawable = bool(value) and bool(CJK.search(value))
            if "Button" in line:
                entry["buttons"].add(str(sub) if sub is not None else str(key))
            elif "EndMessage" not in line:
                pass
            if not drawable:
                entry["keys"].discard(name)
                entry.setdefault("undrawable", set()).add(
                name if value is None else f"{name} (no Chinese)")
        if "EndMessage(true)" in line and sub is not None:
            entry["results"].add(sub)
        concat = CONCAT.search(line)
        if concat:
            entry["computed"].add(f"{concat.group(1)}..({concat.group(2)}){concat.group(3)}")
    for entry in branches.values():
        entry["numbers"] = sorted(entry["numbers"])
        for field in ("buttons", "results", "computed", "keys", "undrawable"):
            entry[field] = sorted(entry.get(field, ()), key=str)
    return branches


def main():
    text = labels()
    dispatch = flags_by_script()
    report = {}
    for file in sorted(os.listdir(NPC_DIR)):
        if not file.endswith(".lua") or file == "NpcFun.lua":
            continue
        script = file[:-4]
        branches = analyse(script, text)
        if not branches:
            continue
        report[script] = {
            "flags": dispatch.get(script, []),
            "branches": branches,
        }

    with open(JSON_OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1, sort_keys=True, default=list)

    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write("# 各功能模块的可回包取值域（由客户端脚本反推）\n\n")
        handle.write("机制：客户端对服务端 `10070` 里的**每一个号**调用一次 "
                     "`<脚本>_SetText(Type, Index, BtnID, SubID)`，只画有分支的号。"
                     "所以脚本分支集合 = 服务端合法回复域；分支里对 `SubID` 做的算式 = "
                     "服务端必须使用的数值编码。**本表不含「点 X 该回 Y」的顺序关系**——"
                     "客户端里没有这个信息，只能靠抓包。\n\n")
        for script in sorted(report):
            info = report[script]
            flags = ", ".join(f"{value} ({name})" for value, name in info["flags"]) or "无分发表入口"
            handle.write(f"## {script}.lua  —  功能号 {flags}\n\n")
            handle.write("| Index | 可回号 | 按钮 | 结果(EndMessage) | 合成算式 | 无中文可画的键 |\n")
            handle.write("|---:|---|---|---|---|---|\n")
            for key in sorted(info["branches"], key=lambda k: str(k)):
                entry = info["branches"][key]
                handle.write("| {} | {} | {} | {} | {} | {} |\n".format(
                    entry["index"],
                    ", ".join(str(n) for n in entry["numbers"][:24])
                    + ("…" if len(entry["numbers"]) > 24 else "") or key,
                    ", ".join(str(b) for b in entry["buttons"][:12]) or "-",
                    ", ".join(str(r) for r in entry["results"][:12]) or "-",
                    "; ".join(entry["computed"][:4]) or "-",
                    "; ".join(entry["undrawable"][:6]) or "-"))
            handle.write("\n")
    print(f"scripts analysed : {len(report)}")
    print(f"markdown         : {OUT}")
    print(f"machine-readable : {JSON_OUT}")


if __name__ == "__main__":
    main()
