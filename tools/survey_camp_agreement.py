"""Check that camp-by-id agrees with camp-by-npc-prefix before using it."""
import importlib.util

GENERATOR = r"D:\Godswar-Reborn-main\tools\gen_quest_objectives.py"

spec = importlib.util.spec_from_file_location("gen", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

SPARTA_REGIONS = ("Sparta", "Peloponnese", "Nemea", "Argolis", "Derveni")
ATHENS_REGIONS = ("Athens", "Marathon", "Parnitha", "Megara", "Plataea")


def side_by_prefix(row):
    keys = (row.get("GiverName", ""), row.get("ResponderName", ""))
    sparta = any(key.startswith(SPARTA_REGIONS) for key in keys if key)
    athens = any(key.startswith(ATHENS_REGIONS) for key in keys if key)
    if sparta and not athens:
        return "Sparta"
    if athens and not sparta:
        return "Athens"
    return ""


def main():
    rows = gen.quest_rows()
    disagreements = []
    counted = {"Sparta": 0, "Athens": 0, "": 0}
    for quest_id, row in sorted(rows.items()):
        by_id = "Sparta" if quest_id <= 1000 else "Athens"
        by_prefix = side_by_prefix(row)
        counted[by_prefix] += 1
        if by_prefix and by_prefix != by_id:
            disagreements.append((quest_id, by_id, by_prefix,
                                  row.get("GiverName"),
                                  row.get("ResponderName")))
    print(f"quests by prefix: {counted}")
    print(f"disagreements between id side and npc prefix: "
          f"{len(disagreements)}")
    for item in disagreements[:20]:
        print(f"  id {item[0]} (id-side {item[1]}, prefix-side {item[2]}) "
              f"giver={item[3]} responder={item[4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
