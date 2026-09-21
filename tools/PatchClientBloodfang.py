#!/usr/bin/env python3
"""Preview/install Bloodfang's miniature Wonderland Platinum Dragon appearance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

from bloodfang_client import content, portrait, release
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import Change, atomic_write, contained
from PatchClientWonderlandStatus import assert_client_closed

PATCH_ID = release.PATCH_ID
ASSET_HASHES = release.ASSET_HASHES
OWNED_ASSET_PREDECESSORS = {
    content.MODEL: frozenset({'20fb274b45e8c10b28778f7f57ff04c417b8cfea648735b860d4d8b6308baafc',
        '023d46de812a4f1c1f1cc396c664106331fec1608953adcaa635f55172006091'}),
    content.TEXTURE: frozenset({'985ff33b98d644bea6bd1a9501f5c2e57340f3c0650b5eff01035d9eafbd15a8',
        '2522183ad17de949a816fe97e40289885c8de3dfcd5528883c30f9b2cf3184af',
        'e5a68f411ef166eecf34987263ce141a5713bed805ca6f18ef4dffbbf65b038d'})}


def build_plan(client, assets, repository=None, portrait_path=None):
    client = client.resolve()
    if (set(ASSET_HASHES) != {content.MODEL, content.TEXTURE}
            or not all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                       for value in [*ASSET_HASHES.values(), release.PORTRAIT_SHA256])):
        raise PatchError('Reviewed Bloodfang asset and portrait hashes are not frozen')
    model_nodes = content.models()  # Validate reviewed bounds before any writes.
    # Native loader 0x684C20 strips the first path character, then appends to
    # the executable directory WITHOUT adding a separator. Check those actual
    # references, not just the existence of unrelated hardcoded asset paths.
    for node in model_nodes:
        for index, model in enumerate(node.findall('PetModel'), 1):
            value = model.get('unitefile', '')
            resolved = Path(str(client) + value[1:]).resolve()
            expected = (client / 'Characters/PetUniteEffect' / f'e_he_000{index}_all.gwm').resolve()
            if resolved != expected:
                raise PatchError('Invalid native pet merge effect path')
            if not resolved.is_file():
                raise PatchError('Missing native pet merge effect')
    if repository is not None:
        repository = repository.resolve()
        if client.is_relative_to(repository) or repository.is_relative_to(client):
            raise PatchError('Client and repository must be distinct non-nested roots')
    changes = []
    for name, expected in ASSET_HASHES.items():
        data = (assets / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise PatchError(f'Frozen authored asset changed: {name}')
        path = contained(client, client / 'Pet' / name)
        before = path.read_bytes() if path.exists() else None
        if before is not None and before != data and hashlib.sha256(before).hexdigest() not in OWNED_ASSET_PREDECESSORS.get(name,()):
            raise PatchError(f'Bloodfang asset filename is occupied: {name}')
        changes.append(Change(path, before, data))
    for locale in ('en_us','zh_cn'):
        base = client / 'Localization' / locale
        for filename in ('Pet.xml','Pet_Confect.xml','Pet_Alter.xml','ItemBaseAttribute.xml'):
            path = contained(client, base / 'Settings/Sys' / filename)
            doc = Document.read(path)
            changes.append(Change(path, path.read_bytes(), doc.encode(content.xml(doc, filename))))
        for filename, kind in [('Message_Pet.dat','pet'),('EquipName.dat','name'),('EquipDescription.dat','description')]:
            path = contained(client, base / 'Text' / filename)
            doc = Document.read(path)
            changes.append(Change(path, path.read_bytes(), doc.encode(content.labels(doc,kind))))
        for relative in ('UI/Base/text.lua','UI/XML/PetDetailProc.lua','UI/XML/PetInfoProc.lua',
                         'UI/XML/PetIndentureUI.lua','UI/XML/PetSamsaraUI.lua'):
            path = contained(client, base / relative)
            doc = Document.read(path)
            changes.append(Change(path, path.read_bytes(), doc.encode(content.lua(doc,relative.endswith('/text.lua')))))
        # The original portrait is installed through the same guarded transaction.
        for name in ('Icon.gwo','Icon2.gwo'):
            if not (base / 'UI/Texture' / name).is_file(): raise PatchError('Missing native icon atlas')
    portrait_path = portrait_path or assets / release.PORTRAIT_FILENAME
    atlas_changes, _ = portrait.atlas_changes(client, portrait_path, release.PORTRAIT_SHA256)
    changes.extend(atlas_changes)
    if repository is not None:
        base = repository / 'Localization/en_us'
        path = contained(repository, base / 'Settings/Sys/ItemBaseAttribute.xml')
        doc = Document.read(path)
        changes.append(Change(path, path.read_bytes(), doc.encode(content.items(doc))))
        for name, kind in [('EquipName.dat','name'),('EquipDescription.dat','description')]:
            path = contained(repository, base / 'Text' / name)
            doc = Document.read(path)
            changes.append(Change(path, path.read_bytes(), doc.encode(content.labels(doc,kind))))
    return changes


def metadata(client, repository, changes):
    result = []
    for c in changes:
        owner = 'client' if c.path.is_relative_to(client.resolve()) else 'repository'
        root = client if owner == 'client' else repository
        if root is None: raise PatchError('Unowned output path')
        contained(root,c.path)
        result.append(dict(c.summary(root.resolve()),root=owner))
    return result


def install(client, repository, changes):
    selected = [c for c in changes if c.changed]
    if not selected: return {'status':'AlreadyMatches','files_changed':0}
    assert_client_closed()
    rows = metadata(client,repository,changes)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex
    backup = contained(client,client/'backups/bloodfang'/stamp)
    backup.mkdir(parents=True,exist_ok=False)
    manifest = {'patch_id':PATCH_ID,'status':'Prepared','files':rows}
    receipt = backup/'manifest.json'
    def save(): atomic_write(receipt,(json.dumps(manifest,indent=2)+'\n').encode())
    for change,row in zip(changes,rows,strict=True):
        if change.before is not None:
            dest=contained(backup,backup/row['root']/row['path'])
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(change.before)
            if dest.read_bytes()!=change.before: raise PatchError('Backup readback differs')
    save()
    written=[]
    try:
        for c in changes:
            if (c.path.read_bytes() if c.path.exists() else None)!=c.before:
                raise PatchError('Client/repository changed after preflight')
        for c in selected:
            if (c.path.read_bytes() if c.path.exists() else None)!=c.before:
                raise PatchError('Client/repository changed before write')
            c.path.parent.mkdir(parents=True,exist_ok=True)
            atomic_write(c.path,c.after)
            written.append(c)
            if c.path.read_bytes()!=c.after: raise PatchError('Installed readback differs')
        manifest['status']='Verified'
    except BaseException:
        failures=[]
        for c in reversed(written):
            try:
                if not c.path.exists() or c.path.read_bytes()!=c.after:
                    raise PatchError(f'File changed externally; preserved it: {c.path}')
                if c.before is None: c.path.unlink()
                else: atomic_write(c.path,c.before)
                if (c.path.read_bytes() if c.path.exists() else None)!=c.before:
                    raise PatchError(f'Rollback readback differs: {c.path}')
            except (OSError,PatchError) as error: failures.append(str(error))
        manifest['status']='RollbackFailed' if failures else 'RolledBack'
        if failures: manifest['rollback_errors']=failures
        raise
    finally: save()
    return {'status':'Verified','files_changed':len(selected),'backup_manifest':str(receipt)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-root',type=Path,required=True)
    parser.add_argument('--repository-root',type=Path)
    parser.add_argument('--assets',type=Path,default=release.ASSET_DIRECTORY)
    parser.add_argument('--portrait',type=Path,help='Reviewed PNG; defaults to bloodfang-portrait.png in --assets')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    try:
        changes=build_plan(args.client_root,args.assets,args.repository_root,args.portrait)
        result={'patch_id':PATCH_ID,'species':46,'egg':10194,'jade':11096,
                'files':metadata(args.client_root,args.repository_root,changes)}
        if args.apply:
            result.update(install(args.client_root,args.repository_root,changes))
            if any(c.changed for c in build_plan(args.client_root,args.assets,args.repository_root,args.portrait)):
                raise PatchError('Post-install plan differs; inspect backup manifest')
        else: result['status']='Preview'
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))
        return 0
    except (OSError,ValueError,PatchError) as error:
        print(f'Bloodfang patch failed: {error}',file=sys.stderr)
        return 1


if __name__=='__main__': raise SystemExit(main())
