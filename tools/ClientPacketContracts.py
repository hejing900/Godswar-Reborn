"""Turn each client NPC-function script into a plain-language packet contract.

The client is the only surviving specification of what a reply must contain: it calls
`<Script>_SetText(Type, Index, BtnID, SubID)` once per number the server puts into the
`10070` answer and draws only what a branch exists for. This tool walks every branch,
resolves the text keys it uses against the shipped `zh_cn` `LuaText.lua`, and prints, for
each number a server may send, the literal Chinese the player ends up seeing and whether
that line is a clickable button or a closing result.

Unlike `ClientResponseAlphabet.py`, which reports the legal number sets, this reports the
meaning of each number, which is what a server author needs to answer a click.

Output: `artifacts/npc-dialogue-probe-tags/packet-contracts.md` (generated, kept out of
`docs/` because it is one section per client script and far above the 20 KB file limit);
the short entry page is `docs/NPC对话封包格式与应答读法-20260922.md`.
"""

import json
import os
import re

NPC_DIR = r"D:\Godswar Origin\Localization\zh_cn\UI\XML\NpcFun"
TEXT = r"D:\Godswar Origin\Localization\zh_cn\UI\Base\LuaText.lua"
OUT_MD = r"D:\Godswar-Reborn-main\artifacts\npc-dialogue-probe-tags\packet-contracts.md"
OUT_JSON = r"D:\Godswar-Reborn-main\artifacts\npc-dialogue-probe-tags\packet-contracts.json"

COLOR = re.compile(r"\|c[0-9a-fA-F]{6,8}")
INDEX_TEST = re.compile(r"Index\s*==\s*(\d+)")
SUBID_EQ = re.compile(r"SubID\s*==\s*(\d+)")
SUBID_MOD = re.compile(r"math\.mod\(\s*SubID\s*,\s*(\d+)\s*\)\s*==\s*(\d+)")
SUBID_MOD_INLINE = re.compile(r"SubID\s*%\s*(\d+)\s*==\s*(\d+)")
POSITION = re.compile(r"SetPosition\(\s*(\d+)\s*,\s*(\d+)\s*\)")
SETTEXT_PLAIN = re.compile(r"SetText\(\s*(?:LuaText\.)?([A-Za-z_]\w*)\s*\)")
SETTEXT_CONCAT = re.compile(
    r"SetText\(\s*([A-Za-z_]\w*)\s*\.\.(.*?)\.\.\s*([A-Za-z_]\w*)\s*\)")


def read_text(path):
    return open(path, encoding="utf-8-sig", errors="replace").read()


def labels():
    table = {}
    for line in read_text(TEXT).splitlines():
        match = re.match(r'\s*(?:LuaText\.)?([A-Za-z_]\w*)\s*=\s*"((?:[^"\\]|\\.)*)"', line)
        if match and match.group(1) not in table:
            table[match.group(1)] = COLOR.sub("", match.group(2)).strip()
    return table


def flags_by_script():
    lines = read_text(os.path.join(NPC_DIR, "NpcFun.lua")).splitlines()
    values = {}
    dispatch = {}
    for line in lines:
        match = re.match(r"\s*(NPC_FLAG[A-Za-z_0-9]*)\s*=\s*(\d+)", line)
        if match:
            values[match.group(1)] = int(match.group(2))
    for index, line in enumerate(lines):
        match = re.search(r"Type == (NPC_FLAG[A-Za-z_0-9]+)", line)
        if not match or match.group(1) not in values:
            continue
        follower = re.search(r"(\w+?)_SetText\(", "\n".join(lines[index + 1:index + 6]))
        if follower:
            dispatch.setdefault(follower.group(1), []).append(
                (values[match.group(1)], match.group(1)))
    return dispatch


def branch_key(index, sub):
    if sub is None:
        return f"index{index}-any"
    if isinstance(sub, tuple):
        return "mod{}=={}".format(*sub)
    return str(sub)


def analyse(script, text):
    body = read_text(os.path.join(NPC_DIR, script + ".lua"))
    start = body.find("_SetText(")
    if start < 0:
        return {}
    branches = {}
    index = None
    sub = None
    for line in body[start:].splitlines()[1:]:
        found_index = INDEX_TEST.search(line)
        if found_index:
            index = int(found_index.group(1))
        found_sub = SUBID_EQ.search(line)
        found_mod = SUBID_MOD.search(line) or SUBID_MOD_INLINE.search(line)
        if found_sub:
            sub = int(found_sub.group(1))
        elif found_mod:
            sub = (int(found_mod.group(1)), int(found_mod.group(2)))
        elif re.search(r"\belseif\b|\belse\b", line):
            sub = None
        if not re.search(r"SetText\(|SetPosition|EndMessage", line):
            continue
        entry = branches.setdefault(
            branch_key(index, sub),
            {"index": index, "sub": None if isinstance(sub, tuple) else sub,
             "mod": list(sub) if isinstance(sub, tuple) else None,
             "lines": [], "slots": [], "closes": False})
        position = POSITION.search(line)
        where = f"{position.group(1)},{position.group(2)}" if position else ""
        if position:
            entry["slots"].append(where)
        if "EndMessage(true)" in line:
            entry["closes"] = True
            continue
        concat = SETTEXT_CONCAT.search(line)
        if concat:
            head = text.get(concat.group(1), concat.group(1) + " ?")
            tail = text.get(concat.group(3), concat.group(3) + " ?")
            entry["lines"].append({
                "kind": "button" if "Button" in line else "text",
                "slot": where,
                "text": f"{head}【号里有数值：{concat.group(2).strip()}】{tail}",
                "formula": f"{concat.group(1)}..({concat.group(2)})..{concat.group(3)}",
            })
            continue
        plain = SETTEXT_PLAIN.search(line)
        if plain:
            name = plain.group(1)
            entry["lines"].append({
                "kind": "button" if "Button" in line else "text",
                "slot": where,
                "text": text.get(name, f"{name}（客户端里没有这条文本，画不出来）"),
                "key": name,
            })
    return branches


def render(md, script, info, text):
    flags = info["flags"]
    numbers = ", ".join(str(v) for v, _ in flags) or "（分发表里没有入口，点了不会被打开）"
    names = " / ".join(n for _, n in flags) or "-"
    md.write(f"\n## {script}.lua — 功能号 {numbers}\n\n")
    md.write(f"客户端脚本分支名：`{names}`\n\n")
    md.write("| 服务端发的号 | 客户端画出什么 | 位置 | 玩家点它时客户端回什么 | 发完这号窗口是否关闭 |\n")
    md.write("|---|---|---|---|---|\n")
    for key in sorted(info["branches"], key=lambda k: (0, int(k)) if k.isdigit()
                      else (1, k.find("mod") < 0, k)):
        entry = info["branches"][key]
        if entry["sub"] is not None:
            sent = f"`{entry['sub']}`"
            back = "把同一个号放回 `10069`" if any(
                l["kind"] == "button" for l in entry["lines"]) else "（纯文字，点不到）"
        elif entry["mod"]:
            modulus, remainder = entry["mod"]
            sent = f"除以 {modulus} 余 {remainder} 的号（{remainder}, {remainder + modulus}, {remainder + 2 * modulus}…）"
            back = ("把玩家点中的那个号放回 `10069`" if any(
                l["kind"] == "button" for l in entry["lines"]) else "（纯文字，点不到）")
        else:
            sent = f"这一层任意号（脚本没写 `SubID` 判断，第 {entry['index']} 层）"
            back = "-"
        body = "<br>".join(
            ("**按钮** " if l["kind"] == "button" else "") + l["text"]
            for l in entry["lines"]) or "（这个号什么都不画）"
        md.write(f"| {sent} | {body} | "
                 f"{' / '.join(entry['slots']) or '-'} | "
                 f"{back} | {'是' if entry['closes'] else '否'} |\n")


def main():
    text = labels()
    dispatch = flags_by_script()
    report = {}
    for file in sorted(os.listdir(NPC_DIR)):
        if not file.endswith(".lua") or file == "NpcFun.lua":
            continue
        script = file[:-4]
        branches = analyse(script, text)
        if branches:
            report[script] = {"flags": dispatch.get(script, []), "branches": branches}

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1, sort_keys=True)

    with open(OUT_MD, "w", encoding="utf-8") as md:
        md.write("# NPC 功能封包应答对照表（由客户端脚本逐分支读出）\n\n")
        md.write("""## 一、只有三个包

| 方向 | Opcode | 字节 | 字段 |
|---|---|---:|---|
| 服务器→客户端 | `10067` | 48 | `+4` NPC 实体 ID；`+8` 功能标记位；`+12` 千进制打包的功能号列表（最低位先）；`+16` 脚本名 ASCII |
| 客户端→服务器 | `10069` | 92 | `+4` NPC 实体 ID；`+8` 功能号；`+16` 功能号；`+20` 玩家点中的那个号；`+24` 之后是附加参数 |
| 服务器→客户端 | `10070` | 12+4N | `+4` NPC 实体 ID；`+8` 页号（整段对话里保持不变）；`+12` 起 N 个号，客户端每个号画一行 |

机制：客户端拿到 `10070` 后，对里面的**每一个号**调用一次
`<脚本>_SetText(功能号, 页号, 按钮槽位, 这个号)`，脚本里写了对应分支才画得出来。
所以本表的「服务端发的号」就是该功能的全部合法应答；写表外的号，客户端静默不画。

方括号【号里有数值：…】是客户端拿这个号做的算式，意思是**这个号本身携带一个数值**。
例如「除以 10 余 8」这一族，客户端显示「运气不好，你选择错误。你今天还能许愿 N 次」，
其中 N =（号 − 8）÷ 10；还剩 3 次就发 `38`，还剩 1 次就发 `18`。

「玩家点它时客户端回什么」：按钮被点时，客户端把**画出的这个按钮所对应的那个号**原样放进
`+20` 发回来。按钮标签里的 `#功能号-页号-号` 是我们 2026-09-21 打的探针（见
`docs/NPC对话链路技术文本-城内功能补录-20260921.md`），不是客户端原文，作用是让每次点击在
服务端日志里可辨认。同一段文案可能被好几个号画到（例如「领取奖励」既由 `1000` 画，也由
「除以 100 余 5」这一族画），探针号只能记其中一个，以本表左列为准。

本表只说明「发某个号 → 客户端显示什么」。某个点击**应该**换回哪几个号是服务端的玩法决定，
客户端里不存在这个信息；已经抓包验证过的对局记录在技术文档正文里。

""")
        for script in sorted(report, key=lambda s: (min([f[0] for f in report[s]["flags"]], default=9999), s)):
            render(md, script, report[script], text)
    print(f"scripts: {len(report)}")
    print(f"markdown: {OUT_MD}")


if __name__ == "__main__":
    main()
