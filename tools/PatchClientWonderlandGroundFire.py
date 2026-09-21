#!/usr/bin/env python3
"""Add a coordinate-only Fire Blast presentation while preserving native skill580."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid

from PatchClientWonderlandStatus import assert_client_closed
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import Change, atomic_write, contained

MANIFEST = Path(__file__).with_name('client_patch_helpers') / 'WonderlandGroundFire.json'
LOCALES = ('en_us', 'zh_cn')
VISUAL_ID = 589


def source_section(locale: str) -> str:
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest['source_id'] != 580 or manifest['visual_id'] != VISUAL_ID or \
            manifest['effect_file'] != 'effect_fire_002_all.gwm':
        raise PatchError('Unreviewed ground-fire identity manifest')
    return manifest['source_sections'][locale]


def blocks(text: str, identity: int) -> list[str]:
    headers = list(re.finditer(r'^\[(\d+)\][ \t]*\r?$', text, re.MULTILINE))
    return [text[match.start():headers[i + 1].start() if i + 1 < len(headers) else len(text)]
            .replace('\r\n', '\n').rstrip('\n')
            for i, match in enumerate(headers) if int(match[1]) == identity]


def alias_section(locale: str) -> str:
    original = source_section(locale)
    if original.count('\nTarget=1\n') != 1 or \
            '\nEffectFile1=effect_fire_002_all.gwm\n' not in original:
        raise PatchError('Fire Blast source does not match the verified native coordinate prerequisite')
    return original.replace('[580]', f'[{VISUAL_ID}]', 1).replace('\nTarget=1\n', '\nTarget=17\n', 1)


def patch_text(document: Document, locale: str) -> str:
    if locale not in LOCALES:
        raise PatchError('Unsupported locale')
    if blocks(document.text, 580) != [source_section(locale)]:
        raise PatchError('Native Fire Blast580 is missing, duplicated or modified')
    alias = alias_section(locale)
    existing = blocks(document.text, VISUAL_ID)
    if existing:
        if existing != [alias]:
            raise PatchError('Ground-fire alias589 is already occupied, duplicated or modified')
        return document.text
    newline = document.newline
    return document.text + ('' if document.text.endswith('\n') else newline) + newline + \
        alias.replace('\n', newline) + newline


def build_plan(root: Path) -> list[Change]:
    result = []
    for locale in LOCALES:
        path = contained(root, root / 'Localization' / locale / 'Settings/Sys/Magic.ini')
        document = Document.read(path)
        if document.encoding != 'utf-16-le' or document.bom != b'\xff\xfe':
            raise PatchError('Magic.ini must preserve native UTF-16LE with BOM')
        result.append(Change(path, document.encode(document.text), document.encode(patch_text(document, locale))))
    effect = contained(root, root / 'Effect/effect_fire_002_all.gwm')
    if not effect.is_file() or effect.stat().st_size == 0:
        raise PatchError('The actual native Fire Blast effect asset is missing')
    return result


def install(root: Path, plan: list[Change]) -> dict:
    selected = [change for change in plan if change.changed]
    if not selected:
        return {'status': 'AlreadyMatches', 'files_changed': 0}
    assert_client_closed()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex
    backup = contained(root, root / 'backups/wonderland-ground-fire' / stamp)
    backup.mkdir(parents=True, exist_ok=False)
    receipt = backup / 'manifest.json'
    record = {'patch_id': 'reborn.wonderland-ground-fire.v1', 'status': 'Prepared',
              'files': [change.summary(root) for change in plan]}
    def save():
        atomic_write(receipt, (json.dumps(record, indent=2) + '\n').encode())
    for change in plan:
        path = contained(backup, backup / change.path.relative_to(root))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(change.before)
        if path.read_bytes() != change.before:
            raise PatchError('Ground-fire backup verification failed')
    save()
    written = []
    try:
        assert_client_closed()
        for change in plan:
            if change.path.read_bytes() != change.before:
                raise PatchError('Magic.ini changed after preflight')
        for change in selected:
            if change.path.read_bytes() != change.before:
                raise PatchError('Magic.ini changed before replacement')
            atomic_write(change.path, change.after)
            written.append(change)
            if change.path.read_bytes() != change.after:
                raise PatchError('Installed Magic.ini readback failed')
        record['status'] = 'Verified'
    except BaseException:
        failures = []
        for change in reversed(written):
            try:
                current = change.path.read_bytes()
                if current != change.before:
                    if current != change.after:
                        raise PatchError('Concurrent edits preserved; restore the verified backup manually')
                    atomic_write(change.path, change.before)
                if change.path.read_bytes() != change.before:
                    raise PatchError('Restored Magic.ini differs')
            except Exception as error:
                failures.append(str(error))
        record['status'] = 'RollbackFailed' if failures else 'RolledBack'
        if failures:
            record['rollback_errors'] = failures
        raise
    finally:
        save()
    return {'status': 'Verified', 'files_changed': len(selected), 'backup_manifest': str(receipt)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-root', type=Path, default=Path(r'C:\Godswar Origin'))
    parser.add_argument('--mode', choices=('preview', 'apply', 'verify'), default='preview')
    args = parser.parse_args()
    try:
        root = args.client_root.resolve()
        plan = build_plan(root)
        if args.mode == 'verify' and any(change.changed for change in plan):
            raise PatchError('Ground-fire client definition is not installed')
        result = install(root, plan) if args.mode == 'apply' else {
            'status': 'Verified' if args.mode == 'verify' else 'Preview',
            'files': [change.summary(root) for change in plan]}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, PatchError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
