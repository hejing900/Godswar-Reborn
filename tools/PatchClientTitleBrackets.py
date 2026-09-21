#!/usr/bin/env python3
"""Restore native display brackets while keeping title selection names plain."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct
import sys
import uuid

from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import Change, atomic_write, contained
from PatchClientWonderlandTitleColors import assert_client_closed, read_catalog, row
from client_patch_helpers import title_bracket_colors as native

PATCH_ID = "reborn.title-display-brackets.v2"
FORMAT_OFFSET = 0x20921
WIDTH_OFFSET = 0x21BD1
LEGACY_FORMAT = bytes.fromhex("8B44240880387C756FE962000000CC")
DISPLAY_FORMAT = bytes.fromhex("E9CA24FEFFCCCCCCCCCCCCCCCCCCCC")
LEGACY_WIDTH = bytes.fromhex("89F180BFA10900007C7465EB66CCCC")
DISPLAY_WIDTH = bytes.fromhex("89F180BFA20900007C7465EB66CCCC")
COLORS = {5009: "A335EE", 5010: "A335EE", 5011: "A335EE",
          5152: "DC143C", 5153: "FF8000", 5154: "FF8000"}
# The existing three display format hooks all target the reviewed cave. The
# selection-list lookup 555089 and its preview 5551BC never call this formatter.
HOOKS = (0x210C0, 0x21185, 0x211AD)
REQUIRED = {
    0x20991: bytes.fromhex("C744240404229500E95224FEFFCCCC"),
    0x21C41: bytes.fromhex("83E914C1E103C3CCCCCCCCCCCCCCCC"),
    0x5503F8: b"[%s]\0",
    0x552204: b"%s\0",
}


def relative_call(offset: int, target: int) -> bytes:
    return b"\xe8" + struct.pack("<i", target - (0x400000 + offset + 5))


def executable_state(data: bytes) -> str:
    if len(data) != 6676480 or data[:2] != b"MZ":
        raise PatchError("Origin.exe does not match the supported x86 title layout")
    for offset, expected in REQUIRED.items():
        if data[offset:offset + len(expected)] != expected:
            raise PatchError(f"Title prerequisite bytes differ at 0x{offset:X}")
    for offset in HOOKS:
        if data[offset:offset + 5] != relative_call(offset, 0x420921):
            raise PatchError(f"Title display hook differs at 0x{offset:X}")
    native.validate_cave_mapping(data)
    pair = data[FORMAT_OFFSET:FORMAT_OFFSET + 15], data[WIDTH_OFFSET:WIDTH_OFFSET + 15]
    cave = data[native.CAVE_OFFSET:native.CAVE_OFFSET + native.CAVE_LENGTH]
    installed = pair == (native.ENTRY, LEGACY_WIDTH) and cave == native.CAVE
    native.validate_cave_references(data, installed)
    if installed:
        return "ColoredBrackets"
    if cave != bytes(native.CAVE_LENGTH):
        raise PatchError("Title bracket color cave is occupied or partial")
    if pair == (LEGACY_FORMAT, LEGACY_WIDTH):
        return "Legacy"
    if pair == (DISPLAY_FORMAT, DISPLAY_WIDTH):
        return "DisplayBrackets"
    raise PatchError("Title formatter and width helper are partial or unsupported")


def patch_name_catalog(document, expected_state: str) -> str:
    replacements = []
    for identity, color in COLORS.items():
        match = row(document, identity)
        value = match.group().split("\t", 1)[1]
        colored = re.fullmatch(r"(\|cff" + color + r")(.+)(\|cFFFFFFFF)", value)
        if not colored:
            raise PatchError(f"Medusa title {identity} has an unsupported color or name")
        name = colored[2]
        bracketed = name.startswith("[") and name.endswith("]")
        plain = name[1:-1] if bracketed else name
        if not plain or "[" in plain or "]" in plain or "|" in plain:
            raise PatchError(f"Medusa title {identity} has an ambiguous visible name")
        if bracketed != (expected_state == "Legacy"):
            raise PatchError("Title names and executable have different patch states")
        replacements.append((match, f"{identity}\t{colored[1]}{plain}{colored[3]}"))
    result = document.text
    for match, desired in sorted(replacements, key=lambda pair: pair[0].start(), reverse=True):
        result = result[:match.start()] + desired + result[match.end():]
    return result


def build_plan(root: Path) -> list[Change]:
    executable = contained(root, root / "Origin.exe")
    before = executable.read_bytes()
    state = executable_state(before)
    after = bytearray(before)
    # The wrapper preserves stock formatting, then moves both brackets inside
    # an existing complete color span. Catalog names remain unbracketed.
    after[FORMAT_OFFSET:FORMAT_OFFSET + 15] = native.ENTRY
    after[native.CAVE_OFFSET:native.CAVE_OFFSET + native.CAVE_LENGTH] = native.CAVE
    # Colored output starts |c again, so the width probe returns to byte zero.
    after[WIDTH_OFFSET:WIDTH_OFFSET + 15] = LEGACY_WIDTH
    plan = [Change(executable, before, bytes(after))]
    for locale in ("en_us", "zh_cn"):
        directory = root / "Localization" / locale / "Text"
        path = contained(root, directory / "DesigName.dat")
        document = read_catalog(path)
        plan.append(Change(path, document.encode(document.text),
                           document.encode(patch_name_catalog(document, state))))
        # Descriptions and reward/stat text must remain identical and are
        # included in preflight, backup and postwrite verification.
        info = contained(root, directory / "DesigInfo.dat")
        content = info.read_bytes()
        plan.append(Change(info, content, content))
    return plan


def install(root: Path, plan: list[Change]) -> dict:
    selected = [change for change in plan if change.changed]
    if not selected:
        return {"status": "AlreadyMatches", "files_changed": 0}
    assert_client_closed()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex
    backup_root = contained(root, root / "backups/title-display-brackets" / stamp)
    backup_root.mkdir(parents=True, exist_ok=False)
    receipt = backup_root / "manifest.json"
    metadata = {"patch_id": PATCH_ID, "schema_version": 1, "status": "Prepared",
                "created_utc": datetime.now(timezone.utc).isoformat(), "client_root": str(root),
                "files": [change.summary(root) for change in plan]}

    def save():
        atomic_write(receipt, (json.dumps(metadata, indent=2) + "\n").encode())

    for change in plan:
        contained(root, change.path)
        backup = contained(backup_root, backup_root / change.path.relative_to(root))
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(change.before)
        if backup.read_bytes() != change.before:
            raise PatchError("Title display backup verification failed")
    save()
    written = []
    try:
        assert_client_closed()
        if any(change.path.read_bytes() != change.before for change in plan):
            raise PatchError("Title display files changed after preflight")
        for change in selected:
            if change.path.read_bytes() != change.before:
                raise PatchError("Title display file changed before replacement")
            atomic_write(change.path, change.after)
            written.append(change)
        if any(change.path.read_bytes() != change.after for change in plan):
            raise PatchError("Title display verification failed")
        metadata["status"] = "Verified"
    except BaseException:
        failures = []
        for change in reversed(written):
            try:
                current = change.path.read_bytes()
                if current == change.before:
                    continue
                if current != change.after:
                    raise PatchError("Concurrent edit preserved; restore the verified backup manually")
                atomic_write(change.path, change.before)
                if change.path.read_bytes() != change.before:
                    raise PatchError("Restored bytes differ")
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


def legacy_guard(root: Path) -> int:
    executable = root / "Origin.exe"
    if not executable.exists():
        return 2
    data = executable.read_bytes()
    entry = data[FORMAT_OFFSET:FORMAT_OFFSET + 15]
    cave = data[native.CAVE_OFFSET:native.CAVE_OFFSET + native.CAVE_LENGTH]
    if entry not in (DISPLAY_FORMAT, native.ENTRY) and \
            data[WIDTH_OFFSET:WIDTH_OFFSET + 15] != DISPLAY_WIDTH and cave != native.CAVE:
        return 2
    state = executable_state(data)
    # Both complete forward generations use plain names. The legacy installer
    # must preserve v1 as well, even while the explicit v2 upgrade is pending.
    if state not in ("DisplayBrackets", "ColoredBrackets"):
        raise PatchError("Forward title display installation is partial")
    for locale in ("en_us", "zh_cn"):
        document = read_catalog(root / "Localization" / locale / "Text/DesigName.dat")
        if patch_name_catalog(document, state) != document.text:
            raise PatchError("Forward title display catalog is partial")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, default=Path(r"C:\Godswar Origin"))
    parser.add_argument("--mode", choices=("preview", "apply", "verify", "legacy-guard"), default="preview")
    args = parser.parse_args()
    try:
        root = args.client_root.resolve()
        if args.mode == "legacy-guard":
            return legacy_guard(root)
        plan = build_plan(root)
        result = {"patch_id": PATCH_ID, "mode": args.mode, "files": [change.summary(root) for change in plan]}
        if args.mode == "apply":
            result.update(install(root, plan))
            if any(change.changed for change in build_plan(root)):
                raise PatchError("Installed title display differs")
        elif args.mode == "verify":
            if any(change.changed for change in plan):
                raise PatchError("Title display requires installation")
            result["status"] = "Verified"
        print(json.dumps(result, indent=2))
        return 0
    except (PatchError, OSError, ValueError) as error:
        print(f"Title display patch failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
