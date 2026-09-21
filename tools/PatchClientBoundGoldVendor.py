"""Install the Bound Gold Vendor's scoped Gears and Holy Suit tab captions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from holy_suit_tiers.text import Document, PatchError, replace_rows
from holy_suit_tiers.transaction import Change, contained, install


CAPTIONS = {"44": "Gears", "45": "Holy Suit"}


def build_plan(root: Path) -> list[Change]:
    changes = []
    for locale in ("en_us", "zh_cn"):
        path = contained(root, root / "Localization" / locale / "Text/EquipDescription.dat")
        before = path.read_bytes()
        document = Document.read(path)
        after = document.encode(replace_rows(document.text, CAPTIONS, document.newline,
                                             new_keys=frozenset(CAPTIONS)))
        changes.append(Change(path, before, after))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--mode", choices=("preview", "apply", "verify"), default="preview")
    args = parser.parse_args()
    try:
        root = args.client_root.resolve()
        plan = build_plan(root)
        result = {"captions": CAPTIONS, "files": [change.summary(root) for change in plan]}
        if args.mode == "apply":
            result.update(install(root, plan))
            if any(change.changed for change in build_plan(root)):
                raise PatchError("Post-install caption readback failed; inspect the backup manifest")
        elif args.mode == "verify":
            if any(change.changed for change in plan):
                raise PatchError("Bound Gold Vendor client captions need an update")
            result["status"] = "Verified"
        else:
            result["status"] = "Preview"
        print(json.dumps(result, indent=2))
        return 0
    except (PatchError, OSError, UnicodeError) as error:
        print(f"Bound Gold Vendor client patch failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
