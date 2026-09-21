#!/usr/bin/env python3
"""Preview, apply, or verify the dedicated Socket Spell artwork."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from socket_spell_icons import build_plan
from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import install
from level5_forge_icons.common import InstallError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets/socket-spells")
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--repository-source", action="store_true",
                        help="Patch only tracked English item metadata in --client-root")
    parser.add_argument("--mode", choices=("preview", "apply", "verify"), default="preview")
    args = parser.parse_args(argv)
    try:
        root, assets = args.client_root.resolve(), args.asset_root.resolve()
        plan = build_plan(root, assets, repository_source=args.repository_source)
        summary = {"mode": args.mode, "files": [change.summary(root) for change in plan]}
        if args.mode == "apply":
            summary.update(install(root, plan))
            if any(c.changed for c in build_plan(root, assets, repository_source=args.repository_source)):
                raise InstallError("Post-install Socket Spell verification differs")
        elif args.mode == "verify":
            if any(c.changed for c in plan):
                raise InstallError("Socket Spell artwork requires installation")
            summary["status"] = "Verified"
        else:
            summary["status"] = "Preview"
        print(json.dumps(summary, indent=2))
        return 0
    except (InstallError, PatchError, OSError, ValueError) as error:
        print(f"Socket Spell installation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
