"""Compute the two reviewed sets the batch guard pins, from the generated tables.

Mirrors tests/QuestProtocolChecks.CheckEveryObjectiveResolves: which objectives
name no monster id at all, and which maps ship no client monster matching the
objectives that live there.
"""
import collections
import importlib.util
import re

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"
OBJECTIVES = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
              r"\StarterQuestObjectives.cs")
TEMPLATES = r"D:\Godswar Origin\npc-translation\monster_templates.txt"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

ROW = re.compile(r"\[(\d+)u\] = \[(.*)\],$")
OBJ = re.compile(
    r'new QuestObjective\("(?P<target>[^"]*)", "(?P<match>[^"]*)", '
    r'(?P<required>\d+), (?P<monster>\d+)u, (?P<map>\d+)u, '
    r'(?P<x>-?[\d.]+)f, (?P<z>-?[\d.]+)f\)')


def objectives():
    found = []
    for line in open(OBJECTIVES, encoding="utf-8"):
        row = ROW.search(line.strip())
        if not row:
            continue
        quest = int(row.group(1))
        for item in OBJ.finditer(row.group(2)):
            found.append((quest, item.group("target"), item.group("match"),
                          int(item.group("monster")), int(item.group("map"))))
    return found


def templates():
    by_map = collections.defaultdict(set)
    for line in open(TEMPLATES, encoding="utf-8", errors="replace"):
        parts = line.strip().split("|")
        if len(parts) == 4:
            by_map[int(parts[3])].add(gen.needle(parts[1]))
    return by_map


def main():
    found = objectives()
    by_map = templates()
    without_id = sorted({quest for quest, _, _, monster, _ in found
                         if monster == 0})
    missing = collections.Counter()
    missing_quests = collections.defaultdict(set)
    for quest, target, match, monster, map_id in found:
        if monster == 0:
            continue
        shapes = gen.shapes(match or target)
        known = by_map.get(map_id, set())
        if any(shape in known or any(shape in other or other in shape
                                     for other in known)
               for shape in shapes):
            continue
        missing[map_id] += 1
        missing_quests[map_id].add(quest)

    print(f"objectives: {len(found)}")
    print(f"without a monster id: {len(without_id)}")
    print(f"  {without_id}")
    print("maps whose objectives have no client monster "
          "(objectives / quests):")
    for map_id, count in sorted(missing.items()):
        print(f"  map {map_id:>3}: {count:>4} objectives, "
              f"{len(missing_quests[map_id]):>4} quests")
    print(f"total such objectives: {sum(missing.values())}, "
          f"maps: {sorted(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
