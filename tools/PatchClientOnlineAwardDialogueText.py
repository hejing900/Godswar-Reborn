"""Define the online-award dialogue texts the shipped client references but never had.

`UI/XML/NpcFun/NpcFunStayReward.lua` draws its four result rows and its online-hours
row from `StayReward3`..`StayReward7`. None of those keys exist in either shipped
`UI/Base/LuaText.lua`, so `FirstWin_Text1:SetText(StayReward4)` sets nil: the client
draws nothing and the shared `FirstWin` panel keeps whatever the previously clicked
NPC left on it. The server side of the feature is unaffected.

Each value carries a `#49-1-<sub-id>` probe tag before its trailing colour reset,
which is the convention used by the other dialogue labels on this client.
"""

import re
import sys

FILES = {
    "zh_cn": r"D:\Godswar Origin\Localization\zh_cn\UI\Base\LuaText.lua",
    "en_us": r"D:\Godswar Origin\Localization\en_us\UI\Base\LuaText.lua",
}

# The `%d` in StayReward3 is required: the client fills it with
# `string.format(StayReward3, hour)`.
TEXTS = [
    ("StayReward3", "|cffFFFF00你已经累计在线 %d 小时，可以领取在线奖励了#49-1-hours|cffffffff"),
    ("StayReward4", "|cffFFFF00恭喜，你领取到了在线奖励#49-1-102|cffffffff"),
    ("StayReward5", "|cffFFFF00这个阶段的在线奖励你已经领取过了#49-1-103|cffffffff"),
    ("StayReward6", "|cffFFFF00背包已满，请先清出空格再来领取#49-1-104|cffffffff"),
    ("StayReward7", "|cffFFFF00当前没有可以领取的在线奖励#49-1-105|cffffffff"),
]


def read(path):
    """Return the file split into lines, plus the byte-level facts to restore."""
    raw = open(path, "rb").read()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in body else "\n"
    return had_bom, newline, body.split(newline)


def defined(lines, key):
    pattern = re.compile(r"^\s*(?:LuaText\.)?" + re.escape(key) + r"\s*=")
    return any(pattern.match(line) for line in lines)


def patch(loc, path, apply):
    had_bom, newline, lines = read(path)
    missing = [key for key, _ in TEXTS if not defined(lines, key)]
    if apply and missing:
        values = dict(TEXTS)
        while lines and not lines[-1].strip():
            lines.pop()
        lines.extend(f"{key} = \"{values[key]}\"" for key in missing)
        lines.append("")
        body = newline.join(lines)
        open(path, "wb").write(
            (b"\xef\xbb\xbf" if had_bom else b"") + body.encode("utf-8"))
    verb = "adding" if apply else "would add"
    print(f"{loc}: {len(missing)} missing ({verb}): {', '.join(missing) or '-'}")
    return missing


def main():
    apply = "--apply" in sys.argv
    targets = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or list(FILES)
    for loc in targets:
        if loc not in FILES:
            raise SystemExit(f"unknown locale {loc!r}; expected one of {list(FILES)}")
        patch(loc, FILES[loc], apply)
    if not apply:
        print("dry run only: pass --apply to write")


if __name__ == "__main__":
    main()
