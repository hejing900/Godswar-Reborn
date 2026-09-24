"""Prove the discard actually removes the pet and everything hanging off it.

Runs the server's own discard sequence - widen the audit vocabulary, write the
audit row, clear the kill ledger, delete the pet - against a real database, and
asserts the outcome from inside the same transaction so the uncommitted state is
visible. Everything is rolled back, so the database is unchanged.

Usage: python tools/verify_pet_discard_delete.py [--database godswar_local]
                                                 [--pet-id 2]
"""
from __future__ import annotations

import argparse
import subprocess
import sys

VOCABULARY = """
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
         "-d", database, "-t", "-A", "-v", "ON_ERROR_STOP=1", "-F", "|"],
        input=sql, capture_output=True, text=True)
    return done.returncode, (done.stdout + done.stderr).strip()


def scalar(database: str, sql: str) -> str:
    _, out = psql(database, sql)
    return out.splitlines()[0] if out else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="godswar_local")
    parser.add_argument("--pet-id", type=int, default=2)
    parser.add_argument("--owner", type=int, default=2)
    args = parser.parse_args()
    db, pet, owner = args.database, args.pet_id, args.owner

    before = {
        "siblings": scalar(db, "SELECT count(*) FROM character_pets "
                               f"WHERE user_id={owner} AND id<>{pet};"),
        "skills": scalar(db, f"SELECT count(*) FROM character_pet_skills "
                             f"WHERE pet_id={pet};"),
        "stats": scalar(db, f"SELECT count(*) FROM character_pet_stat_values "
                            f"WHERE pet_id={pet};"),
    }
    print("=== before (everything below is rolled back) ===")
    print(psql(db, "SELECT id, name, level, is_carried, is_summoned "
                   f"FROM character_pets WHERE id={pet};")[1])
    for key, value in before.items():
        print(f"    {key:<12} {value}")

    # One transaction: the assertions must run on the same connection that made
    # the change, otherwise they cannot see the uncommitted delete.
    script = f"""
BEGIN;
{VOCABULARY}
INSERT INTO pet_operation_audit (
    request_id, user_id, user_id_snapshot, pet_id, pet_id_snapshot,
    operation, outcome)
VALUES (gen_random_uuid(), {owner}, {owner}, {pet}, {pet}, 'delete', 'committed');

INSERT INTO monster_death_pet_experience (
    death_event_id, account_id, character_id, requested_experience,
    pet_id, experience_before, experience_after, pet_revision)
SELECT gen_random_uuid(), COALESCE(a.account_id, 1), {owner}, 1,
       {pet}, 0, 1, 0
FROM (SELECT account_id FROM character_base WHERE id={owner}) a;

DELETE FROM monster_death_pet_experience WHERE pet_id = {pet};
DELETE FROM character_pets WHERE id = {pet} AND user_id = {owner};

SELECT 'pet_row', count(*)::text FROM character_pets WHERE id={pet}
UNION ALL SELECT 'skills', count(*)::text FROM character_pet_skills WHERE pet_id={pet}
UNION ALL SELECT 'stats', count(*)::text FROM character_pet_stat_values WHERE pet_id={pet}
UNION ALL SELECT 'ledger', count(*)::text FROM monster_death_pet_experience WHERE pet_id={pet}
UNION ALL SELECT 'siblings', count(*)::text FROM character_pets WHERE user_id={owner} AND id<>{pet}
UNION ALL SELECT 'audit_kept', count(*)::text FROM pet_operation_audit WHERE pet_id_snapshot={pet} AND operation='delete'
UNION ALL SELECT 'audit_nulled', count(*)::text FROM pet_operation_audit WHERE pet_id_snapshot={pet} AND operation='delete' AND pet_id IS NULL;
ROLLBACK;
"""
    print("\n=== discard sequence + assertions, inside one transaction ===")
    code, out = psql(db, script)
    if code != 0 or "ERROR" in out:
        print(out)
        return 1

    results = {}
    for line in out.splitlines():
        if "|" in line:
            key, value = line.split("|", 1)
            results[key.strip()] = value.strip()
    for key in ("pet_row", "skills", "stats", "ledger", "siblings",
                "audit_kept", "audit_nulled"):
        print(f"    {key:<14} {results.get(key, '<missing>')}")

    print("\n=== after rollback ===")
    print(f"    pet row back: "
          f"{scalar(db, f'SELECT count(*) FROM character_pets WHERE id={pet};')}"
          f"   siblings: "
          f"{scalar(db, f'SELECT count(*) FROM character_pets WHERE user_id={owner};')}")

    print("\n=== result ===")
    problems = []
    if results.get("pet_row") != "0":
        problems.append("the pet row survived")
    if results.get("skills") != "0":
        problems.append("pet skills survived")
    if results.get("stats") != "0":
        problems.append("pet stat values survived")
    if results.get("ledger") != "0":
        problems.append("the kill ledger survived")
    if results.get("siblings") != before["siblings"]:
        problems.append(
            f"a sibling pet was removed "
            f"({before['siblings']} -> {results.get('siblings')})")
    if results.get("audit_kept") != "1":
        problems.append("the audit history was not kept")
    if results.get("audit_nulled") != "1":
        problems.append("the audit row did not lose its live pet reference")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print("OK: the discarded pet and its children are gone, siblings are "
          "untouched, and the audit history survives with its snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
