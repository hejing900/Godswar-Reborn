#!/usr/bin/env python3
"""Install Wonderland status icons and native stun/silence controls safely."""
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

DEFINITIONS = Path(__file__).with_name("client_patch_helpers") / "WonderlandStatuses.json"
LEGACY_DEFINITIONS = DEFINITIONS.with_name("WonderlandStatuses.v1.json")
PATCH_ID = "reborn.wonderland-status.v2"
LOCALES = ("en_us", "zh_cn")
CONTROL_EFFECTS = {1512: [0, 2, 3, 4, 5, 6], 1513: [3, 4]}
NATIVE_CONTROLS = {
    330: {"Effect": "0,2,3,4,5,6", "Values": "1,1,1,1,1,1", "Interval": "0,0,0,0,0,0", "IconPos": "252,108"},
    360: {"Effect": "3,4", "Values": "1,1", "Interval": "0,0", "IconPos": "540,72"}}


def definitions(path: Path = DEFINITIONS) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if [r["id"] for r in rows] != list(range(1510, 1516)):
        raise PatchError("Unexpected Wonderland status identity manifest")
    for row in rows:
        expected = CONTROL_EFFECTS.get(row["id"], [-1]) if path == DEFINITIONS else [-1]
        if row.get("effects", [-1]) != expected:
            raise PatchError("Wonderland status manifest contains unsupported native effects")
    return rows


def section(row: dict, locale: str, newline: str) -> str:
    text = row[locale]
    effects = row.get("effects", [-1])
    return newline.join([
        f'[{row["id"]}]', f'Name={text["name"]}', f'Style={row["style"]}',
        f'Kind={row["kind"]}', 'Priority=1', 'Effect=' + ','.join(map(str, effects)),
        'Values=' + ','.join('0' if effect == -1 else '1' for effect in effects),
        'Interval=' + ','.join('0' for _ in effects),
        f'Time={row["seconds"]}', f'Note={text["note"]}', f'IconPos={row["icon"]}',
        'IconSize=36,36', 'EffectDisplay=-1', 'RideId=-1', 'Action=1'])


def patch_text(document: Document, locale: str) -> str:
    if locale not in LOCALES:
        raise PatchError("Unsupported Wonderland status locale")
    headers = list(re.finditer(r"^\[(\d+)\][ \t]*\r?$", document.text, re.MULTILINE))
    if not headers:
        raise PatchError("Status.ini contains no status definitions")
    existing: dict[int, str] = {}
    spans: dict[int, tuple[int, int]] = {}
    for index, match in enumerate(headers):
        identity = int(match[1])
        if identity in existing:
            raise PatchError(f"Duplicate status [{identity}]")
        end = headers[index + 1].start() if index + 1 < len(headers) else len(document.text)
        existing[identity] = document.text[match.start():end].replace("\r\n", "\n").rstrip("\r\n")
        spans[identity] = (match.start(), end)
    rows = definitions()
    expected = {r["id"]: section(r, locale, "\n") for r in rows}
    for identity, fields in NATIVE_CONTROLS.items():
        for key, value in fields.items():
            if re.findall(r"(?m)^" + key + r"=(.*)$", existing.get(identity, "")) != [value]:
                raise PatchError(f"Native control status [{identity}] {key} differs from the verified client")
    # Verify icon prerequisites and kind ownership even on an existing install.
    for row in rows:
        if not re.search(r"(?m)^IconPos=" + re.escape(row["icon"]) + r"\r?$", document.text):
            raise PatchError(f'Expected existing status icon {row["icon"]} was not found')
        if any(re.search(r"(?m)^Kind=" + str(row["kind"]) + r"$", block)
               for identity, block in existing.items() if identity not in expected):
            raise PatchError(f'Status kind {row["kind"]} is already in use')
    present = [identity for identity in expected if identity in existing]
    if present:
        if len(present) == len(expected) and all(existing[i] == expected[i] for i in present):
            return document.text
        legacy = {r["id"]: section(r, locale, "\n") for r in definitions(LEGACY_DEFINITIONS)}
        if len(present) != len(expected) or any(existing[i] != legacy[i] for i in present):
            raise PatchError("Wonderland status IDs are occupied, partial, or modified")
        # Only a complete exact v1 set can be upgraded. Preserve all surrounding
        # bytes, including blank separators and unrelated following sections.
        result = document.text
        for row in sorted(rows, key=lambda item: spans[item["id"]][0], reverse=True):
            if existing[row["id"]] == expected[row["id"]]:
                continue
            start, end = spans[row["id"]]
            block = document.text[start:end]
            tail = block[len(block.rstrip("\r\n")):]
            result = result[:start] + section(row, locale, document.newline) + tail + result[end:]
        return result
    newline = document.newline
    return document.text + ("" if document.text.endswith("\n") else newline) + newline + \
        (newline + newline).join(section(r, locale, newline) for r in rows) + newline


def build_plan(root: Path) -> list[Change]:
    result = []
    for locale in LOCALES:
        path = contained(root, root / "Localization" / locale / "Settings/Sys/Status.ini")
        document = Document.read(path)
        if document.encoding != "utf-16-le" or document.bom != b"\xff\xfe":
            raise PatchError("Status.ini must retain its native UTF-16LE BOM")
        # Keep the exact bytes represented by this parsed snapshot. A second
        # read here could accidentally adopt another editor's newer preimage.
        result.append(Change(path, document.encode(document.text), document.encode(patch_text(document, locale))))
    return result


def assert_client_closed() -> None:
    if os.name != "nt":
        return
    # No command lines or account data are queried. Recheck immediately before
    # publication; a running game keeps the old definitions in memory.
    check = subprocess.run([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "$p=@(Get-Process -ErrorAction SilentlyContinue | Where-Object { "
        "$_.ProcessName -match '^(Origin|Origin_sixsocket|GWPrivateServer|gworiginsv)$' }); "
        "if($p.Count -gt 0){exit 3}"], capture_output=True, timeout=15)
    if check.returncode != 0:
        raise PatchError("Close the GodsWar client before installing Wonderland status definitions")


def install(root: Path, plan: list[Change]) -> dict:
    selected = [c for c in plan if c.changed]
    if not selected:
        return {"status": "AlreadyMatches", "files_changed": 0}
    assert_client_closed()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex
    backup_root = contained(root, root / "backups/wonderland-status" / stamp)
    backup_root.mkdir(parents=True, exist_ok=False)
    receipt = backup_root / "manifest.json"
    metadata = {"patch_id": PATCH_ID, "status": "Prepared", "client_root": str(root),
                "files": [c.summary(root) for c in plan]}
    def save() -> None:
        atomic_write(receipt, (json.dumps(metadata, indent=2) + "\n").encode())
    for change in plan:
        backup = contained(backup_root, backup_root / change.path.relative_to(root))
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(change.before)
        if backup.read_bytes() != change.before:
            raise PatchError("Status backup verification failed")
    save()
    written = []
    try:
        assert_client_closed()
        for change in plan:
            if change.path.read_bytes() != change.before:
                raise PatchError("Status.ini changed after preflight")
        for change in selected:
            if change.path.read_bytes() != change.before:
                raise PatchError("Status.ini changed before replacement")
            atomic_write(change.path, change.after)
            written.append(change)
            if change.path.read_bytes() != change.after:
                raise PatchError("Status.ini readback failed")
        metadata["status"] = "Verified"
    except BaseException:
        failures = []
        for change in reversed(written):
            try:
                current = change.path.read_bytes()
                if current == change.before:
                    continue
                if current != change.after:
                    raise PatchError("Concurrent status changes preserved; restore the verified backup manually")
                atomic_write(change.path, change.before)
                if change.path.read_bytes() != change.before:
                    raise PatchError("Restored status bytes differ")
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
        result = {"patch_id": PATCH_ID, "mode": args.mode, "files": [c.summary(root) for c in plan]}
        if args.mode == "apply":
            result.update(install(root, plan))
            if any(c.changed for c in build_plan(root)):
                raise PatchError("Installed Wonderland status readback differs")
        elif args.mode == "verify":
            if any(c.changed for c in plan):
                raise PatchError("Wonderland status definitions require installation")
            result["status"] = "Verified"
        print(json.dumps(result, indent=2))
        return 0
    except (PatchError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Wonderland status patch failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
