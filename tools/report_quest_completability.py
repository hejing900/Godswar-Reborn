"""Which chain quests can actually be completed on the server right now.

Compares every kill objective of the chain against the monsters the server
really spawns:

  * map 0  - the captured baseline (npc-translation/map0_monsters.txt);
  * map 4  - the generated Sparta-outskirts plan (SpartaNewbieSpawnPlan...cs);
  * map 8  - the authored Thermopylae regions (PostgresWorldContentReaderLoader
             .Monsters.cs);

Every other map has no spawns at all, so its quests cannot be finished until
monsters are added. The point is to answer "which quests are broken" in one run
instead of trying a few hundred by hand.

Usage: python tools/report_quest_completability.py [out.md]
"""

import importlib.util
import os
import re
import sys

OBJECTIVES = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
              r"\StarterQuestObjectives.cs")
LOADER = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure"
          r"\WorldContent\PostgresWorldContentReaderLoader.Monsters.cs")
SPARTA_PLAN = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure"
               r"\WorldContent\SpartaNewbieSpawnPlan.Generated.cs")
MAP0_SPAWNS = r"D:\Godswar Origin\npc-translation\map0_monsters.txt"
TEMPLATES = r"D:\Godswar Origin\npc-translation\monster_templates.txt"
GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

OBJECTIVE_ROW = re.compile(
    r'new QuestObjective\("(?P<target>[^"]*)", "(?P<match>[^"]*)", '
    r'(?P<required>\d+), (?P<monster>\d+)u, (?P<map>\d+)u, '
    r'(?P<x>-?[\d.]+)f, (?P<z>-?[\d.]+)f\)')
QUEST_ROW = re.compile(r"\[(\d+)u\] = \[(.*)\],$")


def objectives():
    """quest id -> list of (target, match, required, map)."""
    found = {}
    with open(OBJECTIVES, "r", encoding="utf-8") as handle:
        for line in handle:
            row = QUEST_ROW.search(line.strip())
            if not row:
                continue
            quest = int(row.group(1))
            entries = []
            for item in OBJECTIVE_ROW.finditer(row.group(2)):
                entries.append((
                    item.group("target"),
                    item.group("match"),
                    int(item.group("required")),
                    int(item.group("map")),
                ))
            if entries:
                found[quest] = entries
    return found


def template_names():
    """template key -> (display name, map id)."""
    table = {}
    with open(TEMPLATES, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.strip().split("|")
            if len(parts) == 4:
                table[parts[0]] = (parts[1], int(parts[3]))
    return table


def server_spawns():
    """map id -> set of monster names the server spawns on it."""
    table = template_names()
    by_map = {}

    def add(map_id, name):
        by_map.setdefault(map_id, set()).add(gen.needle(name))

    with open(MAP0_SPAWNS, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.strip().split("|")
            if len(parts) == 4 and parts[0]:
                add(0, parts[0])

    plan_keys = re.findall(r'new\("([^"]+)",', open(
        SPARTA_PLAN, "r", encoding="utf-8").read())
    for key in plan_keys:
        if key in table:
            add(4, table[key][0])

    loader = open(LOADER, "r", encoding="utf-8").read()
    for key in re.findall(r'new\("([^"]+)", \d+, [\d_]+,', loader):
        if key in table:
            add(8, table[key][0])

    return by_map


def main():
    chain = gen.chain_ids()
    quests = objectives()
    spawns = server_spawns()
    rows = gen.quest_rows()

    playable, blocked = [], []
    for quest in chain:
        entries = quests.get(quest)
        if not entries:
            continue
        level = int(rows.get(quest, {}).get("MinLevel") or 0)
        missing = []
        for target, match, _, map_id in entries:
            name = match or target
            shapes = gen.shapes(name)
            known = spawns.get(map_id, set())
            if not any(shape in known or any(
                    shape in other or other in shape for other in known)
                    for shape in shapes):
                missing.append(f"{target} (map {map_id})")
        (blocked if missing else playable).append((quest, level, missing))

    lines = [
        "# 任务链可完成性报告（服务端现有刷怪 vs 任务需求）",
        "",
        f"- 有击杀目标的任务：{len(quests)}",
        f"- 现在就能打通的：{len(playable)}",
        f"- 缺怪的：{len(blocked)}",
        "",
        "## 缺怪的任务（怪没刷，或刷在别的地图）",
        "",
        "| 任务 | 等级 | 缺的目标 |",
        "| --- | --- | --- |",
    ]
    for quest, level, missing in blocked:
        lines.append(f"| {quest} | {level} | {'；'.join(missing)} |")
    lines += [
        "",
        "## 现在就能打通的任务",
        "",
        "| 任务 | 等级 |",
        "| --- | --- |",
    ]
    for quest, level, _ in playable:
        lines.append(f"| {quest} | {level} |")

    text = "\n".join(lines) + "\n"
    out = sys.argv[1] if len(sys.argv) > 1 else None
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
