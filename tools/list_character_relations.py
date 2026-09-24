"""List which character-scoped objects are base tables and which are views.

Only base tables can be copied; views over them (available skills/talents, equip,
loadout, summaries) follow automatically.

Usage: python tools/list_character_relations.py --database godswar_local
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="godswar_local")
    args = parser.parse_args()

    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", args.database, "-t", "-A", "-F", "|", "-c",
         "SELECT table_name, table_type FROM information_schema.tables "
         "WHERE table_schema='public' ORDER BY table_type, table_name;"],
        capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit((done.stderr or "").strip())

    character_columns = set()
    done2 = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", args.database, "-t", "-A", "-c",
         "SELECT DISTINCT table_name FROM information_schema.columns "
         "WHERE table_schema='public' "
         "AND column_name IN ('character_id','user_id');"],
        capture_output=True, text=True, encoding="utf-8")
    for line in (done2.stdout or "").splitlines():
        if line.strip():
            character_columns.add(line.strip())

    views, tables = [], []
    for line in (done.stdout or "").splitlines():
        if "|" not in line:
            continue
        name, kind = line.split("|")
        if name not in character_columns:
            continue
        (views if kind == "VIEW" else tables).append(name)

    print(f"=== base tables ({len(tables)}) ===")
    for name in tables:
        print(f"  {name}")
    print(f"\n=== views ({len(views)}) - cannot be inserted, follow automatically ===")
    for name in views:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
