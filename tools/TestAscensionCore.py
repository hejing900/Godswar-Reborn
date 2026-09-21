"""Checks that item9025 receives new presentation without mechanical changes."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

from ascension_core_icons import (ATLAS, OLD_TEXTURE, TEXTURE, build_plan,
                                  expected_manifest, json_bytes, pack, patch_items,
                                  verify_release)
from holy_stone_icons.catalog import sha256
from holy_stone_icons.packing import png_bytes
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import install
from level5_forge_icons.common import InstallError
from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga


class AscensionCoreChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="ascension-core-")
        cls.root = Path(cls.workspace.name)
        cls.assets = cls.root / "assets"
        source = cls.assets / "source"
        source.mkdir(parents=True)
        (cls.assets / "manifest.json").write_bytes(json_bytes(expected_manifest()))
        template = Path(__file__).resolve().parents[1] / "assets/ascension-core/source"
        for name in ("native-tga-format.bin", "native-tga-format.json"):
            (source / name).write_bytes((template / name).read_bytes())
        image = Image.new("RGBA", (72, 72))
        ImageDraw.Draw(image).ellipse((3, 3, 68, 68), fill=(250, 215, 170, 255))
        data = png_bytes(image)
        (source / "ascension-core.png").write_bytes(data)
        (cls.assets / "generation.json").write_bytes(json_bytes({"entries": [
            {"slug": "ascension-core", "source_sha256": sha256(data)}]}))
        cls.outputs = pack(cls.assets)
        for path, data in cls.outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def fixture(self, directory: str) -> Path:
        client = self.root / directory
        item = (f'<Congregation6 ID="9025" Type="consume item" Texture="{OLD_TEXTURE}" '
                'Icon="216,72" Random="2" Distribution="150,200" Money="0" Overlap="99"/>')
        xml = ('<Items>\r\n' + item + '\r\n<Unowned ID="9024" Icon="180,72" '
               'Overlap="1" SpecialFlag="ExpBall"/>\r\n</Items>\r\n')
        names = 'Unowned\tLeave Experience Prism unchanged\r\nCongregation6\tExperience Prism\r\n'
        descriptions = ('Unowned\tCafé unrelated Prism\r\nCongregation6\tExperience Prism\r\n'
                        'SuitUpGradeExp\tEXP or Experience Prism needed for the upgrade\r\n')
        descriptions += ''.join(f'Shenqi{i}\tWare{i} uses Experience Prisms when specified.\r\n'
                                for i in range(9014, 9018))
        lua = ('OTHER = "Leave Experience Prism here"\r\n'
               'NF_L0_ZBJY8 = "Experience Prisms required"\r\n'
               'NF_L0_ZBJY10 = "1 Experience Prism costs 100,000,000 EXP and 600 B-Gold"\r\n')
        help_text = ('-- Other Experience Prism help stays unchanged\r\n' + ''.join(
            f'HelpSystem_Cofig[{i}] = {{ static_text=[[Level 1-2 | {12 + (i-16)*30} Experience Prism\r\n]] }}\r\n'
            for i in (16, 17, 18)))
        for locale in ("en_us", "zh_cn"):
            base = client / "Localization" / locale
            encoding, bom = ("utf-16-le", b"\xff\xfe") if locale == "en_us" else ("utf-8", b"\xef\xbb\xbf")
            for relative, text in (("Settings/Sys/ItemBaseAttribute.xml", xml),
                                   ("Text/EquipName.dat", names), ("Text/EquipDescription.dat", descriptions),
                                   ("UI/Base/LuaText.lua", lua), ("UI/XML/HelpSystemConfig.lua", help_text)):
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bom + text.encode(encoding))
            (base / "UI/Texture").mkdir(parents=True)
            for name in ("Icon2.gwo", "SocketSpells.gwo", "HolyStoneReagents.gwo"):
                (base / "UI/Texture" / name).write_bytes(b"Preserve approved art " + name.encode())
        return client

    def test_native_atlas_has_exactly_one_owned_cell(self):
        self.assertEqual(pack(self.assets), self.outputs)
        atlas = parse_tga(verify_release(self.assets), ATLAS)
        cleared = bytearray(atlas.pixels)
        for y in range(36):
            start = display_pixel_index(atlas, 0, y) * 4
            cleared[start:start + 36 * 4] = bytes(36 * 4)
        self.assertEqual(cleared, bytes(1024 * 1024 * 4))
        self.assertNotEqual(atlas.pixels, bytes(cleared))

    def test_two_locale_rename_preserves_item_mechanics_unowned_text_and_prior_art(self):
        client = self.fixture("valid")
        plan = build_plan(client, self.assets)
        self.assertEqual(sum(c.changed for c in plan), 12)
        result = install(client, plan)
        backup = Path(result["backup_manifest"]).parent
        for change in plan:
            if change.before is not None:
                self.assertEqual((backup / change.path.relative_to(client)).read_bytes(), change.before)
                self.assertEqual(change.before.startswith(b"\xff\xfe"), change.after.startswith(b"\xff\xfe"))
                self.assertEqual(change.before.startswith(b"\xef\xbb\xbf"), change.after.startswith(b"\xef\xbb\xbf"))
        for locale in ("en_us", "zh_cn"):
            base = client / "Localization" / locale
            item = next(n for n in ET.fromstring(Document.read(base / "Settings/Sys/ItemBaseAttribute.xml").text)
                        if n.get("ID") == "9025")
            self.assertEqual(item.attrib, {"ID": "9025", "Type": "consume item", "Texture": TEXTURE,
                                          "Icon": "0,0", "Random": "2", "Distribution": "150,200",
                                          "Money": "0", "Overlap": "99"})
            names = Document.read(base / "Text/EquipName.dat").text
            self.assertIn('Congregation6\tAscension Core\r\n', names)
            self.assertIn('Unowned\tLeave Experience Prism unchanged\r\n', names)
            descriptions = Document.read(base / "Text/EquipDescription.dat").text
            self.assertIn('Each Core represents 100,000,000 EXP and is consumed when used.', descriptions)
            self.assertIn('Unowned\tCafé unrelated Prism\r\n', descriptions)
            lua = Document.read(base / "UI/Base/LuaText.lua").text
            self.assertIn('Each Ascension Core consumes 100,000,000 EXP.', lua)
            self.assertNotIn('600 B-Gold', lua)
            self.assertIn('OTHER = "Leave Experience Prism here"\r\n', lua)
            self.assertIn('Create Ascension Cores', lua)
            help_text = Document.read(base / "UI/XML/HelpSystemConfig.lua").text
            self.assertTrue(help_text.startswith('-- Other Experience Prism help stays unchanged\r\n'))
            self.assertIn('12 Ascension Cores\r\n', help_text)
            for name in ("Icon2.gwo", "SocketSpells.gwo", "HolyStoneReagents.gwo"):
                self.assertEqual((base / "UI/Texture" / name).read_bytes(), b"Preserve approved art " + name.encode())
        self.assertFalse(any(c.changed for c in build_plan(client, self.assets)))

    def test_unknown_atlas_or_mapping_and_unrelated_new_atlas_consumer_are_rejected(self):
        client = self.fixture("unknown")
        (client / "Localization/en_us/UI/Texture" / ATLAS).write_bytes(b"unknown art")
        with self.assertRaisesRegex(InstallError, "unknown Ascension Core atlas"):
            build_plan(client, self.assets)
        xml = Document.read(client / "Localization/en_us/Settings/Sys/ItemBaseAttribute.xml").text
        with self.assertRaisesRegex(PatchError, "reviewed old or new"):
            patch_items(xml.replace('Icon="216,72"', 'Icon="0,72"'))
        with self.assertRaisesRegex(PatchError, "Unrelated item"):
            patch_items(xml.replace('<Unowned ID="9024"', f'<Unowned ID="9024" Texture="{TEXTURE}"'))


if __name__ == "__main__":
    unittest.main()
