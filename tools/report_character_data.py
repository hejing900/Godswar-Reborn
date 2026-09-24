"""Report which character-scoped tables actually hold rows for a character.

The schema references a character from fifty-odd tables, but most are ledgers,
audits and claims that a new character must not inherit. This prints the real row
count per table so only the meaningful ones are copied.

Usage: python tools/report_character_data.py --database godswar_local --character 2
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# Tables whose rows are history, claims or reconciliation evidence: a copied
# character must start without them.
SKIP = {
    "character_currency_ledger",
    "character_inventory_ledger",
    "character_inventory_reconciliation",
    "character_inventory_baseline_items",
    "character_item_audit",
    "character_item_validation",
    "character_wallet_reconciliation",
    "character_progression_interval_authority",
    "monster_death_reward_settlements",
    "monster_loot_pickup_claims",
    "monster_death_pet_experience",
    "online_award_claim_settlements",
    "warehouse_expansion_settlements",
    "legacy_instance_daily_entries",
    "legacy_instance_opal_payments",
    "medusa_daily_entries",
    "medusa_completion_reward_members",
    "atlantis_completion_reward_members",
    "atlantis_character_title_ownership",
    "wonderland_boss_loot_claims",
    "wonderland_chest_claims",
    "wonderland_title_members",
    "faction_crier_daily_claims",
    "faction_crier_weekly_reclaims",
    "faction_crier_exchange_settlements",
    "guild_altar_worship",
    "guild_members",
    "pet_operation_audit",
    "pet_durable_stream_versions",
    "character_wishing_pool_usage",
    "character_bag_consumable_cooldowns",
    "character_experience_modifiers",
    "character_lucky_gods_wish",
}


def psql(database: str, sql: str, strict: bool = True) -> list[str]:
    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", database, "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, encoding="utf-8")
    if strict and done.returncode != 0:
        raise SystemExit((done.stderr or "").strip())
    return [line for line in (done.stdout or "").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="godswar_local")
    parser.add_argument("--character", type=int, default=2)
    args = parser.parse_args()

    columns = {}
    for line in psql(args.database,
                     "SELECT table_name, column_name FROM "
                     "information_schema.columns WHERE table_schema='public' "
                     "AND column_name IN ('character_id','user_id',"
                     "'pet_id') ORDER BY table_name;"):
        table, column = line.split("|")
        columns.setdefault(table, set()).add(column)

    has_rows, empty, skipped, errored = [], [], [], []
    for table in sorted(columns):
        if table in SKIP:
            skipped.append(table)
            continue
        column = ("character_id" if "character_id" in columns[table]
                  else "user_id" if "user_id" in columns[table]
                  else None)
        if column is None:
            # pet-keyed tables hang off character_pets, not the character.
            skipped.append(table)
            continue
        result = psql(args.database,
                      f"SELECT count(*) FROM {table} "
                      f"WHERE {column}={args.character};", strict=False)
        if not result:
            errored.append(table)
            continue
        try:
            count = int(result[0])
        except ValueError:
            errored.append(table)
            continue
        (has_rows if count else empty).append((table, column, count))

    print(f"=== tables WITH rows for character {args.character} "
          f"({len(has_rows)}) ===")
    for table, column, count in has_rows:
        print(f"  {table:<46} {column:<13} {count}")
    print(f"\n=== empty ({len(empty)}) ===")
    print("  " + ", ".join(t for t, _, _ in empty))
    print(f"\n=== excluded as history/claims ({len(skipped)}) ===")
    print("  " + ", ".join(skipped))
    if errored:
        print(f"\n=== could not query ({len(errored)}) ===")
        print("  " + ", ".join(errored))
    return 0


if __name__ == "__main__":
    sys.exit(main())
