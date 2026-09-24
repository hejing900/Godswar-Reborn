"""Reconcile the two migrations whose SQL changed after they were applied.

A database ran an earlier revision of these two, so its stored checksum no longer
matches the registered one and PostgresSchemaMigrationPlan.Build refuses to
build a plan. Both revisions only added idempotent content, so the fix is:

  1. apply the part that revision added but the database is missing, and
  2. move the stored checksum to the registered value so the history reads as
     applied.

What actually differs, verified against the live database rather than assumed:

  * 20260728_014_pet_presence_protocol - the revision registers opcode 10238
    (PetDeleteRequest). The column, index and constraints it also creates are
    already present, and packet_opcodes has no 10238 row, so only the opcode
    upsert is replayed.
  * 20260915_147_monster_loot_policy - the renumbered revision is the same
    idempotent SQL; both tables and their seed rows already exist, so nothing is
    replayed.

Usage:
  python tools/reconcile_changed_migrations.py --database godswar
  python tools/reconcile_changed_migrations.py --database godswar --apply
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# migration id -> the checksum the registered catalog computes for it.
TARGETS = {
    "20260728_014_pet_presence_protocol":
        "62F2D0D39CEB4BF3750F729AC0B8D227B8EEBA9D6EF44E9FA721B3CF6FFB1C9E",
    "20260915_147_monster_loot_policy":
        "8B8471FE58BBC9A1B7606924CA1B61786CBBFDDF13A13B248FE23989D1114F03",
}

# The one row the newer 014 revision adds; the rest of that migration is already
# present, so replaying the whole thing would fail on existing constraints.
OPCODE_10238 = """
INSERT INTO public.packet_opcodes (
    opcode, direction, name, category, confidence, description, notes)
VALUES (
    10238,
    'C2S',
    'PetDeleteRequest',
    'pets',
    'known',
    'Permanently destroys one owned pet.',
    'Eight-byte frame carrying only the uint32 pet ID. Captured 2026-09-24 23:57:38; the reference answered with pet-operation result code 3.')
ON CONFLICT (opcode, direction) DO UPDATE
SET name = EXCLUDED.name,
    category = EXCLUDED.category,
    confidence = EXCLUDED.confidence,
    description = EXCLUDED.description,
    notes = EXCLUDED.notes,
    updated_at = now();
"""


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

    code, out = psql(
        args.database,
        "SELECT migration_id || '|' || checksum FROM schema_migrations "
        "ORDER BY migration_id;")
    if code != 0:
        raise SystemExit(out.strip())
    stored = {}
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 2:
            stored[parts[0]] = parts[1]

    code, out = psql(
        args.database,
        "SELECT count(*) FROM packet_opcodes WHERE opcode = 10238;")
    opcode_present = out.strip().startswith("1")
    print(f"packet_opcodes 10238 present: {opcode_present}")

    print(f"\n{'migration':<42} {'stored':<10} matches registered")
    todo = []
    for migration_id, target in TARGETS.items():
        current = stored.get(migration_id)
        if current is None:
            print(f"{migration_id:<42} {'ABSENT':<10} -")
            continue
        ok = current == target
        print(f"{migration_id:<42} {current[:8]:<10} {ok}")
        if not ok:
            todo.append((migration_id, target))

    if not todo and opcode_present:
        print("\nnothing to reconcile")
        return 0
    if not args.apply:
        print("\n(dry run - pass --apply to write)")
        return 0

    statements = ["BEGIN;"]
    if not opcode_present:
        statements.append(OPCODE_10238)
    for migration_id, target in todo:
        statements.append(
            "UPDATE public.schema_migrations SET checksum = "
            f"'{target}' WHERE migration_id = '{migration_id}';")
    statements.append("COMMIT;")

    code, out = psql(args.database, "\n".join(statements))
    if code != 0:
        print(f"\nFAILED:\n{out}")
        return 1
    print(f"\nreconciled {len(todo)} checksum(s); "
          f"opcode replay: {'yes' if not opcode_present else 'not needed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
