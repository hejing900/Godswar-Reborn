"""Rebuild the migration list literal's real order and diff it against a db.

PostgresSchemaMigrationPlan.Build requires the stored history to be an exact
ordered prefix of the registered catalog, so the first differing position is the
whole diagnosis. The list mixes inlined `new("id", ...)` entries with
`Create*()` factory calls, and a factory's id lives in whichever partial file
declares it, so both have to be resolved to reconstruct the order.

Usage:
  python tools/reconstruct_migration_order.py --db-file <file>
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

MIGRATIONS = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\State\DatabaseMigrations")
CATALOG = MIGRATIONS / "PostgresSchemaMigrationCatalog.cs"

ID = r"20\d{6}_\d{3}_[a-z0-9_]+"
CREATE_CALL = re.compile(r"^\s*(?P<name>Create[A-Za-z0-9_]+)\(\),?\s*$")
ID_LINE = re.compile(rf'^\s*"(?P<id>{ID})",\s*$')
NEW_LINE = re.compile(r"^\s*new\(\s*$")


def factory_ids() -> dict[str, str]:
    """Create* method name -> migration id, across every partial file."""
    table: dict[str, str] = {}
    for path in MIGRATIONS.glob("*.cs"):
        text = path.read_text(encoding="utf-8")
        # <name>() => new(  [optional newline/indent]  "id",
        for match in re.finditer(
                rf"(?P<name>Create[A-Za-z0-9_]+)\(\)\s*=>\s*new\(\s*"
                rf'"(?P<id>{ID})"', text):
            table.setdefault(match.group("name"), match.group("id"))
    return table


def list_order(known: dict[str, str]) -> list[tuple[str, int]]:
    lines = CATALOG.read_text(encoding="utf-8").splitlines()
    field = next(i for i, line in enumerate(lines) if "> All" in line)
    start = next(i for i in range(field, len(lines)) if lines[i].strip() == "[")

    order: list[tuple[str, int]] = []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() == "];":
            break
        call = CREATE_CALL.match(line)
        if call:
            name = call.group("name")
            order.append((known.get(name, f"<UNRESOLVED {name}>"), index + 1))
            continue
        if NEW_LINE.match(line):
            for probe in range(index + 1, min(index + 4, len(lines))):
                found = ID_LINE.match(lines[probe])
                if found:
                    order.append((found.group("id"), index + 1))
                    break
    return order


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-file", required=True,
                        help="file of migration_id|checksum lines")
    args = parser.parse_args()

    known = factory_ids()
    order = list_order(known)
    print(f"factory ids resolved : {len(known)}")
    print(f"list entries built   : {len(order)}")
    unresolved = [e for e in order if e[0].startswith("<UNRESOLVED")]
    if unresolved:
        print(f"UNRESOLVED: {unresolved}")

    ids = [entry[0] for entry in order]
    ascending = all(ids[i - 1] < ids[i] for i in range(1, len(ids)))
    print(f"ascending            : {ascending}")
    if not ascending:
        for i in range(1, len(ids)):
            if ids[i - 1] >= ids[i]:
                print(f"  first descent L{order[i-1][1]} {ids[i-1]}")
                print(f"                L{order[i][1]} {ids[i]}")
                break
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    print(f"duplicates           : {duplicates or 'none'}")

    db = [line.split("|")[0]
          for line in pathlib.Path(args.db_file).read_text(
              encoding="utf-8").splitlines() if line.strip()]
    print(f"\ndb applied           : {len(db)}")

    mismatch = None
    for i in range(min(len(db), len(ids))):
        if db[i] != ids[i]:
            mismatch = i
            break
    if mismatch is None:
        print(f"prefix OK ({len(db)} of {len(ids)}); "
              f"{len(ids) - len(db)} to apply")
    else:
        print(f"FIRST MISMATCH at position {mismatch + 1}")
        for probe in range(max(0, mismatch - 2), mismatch + 4):
            left = db[probe] if probe < len(db) else "<none>"
            right = ids[probe] if probe < len(ids) else "<none>"
            mark = "   <-- differs" if left != right else ""
            print(f"  {probe + 1:>4}  db={left:<50} list={right}{mark}")

    print(f"\nlist ids missing from db: {len(set(ids) - set(db))}")
    for migration_id in ids:
        if migration_id not in set(db):
            print(f"    {migration_id}")
    print(f"db ids missing from list: {len(set(db) - set(ids))}")
    for migration_id in db:
        if migration_id not in set(ids):
            print(f"    {migration_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
