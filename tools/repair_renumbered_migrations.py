"""Rename applied migrations that the catalog renumbered, so the server's
applied-history prefix check can pass again.

The 20260908/15/16 revisions of the exchange, quest, loot, wonderland, holy
suit, monster-balance and bloodfang migrations are the same SQL as the earlier
20260910-14/16 numbered rows a live database already carries; only the ids
changed. PostgresSchemaMigrationPlan.Build requires the stored history to be an
exact ordered prefix of the registered list, so the stale ids have to move.

A single UPDATE per row would hit the primary key mid-flight, so each id is
renamed to a temporary name first, then to its final one.

Usage:
  python tools/repair_renumbered_migrations.py --database godswar
  python tools/repair_renumbered_migrations.py --database godswar --apply
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# Applied id in the database -> the id the catalog registers for the same SQL.
RENAMES = [
    ("20260910_144_wonderland_titles", "20260916_148_wonderland_titles"),
    ("20260910_145_wonderland_all_island_titles",
     "20260916_149_wonderland_all_island_titles"),
    ("20260910_146_holy_suit_divinium", "20260916_150_holy_suit_divinium"),
    ("20260910_147_holy_suit_combat_projection",
     "20260916_151_holy_suit_combat_projection"),
    ("20260911_148_wonderland_chest_claims",
     "20260916_152_wonderland_chest_claims"),
    ("20260911_149_wonderland_boss_loot_claims",
     "20260916_153_wonderland_boss_loot_claims"),
    ("20260914_150_monster_combat_balance",
     "20260916_154_monster_combat_balance"),
    ("20260914_151_bloodfang_pet_species", "20260916_155_bloodfang_pet_species"),
    ("20260916_152_character_quest_state", "20260908_145_character_quest_state"),
    ("20260916_153_character_quests", "20260908_146_character_quests"),
    ("20260916_154_monster_loot_policy", "20260915_147_monster_loot_policy"),
    ("20260916_155_exchange_point_balances",
     "20260908_144_exchange_point_balances"),
]


def psql(database: str, sql: str) -> tuple[int, str]:
    done = subprocess.run(
        ["docker", "exec", "-i", "godswar-postgres", "psql", "-U", "godswar",
         "-d", database, "-t", "-A", "-v", "ON_ERROR_STOP=1"],
        input=sql, capture_output=True, text=True, encoding="utf-8")
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="godswar")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    code, out = psql(args.database,
                     "SELECT migration_id FROM schema_migrations "
                     "ORDER BY migration_id;")
    if code != 0:
        raise SystemExit(out.strip())
    applied = {line.strip() for line in out.splitlines() if line.strip()}
    print(f"{args.database}: {len(applied)} applied migrations")

    todo = [(old, new) for old, new in RENAMES if old in applied]
    already = [(old, new) for old, new in RENAMES
               if old not in applied and new in applied]
    absent = [(old, new) for old, new in RENAMES
              if old not in applied and new not in applied]
    print(f"to rename            : {len(todo)}")
    print(f"already at the new id: {len(already)}")
    print(f"neither id applied   : {len(absent)}")
    for old, new in todo:
        print(f"    {old}\n        -> {new}")
    for old, new in absent:
        print(f"    (absent) {old} / {new}")

    if not todo:
        print("\nnothing to rename")
        return 0
    if not args.apply:
        print("\n(dry run - pass --apply to write)")
        return 0

    statements = ["BEGIN;"]
    for index, (old, new) in enumerate(todo):
        temporary = f"tmp_renumber_{index:02d}"
        statements.append(
            "UPDATE public.schema_migrations "
            f"SET migration_id = '{temporary}' WHERE migration_id = '{old}';")
        statements.append(
            "UPDATE public.schema_migrations "
            f"SET migration_id = '{new}' WHERE migration_id = '{temporary}';")
    statements.append("COMMIT;")
    code, out = psql(args.database, "\n".join(statements))
    if code != 0:
        print(f"\nFAILED:\n{out}")
        return 1
    print(f"\nrenamed {len(todo)} rows")

    code, out = psql(args.database,
                     "SELECT migration_id FROM schema_migrations "
                     "ORDER BY migration_id;")
    now = [line.strip() for line in out.splitlines() if line.strip()]
    print(f"{args.database}: {len(now)} applied migrations after repair")
    return 0


if __name__ == "__main__":
    sys.exit(main())
