"""Install the reviewed RuneSteel/Arcanite/Seraphite/Divinium client content."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from holy_suit_tiers.content import build_plan
from holy_suit_tiers.policy import DIVINIUM_PERCENTAGES
from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import install


def main() -> int:
    repository = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--atlas-source", type=Path,
                        default=repository / "assets/holy-suit-wares/generated/HolySuitWare.gwo")
    parser.add_argument("--badge-atlas-source", type=Path,
                        default=repository / "assets/holy-suit-badges/generated/HolySuitBadges.gwo")
    parser.add_argument("--mode", choices=("preview", "apply", "verify"), default="preview")
    parser.add_argument("--locales", nargs="+", choices=("en_us", "zh_cn"), default=("en_us", "zh_cn"))
    args = parser.parse_args()
    try:
        root = args.client_root.resolve()
        plan = build_plan(root, args.atlas_source.resolve(), tuple(args.locales), args.badge_atlas_source.resolve())
        summary = {"divinium_percentages": DIVINIUM_PERCENTAGES,
                   "files": [change.summary(root) for change in plan]}
        if args.mode == "verify":
            if any(change.changed for change in plan):
                raise PatchError("Holy Suit client content needs an update")
            summary["status"] = "Verified"
        elif args.mode == "apply":
            summary.update(install(root, plan))
            # Complete cross-file revalidation after commit, including atlas
            # parsing and native XML syntax, rather than trusting write success.
            if any(change.changed for change in build_plan(root, args.atlas_source.resolve(), tuple(args.locales),
                                                          args.badge_atlas_source.resolve())):
                raise PatchError("Post-install content validation failed; inspect the backup manifest")
        else:
            summary["status"] = "Preview"
        print(json.dumps(summary, indent=2))
        return 0
    except (PatchError, OSError, UnicodeError) as error:
        print(f"Holy Suit client patch failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
