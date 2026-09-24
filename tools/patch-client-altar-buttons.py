"""Give the altar's page-three buttons three distinct positions.

The window's coordinates live in the client's own script, so a server cannot
space them out: `NpcFunAltar.lua` pins both the "new building" button (SubID 1)
and the "upgrade building" button (SubID 2) to (25,175), and leaves "delete
building" (SubID 3) without a position at all, so it inherits whatever slot the
window's ladder last gave it. Sent together - which is what the real dialogue
does, they are three separate actions - they draw on top of each other.

This patch keeps SubID 1 where it is and moves 2 and 3 one row up each, so the
page carries three buttons at (25,175), (25,135) and (25,155). Nothing else in
the file is touched: it is patched as bytes, because the file carries GBK
comment bytes that a text round-trip would rewrite.

Usage: python tools/patch-client-altar-buttons.py [--revert]
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

LUA = Path(
    r"D:\Godswar Origin\Localization\zh_cn\UI\XML\NpcFun\NpcFunAltar.lua"
)

BACKUP = LUA.with_suffix(".lua.bak-altar-buttons")

# 1-based line numbers in the SubID == 2 and SubID == 3 branches.
UPGRADE_LINE = 458
DELETE_LINE = 463

UPGRADE_OLD = b"\t\t  Button:SetPosition(25,175);"
UPGRADE_NEW = b"\t\t  Button:SetPosition(25,135);"
DELETE_OLD = b"\t      Button:Visible(true);"
DELETE_NEW = (
    b"\t      Button:Visible(true);\r\n"
    b"\t\t  Button:SetPosition(25,155);"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()

    if not LUA.exists():
        print(f"missing: {LUA}")
        return 1

    if args.revert:
        if not BACKUP.exists():
            print(f"no backup to restore: {BACKUP}")
            return 1
        shutil.copyfile(BACKUP, LUA)
        print(f"restored {LUA} from {BACKUP}")
        return 0

    data = LUA.read_bytes()
    lines = data.split(b"\n")
    if len(lines) < DELETE_LINE:
        print(f"unexpected file shape: {len(lines)} lines")
        return 1

    # The two positions have to be judged on the branch's own lines: the same
    # coordinate string occurs elsewhere in the file (SubID 4 and 10 share
    # (25,135) on this very page), so a whole-file search cannot tell whether
    # this branch is patched yet.
    upgrade = lines[UPGRADE_LINE - 1].rstrip(b"\r")
    delete = lines[DELETE_LINE - 1].rstrip(b"\r")
    if upgrade == UPGRADE_NEW and delete == DELETE_NEW:
        print("already patched; nothing to do")
        return 0
    if upgrade != UPGRADE_OLD:
        print(f"line {UPGRADE_LINE} is not what was expected: {upgrade!r}")
        return 1
    if delete != DELETE_OLD:
        print(f"line {DELETE_LINE} is not what was expected: {delete!r}")
        return 1

    if not BACKUP.exists():
        shutil.copyfile(LUA, BACKUP)
        print(f"backup: {BACKUP} sha256={digest(BACKUP.read_bytes())}")

    lines[UPGRADE_LINE - 1] = UPGRADE_NEW
    lines[DELETE_LINE - 1] = DELETE_NEW
    LUA.write_bytes(b"\n".join(lines))
    print(f"patched: {LUA}")
    print(f"  line {UPGRADE_LINE}: {UPGRADE_NEW!r}")
    print(f"  line {DELETE_LINE}: {DELETE_NEW!r}")
    print(f"  bytes={LUA.stat().st_size} sha256={digest(LUA.read_bytes())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
