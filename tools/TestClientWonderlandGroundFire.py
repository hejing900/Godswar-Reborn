#!/usr/bin/env python3
"""Hermetic checks for the original Fire Blast coordinate-only presentation."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import PatchClientWonderlandGroundFire as subject
from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import atomic_write


class GroundFireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wonderland-fire-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = {}
        for locale in subject.LOCALES:
            path = self.root / 'Localization' / locale / 'Settings/Sys/Magic.ini'
            path.parent.mkdir(parents=True)
            text = '; preserve all existing rows\r\n[570]\r\nName=Flame Blast\r\nTarget=63\r\n\r\n' + \
                subject.source_section(locale).replace('\n', '\r\n') + \
                '\r\n\r\n[5625]\r\nName=Unrelated\r\n[5625]\r\nName=Existing duplicate\r\n'
            self.before[path] = b'\xff\xfe' + text.encode('utf-16-le')
            path.write_bytes(self.before[path])
        asset = self.root / 'Effect/effect_fire_002_all.gwm'
        asset.parent.mkdir()
        asset.write_bytes(b'existing native fire asset')

    def test_only_alias_header_and_coordinate_bit_change(self):
        for locale, change in zip(subject.LOCALES, subject.build_plan(self.root)):
            self.assertTrue(change.after.startswith(change.before))
            text = change.after[2:].decode('utf-16-le')
            self.assertEqual(subject.blocks(text, 580), [subject.source_section(locale)])
            alias = subject.blocks(text, 589)[0]
            self.assertEqual(alias.replace('[589]', '[580]', 1).replace('\nTarget=17\n', '\nTarget=1\n'),
                             subject.source_section(locale))
            self.assertIn('EffectFile1=effect_fire_002_all.gwm', alias)
            self.assertNotIn('effect_fire_004_all.gwm', alias)
            self.assertEqual(len(subject.blocks(text, 5625)), 2)

    @patch.object(subject, 'assert_client_closed')
    def test_verified_install_exact_backups_and_idempotence(self, closed):
        plan = subject.build_plan(self.root)
        result = subject.install(self.root, plan)
        self.assertEqual(result['files_changed'], 2)
        manifest = Path(result['backup_manifest'])
        self.assertEqual(json.loads(manifest.read_text())['status'], 'Verified')
        for change in plan:
            self.assertEqual((manifest.parent / change.path.relative_to(self.root)).read_bytes(), change.before)
        self.assertTrue(all(not change.changed for change in subject.build_plan(self.root)))
        self.assertEqual(closed.call_count, 2)

    def test_changed_or_duplicate_source_rejected(self):
        path = next(iter(self.before))
        for text in (subject.source_section('en_us').replace('Target=1', 'Target=16'),
                     subject.source_section('en_us') + '\n' + subject.source_section('en_us')):
            path.write_bytes(b'\xff\xfe' + text.encode('utf-16-le'))
            with self.assertRaises(PatchError): subject.build_plan(self.root)

    def test_occupied_modified_or_duplicate_alias_rejected(self):
        path = next(iter(self.before))
        for alias in ('[589]\nName=Other', subject.alias_section('en_us').replace('Target=17', 'Target=63'),
                      subject.alias_section('en_us') + '\n' + subject.alias_section('en_us')):
            path.write_bytes(self.before[path] + ('\n' + alias).encode('utf-16-le'))
            with self.assertRaises(PatchError): subject.build_plan(self.root)

    def test_missing_actual_fire_effect_rejected(self):
        (self.root / 'Effect/effect_fire_002_all.gwm').unlink()
        with self.assertRaises(PatchError): subject.build_plan(self.root)

    def test_encoding_change_rejected(self):
        next(iter(self.before)).write_text(subject.source_section('en_us'), encoding='utf-8')
        with self.assertRaises(PatchError): subject.build_plan(self.root)

    @patch.object(subject, 'assert_client_closed')
    def test_concurrent_edit_preserved(self, _):
        plan = subject.build_plan(self.root)
        changed = plan[1].before + '\r\n; concurrent'.encode('utf-16-le')
        plan[1].path.write_bytes(changed)
        with self.assertRaises(PatchError): subject.install(self.root, plan)
        self.assertEqual(plan[0].path.read_bytes(), plan[0].before)
        self.assertEqual(plan[1].path.read_bytes(), changed)

    @patch.object(subject, 'assert_client_closed')
    def test_second_write_failure_rolls_back_first_locale(self, _):
        plan = subject.build_plan(self.root)
        def write(path, data):
            if path == plan[1].path and data == plan[1].after:
                raise OSError('injected second-locale write failure')
            atomic_write(path, data)
        with patch.object(subject, 'atomic_write', side_effect=write):
            with self.assertRaises(OSError): subject.install(self.root, plan)
        for change in plan: self.assertEqual(change.path.read_bytes(), change.before)

    @patch.object(subject, 'assert_client_closed', side_effect=PatchError('client open'))
    def test_running_client_prevents_all_writes(self, _):
        with self.assertRaises(PatchError): subject.install(self.root, subject.build_plan(self.root))
        for path, before in self.before.items(): self.assertEqual(path.read_bytes(), before)

    def test_server_uses_presentation_alias_damage_stays580(self):
        root = Path(__file__).resolve().parents[1]
        server = (root / 'src/Godswar.Server/Game/GameSessionRegistry.WonderlandCombat.GroundFire.cs').read_text()
        self.assertRegex(server, r'WonderlandGroundFireVisualSkillId\s*=\s*589;')
        policy = (root / 'src/Godswar.Server/Application/WorldInstances/WonderlandBossAbilityPolicy.cs').read_text()
        self.assertRegex(policy, r'TerrainFire\s*\{ get; \}\s*=\s*Ability\("Ground Fire",\s*580,')


if __name__ == '__main__':
    unittest.main()
