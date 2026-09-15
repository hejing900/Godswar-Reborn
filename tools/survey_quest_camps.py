"""Survey Quest.xml by giver/responder prefix, so both camps can be scoped."""
import collections
import importlib.util
import re
import subprocess

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def prefix(key):
    if not key:
        return "(none)"
    if "_" not in key:
        return key
    head = key.split("_")[0]
    if head == "Sparta" and key.startswith("Sparta_Newbie"):
        return "Sparta_Newbie"
    return head


def npc_catalog():
    """npc key -> (map id) for every npc the server publishes."""
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c",
         "SELECT npc_key, map_id FROM npc_spawn_definitions;"],
        capture_output=True, text=True, check=True).stdout
    table = {}
    for line in out.splitlines():
        if "|" in line:
            key, map_id = line.split("|")
            table[key.strip()] = int(map_id)
    return table


def main():
    rows = gen.quest_rows()
    catalog = npc_catalog()
    by_giver = collections.defaultdict(list)
    by_responder = collections.defaultdict(list)
    for quest_id, row in rows.items():
        by_giver[prefix(row.get("GiverName", ""))].append(quest_id)
        by_responder[prefix(row.get("ResponderName", ""))].append(quest_id)

    print(f"Quest.xml quests: {len(rows)}")
    print(f"published npcs: {len(catalog)}")
    print()
    print(f"{'prefix':<16}{'giver':>7}{'responder':>10}{'levels':>12}"
          f"{'giver npc published':>22}")
    for name in sorted(set(by_giver) | set(by_responder),
                       key=lambda n: -len(by_giver[n])):
        givers = by_giver[name]
        responders = by_responder[name]
        levels = [int(rows[q].get("MinLevel") or 0) for q in givers + responders]
        low = min(levels) if levels else 0
        high = max(levels) if levels else 0
        keys = {rows[q].get("GiverName", "") for q in givers}
        known = sum(1 for key in keys if key in catalog)
        print(f"{name:<16}{len(givers):>7}{len(responders):>10}"
              f"{f'{low}-{high}':>12}{f'{known}/{len(keys)}':>22}")

    print()
    print("maps of the published npcs per prefix:")
    maps = collections.defaultdict(collections.Counter)
    for key, map_id in catalog.items():
        maps[prefix(key)][map_id] += 1
    for name in sorted(maps):
        print(f"  {name:<16} {dict(maps[name])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
