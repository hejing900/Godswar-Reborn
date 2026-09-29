"""Turn a captured dialogue number into the client's own label for it.

The client draws an NPC window by calling one `NpcFun<Script>_SetText` function
per number the server sent. This tool resolves which file owns a function flag,
then lists every `SubID` branch it can draw together with the `LuaText` key and
the shipped zh_cn string behind it - so a captured number can be read as the
button the player saw instead of a bare integer.

Usage:
  python tools/describe_client_npc_dialogue.py flag NPC_FLAG_SYS_REPETITION
  python tools/describe_client_npc_dialogue.py file NpcFunTranmit.lua
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UI = r"D:\Godswar Origin\Localization\zh_cn\UI"
NPFUN_DIR = os.path.join(UI, "XML", "NpcFun")
NPFUN = os.path.join(NPFUN_DIR, "NpcFun.lua")
LUA_TEXT = os.path.join(UI, "Base", "LuaText.lua")


def read(path: str) -> list[str]:
    raw = open(path, "rb").read()
    for codec in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(codec).splitlines()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace").splitlines()


def load_lua_text() -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(
        r'^\s*(?:LuaText\["(?P<key1>[^"]+)"\]|(?P<key2>[A-Za-z_]\w*))\s*=\s*'
        r'"(?P<value>[^"]*)"')
    for line in read(LUA_TEXT):
        found = pattern.match(line)
        if found:
            values[found.group("key1") or found.group("key2")] = \
                found.group("value")
    return values


def script_for_flag(flag: str) -> str | None:
    """Map every function flag to the NpcFun script its drawing chain calls."""
    lines = read(NPFUN)
    mapping: dict[str, str] = {}
    current: str | None = None
    for line in lines:
        found = re.search(r"Type\s*==\s*(NPC_FLAG_\w+)", line)
        if found:
            current = found.group(1)
            continue
        found = re.search(r"(NpcFun\w+)_SetText\(", line)
        if found and current is not None:
            mapping.setdefault(current, found.group(1))
    return mapping.get(flag)


def label(expression: str, texts: dict[str, str]) -> str:
    expression = expression.strip().rstrip(";")
    found = re.search(r'LuaText\["([^"]+)"\]', expression)
    if found:
        key = found.group(1)
        return f'{key}="{texts.get(key, "?")}"'
    found = re.match(r"^([A-Za-z_]\w*)$", expression)
    if found:
        key = found.group(1)
        return f'{key}="{texts.get(key, "?")}"' if key in texts else key
    found = re.match(r'^"([^"]*)"', expression)
    if found:
        return f'literal "{found.group(1)}"'
    if expression.startswith("NF_L0_R117"):
        return f'{expression} (family)'
    return expression


def dump(script: str) -> int:
    texts = load_lua_text()
    path = os.path.join(NPFUN_DIR, script + ".lua")
    if not os.path.exists(path):
        print(f"missing {path}")
        return 1
    lines = read(path)
    page = "?"
    current: str | None = None
    body: list[str] = []

    def flush() -> None:
        if current is None:
            return
        text = [label(item, texts) for item in body if item]
        print(f"  page {page}  SubID {current:<6} -> " + "; ".join(text))

    for line in lines:
        found = re.search(r"if\s+Index\s*==\s*(\d+)", line)
        if found:
            flush()
            current, body = None, []
            page = found.group(1)
            continue
        found = re.search(r"(?:if|elseif)\s+SubID\s*==\s*(\d+)", line)
        if found:
            flush()
            current, body = found.group(1), []
            rest = line.split("then", 1)[-1]
            body.extend(re.findall(r"SetText\(([^)]*)\)", rest))
            continue
        found = re.search(r"(?:if|elseif)\s+SubID\s*>=\s*(\d+)", line)
        if found:
            flush()
            current, body = f">={found.group(1)}", []
            continue
        if re.search(r"(?:if|elseif)\s+SubID\s*==", line) is None:
            body.extend(re.findall(r"SetText\(([^)]*)\)", line))
    flush()
    return 0


def main() -> int:
    if sys.argv[1] == "flag":
        script = script_for_flag(sys.argv[2])
        print(f"{sys.argv[2]} -> {script}")
        if script:
            dump(script)
        return 0
    print(f"file {sys.argv[2]}")
    return dump(sys.argv[2].removesuffix(".lua"))


if __name__ == "__main__":
    sys.exit(main())
