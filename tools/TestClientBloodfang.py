#!/usr/bin/env python3
"""Bloodfang client compatibility checks using read-only installed fixtures.

All mutations and transaction tests occur in isolated temporary directories.
The installed game supplies only the minimal native input files and atlases.
"""
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import PatchClientBloodfang as subject
from bloodfang_client import content, release
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import atomic_write


GAME = Path(r'C:\Godswar Origin')
REPOSITORY = Path(__file__).resolve().parents[1]
ASSETS = release.ASSET_DIRECTORY
XML_NAMES = ('Pet.xml', 'Pet_Confect.xml', 'Pet_Alter.xml', 'ItemBaseAttribute.xml')
DAT_NAMES = ('Message_Pet.dat', 'EquipName.dat', 'EquipDescription.dat')
LUA_NAMES = ('UI/Base/text.lua', 'UI/XML/PetDetailProc.lua', 'UI/XML/PetInfoProc.lua',
             'UI/XML/PetIndentureUI.lua', 'UI/XML/PetSamsaraUI.lua')


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def remove_owned_rows_from_fixture(path):
    """Keep tests repeatable after installation; alter only the temporary copy."""
    doc=Document.read(path);text=doc.text
    if path.suffix=='.xml':
        for tag in ('Pet46_0','Pet46_1','Bloodfang'):
            text=re.sub(r'<' + tag + r'\b[^>]*>.*?</' + tag + r'\s*>','',text,flags=re.S)
        for tag in ('BloodfangFood','Type46','Pet10194','Pet11096'):
            text=re.sub(r'<' + tag + r'\b[^>]*/>','',text)
    elif path.suffix=='.dat':
        text=re.sub(r'^(?:Pet46_[01]|Pet10194|Pet11096)\t[^\r\n]*(?:\r?\n|$)','',text,flags=re.M)
    elif path.name=='text.lua':
        text=re.sub(r'^PETTYPE46\s*=[^\r\n]*(?:\r?\n|$)','',text,flags=re.M)
    else:
        text=re.sub(r'^[ \t]*elseif value == 46 then\s*\n[ \t]*\w+:SetText\(PETTYPE46\);(?:\r?\n|$)',
                    '',text,flags=re.M)
    path.write_bytes(doc.encode(text))


def original_subtree_preserved(case, before, after):
    case.assertEqual(before.tag, after.tag)
    case.assertEqual(before.attrib, after.attrib, before.tag)
    case.assertEqual((before.text or '').strip(), (after.text or '').strip(), before.tag)
    case.assertGreaterEqual(len(after), len(before), before.tag)
    for old, new in zip(before, after):
        original_subtree_preserved(case, old, new)


class BloodfangClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference_temp = tempfile.TemporaryDirectory(prefix='bloodfang-readonly-fixture-')
        cls.addClassCleanup(cls.reference_temp.cleanup)
        cls.reference = Path(cls.reference_temp.name)
        for locale in ('en_us', 'zh_cn'):
            base = Path('Localization') / locale
            relatives = [base / 'Settings/Sys' / name for name in XML_NAMES]
            relatives += [base / 'Text' / name for name in DAT_NAMES]
            relatives += [base / name for name in LUA_NAMES]
            relatives += [base / 'UI/Texture' / name for name in ('Icon.gwo', 'Icon2.gwo')]
            for relative in relatives:
                copy_file(GAME / relative, cls.reference / 'client' / relative)
                if relative.suffix in ('.xml','.dat','.lua'):
                    remove_owned_rows_from_fixture(cls.reference/'client'/relative)
        for index in range(1, 5):
            relative = Path('Characters/PetUniteEffect') / f'e_he_000{index}_all.gwm'
            copy_file(GAME / relative, cls.reference / 'client' / relative)
        for relative in ('Settings/Sys/ItemBaseAttribute.xml', 'Text/EquipName.dat', 'Text/EquipDescription.dat'):
            path = Path('Localization/en_us') / relative
            copy_file(REPOSITORY / path, cls.reference / 'repository' / path)
            remove_owned_rows_from_fixture(cls.reference/'repository'/path)
        for name in (content.MODEL, content.TEXTURE, release.PORTRAIT_FILENAME):
            copy_file(ASSETS / name, cls.reference / 'assets' / name)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bloodfang-client-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(self.reference, self.root, dirs_exist_ok=True)
        self.client = self.root / 'client'
        self.repository = self.root / 'repository'
        self.assets = self.root / 'assets'

    def plan(self):
        return subject.build_plan(self.client, self.assets, self.repository)

    def xml_path(self, name, locale='en_us'):
        return self.client / 'Localization' / locale / 'Settings/Sys' / name

    def write_text(self, path, transform):
        doc = Document.read(path)
        path.write_bytes(doc.encode(transform(doc.text)))

    def apply_fixture(self, plan=None):
        for change in self.plan() if plan is None else plan:
            change.path.parent.mkdir(parents=True, exist_ok=True)
            change.path.write_bytes(change.after)

    def test_both_locales_repository_and_idempotency(self):
        plan = self.plan()
        self.assertEqual(31, len(plan))
        self.assertEqual(31, len({change.path for change in plan}))
        for change in plan:
            if change.path.suffix == '.xml':
                before = Document.read(change.path)
                after = change.after[len(before.bom):].decode(before.encoding)
                original_subtree_preserved(self, ET.fromstring(before.text), ET.fromstring(after))
            elif change.path.suffix == '.dat':
                self.assertTrue(change.after.startswith(change.before), change.path)
        self.apply_fixture(plan)
        self.assertTrue(all(not change.changed for change in self.plan()))

    def test_both_genders_all_rebirth_stages_resolve_reviewed_assets(self):
        self.apply_fixture()
        for locale in ('en_us', 'zh_cn'):
            tree = ET.fromstring(Document.read(self.xml_path('Pet.xml', locale)).text)
            for gender in (0, 1):
                model = tree.find(f'Pet46_{gender}')
                self.assertIsNotNone(model)
                self.assertEqual('396,864', model.find('PetInfo').get('IconPos'))
                rows = model.findall('PetModel')
                self.assertEqual(['0', '8', '20', '90'], [row.get('Samsara') for row in rows])
                for index, row in enumerate(rows, 1):
                    self.assertEqual(content.MODEL, row.get('FileName'))
                    self.assertEqual(content.TEXTURE, row.get('TextureName'))
                    self.assertTrue((self.client / 'Pet' / row.get('FileName')).is_file())
                    self.assertTrue((self.client / 'Pet' / row.get('TextureName')).is_file())
                    relative = row.get('unitefile').replace('\\', '/').lstrip('/')
                    self.assertTrue((self.client / relative).is_file())
                    self.assertTrue(relative.endswith(f'e_he_000{index}_all.gwm'))
                    for axis in 'XYZ':
                        self.assertLess(float(row.get('AabbMin' + axis)), float(row.get('AabbMax' + axis)))

    def test_species46_food_aptitudes_innate_skill_and_item_targets(self):
        self.apply_fixture()
        for locale in ('en_us', 'zh_cn'):
            tree = ET.fromstring(Document.read(self.xml_path('Pet_Confect.xml', locale)).text)
            food = [node for node in tree.find('Confect') if node.get('Type') == '46']
            self.assertEqual(1, len(food))
            self.assertEqual('2', food[0].get('Food'))
            groups = [node for node in tree.find('Aptitude') if node.get('Type') == '46']
            self.assertEqual(1, len(groups))
            rows = list(groups[0])
            self.assertEqual({1,2,3,4,5,7,8,9,10,12,14}, {int(row.get('Aptitude')) for row in rows})
            for row in rows:
                self.assertEqual('46', row.get('Type'))
                self.assertEqual('6400', row.get('StartSkill'))
                self.assertIn('6400', row.get('AllowSkill').split(','))
            tree = ET.fromstring(Document.read(self.xml_path('ItemBaseAttribute.xml', locale)).text)
            egg = next(node for node in tree.iter() if node.get('ID') == '10194')
            self.assertEqual('46', egg.get('Values'))
            self.assertEqual('4740', egg.get('Skill'))
            self.assertEqual('6', egg.get('ItemType'))
            self.assertEqual(1, sum(node.get('ID') == '11096' for node in tree.iter()))

    def test_all_lua_menus_keep_previous_branches_and_add46(self):
        originals = {}
        for locale in ('en_us', 'zh_cn'):
            for relative in LUA_NAMES:
                path = self.client / 'Localization' / locale / relative
                originals[path] = Document.read(path).text
        self.apply_fixture()
        for path, original in originals.items():
            after = Document.read(path).text
            self.assertEqual(1, after.count('PETTYPE46'), str(path))
            if path.name == 'text.lua':
                self.assertIn('PETTYPE46 = "Bloodfang"', after)
            else:
                self.assertIn('elseif value == 46 then', after)
                self.assertIn(':SetText(PETTYPE46);', after)
                self.assertEqual(original.count('elseif value == 45 then'), after.count('elseif value == 45 then'))
            for line in original.splitlines():
                if line.strip(): self.assertIn(line, after, str(path))

    def test_utf8_utf16_bom_and_newline_roundtrip(self):
        source = '<PetModel>\n<Pet45_0><PetInfo Name="Existing"/></Pet45_0>\n</PetModel>\n'
        for encoding, bom in [('utf-8',b''), ('utf-8',b'\xef\xbb\xbf'), ('utf-16-le',b'\xff\xfe')]:
            for newline in ('\n', '\r\n'):
                path = self.root / 'encoded.xml'
                path.write_bytes(bom + source.replace('\n', newline).encode(encoding))
                doc = Document.read(path)
                encoded = doc.encode(content.xml(doc, 'Pet.xml'))
                self.assertTrue(encoded.startswith(bom))
                path.write_bytes(encoded)
                again = Document.read(path)
                self.assertEqual(encoding, again.encoding)
                self.assertEqual(newline, again.newline)
                self.assertEqual(encoded, again.encode(content.xml(again, 'Pet.xml')))

    def test_unrelated_species46_rejected(self):
        for name, close, row in [('Pet_Confect.xml','</Confect>','<Other Type="46" Food="1"/>'),
                                 ('Pet_Alter.xml','</typePoint>','<Other PetType="46" Values="9"/>')]:
            path = self.xml_path(name);before = path.read_bytes()
            self.write_text(path, lambda text: text.replace(close, row + close, 1))
            with self.assertRaises(PatchError): self.plan()
            path.write_bytes(before)

    def test_existing_species46_model_or_item_collision_rejected(self):
        cases = [('Pet.xml','</PetModel>','<Pet46_0><PetInfo Name="Other"/></Pet46_0>'),
                 ('ItemBaseAttribute.xml','</ItemBaseAttribute>','<Other ID="10194"/>'),
                 ('ItemBaseAttribute.xml','</ItemBaseAttribute>','<Other ID="11096"/>')]
        for name, close, row in cases:
            path = self.xml_path(name);before = path.read_bytes()
            # The item root is native and may have a different spelling.
            doc = Document.read(path)
            if name == 'ItemBaseAttribute.xml': close = '</' + ET.fromstring(doc.text).tag + '>'
            path.write_bytes(doc.encode(doc.text.replace(close, row + close, 1)))
            with self.assertRaises(PatchError): self.plan()
            path.write_bytes(before)

    def test_labels_lua_and_owned_model_modification_fail_closed(self):
        self.apply_fixture()
        targets = [(self.client / 'Localization/en_us/Text/EquipName.dat', 'Bloodfang Egg', 'Unrelated Egg'),
                   (self.client / 'Localization/zh_cn/UI/Base/text.lua', 'PETTYPE46 = "Bloodfang"', 'PETTYPE46 = "Other"'),
                   (self.xml_path('Pet.xml'), 'Name="Pet46_0"', 'Name="Other"')]
        for path, old, new in targets:
            before = path.read_bytes();self.write_text(path, lambda text: text.replace(old,new,1))
            with self.assertRaises(PatchError): self.plan()
            path.write_bytes(before)

    def test_asset_tamper_occupied_filename_missing_dependencies_and_overlap_rejected(self):
        path = self.assets / content.MODEL;before = path.read_bytes();path.write_bytes(before+b'tamper')
        with self.assertRaises(PatchError): self.plan()
        path.write_bytes(before)
        target = self.client / 'Pet' / content.MODEL;target.parent.mkdir(parents=True)
        target.write_bytes(b'unrelated native asset')
        with self.assertRaises(PatchError): self.plan()
        target.unlink()
        atlas = self.client / 'Localization/zh_cn/UI/Texture/Icon2.gwo';before=atlas.read_bytes();atlas.unlink()
        with self.assertRaises(PatchError): self.plan()
        atlas.write_bytes(before)
        effect=self.client/'Characters/PetUniteEffect/e_he_0004_all.gwm';effect.unlink()
        with self.assertRaises(PatchError): self.plan()
        with self.assertRaises(PatchError): subject.build_plan(self.client,self.assets,self.client)

    def test_generated_merge_path_is_checked_before_any_writes(self):
        # All four effects exist. Reproduce the old metadata defect anyway:
        # native loading strips the only leading separator and misses them.
        before = {p: p.read_bytes() for p in self.client.rglob('*') if p.is_file()}
        malformed = content.models()
        row = malformed[0].find('PetModel')
        row.set('unitefile', row.get('unitefile').replace('\\\\', '\\'))
        with patch.object(content, 'models', return_value=malformed):
            with self.assertRaisesRegex(PatchError, 'Invalid native pet merge effect path'):
                self.plan()
        self.assertEqual(before, {p: p.read_bytes() for p in self.client.rglob('*') if p.is_file()})

    @patch.object(subject, 'assert_client_closed')
    def test_install_backup_readback_and_repeat(self, closed):
        plan=self.plan();result=subject.install(self.client,self.repository,plan)
        self.assertEqual('Verified',result['status'])
        self.assertEqual(sum(change.changed for change in plan),result['files_changed'])
        self.assertTrue(closed.called)
        backup=Path(result['backup_manifest']).parent
        for change,row in zip(plan,subject.metadata(self.client,self.repository,plan)):
            self.assertEqual(change.after,change.path.read_bytes())
            if change.before is not None:
                self.assertEqual(change.before,(backup/row['root']/row['path']).read_bytes())
        self.assertEqual('AlreadyMatches',subject.install(self.client,self.repository,self.plan())['status'])

    @patch.object(subject, 'assert_client_closed', side_effect=PatchError('game is open'))
    def test_open_client_prevents_content_writes(self, _):
        plan=self.plan()
        with self.assertRaises(PatchError):subject.install(self.client,self.repository,plan)
        for change in plan:
            self.assertEqual(change.before,change.path.read_bytes() if change.path.exists() else None)

    @patch.object(subject, 'assert_client_closed')
    def test_stale_input_prevents_any_content_writes(self, _):
        plan=self.plan();changed=plan[-1].before+b'Concurrent change';plan[-1].path.write_bytes(changed)
        with self.assertRaises(PatchError):subject.install(self.client,self.repository,plan)
        self.assertEqual(changed,plan[-1].path.read_bytes())
        for change in plan[:-1]:
            self.assertEqual(change.before,change.path.read_bytes() if change.path.exists() else None)

    @patch.object(subject, 'assert_client_closed')
    def test_late_write_failure_rolls_back_assets_both_locales_repository(self, _):
        plan=self.plan()
        def injected(path,data):
            if path==plan[-1].path and data==plan[-1].after:raise OSError('Injected final write failure')
            atomic_write(path,data)
        with patch.object(subject,'atomic_write',side_effect=injected):
            with self.assertRaises(OSError):subject.install(self.client,self.repository,plan)
        for change in plan:
            self.assertEqual(change.before,change.path.read_bytes() if change.path.exists() else None)

    @patch.object(subject, 'assert_client_closed')
    def test_rollback_preserves_external_concurrent_edit(self, _):
        plan=self.plan();external=b'An external edit after our write'
        def injected(path,data):
            if path==plan[1].path and data==plan[1].after:
                plan[0].path.write_bytes(external)
                raise OSError('Injected second write failure')
            atomic_write(path,data)
        with patch.object(subject,'atomic_write',side_effect=injected):
            with self.assertRaises(OSError):subject.install(self.client,self.repository,plan)
        self.assertEqual(external,plan[0].path.read_bytes())


if __name__ == '__main__':
    unittest.main()
