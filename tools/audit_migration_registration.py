"""Find migration factories that are defined but never registered, and compare
the catalog against a database's applied history.

PostgresSchemaMigrationPlan.Build requires the stored history to be an exact
ordered prefix of the registered list, so a factory that exists but is never
called in the All literal is invisible to the server while remaining present in
databases that ran it earlier - which is exactly what breaks startup.

Usage: python tools/audit_migration_registration.py --db-file <file>
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import subprocess
import sys

MIGRATIONS = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\State\DatabaseMigrations")
CATALOG = MIGRATIONS / "PostgresSchemaMigrationCatalog.cs"
ID = r"20\d{6}_\d{3}_[a-z0-9_]+"

FACTORY = re.compile(
    rf"(?P<name>[A-Za-z][A-Za-z0-9_]*)\(\)\s*=>\s*new\(\s*\"(?P<id>{ID})\"")
CALL = re.compile(r"^\s*(?P<name>Create[A-Za-z0-9_]+)\(\),?\s*$")


def run(sql: str) -> str:
    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit((done.stderr or "").strip())
    return done.stdout or ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-file", required=True)
    args = parser.parse_args()

    # Every factory definition across the partial files.
    defined: dict[str, tuple[str, str]] = {}
    for path in MIGRATIONS.glob("*.cs"):
        text = path.read_text(encoding="utf-8")
        for match in FACTORY.finditer(text):
            defined.setdefault(
                match.group("name"), (match.group("id"), path.name))

    # Every factory actually called in the All literal.
    lines = CATALOG.read_text(encoding="utf-8").splitlines()
    field = next(i for i, line in enumerate(lines) if "> All" in line)
    start = next(i for i in range(field, len(lines)) if lines[i].strip() == "[")
    called: set[str] = set()
    order: list[str] = []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() == "];":
            break
        call = CALL.match(line)
        if call:
            name = call.group("name")
            called.add(name)
            resolved = defined.get(name)
            order.append((resolved[0] if resolved
                          else f"<UNRESOLVED {name}>") + f"\tL{index + 1}")
        elif re.match(r"^\s*new\(\s*$", line):
            for probe in range(index + 1, min(index + 4, len(lines))):
                found = re.match(rf'^\s*"({ID})",\s*$', lines[probe])
                if found:
                    order.append(f"{found.group(1)}\tL{index + 1}")
                    break

    print(f"factory definitions : {len(defined)}")
    print(f"factories called    : {len(called & set(defined))}")
    print(f"list entries        : {len(order)}")

    orphans = sorted(set(defined) - called)
    print(f"\n=== defined but NEVER registered: {len(orphans)} ===")
    for name in orphans:
        migration_id, source = defined[name]
        print(f"  {migration_id:<58} {name}  [{source}]")

    ids = [entry.split("\t")[0] for entry in order]
    descending = [(ids[i - 1], ids[i]) for i in range(1, len(ids))
                  if ids[i - 1] >= ids[i]]
    print(f"\nlist ascending: {not descending}")
    for previous, current in descending[:6]:
        print(f"  {previous}  >=  {current}")

    db = [line.split("|")[0]
          for line in pathlib.Path(args.db_file).read_text(
              encoding="utf-8").splitlines() if line.strip()]
    print(f"\ndb applied: {len(db)}")
    print(f"catalog-only (to apply) : {len(set(ids) - set(db))}")
    db_only = [m for m in db if m not in set(ids)]
    print(f"db-only (blocks startup): {len(db_only)}")
    for migration_id in db_only:
        print(f"  {migration_id}")

    print("\n=== db-only entries that a defined-but-unregistered factory owns ===")
    for migration_id in db_only:
        owner = [name for name, (mid, _) in defined.items() if mid == migration_id]
        if owner:
            print(f"  {migration_id}")
            print(f"      factory '{owner[0]}' exists but is not in the list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
