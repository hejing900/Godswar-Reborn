#!/usr/bin/env python3
"""Preview, apply, or verify accurate Holy Spirit help and reachable Zephyr navigation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from holy_spirit_help.patch import build_plan
from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import install


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--mode", choices=("preview", "apply", "verify"), default="preview")
    args = parser.parse_args()
    try:
        root = args.client_root.resolve()
        plan = build_plan(root)
        result = {"mode": args.mode, "files": [c.summary(root) for c in plan]}
        if args.mode == "apply":
            result.update(install(root, plan))
            if any(c.changed for c in build_plan(root)):
                raise PatchError("Holy Spirit help readback differs")
        elif args.mode == "verify":
            if any(c.changed for c in plan):
                raise PatchError("Holy Spirit help requires installation")
            result["status"] = "Verified"
        else:
            result["status"] = "Preview"
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, PatchError) as error:
        print(f"Holy Spirit help installation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
