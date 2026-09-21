#!/usr/bin/env python3
"""Apply the agreed Wonderland title palette without changing names or rewards."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import Change, atomic_write, contained

PATCH_ID = "reborn.wonderland-title-colors.v1"
LOCALES = ("en_us", "zh_cn")
# Identity and visible names match WonderlandTitlePolicy. Rarity is cosmetic;
# server ownership, attributes, selection and island rewards are not edited.
TITLES = (
    (5155, "Gatebreaker", "Uncommon", "4FD17B"),
    (5114, "Demonbreaker", "Rare", "4AA8FF"),
    (5156, "Flamebreaker", "Rare", "56C5FF"),
    (5115, "Stonebreaker", "Epic", "A875FF"),
    (5157, "Marshal's Bane", "Epic", "CB7CFF"),
    (5116, "Dragonbane", "Legendary", "FF9F32"),
    (5117, "Hydra's Bane", "Mythic", "F45D76"),
    (5118, "Wonderland Sovereign", "Sovereign", "FFE49A"),
)


def colored(name: str, color: str) -> str:
    # Native ARGB markup used by the installed Medusa names. Do not add square
    # brackets to Wonderland's existing plain names or leak color to later text.
    return f"|cff{color}{name}|cFFFFFFFF"


def description(island: int, name: str) -> str:
    return (f"Clear Wonderland island {island} with your admitted party. Unlocks the "
            f"{name} title. Select it in the title menu.")


def read_catalog(path: Path) -> Document:
    document = Document.read(path)
    if document.encoding != "utf-16-le" or document.bom != b"\xff\xfe":
        raise PatchError("Title catalogs must retain their native UTF-16LE BOM")
    if len(document.encode(document.text)) >= 20_000:
        raise PatchError("Title catalog exceeds its supported size")
    endings = set(re.findall(r"\r\n|\r|\n", document.text))
    if len(endings) != 1 or "\r" in endings:
        raise PatchError("Title catalogs require consistent CRLF or LF rows")
    return document


def row(document: Document, identity: int) -> re.Match[str]:
    # Reject duplicate/malformed owned keys instead of silently matching one
    # valid line beside another occupied key.
    candidates = list(re.finditer(r"^" + str(identity) + r"(?=\s|$)[^\r\n]*",
                                  document.text, re.MULTILINE))
    if len(candidates) != 1 or not candidates[0].group().startswith(f"{identity}\t"):
        raise PatchError(f"Expected one complete unique owned title row {identity}")
    return candidates[0]


def patch_names(names: Document, infos: Document) -> str:
    old = []
    for island, (identity, name, rarity, color) in enumerate(TITLES, 1):
        match = row(names, identity)
        if row(infos, identity).group() != f"{identity}\t{description(island, name)}":
            raise PatchError(f"Title {identity} description differs from the owned Wonderland pair")
        old.append((match, f"{identity}\t{name}", f"{identity}\t{colored(name, color)}"))
    if all(match.group() == desired for match, plain, desired in old):
        return names.text
    if any(match.group() != plain for match, plain, desired in old):
        raise PatchError("Wonderland name set is modified, partial, or has an unknown color")
    result = names.text
    for match, plain, desired in sorted(old, key=lambda item: item[0].start(), reverse=True):
        result = result[:match.start()] + desired + result[match.end():]
    return result


def build_plan(root: Path) -> list[Change]:
    plan = []
    for locale in LOCALES:
        directory = root / "Localization" / locale / "Text"
        name_path = contained(root, directory / "DesigName.dat")
        info_path = contained(root, directory / "DesigInfo.dat")
        names, infos = read_catalog(name_path), read_catalog(info_path)
        before = names.encode(names.text)
        after = names.encode(patch_names(names, infos))
        if len(after) >= 20_000:
            raise PatchError("Colored title catalog would exceed its supported size")
        # The unchanged descriptions participate in backup and preflight checks.
        plan.extend((Change(name_path, before, after),
                     Change(info_path, infos.encode(infos.text), infos.encode(infos.text))))
    return plan


def assert_client_closed() -> None:
    if os.name != "nt":
        return
    check = subprocess.run([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "$p=@(Get-Process -ErrorAction SilentlyContinue | Where-Object { "
        "$_.ProcessName -match '^(Origin|Origin_sixsocket|GWPrivateServer|gworiginsv|GodsWar)$' }); "
        "if($p.Count -gt 0){exit 3}"], capture_output=True, timeout=15)
    if check.returncode != 0:
        raise PatchError("Close the GodsWar client before installing title colors")


def install(root: Path, plan: list[Change]) -> dict:
    selected = [change for change in plan if change.changed]
    if not selected:
        return {"status": "AlreadyMatches", "files_changed": 0}
    assert_client_closed()
    for change in plan:
        contained(root, change.path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex
    backup_root = contained(root, root / "backups/wonderland-title-colors" / stamp)
    backup_root.mkdir(parents=True, exist_ok=False)
    receipt = backup_root / "manifest.json"
    metadata = {"patch_id": PATCH_ID, "schema_version": 1, "status": "Prepared",
                "created_utc": datetime.now(timezone.utc).isoformat(), "client_root": str(root),
                "files": [change.summary(root) for change in plan], "palette": TITLES}

    def save() -> None:
        atomic_write(receipt, (json.dumps(metadata, indent=2) + "\n").encode())

    for change in plan:
        backup = contained(backup_root, backup_root / change.path.relative_to(root))
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(change.before)
        if backup.read_bytes() != change.before:
            raise PatchError("Title backup verification failed")
    save()
    written = []
    try:
        assert_client_closed()
        for change in plan:
            if change.path.read_bytes() != change.before:
                raise PatchError("Title catalog changed after preflight")
        for change in selected:
            if change.path.read_bytes() != change.before:
                raise PatchError("Title catalog changed before replacement")
            atomic_write(change.path, change.after)
            written.append(change)
            if change.path.read_bytes() != change.after:
                raise PatchError("Title catalog readback failed")
        if any(change.path.read_bytes() != change.after for change in plan):
            raise PatchError("Title catalogs changed during installation")
        metadata["status"] = "Verified"
    except BaseException:
        failures = []
        for change in reversed(written):
            try:
                current = change.path.read_bytes()
                if current == change.before:
                    continue
                if current != change.after:
                    raise PatchError("Concurrent title edit preserved; restore the verified backup manually")
                atomic_write(change.path, change.before)
                if change.path.read_bytes() != change.before:
                    raise PatchError("Restored title bytes differ")
            except Exception as error:
                failures.append(f"{change.path}: {error}")
        metadata["status"] = "RollbackFailed" if failures else "RolledBack"
        if failures:
            metadata["rollback_errors"] = failures
            raise PatchError(f"Restore verified backups from {backup_root}: {failures}")
        raise
    finally:
        save()
    return {"status": "Verified", "files_changed": len(selected), "backup_manifest": str(receipt)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--mode", choices=("preview", "apply", "verify"), default="preview")
    args = parser.parse_args()
    try:
        root = args.client_root.resolve()
        plan = build_plan(root)
        result = {"patch_id": PATCH_ID, "mode": args.mode, "files": [c.summary(root) for c in plan],
                  "palette": [{"island": i, "title_id": t[0], "name": t[1], "rarity": t[2],
                               "rgb": "#" + t[3]} for i, t in enumerate(TITLES, 1)]}
        if args.mode == "apply":
            result.update(install(root, plan))
            if any(c.changed for c in build_plan(root)):
                raise PatchError("Installed Wonderland title colors differ")
        elif args.mode == "verify":
            if any(c.changed for c in plan):
                raise PatchError("Wonderland title colors require installation")
            result["status"] = "Verified"
        print(json.dumps(result, indent=2))
        return 0
    except (PatchError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Wonderland title colors failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
