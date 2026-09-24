"""Build the packet coverage ledger: what we register, receive, send, and can prove.

Joined by numeric id, because the same packet is named differently per layer and written
in four different styles (`Opcodes.cs` decimal constants, builder `*Opcode` hex constants,
bare header literals, and whole frames kept as captured byte templates).

Inventories:

  declared  `Protocol/Opcodes.cs` : `public const ushort NAME = id`
  handled   `case Opcodes.NAME` / `Opcodes.NAME =>` / `packet.Opcode == Opcodes.NAME`
            plus `opcode == <literal>` comparisons
  sent      builder `const ushort *Opcode`, `Opcodes.NAME` inside `Packets/**`,
            `WriteUInt16LittleEndian(…, 2, 2), <literal>`, and captured frame templates
            whose third and fourth bytes decode to the id
  captured  ids named inside a capture / baseline / frame document under docs/

The client's own receive side is NOT statically available: `SrvMsg.lua` holds toast text
ids (`["1030"] = FD_10030`), not packet ids, and the real handler table lives in
`Origin.exe` as 128 `MSG_*` names whose id mapping needs an unaligned xref scan. That gap
is reported as its own section instead of being guessed at.

States, each with its next action:

  A 有实现且有抓包证据   协议层有据，只剩玩法数值与实机验收
  B 有实现无抓包证据     实机点一次记帧，或补一次抓包
  C 静态看不到收发       需人工判定：废弃 or 漏实现（公会邀请等即属后者）
  D 抓包出现过但未登记   真缺口：按抓包定字段，补登记与实现
  E 有收发但未登记       构造器/分发在用，`Opcodes.cs` 缺条目
"""

import csv
import os
import re
import struct
import sys
from collections import Counter

REPO = r"D:\Godswar-Reborn-main"
SRC = os.path.join(REPO, "src")
OPCODES = os.path.join(SRC, r"Godswar.Server\Protocol\Opcodes.cs")
DOCS = os.path.join(REPO, "docs")
EXE = r"D:\Godswar Origin\Origin.exe"
OUT_DIR = os.path.join(REPO, "artifacts", "protocol-coverage")
OUT_CSV = os.path.join(OUT_DIR, "ledger.csv")
OUT_HANDLERS = os.path.join(OUT_DIR, "client-handler-names.txt")
OUT_MD = os.path.join(DOCS, "未实现封包台账-20260923.md")

DECIMAL = re.compile(r"^(?:0[xX][0-9a-fA-F]+|\d+)$")
DECLARED = re.compile(r"public const ushort (\w+) = (\w+)")
BUILDER_CONST = re.compile(r"const ushort (\w*Opcode\w*) = (\w+)")
HANDLED_NAME = re.compile(
    r"case Opcodes\.(\w+)|Opcodes\.(\w+)\s*(?::|=>)|packet\.Opcode == Opcodes\.(\w+)")
HANDLED_LITERAL = re.compile(r"opcode\s*==\s*(0[xX][0-9a-fA-F]{2,4}|\d{4,5})\b", re.I)
OPCODE_WRITE = re.compile(
    r"WriteUInt16LittleEndian\(\s*[^;]*?,\s*2,\s*2\)\s*,\s*(0[xX][0-9a-fA-F]{2,4}|\d{4,5})\s*\)")
BYTE_TEMPLATE = re.compile(r"byte\[\]\s*\w+\s*=\s*\[([^\]]{8,})\]", re.S)
HEX_TEMPLATE = re.compile(r"Convert\.FromHexString\(\"([0-9a-fA-F]{16,})\"\)")
CAPTURE_FILE = re.compile(
    r"capture|抓包|baseline|frame|packet|wishing-pool|npc-function-dialog", re.I)
ANY_ID = re.compile(r"\b(10\d{3})\b")
MSG_NAME = re.compile(rb"(MSG_[A-Z_0-9]{3,32})\x00")

NEXT_ACTION = {
    "A 有实现且有抓包证据": "协议层完成，转玩法数值与实机验收",
    "B 有实现无抓包证据": "实机点一次记帧，或补一次抓包",
    "C 静态看不到收发": "人工判定：废弃 or 漏实现，结论写进文档",
    "D 抓包出现过但未登记": "按抓包定字段，补登记与实现",
    "E 有收发但未登记": "补进 `Opcodes.cs` 或改回已登记常量",
}
STATE_ORDER = list(NEXT_ACTION)


def number(token):
    return int(token, 0) if DECIMAL.match(token) else None


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def csharp_files():
    for root, _, files in os.walk(SRC):
        if set(root.split(os.sep)) & {"bin", "obj"}:
            continue
        for name in files:
            if name.endswith(".cs"):
                yield os.path.join(root, name)


def template_ids(literal, is_hex):
    """Decode the opcode bytes (3rd and 4th) of a captured frame template."""
    if is_hex:
        body = bytes.fromhex(literal)
    else:
        parts = [part for part in re.sub(r"[^0-9a-fA-F,]", "", literal).split(",") if part]
        if len(parts) < 4:
            return None
        try:
            body = bytes(int(part, 16) for part in parts[:4])
        except ValueError:
            return None
    return None if len(body) < 4 else body[2] | (body[3] << 8)


def collect():
    declared = {}
    for name, token in DECLARED.findall(read(OPCODES)):
        value = number(token)
        if value is not None:
            declared[name] = value

    handled, sent = {}, {}
    for path in csharp_files():
        if os.path.abspath(path) == os.path.abspath(OPCODES):
            continue
        text = read(path)
        relative = os.path.relpath(path, SRC).replace("\\", "/")
        in_builders = "/Packets/" in f"/{relative}"

        for groups in HANDLED_NAME.findall(text):
            name = next((part for part in groups if part), None)
            if name in declared:
                handled.setdefault(declared[name], f"{relative}:{name}")
        for pattern, bucket in ((HANDLED_LITERAL, handled), (OPCODE_WRITE, sent)):
            for token in pattern.findall(text):
                value = number(token)
                if value is not None:
                    bucket.setdefault(value, f"{relative}:literal")
        for name, token in BUILDER_CONST.findall(text):
            value = number(token)
            if value is not None and in_builders:
                sent.setdefault(value, f"{relative}:{name}")
        if in_builders:
            for name in re.findall(r"Opcodes\.(\w+)", text):
                if name in declared:
                    sent.setdefault(declared[name], f"{relative}:Opcodes.{name}")
        for literal, is_hex in ((m.group(1), False) for m in BYTE_TEMPLATE.finditer(text)):
            value = template_ids(literal, is_hex)
            if value in set(declared.values()):
                sent.setdefault(value, f"{relative}:captured template")
        for literal in (m.group(1) for m in HEX_TEMPLATE.finditer(text)):
            value = template_ids(literal, True)
            if value in set(declared.values()):
                sent.setdefault(value, f"{relative}:captured template")

    capture, capture_files = Counter(), 0
    for root, _, files in os.walk(DOCS):
        for name in files:
            if name.endswith(".md") and CAPTURE_FILE.search(name):
                capture_files += 1
                for value in ANY_ID.findall(read(os.path.join(root, name))):
                    capture[int(value)] += 1
    return declared, handled, sent, capture, capture_files


def client_handlers():
    """The binary's receive-handler names; mapping them to ids is the open xref job."""
    if not os.path.exists(EXE):
        return [], set()
    data = open(EXE, "rb").read()
    names = sorted({match.group(1).decode() for match in MSG_NAME.finditer(data)})
    targets = {0x400000 + data.find(name.encode()): name for name in names}
    referenced = set()
    for offset in range(0, len(data) - 4, 4):
        hit = targets.get(struct.unpack_from("<I", data, offset)[0])
        if hit:
            referenced.add(hit)
    return names, referenced


def state_of(value, by_id, handled, sent, capture):
    implemented = value in handled or value in sent
    if value not in by_id:
        return "E 有收发但未登记" if implemented else "D 抓包出现过但未登记"
    if not implemented:
        return "C 静态看不到收发"
    return ("A 有实现且有抓包证据" if capture.get(value, 0)
            else "B 有实现无抓包证据")


def main():
    declared, handled, sent, capture, capture_files = collect()
    by_id = {value: name for name, value in declared.items()}
    universe = set(by_id) | set(handled) | set(sent) | {
        value for value, hits in capture.items() if hits >= 2}

    rows = [{
        "id": value,
        "declared_name": by_id.get(value, ""),
        "received": handled.get(value, ""),
        "sent_from": sent.get(value, ""),
        "capture_mentions": capture.get(value, 0),
        "state": state_of(value, by_id, handled, sent, capture),
    } for value in sorted(universe)]
    for row in rows:
        row["next_action"] = NEXT_ACTION[row["state"]]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["state"] for row in rows)
    names, referenced = client_handlers()
    if names:
        with open(OUT_HANDLERS, "w", encoding="utf-8") as handle:
            handle.write("\n".join(names) + "\n")

    with open(OUT_MD, "w", encoding="utf-8") as md:
        md.write("# 未实现封包台账（2026-09-23）\n\n")
        md.write("全静态取数，按**数字**对号；同一个包在四层里有四种写法（十进制常量、"
                 "十六进制 builder 常量、裸立即数、整帧抓包模板），只认常量名会漏。\n\n")
        md.write("| 清单 | 来源 | 条数 |\n| --- | --- | ---:|\n")
        md.write(f"| 已登记 | `Protocol/Opcodes.cs` 的 `public const ushort` | {len(declared)} |\n")
        md.write(f"| 有接收逻辑 | `case Opcodes.X` / `X =>` / `packet.Opcode ==` / "
                 f"`opcode == <立即数>` | {len(handled)} |\n")
        md.write(f"| 有构造逻辑 | `Packets/**` 的 `*Opcode` 常量、`Opcodes.X` 引用、"
                 f"写进帧头 2-3 字节的立即数、抓包模板字节 | {len(sent)} |\n")
        md.write(f"| 抓包/基线文档提及 | `docs/` 中 {capture_files} 篇文件名含 "
                 f"capture/抓包/baseline/frame/packet 的文档里点过的 `10xxx` | {len(capture)} |\n\n")

        md.write("## 一、总览\n\n| 状态 | 数量 | 下一步 |\n| --- | ---:| --- |\n")
        for state in STATE_ORDER:
            md.write(f"| {state} | {counts.get(state, 0)} | {NEXT_ACTION[state]} |\n")
        md.write(f"\n合计 {len(rows)} 个号被至少一项点名。\n\n")

        for state, title in (
                ("D 抓包出现过但未登记", "二、抓包文档里出现过、服务端却没登记（真缺口）"),
                ("C 静态看不到收发", "三、登记了号但静态看不到收发（逐条人工判定）"),
                ("E 有收发但未登记", "四、在收在发但 `Opcodes.cs` 没登记（登记缺口）")):
            picked = [row for row in rows if row["state"] == state]
            md.write(f"## {title}（{len(picked)} 条）\n\n")
            if not picked:
                md.write("无。\n\n")
                continue
            md.write("| 号 | 登记名 | 收 | 发 | 抓包提及 |\n| ---:| --- | --- | --- | ---:|\n")
            for row in picked[:80]:
                md.write(f"| {row['id']} | {row['declared_name'] or '（无）'} | "
                         f"{row['received'] or '-'} | {row['sent_from'] or '-'} | "
                         f"{row['capture_mentions'] or '-'} |\n")
            if len(picked) > 80:
                md.write(f"\n（其余 {len(picked) - 80} 条见 `artifacts/protocol-coverage/ledger.csv`）\n")
            md.write("\n")

        md.write("## 五、客户端侧「能收哪些包」现在是空白\n\n")
        md.write(f"`Origin.exe` 里聚着 **{len(names)}** 个 `MSG_*` handler 名"
                 f"（清单：`artifacts/protocol-coverage/client-handler-names.txt`），"
                 f"其中 {len(referenced)} 个能被指针式引用扫到；名字↔号的对齐映射还没做完，"
                 "所以本表**不能**判断「某包客户端是否会处理」。补法两条：① 未对齐 xref 扫描"
                 "（静态，能覆盖被间接引用的名字）；② 针对具体功能抓一次包，看客户端收到后有无反应"
                 "（实证）。\n\n")
        md.write("## 六、这张表的边界\n\n")
        md.write("- 状态 C 是「静态四种写法都没看到」，不等于一定没实现：若某包通过反射、"
                 "字典表或运行时拼接发出，静态会漏。逐条判定前不要当结论用。"
                 "已确认的一例：`10086 QuestHandInAck` 在 C 里，但实现走的是"
                 "`CapturedHandInAcks` 查表 + 克隆抓包字节（`PacketBuilder.QuestFrames.cs:376`），"
                 "模板里的 opcode 字节没被本工具解出来，属误报。\n")
        md.write("- 「抓包提及」是号在文档中出现的次数，只证明被讨论过，字段以文档正文帧表为准。\n")
        md.write("- A/B 只描述协议层有无，不代表玩法正确；玩法验收按"
                 "`docs/项目开发工作安排表-20260923.md` §4 的 SOP 走。\n\n")
        md.write("```\npython tools/ProtocolCoverageLedger.py   # 明细 artifacts/protocol-coverage/ledger.csv\n```\n")

    print(f"declared {len(declared)}  received {len(handled)}  sent {len(sent)}  "
          f"capture-named {len(capture)}  rows {len(rows)}")
    for state in STATE_ORDER:
        print(f"  {state:<24} {counts.get(state, 0)}")
    print(f"client handler names {len(names)}, referenced {len(referenced)}")
    print(f"csv {OUT_CSV}\ndoc {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
