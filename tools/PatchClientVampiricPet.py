#!/usr/bin/env python3
"""Preview/install Vampiric pet skills and books without changing native binaries."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid
import xml.etree.ElementTree as ET

from PatchClientWonderlandStatus import assert_client_closed
from holy_suit_tiers.text import Document, PatchError, replace_rows
from holy_suit_tiers.transaction import Change, atomic_write, contained

PATCH_ID = 'reborn.vampiric-pet.v1'
LOCALES = ('en_us', 'zh_cn')
PERCENTAGES = (6, 8, 11, 14, 17, 20)
ACCURACY = (0, 64, 192, 235, 270, 305)
ROMANS = ('I', 'II', 'III', 'IV', 'V', 'VI')
FAMILY = 428
SKILL_START, BOOK_START = 6400, 16400
PET_ANCHOR = {'ID': '6300', 'Name': 'Pet6300', 'Info': 'PetInfo6300',
    'IconPos': '684,792', 'Genre': '34', 'Trait': '0,0,0,0,0,0', 'Type': '426',
    'Add': '1', 'Priority': '1', 'Flag': '1', 'Effect': '34',
    'NextID': '6300,6301,6302,6303', 'fact_Value': '90',
    'Restrict': '0,9,13,21', 'Values': '90,169,225,241'}
BOOK_ANCHOR = {'ID': '10225', 'Type': 'consume item',
    'Texture': './Localization/en_us/UI/Texture/Icon2.gwo', 'Icon': '216,972',
    'Random': '0', 'Distribution': '0,0', 'Money': '0', 'Overlap': '99',
    'Use': '1', 'ItemType': '4', 'PetSkill': '2005'}


def skill_rows() -> list[dict[str, str]]:
    return [dict(ID=str(SKILL_START + tier), Name=f'Pet{SKILL_START + tier}',
        Info=f'PetInfo{SKILL_START + tier}', IconPos='684,792', Genre='34',
        Trait=f'0,0,{ACCURACY[tier] * 100},0,0,0', Type=str(FAMILY), Add='1',
        Priority=str(tier + 1), Flag='1', Effect='34', NextID=str(SKILL_START + tier),
        # Native fact_Value is atoi, a FLAT presentation value. The server's
        # family428 owns percentage healing; never add a native flat bonus.
        fact_Value='0', Restrict='0', Values=f'{percent / 100:.2f}')
        for tier, percent in enumerate(PERCENTAGES)]


def book_rows() -> list[dict[str, str]]:
    return [dict(BOOK_ANCHOR, ID=str(BOOK_START + tier),
                 ItemType='4' if tier == 0 else '3', PetSkill=str(SKILL_START + tier))
            for tier in range(6)]


def tooltip(tier: int) -> str:
    return (f'|cFFFFFFFFVampiric {ROMANS[tier]}. Restores the owner\'s HP by '
            f'|cFF39d8b8{PERCENTAGES[tier]}% of damage actually inflicted|cFFFFFFFF '
            'on each successful attack or damaging skill hit while this pet is carried. '
            'Applies separately to each damaged target. No healing from missed or zero-damage hits.')


def labels(kind: str) -> dict[str, str]:
    result = {}
    for tier in range(6):
        if kind == 'pet':
            result[f'Pet{SKILL_START + tier}'] = f'Vampiric {ROMANS[tier]}'
            result[f'PetInfo{SKILL_START + tier}'] = tooltip(tier)
        elif kind == 'name':
            result[f'Pet{BOOK_START + tier}'] = f'Pet Skill: Vampiric {ROMANS[tier]}'
        elif kind == 'description':
            requirement = ('Requires an empty unlocked pet skill slot.' if tier == 0 else
                           f'Requires Vampiric {ROMANS[tier - 1]} and {ACCURACY[tier]} Accuracy.')
            result[f'Pet{BOOK_START + tier}'] = tooltip(tier) + ' ' + requirement
        else:
            raise PatchError('Unknown Vampiric text kind')
    return result


def load_document(path: Path, *, pet_xml: bool = False) -> Document:
    raw = path.read_bytes()
    if pet_xml and raw.startswith(b'<?xml version="1.0" encoding="GB2312"?>'):
        # This native file contains legacy GB2312 bytes in comments. Latin1
        # gives a reversible byte mapping; all inserted attributes are ASCII.
        text = raw.decode('latin1')
        if not raw or len(raw) > 4_000_000 or '\x00' in text:
            raise PatchError('Unsupported native pet XML')
        return Document(text, 'latin1', b'', '\r\n' if '\r\n' in text else '\n')
    return Document.read(path)


def extend_xml(document: Document, rows: list[dict[str, str]],
               anchor: dict[str, str], *, pet: bool) -> str:
    try:
        tree = ET.fromstring(document.text)
    except ET.ParseError as error:
        raise PatchError('Malformed client XML') from error
    expected_root = 'PetSkill' if pet else 'ItemBaseAttribute'
    if tree.tag != expected_root:
        raise PatchError('Unexpected client XML root')
    anchors = [node for node in tree.iter() if node.get('ID') == anchor['ID']]
    if len(anchors) != 1 or anchors[0].attrib != anchor or anchors[0].tag != 'Pet' + anchor['ID']:
        raise PatchError('Native lifedrain icon/book prerequisite changed')
    parents = {child: parent for parent in tree.iter() for child in parent}
    parent = parents[anchors[0]]
    wanted = {row['ID'] for row in rows}
    if pet and any(node.get('Type') == str(FAMILY) and node.get('ID') not in wanted
                   for node in tree.iter()):
        raise PatchError('Vampiric family428 is occupied by another skill')
    missing = []
    for row in rows:
        nodes = [node for node in tree.iter() if node.get('ID') == row['ID']]
        if nodes:
            if len(nodes) != 1 or nodes[0].attrib != row or nodes[0].tag != 'Pet' + row['ID'] or \
                    parents.get(nodes[0]) is not parent or len(nodes[0]):
                raise PatchError(f'Vampiric ID{row["ID"]} is occupied, modified or duplicated')
        else:
            missing.append('        <Pet' + row['ID'] + ' ' +
                           ' '.join(f'{key}="{value}"' for key, value in row.items()) + '/>')
    if not missing:
        return document.text
    matches = list(re.finditer(r'<Pet' + anchor['ID'] + r'(?=\s)[^>]*?/>', document.text))
    if len(matches) != 1:
        raise PatchError('Native insertion anchor is ambiguous')
    offset = matches[0].start()
    # Insert directly before the known sibling without reserializing XML or
    # normalizing any unowned encoding, attribute or whitespace.
    return document.text[:offset] + document.newline.join(missing).lstrip() + \
        document.newline + '        ' + document.text[offset:]


def build_plan(client_root: Path, repository_root: Path | None = None) -> list[Change]:
    client_root = client_root.resolve()
    if repository_root is not None:
        repository_root = repository_root.resolve()
        if client_root == repository_root or client_root.is_relative_to(repository_root) or \
                repository_root.is_relative_to(client_root):
            raise PatchError('Client and repository roots must be distinct non-nested directories')
    changes = []
    targets = [(client_root, locale, False) for locale in LOCALES]
    if repository_root is not None:
        targets.append((repository_root, 'en_us', True))
    for root, locale, repository in targets:
        base = root / 'Localization' / locale
        xmls = [('Settings/Sys/ItemBaseAttribute.xml', False)]
        texts = [('Text/EquipName.dat', 'name'), ('Text/EquipDescription.dat', 'description')]
        if not repository:
            xmls.insert(0, ('Settings/Sys/Pet_Skill.xml', True))
            texts.insert(0, ('Text/Message_Pet.dat', 'pet'))
            for asset in ('Icon.gwo', 'Icon2.gwo'):
                path = contained(root, base / 'UI/Texture' / asset)
                if not path.is_file() or path.stat().st_size == 0:
                    raise PatchError(f'Required existing native icon atlas is absent: {asset}')
        for relative, pet in xmls:
            path = contained(root, base / relative)
            before = path.read_bytes()
            document = load_document(path, pet_xml=pet)
            after = document.encode(extend_xml(document, skill_rows() if pet else book_rows(),
                                               PET_ANCHOR if pet else BOOK_ANCHOR, pet=pet))
            changes.append(Change(path, before, after))
        for relative, kind in texts:
            path = contained(root, base / relative)
            before = path.read_bytes()
            document = load_document(path)
            values = labels(kind)
            after = document.encode(replace_rows(document.text, values, document.newline,
                                                 new_keys=frozenset(values)))
            changes.append(Change(path, before, after))
    return changes


def summarize(client_root: Path, repository_root: Path | None, changes: list[Change]) -> list[dict]:
    result = []
    for change in changes:
        client = change.path.is_relative_to(client_root.resolve())
        root = client_root if client else repository_root
        if root is None:
            raise PatchError('Unowned patch path')
        contained(root, change.path)
        result.append(dict(change.summary(root), root='client' if client else 'repository'))
    return result


def install(client_root: Path, repository_root: Path | None, changes: list[Change]) -> dict:
    metadata = summarize(client_root, repository_root, changes)
    selected = [change for change in changes if change.changed]
    if not selected:
        return {'status': 'AlreadyMatches', 'files_changed': 0}
    assert_client_closed()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex
    backup = contained(client_root, client_root / 'backups/vampiric-pet' / stamp)
    backup.mkdir(parents=True, exist_ok=False)
    receipt = backup / 'manifest.json'
    record = {'patch_id': PATCH_ID, 'status': 'Prepared', 'files': metadata}
    def save():
        atomic_write(receipt, (json.dumps(record, indent=2) + '\n').encode())
    for change, summary in zip(changes, metadata, strict=True):
        path = contained(backup, backup / summary['root'] / summary['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(change.before)
        if path.read_bytes() != change.before:
            raise PatchError('Vampiric backup verification failed')
    save()
    written = []
    try:
        assert_client_closed()
        for change in changes:
            if change.path.read_bytes() != change.before:
                raise PatchError('Client/repository input changed after preflight')
        for change in selected:
            if change.path.read_bytes() != change.before:
                raise PatchError('Input changed before replacement')
            atomic_write(change.path, change.after)
            written.append(change)
            if change.path.read_bytes() != change.after:
                raise PatchError('Vampiric installed readback differs')
        record['status'] = 'Verified'
    except BaseException:
        failures = []
        for change in reversed(written):
            try:
                current = change.path.read_bytes()
                if current not in (change.before, change.after):
                    raise PatchError('Concurrent content retained; inspect exact backup')
                atomic_write(change.path, change.before)
                if change.path.read_bytes() != change.before:
                    raise PatchError('Rollback readback differs')
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
    parser.add_argument('--repository-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--mode', choices=('preview', 'apply', 'verify'), default='preview')
    args = parser.parse_args()
    try:
        client, repository = args.client_root.resolve(), args.repository_root.resolve()
        plan = build_plan(client, repository)
        if args.mode == 'verify' and any(change.changed for change in plan):
            raise PatchError('Vampiric client/book definitions are not fully installed')
        result = {'patch_id': PATCH_ID, 'family': FAMILY, 'percentages': PERCENTAGES,
                  'files': summarize(client, repository, plan)}
        result.update(install(client, repository, plan) if args.mode == 'apply' else
                      {'status': 'Verified' if args.mode == 'verify' else 'Preview'})
        if args.mode == 'apply' and any(change.changed for change in build_plan(client, repository)):
            raise PatchError('Post-install Vampiric plan differs; inspect backup manifest')
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, PatchError) as error:
        print(f'Vampiric client patch failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
