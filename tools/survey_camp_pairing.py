"""Establish the two camps' region pairing from the client's own quest ids.

The client ships the Sparta progression and the Athens progression as parallel
quest sets: the tutorial leg mirrors exactly (518 -> 1518, 531 -> 1531), and the
mirror also pairs the regions that continue each camp (549's Peloponnese giver
against 1549's Marathon giver). This measures that pairing instead of guessing
which region belongs to which camp.
"""
import collections
import importlib.util

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def region(key):
    if not key or "_" not in key:
        return key or "(none)"
    if key.startswith("Sparta_Newbie"):
        return "Sparta_Newbie"
    if key.startswith("Athens_Newbie"):
        return "Athens_Newbie"
    return key.split("_")[0]


def main():
    rows = gen.quest_rows()
    pairs = collections.Counter()
    unpaired = []
    for quest_id, row in sorted(rows.items()):
        if quest_id > 1000:
            continue
        mirror = quest_id + 1000
        if mirror not in rows:
            continue
        left = region(row.get("GiverName", "")) or region(
            row.get("ResponderName", ""))
        other = rows[mirror]
        right = region(other.get("GiverName", "")) or region(
            other.get("ResponderName", ""))
        pairs[(left, right)] += 1

    print("region pairing measured from id+1000 mirrors:")
    for (left, right), count in sorted(pairs.items(), key=lambda kv: -kv[1]):
        print(f"  {left:<14} <-> {right:<14} {count}")

    print()
    low = [quest_id for quest_id in rows if quest_id <= 1000]
    print(f"quests with id <= 1000: {len(low)}, "
          f"with a +1000 mirror: "
          f"{sum(1 for q in low if q + 1000 in rows)}")
    for quest_id in low:
        if quest_id + 1000 not in rows:
            unpaired.append(quest_id)
    print(f"without a mirror: {sorted(unpaired)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
