"""Which Athens quests mirror the Sparta tutorials, and what the camp field is."""
import importlib.util

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

SPARTA_TUTORIAL = [518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529,
                   530, 531, 532, 533, 534, 537, 538, 539, 543, 545, 546, 547,
                   548, 549, 550, 551, 552]


def main():
    rows = gen.quest_rows()
    print("Athens counterparts of the Sparta tutorials (id + 1000):")
    found = []
    for quest_id in SPARTA_TUTORIAL:
        mirror = quest_id + 1000
        row = rows.get(mirror)
        if row is None:
            print(f"  {quest_id} -> {mirror}: absent")
            continue
        found.append(mirror)
        print(f"  {quest_id} -> {mirror}: lv{row.get('MinLevel')} "
              f"giver={row.get('GiverName')} responder={row.get('ResponderName')}")
    print(f"mirrored tutorials: {len(found)}")

    print()
    print("Athens quests at levels 1-3 (the camp's own opening):")
    for quest_id, row in sorted(rows.items()):
        name = row.get("GiverName", "")
        if not name.startswith("Athens"):
            continue
        level = int(row.get("MinLevel") or 0)
        if level <= 3:
            print(f"  {quest_id}: lv{level} giver={name} "
                  f"responder={row.get('ResponderName')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
