"""Bounded multi-file installation with exact backups and rollback."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

from .text import PatchError


def digest(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest().upper()


def contained(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
        raise PatchError(f"Path escaped the selected client root: {path}")
    return resolved


@dataclass(frozen=True)
class Change:
    path: Path
    before: bytes | None
    after: bytes

    @property
    def changed(self) -> bool:
        return self.before != self.after

    def summary(self, root: Path) -> dict[str, object]:
        return {"path": str(self.path.relative_to(root)), "changed": self.changed,
                "before_sha256": digest(self.before), "after_sha256": digest(self.after),
                "before_bytes": None if self.before is None else len(self.before), "after_bytes": len(self.after)}


def atomic_write(path: Path, data: bytes) -> None:
    stage = path.with_name(path.name + "." + uuid.uuid4().hex + ".stage")
    try:
        with stage.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(stage, path)
    finally:
        if stage.exists():
            stage.unlink()


def install(root: Path, changes: list[Change]) -> dict[str, object]:
    selected = [change for change in changes if change.changed]
    if not selected:
        return {"status": "AlreadyMatches", "files_changed": 0}
    root = root.resolve()
    for change in changes:
        contained(root, change.path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex
    backup_root = contained(root, root / "backups" / "holy-suit-tiers" / stamp)
    backup_root.mkdir(parents=True, exist_ok=False)
    manifest_path = backup_root / "manifest.json"
    manifest: dict[str, object] = {"schema_version": 1, "status": "Prepared", "client_root": str(root),
                                  "created_utc": datetime.now(timezone.utc).isoformat(),
                                  "files": [change.summary(root) for change in changes]}

    def save_manifest() -> None:
        atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))

    for change in changes:
        if change.before is None:
            continue
        backup = contained(backup_root, backup_root / change.path.relative_to(root))
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(change.before)
        if backup.read_bytes() != change.before:
            raise PatchError(f"Backup verification failed: {backup}")
    save_manifest()
    written: list[Change] = []
    try:
        # All inputs, including unchanged prerequisites, remain part of the
        # preflight snapshot. A concurrent patch aborts before publication.
        for change in changes:
            current = change.path.read_bytes() if change.path.exists() else None
            if current != change.before:
                raise PatchError(f"Client file changed after preflight: {change.path}")
        for change in selected:
            current = change.path.read_bytes() if change.path.exists() else None
            if current != change.before:
                raise PatchError(f"Client file changed before replacement: {change.path}")
            change.path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(change.path, change.after)
            written.append(change)
            if change.path.read_bytes() != change.after:
                raise PatchError(f"Installed file readback failed: {change.path}")
        manifest["status"] = "Verified"
    except BaseException:
        failures: list[str] = []
        for change in reversed(written):
            try:
                if change.before is None:
                    change.path.unlink()
                else:
                    atomic_write(change.path, change.before)
                restored = change.path.read_bytes() if change.path.exists() else None
                if restored != change.before:
                    raise PatchError("restored bytes differ")
            except Exception as error:
                failures.append(f"{change.path}: {error}")
        manifest["status"] = "RollbackFailed" if failures else "RolledBack"
        if failures:
            manifest["rollback_errors"] = failures
            raise PatchError(f"Rollback failed; restore verified backups from {backup_root}: {failures}")
        raise
    finally:
        save_manifest()
    return {"status": "Verified", "files_changed": len(selected), "backup_manifest": str(manifest_path)}
