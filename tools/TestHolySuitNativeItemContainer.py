"""Regression for native item loading, which ignores root-level material rows."""
from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from holy_suit_tiers.content import items
from holy_suit_tiers.policy import atlas_path
from holy_suit_tiers.text import PatchError


def material(item_id: int, locale: str = "en_us") -> str:
    return (f'<Shenqi{item_id} ID="{item_id}" Type="consume item" Texture="{atlas_path(locale)}" '
            f'Icon="{(item_id - 9014) * 36},0" Random="0" Distribution="0,0" Money="0" Overlap="99"/>')


def native_items(xml: str) -> dict[int, ET.Element]:
    # Match the real ItemBaseAttribute -> Item -> item traversal. A complete
    # XML ID search would hide the root-orphan bug this test guards against.
    root = ET.fromstring(xml)
    return {int(node.get("ID")): node for section in root if section.tag == "Item"
            for node in section if node.get("ID", "").isdigit()}


class NativeHolySuitItemContainerChecks(unittest.TestCase):
    def fixture(self, locale: str, *, orphan: bool) -> str:
        return ('<ItemBaseAttribute>\r\n<Item>\r\n' + '\r\n'.join(material(i, locale) for i in (9014, 9015, 9016)) +
                '\r\n</Item>\r\n<Mount><Unrelated ID="500"/></Mount>\r\n'
                '<Item><ElementStone16300 ID="16300" Type="consume item"/></Item>\r\n' +
                (material(9017, locale) + '\r\n' if orphan else '') + '</ItemBaseAttribute>\r\n')

    def test_existing_orphan_moves_beside_seraphite_and_loads_natively(self):
        for locale in ("en_us", "zh_cn"):
            with self.subTest(locale=locale):
                before = self.fixture(locale, orphan=True)
                self.assertNotIn(9017, native_items(before))
                after = items(before, '\r\n', locale)
                loaded = native_items(after)
                self.assertIn(9017, loaded)
                self.assertEqual(loaded[9017].attrib, ET.fromstring(material(9017, locale)).attrib)
                root = ET.fromstring(after)
                self.assertEqual([int(n.get("ID")) for n in root[0]], [9014, 9015, 9016, 9017])
                # ElementTree attaches the removed row's surrounding blank
                # lines to its former previous sibling; ignore only that tail.
                self.assertEqual(ET.tostring(root[1]).rstrip(), ET.tostring(ET.fromstring(before)[1]).rstrip())
                self.assertEqual(ET.tostring(root[2]).rstrip(), ET.tostring(ET.fromstring(before)[2]).rstrip())
                self.assertEqual(items(after, '\r\n', locale), after)

    def test_new_definition_inherits_the_native_predecessor_container(self):
        before = self.fixture("en_us", orphan=False)
        after = items(before, '\r\n', "en_us")
        self.assertIn(9017, native_items(after))
        self.assertEqual(items(after, '\r\n', "en_us"), after)

    def test_duplicates_wrong_parent_and_unknown_orphan_attributes_are_rejected(self):
        before = self.fixture("en_us", orphan=True)
        with self.assertRaisesRegex(PatchError, "already allocated"):
            items(before.replace('</ItemBaseAttribute>', material(9017) + '</ItemBaseAttribute>'), '\r\n', "en_us")
        with self.assertRaisesRegex(PatchError, "unreviewed container"):
            items(before.replace(material(9017), '<Mount>' + material(9017) + '</Mount>'), '\r\n', "en_us")
        with self.assertRaisesRegex(PatchError, "unrelated content"):
            items(before.replace(material(9017), material(9017).replace('Overlap="99"', 'Overlap="1"')), '\r\n', "en_us")


if __name__ == "__main__":
    unittest.main()
