"""Verify the pet-discard audit migration without leaving a trace.

Applies the new constraint inside a transaction, checks that the discard verb is
accepted AND that every verb earlier revisions contributed is still accepted,
then rolls back. A constraint rewritten with a short list would silently reject
an unrelated pet operation later, which is the failure this guards.

Usage: python tools/verify_pet_delete_migration.py [--database godswar_local]
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# Every verb the constraint carried before the discard was added. Read from the
# v8 revision (PostgresSchemaMigrationCatalog.PetManagerUtility.cs).
EXISTING_VERBS = [
    "owner_merge", "pet_merge", "rebirth", "soul_contract", "take", "summon",
    "dismiss", "reveal_growth", "reset_basic_savvy", "change_appearance",
    "bind", "seal", "unseal", "hatch", "level_up", "check_growth",
    "claim_pet_call", "claim_merge", "change_gender",
]
NEW_VERB = "delete"

CONSTRAINT_V9 = """
ALTER TABLE public.pet_operation_audit
    ADD CONSTRAINT ck_pet_operation_audit_operation_v9
    CHECK (
        operation IN (
            'owner_merge', 'pet_merge', 'rebirth', 'soul_contract', 'take',
            'summon', 'dismiss', 'reveal_growth', 'reset_basic_savvy',
            'change_appearance', 'bind', 'seal', 'unseal', 'hatch',
            'level_up', 'check_growth', 'claim_pet_call', 'claim_merge',
            'change_gender', 'delete'
        )
    ) NOT VALID;
ALTER TABLE public.pet_operation_audit
    VALIDATE CONSTRAINT ck_pet_operation_audit_operation_v9;
ALTER TABLE public.pet_operation_audit
    DROP CONSTRAINT pet_operation_audit_operation_check;
ALTER TABLE public.pet_operation_audit
    RENAME CONSTRAINT ck_pet_operation_audit_operation_v9
    TO pet_operation_audit_operation_check;
"""


def psql(database: str, sql: str) -> tuple[int, str]:
    done = subprocess.run(
        ["docker", "exec", "-i", "godswar-postgres", "psql", "-U", "godswar",
         "-d", database, "-t", "-A", "-v", "ON_ERROR_STOP=1"],
        input=sql, capture_output=True, text=True)
    return done.returncode, (done.stdout + done.stderr).strip()


def accepted(database: str, verb: str) -> bool:
    sql = (
        "BEGIN;\n"
        f"{CONSTRAINT_V9}\n"
        "SAVEPOINT probe;\n"
        "INSERT INTO public.pet_operation_audit (\n"
        "    request_id, user_id_snapshot, pet_id_snapshot, operation,\n"
        "    outcome)\n"
        f"VALUES (gen_random_uuid(), 1, 1, '{verb}', 'committed');\n"
        "ROLLBACK;\n"
    )
    code, out = psql(database, sql)
    return code == 0 and "ERROR" not in out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="godswar_local")
    args = parser.parse_args()

    print(f"=== current constraint on {args.database} ===")
    _, out = psql(args.database,
                  "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                  "WHERE conrelid='pet_operation_audit'::regclass "
                  "AND conname='pet_operation_audit_operation_check';")
    current = [v for v in EXISTING_VERBS + [NEW_VERB] if f"'{v}'" in out]
    print(f"    verbs now present: {len(current)}")
    missing_now = [v for v in EXISTING_VERBS if v not in current]
    print(f"    earlier verbs missing before this change: {missing_now or 'none'}")
    print(f"    discard verb already present: {NEW_VERB in current}")

    print(f"\n=== probing each verb against the rewritten constraint ===")
    failures = []
    for verb in EXISTING_VERBS:
        ok = accepted(args.database, verb)
        if not ok:
            failures.append(verb)
        print(f"    {verb:<20} {'accepted' if ok else 'REJECTED'}")
    discard_ok = accepted(args.database, NEW_VERB)
    print(f"    {NEW_VERB:<20} {'accepted' if discard_ok else 'REJECTED'}")

    print("\n=== result ===")
    if failures:
        print(f"FAIL: earlier verbs would be rejected: {failures}")
        return 1
    if not discard_ok:
        print("FAIL: the discard verb is not accepted")
        return 1
    print(f"OK: all {len(EXISTING_VERBS)} earlier verbs survive and "
          f"'{NEW_VERB}' is accepted (everything rolled back)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
