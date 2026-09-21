#!/usr/bin/env python3
"""Legacy Bloodfang upgrade guards; writes use disposable fixtures."""
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zlib

import PatchClientBloodfang as subject
from bloodfang_client import content, model_config, portrait as artwork, release
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import atomic_write

ROOT = Path(__file__).resolve().parents[1]
PROFILE = {**model_config.V2_PROFILE, 'AabbMaxZ': '1.85', 'AabbMinZ': '-1.10', 'NameHeight': '2.5'}


def document(text):
    return Document(text, 'utf-8', b'\xef\xbb\xbf', '\r\n')


def pet_xml(profile=model_config.V2_PROFILE, portrait=model_config.V2_PORTRAIT):
    # Deliberately unusual whitespace/quotes around owned values tests that
    # upgrades only change those values, not serializer formatting.
    # Historical releases emitted one literal separator; never derive these
    # fixture paths from the corrected production path builder.
    elements = model_config.nodes(profile, portrait)
    for node in elements:
        for index, row in enumerate(node.findall('PetModel'), 1):
            row.set('unitefile', f'\\Characters\\PetUniteEffect\\e_he_000{index}_all.gwm')
    rows = [ET.tostring(n, encoding='unicode') for n in elements]
    text = '\r\n'.join(rows).replace('="', ' = "')
    return '<PetModel>\r\n<!-- KEEP exact prefix -->\r\n' + text + '\r\n<Other untouched="yes"/>\r\n</PetModel>\r\n'


def png():
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    pixels = (b'\0' + bytes((90, 10, 20, 255)) * 36) * 36
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 36, 36, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


class ModelNodeUpgradeTests(unittest.TestCase):
    def test_both_reviewed_v2_variants_upgrade_losslessly(self):
        for portrait in (model_config.V2_PORTRAIT, model_config.V3_PORTRAIT):
            before = pet_xml(portrait=portrait)
            after = model_config.update(document(before), PROFILE)
            expected = (before.replace('IconPos = "' + portrait + '"', 'IconPos = "396,864"')
                        .replace('NameHeight = "3.2"', 'NameHeight = "2.5"')
                        .replace('AabbMaxZ = "1.10"', 'AabbMaxZ = "1.85"')
                        .replace('AabbMinZ = "-1.78"', 'AabbMinZ = "-1.10"'))
            self.assertEqual(expected.replace('\\', '\\\\'), after)
            self.assertEqual(after, model_config.update(document(after), PROFILE))

    def test_reviewed_v3_upgrade_preserves_portrait_and_every_unmodified_byte(self):
        before = pet_xml(model_config.V3_PROFILE, model_config.V3_PORTRAIT)
        after = model_config.update(document(before), PROFILE)
        expected = before
        for key, value in PROFILE.items():
            if key in ('Scale0', 'ScaleOther'):
                continue
            expected = expected.replace(f'{key} = "{model_config.V3_PROFILE[key]}"',
                                        f'{key} = "{value}"')
        self.assertEqual(expected.replace('\\', '\\\\'), after)
        self.assertEqual(2, after.count('IconPos = "396,864"'))
        self.assertEqual(after, model_config.update(document(after), PROFILE))

    def test_v3_modified_fields_or_mixed_v2_and_v3_gender_pair_are_rejected(self):
        original = pet_xml(model_config.V3_PROFILE, model_config.V3_PORTRAIT)
        v2 = pet_xml(model_config.V2_PROFILE, model_config.V3_PORTRAIT)
        old_gender = re.search(r'<Pet46_1>.*?</Pet46_1>', v2, re.S).group()
        changes = [original.replace('AabbMaxX = "2.97"', 'AabbMaxX = "3.0"', 1),
                   original.replace('IconPos = "396,864"', 'IconPos = "864,900"'),
                   re.sub(r'<Pet46_1>.*?</Pet46_1>', lambda _: old_gender, original, flags=re.S)]
        for value in changes:
            with self.subTest(value=value), self.assertRaises(PatchError):
                model_config.update(document(value), PROFILE)

    def test_foreign_attributes_text_comments_missing_duplicate_and_mixed_nodes_fail(self):
        original = pet_xml()
        changes = [lambda t: t.replace('NameHeight = "3.2"', 'NameHeight = "99"', 1),
                   lambda t: t.replace('<Pet46_0>', '<Pet46_0>foreign'),
                   lambda t: t.replace('<Pet46_0>', '<Pet46_0><!-- foreign -->'),
                   lambda t: re.sub(r'<Pet46_1>.*?</Pet46_1>', '', t, flags=re.S),
                   lambda t: t.replace('</PetModel>', '<Pet46_0/>' + '</PetModel>'),
                   lambda t: t.replace('IconPos = "864,900"', 'IconPos = "396,864"', 1),
                   lambda t: t.replace('<Pet46_0>', '<Nested><Pet46_0>').replace('</Pet46_0>', '</Pet46_0></Nested>')]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(PatchError):
                model_config.update(document(change(original)), PROFILE)

    def test_unfrozen_invalid_or_partial_bounds_fail(self):
        for profile in (None, {}, {**PROFILE, 'AabbMinZ': '2'}, {**PROFILE, 'Scale0': 'nan'}):
            with self.subTest(profile=profile), self.assertRaises(PatchError):
                model_config.update(document(pet_xml()), profile)

    def test_new_species_append_preserves_all_existing_bytes(self):
        original = '<PetModel>\r\n<Other untouched="yes"/>\r\n</PetModel>\r\n'
        after = model_config.update(document(original), PROFILE)
        stripped = re.sub(r'<Pet46_[01]>.*?</Pet46_[01]>\r\n', '', after, flags=re.S)
        self.assertEqual(original, stripped)
        self.assertEqual(after, model_config.update(document(after), PROFILE))


class UpgradeTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bloodfang-v4-upgrade-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client, self.assets = self.root / 'client', self.root / 'assets'
        self.assets.mkdir()
        original = ROOT / 'assets/bloodfang/fixtures/v2'
        hashes = {}
        for name in (content.MODEL, content.TEXTURE):
            before = (original / name).read_bytes()
            self.assertIn(hashlib.sha256(before).hexdigest(), subject.OWNED_ASSET_PREDECESSORS[name])
            # Deliberately synthetic v4 fixture checks installer ownership and
            # rollback. Native asset validation is a separate release gate.
            after = before + b'\nreviewed-v4-transaction-fixture'
            (self.assets / name).write_bytes(after)
            hashes[name] = hashlib.sha256(after).hexdigest()
            self.write(self.client / 'Pet' / name, before)
        self.write(self.assets / release.PORTRAIT_FILENAME, png())
        for target, key, value in [(subject, 'ASSET_HASHES', hashes), (release, 'MODEL_PROFILE', PROFILE),
                                   (release, 'PORTRAIT_SHA256', hashlib.sha256(png()).hexdigest())]:
            context = patch.object(target, key, value)
            context.start()
            self.addCleanup(context.stop)
        header = struct.pack('<BBBHHBHHHHBB', 0, 0, 10, 0, 0, 0, 0, 0, 1024, 1024, 32, 8)
        stream = (b'\xff' + bytes(4)) * (1024 * 1024 // 128)
        extension = struct.pack('<H', 495) + bytes(493)
        atlas = header + stream + extension + struct.pack('<II', len(header + stream), 0) + b'TRUEVISION-XFILE.\0'
        for locale in ('en_us', 'zh_cn'):
            base = self.client / 'Localization' / locale
            resources = {'Pet.xml': pet_xml(),
                'Pet_Confect.xml': '<Confect><Confect><StockFood Type="45"/></Confect><Aptitude><Stock Type="45"/></Aptitude></Confect>',
                'Pet_Alter.xml': '<Alter><typePoint><Type45 PetType="45" Values="2"/></typePoint></Alter>',
                'ItemBaseAttribute.xml': '<Items><Pet10193 ID="10193" Values="44"/></Items>'}
            for name, text in resources.items():
                doc = document(text)
                result = text if name == 'Pet.xml' else content.xml(doc, name)
                self.write(base / 'Settings/Sys' / name, doc.encode(result))
            for name, kind in [('Message_Pet.dat', 'pet'), ('EquipName.dat', 'name'), ('EquipDescription.dat', 'description')]:
                doc = document('Unrelated\tKeep\r\n')
                self.write(base / 'Text' / name, doc.encode(content.labels(doc, kind)))
            for name in ('UI/Base/text.lua', 'UI/XML/PetDetailProc.lua', 'UI/XML/PetInfoProc.lua',
                         'UI/XML/PetIndentureUI.lua', 'UI/XML/PetSamsaraUI.lua'):
                base_lua = name.endswith('/text.lua')
                doc = document('PETTYPE45 = "Old"\r\n' if base_lua else
                               'if value == 44 then\r\n x:SetText(PETTYPE44);\r\nelseif value == 45 then\r\n x:SetText(PETTYPE45);\r\nend\r\n')
                self.write(base / name, doc.encode(content.lua(doc, base_lua)))
            self.write(base / 'UI/Texture/Icon.gwo', b'unrelated prerequisite')
            self.write(base / 'UI/Texture/Icon2.gwo', atlas)
        for i in range(1, 5):
            self.write(self.client / f'Characters/PetUniteEffect/e_he_000{i}_all.gwm', b'existing effect')

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def plan(self):
        return subject.build_plan(self.client, self.assets)

    def prepare_v3_predecessor(self):
        original = ROOT / 'assets/bloodfang/fixtures/v3'
        for name in (content.MODEL, content.TEXTURE):
            data = (original / name).read_bytes()
            self.assertIn(hashlib.sha256(data).hexdigest(), subject.OWNED_ASSET_PREDECESSORS[name])
            self.write(self.client / 'Pet' / name, data)
        sprite = artwork.normalized_sprite(png(), release.PORTRAIT_SHA256)
        for locale in ('en_us', 'zh_cn'):
            base = self.client / 'Localization' / locale
            self.write(base / 'Settings/Sys/Pet.xml', document('').encode(
                pet_xml(model_config.V3_PROFILE, model_config.V3_PORTRAIT)))
            atlas = base / 'UI/Texture/Icon2.gwo'
            self.write(atlas, artwork.pack(atlas.read_bytes(), sprite))

    def test_v3_upgrade_changes_only_models_and_owned_xml_and_keeps_portrait(self):
        self.prepare_v3_predecessor()
        plan = self.plan()
        changed = [c for c in plan if c.changed]
        self.assertEqual(4, len(changed))
        self.assertEqual([content.MODEL, content.TEXTURE, 'Pet.xml', 'Pet.xml'],
                         [c.path.name for c in changed])
        with patch.object(subject, 'assert_client_closed'):
            result = subject.install(self.client, None, plan)
        self.assertEqual(4, result['files_changed'])
        self.assertFalse(any(c.changed for c in self.plan()))
        for c in plan:
            if c.path.name == 'Icon2.gwo':
                self.assertEqual(c.before, c.path.read_bytes())

    def test_v3_upgrade_failure_restores_prior_models_and_exact_model_nodes(self):
        self.prepare_v3_predecessor()
        plan = self.plan()
        target = [c for c in plan if c.changed][-1]
        self.assertEqual('Pet.xml', target.path.name)
        def inject(path, data):
            if path == target.path and data == target.after:
                raise OSError('last model configuration write failed')
            atomic_write(path, data)
        with patch.object(subject, 'assert_client_closed'), patch.object(subject, 'atomic_write', side_effect=inject):
            with self.assertRaises(OSError):
                subject.install(self.client, None, plan)
        for c in plan:
            self.assertEqual(c.before, c.path.read_bytes())

    def test_one_plan_upgrades_only_six_owned_model_xml_and_atlas_files(self):
        plan = self.plan()
        self.assertEqual(28, len(plan))
        self.assertEqual(len(plan), len({c.path for c in plan}))
        self.assertEqual(6, sum(c.changed for c in plan))
        with patch.object(subject, 'assert_client_closed'):
            result = subject.install(self.client, None, plan)
        self.assertEqual(6, result['files_changed'])
        manifest = json.loads(Path(result['backup_manifest']).read_text())
        self.assertEqual('reborn.bloodfang-species46.v6', manifest['patch_id'])
        self.assertFalse(any(c.changed for c in self.plan()))
        for row, change in zip(manifest['files'], plan, strict=True):
            self.assertEqual(change.before, (Path(result['backup_manifest']).parent / row['root'] / row['path']).read_bytes())

    def test_final_atlas_write_failure_rolls_back_model_xml_and_first_atlas(self):
        plan = self.plan()
        target = plan[-1]
        self.assertEqual('Icon2.gwo', target.path.name)
        def inject(path, data):
            if path == target.path and data == target.after:
                raise OSError('last atlas write failed')
            atomic_write(path, data)
        with patch.object(subject, 'assert_client_closed'), patch.object(subject, 'atomic_write', side_effect=inject):
            with self.assertRaises(OSError):
                subject.install(self.client, None, plan)
        for c in plan:
            self.assertEqual(c.before, c.path.read_bytes())

    def test_foreign_model_and_unknown_atlas_cell_fail_before_writes(self):
        path = self.client / 'Pet' / content.MODEL
        before = path.read_bytes()
        path.write_bytes(b'foreign model')
        with self.assertRaisesRegex(PatchError, 'occupied'):
            self.plan()
        path.write_bytes(before)
        atlas = self.client / 'Localization/en_us/UI/Texture/Icon2.gwo'
        data = bytearray(atlas.read_bytes())
        # Native bottom-origin RLE: alter the run containing cell (396,864).
        data[18 + ((1023 - 864) * 8 + 396 // 128) * 5 + 1] = 55
        atlas.write_bytes(data)
        with self.assertRaises(PatchError):
            self.plan()
        self.assertEqual(before, path.read_bytes())

    def test_pending_release_pins_and_tampered_portrait_fail_closed(self):
        with patch.object(subject, 'ASSET_HASHES', {content.MODEL: None, content.TEXTURE: None}):
            with self.assertRaisesRegex(PatchError, 'not frozen'):
                self.plan()
        with patch.object(release, 'PORTRAIT_SHA256', None), self.assertRaisesRegex(PatchError, 'not frozen'):
            self.plan()
        with patch.object(release, 'MODEL_PROFILE', None), self.assertRaisesRegex(PatchError, 'not frozen'):
            self.plan()
        path = self.assets / release.PORTRAIT_FILENAME
        path.write_bytes(path.read_bytes() + b'tamper')
        with self.assertRaises(PatchError):
            self.plan()


if __name__ == '__main__':
    unittest.main()
