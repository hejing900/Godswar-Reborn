#!/usr/bin/env python3
"""Preview, apply, or verify the four Holy Stone/Spirit client atlas files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from holy_stone_icons.installation import build_plan
from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import install
from level5_forge_icons.common import InstallError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets/holy-stones-and-spirits")
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--mode", choices=("preview", "apply", "verify"), default="preview")
    args = parser.parse_args(argv)
    try:
        root, assets = args.client_root.resolve(), args.asset_root.resolve()
        plan = build_plan(root, assets)
        summary = {"mode": args.mode, "files": [change.summary(root) for change in plan]}
        if args.mode == "apply":
            summary.update(install(root, plan))
            if any(change.changed for change in build_plan(root, assets)):
                raise InstallError("Post-install Holy Stone artwork verification differs")
        elif args.mode == "verify":
            if any(change.changed for change in plan):
                raise InstallError("Holy Stone artwork requires installation")
            summary["status"] = "Verified"
        else:
            summary["status"] = "Preview"
        print(json.dumps(summary, indent=2))
        return 0
    except (InstallError, PatchError, OSError, ValueError) as error:
        print(f"Holy Stone artwork installation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
