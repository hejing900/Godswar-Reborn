#!/usr/bin/env python3
"""Deterministically prepare four Socket Spell icons (Pillow12)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from socket_spell_icons import pack
from level5_forge_icons.common import InstallError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets/socket-spells")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs = pack(args.asset_root.resolve())
        changed = [p for p, data in outputs.items() if not p.exists() or p.read_bytes() != data]
        if args.check and changed:
            raise InstallError("Prepared artwork differs: " + ", ".join(str(p) for p in changed))
        for path in changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(outputs[path])
        print(json.dumps({"verified": len(outputs), "written": len(changed),
                          "preview": str(args.asset_root.resolve() / "generated/preview.png")}))
        return 0
    except (InstallError, OSError, ValueError) as error:
        print(f"Socket Spell preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
