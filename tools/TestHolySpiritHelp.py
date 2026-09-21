#!/usr/bin/env python3
"""Regressions for native reachability, authoritative values and lossless help migration."""
from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from holy_spirit_help.data import FIRE, WATER, ZEPHYR, LIVE_COOLED_MAXIMA, page
from holy_spirit_help.patch import (ATTRIBUTES, PREVIOUS, build_plan, config, labels, layout,
                                    normalized, proc, validate_navigation)
from holy_stone_reagents.help import UPGRADE_HELP, patch_help
from holy_suit_tiers.text import PatchError
from holy_suit_tiers.transaction import install

ROOT = Path(__file__).resolve().parents[1]


def config_fixture() -> str:
    overview = ("unowned opening\n" + PREVIOUS["overview2"] + UPGRADE_HELP +
                PREVIOUS["overview4"] + "5.unowned ending\n")
    return ('HelpSystem_Cofig = {}\n' + ''.join(
        f'HelpSystem_Cofig[{n}] = {{ static_text=[[{body}]] }}\n'
        for n, body in ((10, overview), (19, PREVIOUS["19"]), (20, PREVIOUS["20"]))) +
        'HelpSystem_Cofig[99] = { static_text=[[unowned help]] }\n')


def layout_fixture() -> str:
    return '''<Root><Container Auto="1">
<DiviniumBtn Rectangle="20,545,120,565"/>
<StoneBtn Rectangle="20,620,80,640" SText="HS_X0_33"/>
<PetsystemBtn Rectangle="10,645,80,665"/>
<PetsystemBtn1 Rectangle="20,670,120,700"/>
<PetsystemBtn2 Rectangle="20,695,120,725"/>
<LiveSkillBtn Rectangle="10,720,80,750"/>
<CreateBtn Rectangle="10,745,80,775"/>
</Container><Container1 Auto="1"><Text Rectangle="0,10,410,400" Auto="1"/></Container1></Root>'''


class HolySpiritHelpTests(unittest.TestCase):
    def test_data_matches_authoritative_definitions_and_live_overrides(self) -> None:
        source = (ROOT / 'src/Godswar.Server/Domain/Inventory/HolySpiritImplementationPolicy.cs').read_text()
        constants = dict(re.findall(r'public const (?:int|short|uint) (\w+) = (\d+);', source))
        def value(token: str) -> int:
            return int(constants.get(token.strip(), token.strip()))
        found = {}
        for kind, item, stone, affinity, effect, low, high in re.findall(
                r'(Percent|Flat)\((\d+),\s*(\w+),\s*HolySpiritImplementationAffinity\.(\w+),'
                r'\s*(\w+),\s*(\w+),\s*(\w+)\)', source):
            effect_id = value(effect)
            found[int(item)] = (effect_id, value(low), LIVE_COOLED_MAXIMA.get(effect_id, value(high)),
                                kind == 'Percent')
        expected = {s.item: (s.effect, s.minimum, s.maximum, s.percent) for s in FIRE + WATER + ZEPHYR}
        self.assertEqual(expected, found)
        snapshot = json.loads((ROOT / 'tools/holy_spirit_help/balance-snapshot.json').read_text())
        self.assertEqual({int(k): v for k, v in snapshot['live_grade_one_maxima'].items()}, LIVE_COOLED_MAXIMA)
        self.assertEqual('0.22%-0.70%', WATER[0].bracket(1))
        self.assertEqual('2.20%-7.00%', WATER[0].bracket(10))
        self.assertEqual('2.80%-6.00%', WATER[6].bracket(10))
        self.assertEqual('10.00%-20.00%', ZEPHYR[2].bracket(10))

    def test_historical_upgrades_and_unowned_sections_survive(self) -> None:
        before = config_fixture()
        after = config(before, '\n')
        self.assertEqual(after, config(after, '\n'))
        self.assertEqual(after, patch_help(after, '\n'))
        self.assertIn(UPGRADE_HELP, after)
        self.assertIn('5.unowned ending\n', after)
        self.assertTrue(after.startswith('HelpSystem_Cofig = {}\n'))
        self.assertIn('HelpSystem_Cofig[99] = { static_text=[[unowned help]] }', after)
        self.assertNotIn("Opponent's physical attacks do not affect you", after)
        self.assertIn('does not increase critical chance', after)
        self.assertEqual(2, page('Water').count('Never damages monsters.'))
        self.assertEqual(2, page('Zephyr').count('Currently has no combat effect.'))
        with self.assertRaises(PatchError):
            config(before.replace('5.50%', '5.60%', 1), '\n')

    def test_native_navigation_chain_and_unrelated_panel(self) -> None:
        original = layout_fixture()
        after = layout(original, '\n')
        callbacks, contents, tokens = proc('', '\n'), config(config_fixture(), '\n'), labels('', '\n')
        validate_navigation(after, callbacks, contents, tokens)
        self.assertEqual(after, layout(after, '\n'))
        old_root, new_root = ET.fromstring(original), ET.fromstring(after)
        for old in old_root.find('Container'):
            new = new_root.find('Container').find(old.tag)
            a, b = [int(v) for v in old.get('Rectangle').split(',')], [int(v) for v in new.get('Rectangle').split(',')]
            shift = 0 if old.tag in ('StoneBtn', 'DiviniumBtn') else 25
            self.assertEqual([a[0], a[1] + shift, a[2], a[3] + shift], b)
        self.assertEqual(ET.tostring(old_root.find('Container1')), ET.tostring(new_root.find('Container1')))
        for broken in (after.replace('Auto="1"', 'Auto="0"', 1),
                       after.replace('OnClick="' + ATTRIBUTES['OnClick'] + '"', 'OnClick="Wrong()"')):
            with self.assertRaises(PatchError):
                validate_navigation(broken, callbacks, contents, tokens)
        with self.assertRaises(PatchError):
            layout(original.replace('20,620,80,640', '20,620,80,650'), '\n')

    def test_legacy_newlines_and_exact_encoding_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            originals = {}
            for locale in ('en_us', 'zh_cn'):
                for name, body in {'XML/HelpSystemConfig.lua': config_fixture(),
                                   'XML/HelpSystemProc.lua': '-- original callback\n',
                                   'XML/HelpSystem.xml': layout_fixture(),
                                   'Base/text.lua': 'UNOWNED = "keep me"\n'}.items():
                    path = root / 'Localization' / locale / 'UI' / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    encoding, bom = ('utf-8', b'\xef\xbb\xbf') if locale == 'en_us' else ('utf-16-le', b'\xff\xfe')
                    raw = bom + body.replace('\n', '\r\r\n').encode(encoding)
                    path.write_bytes(raw)
                    originals[path.relative_to(root)] = raw
            plan = build_plan(root)
            self.assertEqual(8, sum(c.changed for c in plan))
            receipt = install(root, plan)
            self.assertEqual(8, receipt['files_changed'])
            backup = Path(receipt['backup_manifest']).parent
            for relative, raw in originals.items():
                self.assertEqual(raw, (backup / relative).read_bytes())
                self.assertEqual(raw[:2], (root / relative).read_bytes()[:2])
            self.assertFalse(any(c.changed for c in build_plan(root)))
            self.assertEqual('AlreadyMatches', install(root, build_plan(root))['status'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
