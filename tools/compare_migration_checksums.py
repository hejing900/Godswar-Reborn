"""Compare each registered migration's checksum with the applied one.

PostgresSchemaMigrationPlan.Build fails when a stored checksum differs from the
registered one for the same id, and the structured console swallows the message,
so this prints the offending rows directly.

Usage:
  python tools/compare_migration_checksums.py --probe <probe.txt> --db <db.txt>
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", required=True,
                        help="probe output: [probe] <n>\\t<id>\\t<checksum>")
    parser.add_argument("--db", required=True,
                        help="psql output: <id>|<checksum>")
    args = parser.parse_args()

    registered: list[tuple[str, str]] = []
    for line in pathlib.Path(args.probe).read_text(
            encoding="utf-8").splitlines():
        match = re.match(r"^\[probe\]\s+(\d+)\t([^\t]+)\t([0-9A-F]+)$", line)
        if match:
            registered.append((match.group(2), match.group(3)))

    applied: dict[str, str] = {}
    for line in pathlib.Path(args.db).read_text(
            encoding="utf-8").splitlines():
        parts = line.split("|")
        if len(parts) >= 2:
            applied[parts[0]] = parts[1]

    print(f"registered: {len(registered)}   applied: {len(applied)}")
    missing = [mid for mid, _ in registered if mid not in applied]
    print(f"not yet applied: {len(missing)}")

    mismatched = []
    for migration_id, checksum in registered:
        stored = applied.get(migration_id)
        if stored is not None and stored != checksum:
            mismatched.append((migration_id, stored, checksum))

    print(f"\n=== checksum mismatches: {len(mismatched)} ===")
    for migration_id, stored, expected in mismatched:
        print(f"  {migration_id}")
        print(f"      db  : {stored}")
        print(f"      code: {expected}")
    if not mismatched:
        print("  none - the registered prefix is consistent with the database")
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
