"""Confirm the publisher's provenance label equals the deployed realm's.

Usage: python tools/verify_publication_source.py
"""
from __future__ import annotations

import subprocess
import sys

CODE = ("items-v9+pets-v7+nameplates-v1+warehouse-v1+opal-v1+holy-v5+"
        "holy-stones-v3+sockets-v2+ascension-v1+wonderland-v1+exp-pill-v1")


def main() -> int:
    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c",
         "SELECT source FROM item_template_content_revisions "
         "ORDER BY entry_count DESC LIMIT 1;"],
        capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit((done.stderr or "").strip())
    deployed = (done.stdout or "").strip()

    print(f"deployed length: {len(deployed)}")
    print(f"code     length: {len(CODE)}")
    print(f"identical      : {deployed == CODE}")
    if deployed != CODE:
        print(f"\ndeployed: {deployed}")
        print(f"code    : {CODE}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
