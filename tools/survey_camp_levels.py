"""Athens vs Sparta quests by level, to design the two camp chains."""
import collections
import importlib.util

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def camp(row):
    giver = row.get("GiverName", "")
    responder = row.get("ResponderName", "")
    for key in (giver, responder):
        if key.startswith("Athens"):
            return "Athens"
        if key.startswith("Sparta"):
            return "Sparta"
    return ""


def main():
    rows = gen.quest_rows()
    chain = set(gen.chain_ids())
    buckets = collections.defaultdict(list)
    for quest_id, row in rows.items():
        name = camp(row)
        if not name:
            continue
        level = int(row.get("MinLevel") or 0)
        if level > 200:
            continue
        buckets[(name, level)].append(quest_id)

    print("quests per camp and level (levels up to 30):")
    for name in ("Sparta", "Athens"):
        listed = sorted(level for (c, level) in buckets if c == name)
        print(f"  {name}: {sum(len(buckets[(name, l)]) for l in set(listed))} "
              f"quests, levels {min(listed)}-{max(listed)}")
    print()
    print(f"{'level':>6}{'Sparta quests':>34}{'Athens quests':>34}")
    for level in range(0, 31):
        sparta = sorted(buckets[("Sparta", level)])
        athens = sorted(buckets[("Athens", level)])
        print(f"{level:>6}  {str(sparta):<34}{str(athens):<34}")
    print()
    print("quests in the current chain, by camp:")
    counted = collections.Counter()
    for quest_id in gen.chain_ids():
        counted[camp(rows.get(quest_id, {})) or "(other)"] += 1
    print(f"  {dict(counted)}")
    print()
    print("Athens quests that are kill quests vs talk quests:")
    kills = talks = 0
    for quest_id, row in rows.items():
        if camp(row) != "Athens":
            continue
        if int(row.get("MinLevel") or 0) > 200:
            continue
        if row.get("CreatureMapID", "").strip("0,"):
            kills += 1
        else:
            talks += 1
    print(f"  kill={kills} talk={talks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
