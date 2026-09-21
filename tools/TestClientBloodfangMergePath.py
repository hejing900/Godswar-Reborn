#!/usr/bin/env python3
"""Native merge-effect path, exact v4 repair, and scale-only v5 upgrade."""
import ntpath
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from bloodfang_client import model_config, release
from holy_suit_tiers.text import Document, PatchError


SLASH = chr(92)


def document(text):
    return Document(text, 'utf-8', b'\xef\xbb\xbf', '\r\n')


def previous_xml():
    # The faulty v4 bytes are authored independently of the production path
    # builder so a regression cannot silently change both sides of the test.
    nodes = model_config.nodes(model_config.V4_PROFILE)
    for node in nodes:
        for index, row in enumerate(node.findall('PetModel'), 1):
            row.set('unitefile', SLASH.join(('', 'Characters', 'PetUniteEffect',
                                            f'e_he_000{index}_all.gwm')))
    rows = [ET.tostring(n, encoding='unicode') for n in nodes]
    return ('<PetModel>\r\n<!-- Unrelated bytes stay unchanged -->\r\n'
            + '\r\n'.join(rows).replace('="', " = '").replace('"', "'")
            + '\r\n<Other untouched="yes"/>\r\n</PetModel>\r\n')


class BloodfangMergePathTests(unittest.TestCase):
    def test_all_genders_and_rebirth_stages_match_native_directory_rule(self):
        base = r'C:\Godswar Origin'
        for node in model_config.nodes(release.MODEL_PROFILE):
            self.assertEqual([0, 8, 20, 90], [int(r.get('Samsara')) for r in node.findall('PetModel')])
            for index, row in enumerate(node.findall('PetModel'), 1):
                filename = f'e_he_000{index}_all.gwm'
                expected = (SLASH * 2).join(('', 'Characters', 'PetUniteEffect', filename))
                self.assertEqual(expected, row.get('unitefile'))
                resolved = ntpath.normpath(base + row.get('unitefile')[1:])
                self.assertEqual(ntpath.join(base, 'Characters', 'PetUniteEffect', filename), resolved)

    def test_new_paths_match_stock_blue_crystal_dragon_byte_for_byte(self):
        path = Path(r'C:\Godswar Origin\Localization\en_us\Settings\Sys\Pet.xml')
        stock = ET.fromstring(Document.read(path).text)
        for gender, node in enumerate(model_config.nodes(release.MODEL_PROFILE)):
            expected = stock.find(f'Pet12_{gender}').findall('PetModel')
            actual = node.findall('PetModel')
            self.assertEqual([r.get('unitefile') for r in expected],
                             [r.get('unitefile') for r in actual])

    def test_v4_upgrade_changes_only_eight_paths_and_preserves_encoding(self):
        before = previous_xml()
        after = model_config.update(document(before), model_config.V4_PROFILE)
        expected = re.sub(r"unitefile = '([^']+)'",
                          lambda match: "unitefile = '" + match[1].replace(SLASH, SLASH * 2) + "'", before)
        self.assertEqual(expected, after)
        self.assertEqual(8, len(re.findall(r'unitefile', after)))
        for encoding, bom in (('utf-8', b''), ('utf-8', b'\xef\xbb\xbf'),
                              ('utf-16-le', b'\xff\xfe')):
            doc = Document(before, encoding, bom, '\r\n')
            self.assertEqual(bom + expected.encode(encoding),
                             doc.encode(model_config.update(doc, model_config.V4_PROFILE)))
        self.assertEqual(after, model_config.update(document(after), model_config.V4_PROFILE))

    def test_release_preserves_model_assets_and_portrait(self):
        self.assertEqual('reborn.bloodfang-species46.v6', release.PATCH_ID)
        self.assertEqual({
            'Bloodfang_male_001.jcs': '2a9276ed42b191a70b554a304afe89195add643fde3f2d8d4f35ff526eb7b7df',
            'Bloodfang_male_001.gwo': 'afa6e9b228320db15c780aa20531b88ecb2e2306ef7e7abf1724b0823f3fe292',
        }, release.ASSET_HASHES)
        before = ET.fromstring(previous_xml())
        after = ET.fromstring(model_config.update(document(previous_xml()), model_config.V4_PROFILE))
        for old, new in zip(before.findall('./Pet46_0/PetModel') + before.findall('./Pet46_1/PetModel'),
                            after.findall('./Pet46_0/PetModel') + after.findall('./Pet46_1/PetModel'), strict=True):
            old.attrib.pop('unitefile'); new.attrib.pop('unitefile')
            self.assertEqual(old.attrib, new.attrib)
        for gender in (0, 1):
            self.assertEqual(before.find(f'Pet46_{gender}/PetInfo').attrib,
                             after.find(f'Pet46_{gender}/PetInfo').attrib)

    def test_v5_upgrade_changes_only_scale_for_both_genders_and_all_stages(self):
        before = model_config.update(document(previous_xml()), model_config.V4_PROFILE)
        expected = before.replace("Scale = '0.35f'", "Scale = '0.525f'").replace(
            "Scale = '0.385f'", "Scale = '0.5775f'")
        self.assertNotEqual(before, expected)
        for encoding, bom in (('utf-8', b''), ('utf-8', b'\xef\xbb\xbf'),
                              ('utf-16-le', b'\xff\xfe')):
            doc = Document(before, encoding, bom, '\r\n')
            after = model_config.update(doc, release.MODEL_PROFILE)
            self.assertEqual(bom + expected.encode(encoding), doc.encode(after))
            self.assertEqual(after, model_config.update(document(after), release.MODEL_PROFILE))
        self.assertEqual(2, expected.count("Scale = '0.525f'"))
        self.assertEqual(6, expected.count("Scale = '0.5775f'"))

    def test_partial_mixed_or_unknown_v4_path_edits_fail_closed(self):
        before = previous_xml()
        path = re.search(r"unitefile = '([^']+)'", before)[1]
        changes = [before.replace(path, path.replace(SLASH, SLASH * 2), 1),
                   before.replace(path, path.replace(SLASH, SLASH * 2), 4),
                   before.replace(path, SLASH + path, 1),
                   before.replace(path, path.replace('0001', '0009'), 1),
                   before.replace("Scale = '0.35f'", "Scale = '0.36f'", 1),
                   before.replace("IconPos = '396,864'", "IconPos = '864,900'", 1)]
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(PatchError):
                model_config.update(document(changed), release.MODEL_PROFILE)


if __name__ == '__main__':
    unittest.main()
