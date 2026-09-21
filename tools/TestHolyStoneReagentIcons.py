"""Checks for independent reagent artwork and reversible Platinum client updates."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from holy_stone_reagents.catalog import ATLAS, ITEMS, TEXTURE, expected_manifest, json_bytes, sha256
from holy_stone_reagents.installation import build_plan, verify_release
from holy_stone_reagents.help import OLD_UPGRADE_HELP, PREVIOUS_UPGRADE_HELP, UPGRADE_HELP, patch_help
from holy_stone_reagents.packing import pack
from holy_stone_reagents.text import patch_items, patch_result_branch
from holy_stone_icons.packing import png_bytes
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import install
from level5_forge_icons.common import InstallError
from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga


class HolyStoneReagentChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="holy-stone-reagents-")
        cls.root = Path(cls.workspace.name)
        cls.assets = cls.root / "assets"
        source = cls.assets / "source"
        source.mkdir(parents=True)
        (cls.assets / "manifest.json").write_bytes(json_bytes(expected_manifest()))
        template = Path(__file__).resolve().parents[1] / "assets/holy-stone-reagents/source"
        for name in ("native-tga-format.bin", "native-tga-format.json"):
            (source / name).write_bytes((template / name).read_bytes())
        provenance = []
        for index, (_, slug, _, _, _) in enumerate(ITEMS):
            image = Image.new("RGBA", (72, 72))
            ImageDraw.Draw(image).ellipse((3, 3, 68, 68), fill=(40 + index * 20, 120, 205, 255))
            data = png_bytes(image)
            (source / (slug + ".png")).write_bytes(data)
            provenance.append({"slug": slug, "source_sha256": sha256(data)})
        (cls.assets / "generation.json").write_bytes(json_bytes({"entries": provenance}))
        cls.outputs = pack(cls.assets)
        for path, data in cls.outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def fixture(self, name: str) -> Path:
        client = self.root / name
        alias = ('<Other ID="9055" Texture="./Localization/en_us/UI/Texture/Icon.gwo" '
                 'Icon="612,936" Custom="leave this unchanged"/>')
        items = "<Items>\r\n" + "\r\n".join(
            f'<Stone{item_id} ID="{item_id}" Type="consume item" '
            f'Texture="./Localization/en_us/UI/Texture/{atlas}" Icon="{icon}" '
            'Overlap="99" Money="0"/>' for item_id, _, _, atlas, icon in ITEMS)
        items += "\r\n" + alias + "\r\n</Items>\r\n"
        rows = "Unowned\tCafé keep exactly\r\n" + "\r\n".join(
            f"Stone{i}\tOld label {i}" for i in [9040, 9041, 9042, 9050, 9051, 9052, 9053, 9054, 9055, 9056]) + "\r\n"
        lua = '-- Leave this comment and spacing exactly\r\n'
        lua += '\r\n'.join(f'{k} = "old text"' for k in
                           ("NF_L0_ZBXQ7", "NF_L0_ZBXQ8", "NF_L0_ZBXQ2400")) + '\r\n'
        branch = ('\t\telseif SubID / 100 == 30 then\r\n'
                  '\t\t\tFirstWin_Text1:SetText(NF_LO_L05);\r\n'
                  '\t\t\tFirstWin_Text1:Visible(true);\r\n'
                  '\t\t\tFirstWin_Text1:SetPosition(45,100);\r\n'
                  '\t   end;\r\n\r\n\t   NPCFUN:EndMessage(true);\r\n')
        help_text = ('-- Other help is unchanged\r\nHelpSystem_Cofig[10] = {\r\n static_text=[[\r\n'
                     'Existing introduction\r\n' + OLD_UPGRADE_HELP.replace('\n', '\r\n') +
                     '4. Existing spirit descriptions\r\n]]\r\n}\r\n')
        for locale in ("en_us", "zh_cn"):
            base = client / "Localization" / locale
            for relative, text in (("Settings/Sys/ItemBaseAttribute.xml", items),
                                   ("Text/EquipName.dat", rows), ("Text/EquipDescription.dat", rows),
                                   ("UI/Base/LuaText.lua", lua),
                                   ("UI/XML/HelpSystemConfig.lua", help_text),
                                   ("UI/XML/NpcFun/NpcFunEment.lua", branch)):
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                encoding, bom = ("utf-16-le", b"\xff\xfe") if locale == "en_us" else ("utf-8", b"\xef\xbb\xbf")
                path.write_bytes(bom + text.encode(encoding))
            (base / "UI/Texture").mkdir(parents=True)
            (base / "UI/Texture/Icon.gwo").write_bytes(b"untouched shared atlas")
        return client

    def test_reproducible_atlas_contains_only_the_eight_native_cells(self):
        self.assertEqual(pack(self.assets), self.outputs)
        encoded = verify_release(self.assets)
        atlas = parse_tga(encoded, ATLAS)
        cleared = bytearray(atlas.pixels)
        for index in range(8):
            for y in range(36):
                start = display_pixel_index(atlas, index * 36, y) * 4
                cleared[start:start + 36 * 4] = bytes(36 * 4)
        self.assertEqual(cleared, bytes(1024 * 1024 * 4))
        self.assertNotEqual(atlas.pixels, bytes(1024 * 1024 * 4))

    def test_two_locale_install_preserves_encoding_aliases_and_exact_backups(self):
        client = self.fixture("valid")
        plan = build_plan(client, self.assets)
        self.assertEqual(sum(change.changed for change in plan), 14)
        result = install(client, plan)
        backup = Path(result["backup_manifest"]).parent
        for change in plan:
            if change.before is not None:
                self.assertEqual((backup / change.path.relative_to(client)).read_bytes(), change.before)
                before = change.before
                self.assertEqual(change.after[:2] == b"\xff\xfe", before[:2] == b"\xff\xfe")
                self.assertEqual(change.after[:3] == b"\xef\xbb\xbf", before[:3] == b"\xef\xbb\xbf")
        for locale in ("en_us", "zh_cn"):
            base = client / "Localization" / locale
            text = Document.read(base / "Settings/Sys/ItemBaseAttribute.xml").text
            self.assertIn('ID="9055" Texture="./Localization/en_us/UI/Texture/Icon.gwo" Icon="612,936"', text)
            self.assertIn('Custom="leave this unchanged"', text)
            self.assertIn(TEXTURE, text)
            names = Document.read(base / "Text/EquipName.dat").text
            self.assertIn("Stone9054\tPlatinum Evasion Signet\r\n", names)
            self.assertIn("Stone9053\tOld label 9053\r\n", names)
            self.assertIn("Unowned\tCafé keep exactly\r\n", names)
            self.assertEqual((base / "UI/Texture/Icon.gwo").read_bytes(), b"untouched shared atlas")
            help_text = Document.read(base / "UI/XML/HelpSystemConfig.lua").text
            self.assertIn(UPGRADE_HELP.replace('\n', '\r\n'), help_text)
            self.assertTrue(help_text.startswith('-- Other help is unchanged\r\n'))
            self.assertIn('Existing introduction\r\n', help_text)
            self.assertTrue(help_text.endswith('4. Existing spirit descriptions\r\n]]\r\n}\r\n'))
        repeat = build_plan(client, self.assets)
        self.assertFalse(any(change.changed for change in repeat))
        self.assertEqual(install(client, repeat)["files_changed"], 0)

    def test_unknown_atlas_or_item_mapping_cannot_be_silently_replaced(self):
        client = self.fixture("unknown")
        target = client / "Localization/en_us/UI/Texture" / ATLAS
        target.write_bytes(b"unknown dedicated art")
        with self.assertRaisesRegex(InstallError, "unknown dedicated"):
            build_plan(client, self.assets)
        xml = Document.read(client / "Localization/en_us/Settings/Sys/ItemBaseAttribute.xml").text
        with self.assertRaisesRegex(PatchError, "reviewed old or new"):
            patch_items(xml.replace('Icon="828,900"', 'Icon="0,72"'))
        with self.assertRaisesRegex(PatchError, "Unrelated item"):
            patch_items(xml.replace('ID="9055" Texture="./Localization/en_us/UI/Texture/Icon.gwo"',
                                    f'ID="9055" Texture="{TEXTURE}"'))

    def test_result_branch_rejects_unknown_implementation(self):
        branch = '\t\telseif SubID / 100 == 34 then\r\nmalformed body\r\n'
        with self.assertRaisesRegex(PatchError, "Unknown or duplicate"):
            patch_result_branch(branch, '\r\n')

    def test_unknown_help_is_rejected_without_rewriting_other_help(self):
        text = 'HelpSystem_Cofig[10] = { static_text=[[Custom upgrade guide]] }'
        with self.assertRaisesRegex(PatchError, "audited old or updated"):
            patch_help(text, '\n')

    def test_first_published_help_migrates_without_rewriting_surrounding_text(self):
        prefix = '-- Keep this\r\nHelpSystem_Cofig[10] = { static_text=[[Introduction\r\n'
        suffix = 'Existing spirit descriptions\r\n]] }\r\n'
        previous = prefix + PREVIOUS_UPGRADE_HELP.replace('\n', '\r\n') + suffix
        desired = prefix + UPGRADE_HELP.replace('\n', '\r\n') + suffix
        self.assertEqual(patch_help(previous, '\r\n'), desired)
        self.assertEqual(patch_help(desired, '\r\n'), desired)


if __name__ == "__main__":
    unittest.main()
