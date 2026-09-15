"""How many npc-giver quests reference an npc the server does not publish."""
import collections
import importlib.util
import subprocess

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def catalog():
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
    known = catalog()
    missing_giver = collections.Counter()
    missing_responder = collections.Counter()
    examples = collections.defaultdict(list)
    total = 0
    for quest_id, row in sorted(rows.items()):
        giver = row.get("GiverName", "")
        responder = row.get("ResponderName", "")
        if "_" not in giver:
            continue
        total += 1
        if giver not in known:
            key = giver.split("_")[0]
            missing_giver[key] += 1
            examples[key].append((quest_id, giver, responder))
        if responder and "_" in responder and responder not in known:
            key = responder.split("_")[0]
            missing_responder[key] += 1

    print(f"npc-giver quests: {total}")
    print(f"giver not published: {sum(missing_giver.values())} "
          f"{dict(missing_giver)}")
    print(f"responder not published: {sum(missing_responder.values())} "
          f"{dict(missing_responder)}")
    for key, items in examples.items():
        for quest_id, giver, responder in items[:6]:
            print(f"  {key}: quest {quest_id} giver={giver} "
                  f"responder={responder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
