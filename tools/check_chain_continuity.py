"""Check the regenerated two-camp chain against the chain that is live.

Three things have to hold before it replaces the live file:

  * every quest the old chain carried is still carried, so a character mid-chain
    keeps its progress and its next quest;
  * a next-quest pointer never crosses camps;
  * the old chain's order survives for the rows it had, so the quest a character
    is on is still followed by the same quest.
"""
import re
import sys

OLD = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
       r"\StarterQuestChain.cs")
NEW = sys.argv[1] if len(sys.argv) > 1 else (
    r"D:\Godswar-Reborn-main\tools\_chain_preview.cs")

ROW = re.compile(
    r'new\((\d+), (?:([A-Za-z]+)Camp, )?"([^"]*)", "([^"]*)", '
    r'(?:(\d+)u|null), (-?\d+), (-?\d+), (-?\d+), (-?\d+)\)')


def load(path):
    """Read either shape: the live rows without a camp, the new ones with it."""
    steps = {}
    order = []
    for line in open(path, encoding="utf-8"):
        match = ROW.search(line)
        if not match:
            continue
        quest_id = int(match.group(1))
        steps[quest_id] = {
            "camp": match.group(2) or (
                "Sparta" if quest_id <= 1000 else "Athens"),
            "giver": match.group(3),
            "responder": match.group(4),
            "next": int(match.group(5)) if match.group(5) else None,
            "rewards": tuple(int(match.group(i)) for i in range(6, 10)),
        }
        order.append(quest_id)
    return steps, order


def camp_by_id(quest_id):
    return "Sparta" if quest_id <= 1000 else "Athens"


def main():
    old, old_order = load(OLD)
    new, new_order = load(NEW)
    print(f"old rows {len(old)}, new rows {len(new)}")

    missing = [quest_id for quest_id in old if quest_id not in new]
    print(f"quests the old chain had and the new one lost: {len(missing)} "
          f"{missing[:10]}")

    changed = []
    for quest_id, step in old.items():
        if quest_id not in new:
            continue
        mine = new[quest_id]
        if (mine["giver"] != step["giver"] or
                mine["responder"] != step["responder"] or
                mine["rewards"] != step["rewards"]):
            changed.append(quest_id)
    print(f"rows whose giver/responder/rewards changed: {len(changed)} "
          f"{changed[:10]}")

    crossed = [quest_id for quest_id, step in new.items()
               if step["next"] is not None and
               new.get(step["next"], {}).get("camp") != step["camp"]]
    print(f"next pointers crossing camps: {len(crossed)} {crossed[:10]}")

    wrong_camp = [quest_id for quest_id, step in new.items()
                  if step["camp"] != camp_by_id(quest_id)]
    print(f"rows whose camp disagrees with the id side: {len(wrong_camp)} "
          f"{wrong_camp[:10]}")

    moved = []
    old_positions = {quest_id: index for index, quest_id in enumerate(old_order)}
    new_positions = {quest_id: index for index, quest_id in enumerate(
        [q for q in new_order if q in old])}
    previous = None
    for quest_id in old_order:
        if quest_id not in new_positions:
            continue
        position = new_positions[quest_id]
        if previous is not None and position < previous:
            moved.append(quest_id)
        previous = position
    print(f"quests that moved earlier than a quest they used to follow: "
          f"{len(moved)} {moved[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
