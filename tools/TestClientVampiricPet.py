#!/usr/bin/env python3
"""Hermetic compatibility and transaction checks for the six Vampiric tiers."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import PatchClientVampiricPet as subject
from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import atomic_write


def node(attributes):
    return '<Pet' + attributes['ID'] + ' ' + ' '.join(
        f'{key}="{value}"' for key, value in attributes.items()) + '/>'


class VampiricPetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vampiric-pet-')
        self.addCleanup(self.temp.cleanup)
        self.client = Path(self.temp.name) / 'client'
        self.repository = Path(self.temp.name) / 'repository'
        self.before = {}
        for root, locales in ((self.client, subject.LOCALES), (self.repository, ('en_us',))):
            for locale in locales:
                base = root / 'Localization' / locale
                item = '<?xml version="1.0" encoding="UTF-8"?><ItemBaseAttribute><Books>\r\n' + \
                    node(subject.BOOK_ANCHOR) + '\r\n<Unrelated ID="12" Note="keep"/>\r\n</Books></ItemBaseAttribute>'
                self.write(base / 'Settings/Sys/ItemBaseAttribute.xml', b'\xef\xbb\xbf' + item.encode())
                self.write(base / 'Text/EquipName.dat', b'\xff\xfe' + 'Old\tPreserve name\r\n'.encode('utf-16-le'))
                self.write(base / 'Text/EquipDescription.dat', b'\xef\xbb\xbfOld\tPreserve description\n')
                if root == self.client:
                    pet = b'<?xml version="1.0" encoding="GB2312"?>\r\n<!--legacy \xa3\xa1-->\r\n<PetSkill><PetSkill>\r\n' + \
                        node(subject.PET_ANCHOR).encode() + b'\r\n</PetSkill><Genius><Genius1 ID="1"/></Genius></PetSkill>'
                    self.write(base / 'Settings/Sys/Pet_Skill.xml', pet)
                    self.write(base / 'Text/Message_Pet.dat', b'\xff\xfe' + 'Old\tPreserve skill\r\n'.encode('utf-16-le'))
                    for atlas in ('Icon.gwo', 'Icon2.gwo'):
                        self.write(base / 'UI/Texture' / atlas, b'existing native atlas')

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.before[path] = data

    def plan(self):
        return subject.build_plan(self.client, self.repository)

    def pet_path(self):
        return self.client / 'Localization/en_us/Settings/Sys/Pet_Skill.xml'

    def test_six_tiers_exact_native_contract_and_roundtrip(self):
        plan = self.plan()
        self.assertEqual(13, len(plan))
        for change in plan:
            change.path.write_bytes(change.after)
        self.assertTrue(all(not change.changed for change in self.plan()))
        document = subject.load_document(self.pet_path(), pet_xml=True)
        self.assertIn('<!--legacy \xa3\xa1-->', document.text)
        parsed = ET.fromstring(document.text)
        rows = {int(n.get('ID')): n.attrib for n in parsed.iter() if n.get('Type') == '428'}
        self.assertEqual(set(range(6400, 6406)), set(rows))
        for tier, (percent, accuracy) in enumerate(zip((6, 8, 11, 14, 17, 20), (0, 64, 192, 235, 270, 305))):
            row = rows[6400 + tier]
            self.assertEqual(str(tier + 1), row['Priority'])
            self.assertEqual(f'{percent / 100:.2f}', row['Values'])
            self.assertEqual(f'0,0,{accuracy * 100},0,0,0', row['Trait'])
            self.assertEqual('0', row['fact_Value'])
            self.assertEqual('0', row['Restrict'])
            self.assertEqual(str(6400 + tier), row['NextID'])
            self.assertEqual('34', row['Effect'])
            self.assertEqual('684,792', row['IconPos'])
        for change in plan:
            if change.path.suffix == '.dat':
                self.assertTrue(change.after.startswith(change.before), str(change.path))
            if change.path.name == 'ItemBaseAttribute.xml':
                tree = ET.fromstring(subject.load_document(change.path).text)
                books = [n.attrib for n in tree.iter() if n.get('ID') in {str(i) for i in range(16400, 16406)}]
                self.assertEqual(6, len(books))
                for tier, row in enumerate(books):
                    self.assertEqual(str(6400 + tier), row['PetSkill'])
                    self.assertEqual('4' if tier == 0 else '3', row['ItemType'])
                    self.assertEqual('99', row['Overlap'])
                    self.assertEqual('216,972', row['Icon'])

    def test_static_percent_labels_never_use_flat_native_interpolation(self):
        labels = subject.labels('pet')
        for tier, roman in enumerate(('I', 'II', 'III', 'IV', 'V', 'VI')):
            self.assertEqual('Vampiric ' + roman, labels[f'Pet{6400 + tier}'])
            info = labels[f'PetInfo{6400 + tier}']
            self.assertIn(str((6, 8, 11, 14, 17, 20)[tier]) + '% of damage actually inflicted', info)
            self.assertNotIn('%Values%', info)
            self.assertNotIn('%Restrict%', info)
        self.assertIn('Requires Vampiric V and 305 Accuracy.', subject.labels('description')['Pet16405'])

    def test_changed_native_anchor_rejected(self):
        path = self.pet_path()
        path.write_bytes(path.read_bytes().replace(b'IconPos="684,792"', b'IconPos="0,0"'))
        with self.assertRaises(PatchError): self.plan()

    def test_occupied_family_or_id_or_duplicate_rejected(self):
        path = self.pet_path()
        original = path.read_bytes()
        variants = (b'<Other ID="6500" Type="428"/>', b'<Other ID="6400"/>',
                    (node(subject.skill_rows()[0]) * 2).encode())
        for addition in variants:
            path.write_bytes(original.replace(b'</PetSkill>', addition + b'</PetSkill>', 1))
            with self.assertRaises(PatchError): self.plan()

    def test_owned_row_in_wrong_xml_section_rejected(self):
        path = self.pet_path()
        path.write_bytes(path.read_bytes().replace(b'<Genius>', b'<Genius>' + node(subject.skill_rows()[0]).encode()))
        with self.assertRaises(PatchError): self.plan()

    def test_book_or_label_collision_rejected(self):
        path = self.client / 'Localization/en_us/Settings/Sys/ItemBaseAttribute.xml'
        before = path.read_bytes()
        path.write_bytes(before.replace(b'</Books>', b'<Other ID="16400"/></Books>'))
        with self.assertRaises(PatchError): self.plan()
        path.write_bytes(before)
        path = self.client / 'Localization/en_us/Text/EquipName.dat'
        path.write_bytes(path.read_bytes() + 'Pet16400\tAnother item\r\n'.encode('utf-16-le'))
        with self.assertRaises(PatchError): self.plan()

    def test_missing_atlas_and_root_overlap_rejected(self):
        with self.assertRaises(PatchError): subject.build_plan(self.client, self.client)
        (self.client / 'Localization/zh_cn/UI/Texture/Icon2.gwo').unlink()
        with self.assertRaises(PatchError): self.plan()

    @patch.object(subject, 'assert_client_closed')
    def test_install_backs_up_all_thirteen_exact_inputs(self, closed):
        plan = self.plan()
        receipt = subject.install(self.client, self.repository, plan)
        self.assertEqual(13, receipt['files_changed'])
        self.assertEqual(2, closed.call_count)
        backup = Path(receipt['backup_manifest']).parent
        for change, metadata in zip(plan, subject.summarize(self.client, self.repository, plan)):
            self.assertEqual(change.before, (backup / metadata['root'] / metadata['path']).read_bytes())
            self.assertEqual(change.after, change.path.read_bytes())
        self.assertTrue(all(not change.changed for change in self.plan()))

    @patch.object(subject, 'assert_client_closed', side_effect=PatchError('client open'))
    def test_open_client_blocks_all_writes(self, _):
        plan = self.plan()
        with self.assertRaises(PatchError): subject.install(self.client, self.repository, plan)
        for change in plan: self.assertEqual(change.before, change.path.read_bytes())

    @patch.object(subject, 'assert_client_closed')
    def test_stale_repository_input_prevents_client_publication(self, _):
        plan = self.plan()
        changed = plan[-1].before + b'Concurrent edit'
        plan[-1].path.write_bytes(changed)
        with self.assertRaises(PatchError): subject.install(self.client, self.repository, plan)
        self.assertEqual(changed, plan[-1].path.read_bytes())
        for change in plan[:-1]: self.assertEqual(change.before, change.path.read_bytes())

    @patch.object(subject, 'assert_client_closed')
    def test_repository_write_failure_rolls_back_both_locales(self, _):
        plan = self.plan()
        def injected(path, data):
            if path == plan[-1].path and data == plan[-1].after:
                raise OSError('injected final write failure')
            atomic_write(path, data)
        with patch.object(subject, 'atomic_write', side_effect=injected):
            with self.assertRaises(OSError): subject.install(self.client, self.repository, plan)
        for change in plan: self.assertEqual(change.before, change.path.read_bytes())

    @patch.object(subject, 'assert_client_closed')
    def test_rollback_preserves_unrelated_concurrent_edits(self, _):
        plan = self.plan()
        changed = b'External content changed after first write'
        def injected(path, data):
            if path == plan[1].path and data == plan[1].after:
                plan[0].path.write_bytes(changed)
                raise OSError('injected later write failure')
            atomic_write(path, data)
        with patch.object(subject, 'atomic_write', side_effect=injected):
            with self.assertRaises(OSError): subject.install(self.client, self.repository, plan)
        self.assertEqual(changed, plan[0].path.read_bytes())
        for change in plan[1:]: self.assertEqual(change.before, change.path.read_bytes())


if __name__ == '__main__':
    unittest.main()
