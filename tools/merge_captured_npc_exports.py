"""Merge the fresh capture exports into the placement table's input directory.

tools/gen_captured_npc_placements.py rebuilds CapturedNpcPlacements.Generated.cs
from ``captured-npcs-map{N}.txt`` files. This session's capture covers maps
1/2/3/11 while the existing exports also carry map 0 and 4, so the two are
merged rather than replaced: a map the new capture covers is taken from it, and
every other map keeps the rows already there.

Writes a backup of each replaced file first, and reports the per-map delta.

Usage: python tools/merge_captured_npc_exports.py [--apply]
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

TARGET = pathlib.Path(r"D:\Godswar Origin\npc-translation")
FRESH = pathlib.Path(r"D:\Godswar-Reborn-main\artifacts\npc-port")
BACKUP = FRESH / "previous-exports"


def read(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write the merged files (default: dry run)")
    args = parser.parse_args()

    fresh_maps = sorted(int(p.name[len("captured-npcs-map"):-len(".txt")])
                        for p in FRESH.glob("captured-npcs-map*.txt"))
    if not fresh_maps:
        print("no fresh exports found")
        return 1

    print(f"fresh capture maps: {fresh_maps}")
    BACKUP.mkdir(parents=True, exist_ok=True)

    for map_id in fresh_maps:
        source = FRESH / f"captured-npcs-map{map_id}.txt"
        target = TARGET / f"captured-npcs-map{map_id}.txt"
        before = read(target)
        after = read(source)
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        print(f"\nmap {map_id}: existing {len(before)} -> fresh {len(after)}")
        print(f"    +{len(added)}  -{len(removed)}")
        for line in added:
            print(f"      add     {line}")
        for line in removed:
            print(f"      remove  {line}")
        if args.apply:
            if target.exists():
                shutil.copy2(target, BACKUP / target.name)
            header = "# objectId|template|appearance|x|z|facing\n"
            target.write_text(header + "\n".join(after) + "\n",
                              encoding="utf-8", newline="\n")
            print(f"    wrote {target}")

    if not args.apply:
        print("\n(dry run - pass --apply to write)")
    else:
        print(f"\nbackups in {BACKUP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
