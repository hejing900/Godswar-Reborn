"""Find duplicate npc keys in the shipped placement table and the capture exports.

CapturedNpcPlacements.All is a Dictionary, so a repeated key silently keeps only
the last row while ByMap still emits two All[] lookups; the runtime then sees a
different placement than the table appears to hold.

Usage: python tools/find_duplicate_npc_keys.py
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

SERVER = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure\WorldContent"
    r"\CapturedNpcPlacements.Generated.cs")
EXPORTS = pathlib.Path(r"D:\Godswar Origin\npc-translation")

KEY = re.compile(r'\["(?P<key>[A-Za-z_0-9]+)"\]\s*=\s*new\(')
MODEL = re.compile(r"^(?P<key>.+)_(?P<model>[A-Za-z0-9]+)$")


def main() -> int:
    text = SERVER.read_text(encoding="utf-8")

    assigned = collections.Counter()
    for found in KEY.finditer(text):
        assigned[found.group("key")] += 1

    referenced = collections.Counter()
    for found in re.finditer(r'All\["(?P<key>[A-Za-z_0-9]+)"\]', text):
        referenced[found.group("key")] += 1

    print("=== CapturedNpcPlacements.Generated.cs ===")
    dup_assign = {k: v for k, v in assigned.items() if v > 1}
    print(f"rows: {sum(assigned.values())}  distinct keys: {len(assigned)}")
    print(f"keys assigned more than once: {len(dup_assign)}")
    for key, count in sorted(dup_assign.items()):
        print(f"    {key:<24} assigned {count}x")
        for line_no, line in enumerate(text.splitlines(), 1):
            if f'["{key}"] = new(' in line:
                print(f"        L{line_no}: {line.strip()[:110]}")

    missing_ref = sorted(set(referenced) - set(assigned))
    print(f"All[...] references with no assignment: {len(missing_ref)} {missing_ref}")

    print("\n=== capture exports ===")
    for path in sorted(EXPORTS.glob("captured-npcs-map*.txt")):
        keys = collections.Counter()
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("|")
            if len(parts) != 6:
                continue
            found = MODEL.match(parts[1])
            if found:
                keys[found.group("key")] += 1
        dup = {k: v for k, v in keys.items() if v > 1}
        print(f"  {path.name}: {len(keys)} distinct keys, duplicates: {dup or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
