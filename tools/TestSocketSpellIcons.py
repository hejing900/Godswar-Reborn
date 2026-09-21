"""Regression checks for four isolated Socket Spell cells and exact client edits."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from holy_stone_icons.catalog import sha256
from holy_stone_icons.packing import png_bytes
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import install
from level5_forge_icons.common import InstallError
from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga
from socket_spell_icons import (ATLAS, IDS, OLD_TEXTURE, TEXTURE, build_plan,
                                expected_manifest, json_bytes, pack, patch_items,
                                verify_release)


class SocketSpellArtworkChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="socket-spell-icons-")
        cls.root = Path(cls.workspace.name)
        cls.assets = cls.root / "assets"
        source = cls.assets / "source"
        source.mkdir(parents=True)
        (cls.assets / "manifest.json").write_bytes(json_bytes(expected_manifest()))
        template = Path(__file__).resolve().parents[1] / "assets/socket-spells/source"
        for name in ("native-tga-format.bin", "native-tga-format.json"):
            (source / name).write_bytes((template / name).read_bytes())
        provenance = []
        for index in range(4):
            slug = f"socket-spell-{index + 1}"
            image = Image.new("RGBA", (72, 72))
            ImageDraw.Draw(image).rectangle((4, 4, 66, 66), fill=(40 + index * 50, 120, 210, 255))
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

    def fixture(self, directory: str) -> Path:
        client = self.root / directory
        xml = "<Items>\r\n" + "\r\n".join(
            f'<Smithing{i} ID="{i}" Type="consume item" Texture="{OLD_TEXTURE}" '
            'Icon="108,900" Money="0" Overlap="99"/>' for i in IDS)
        xml += (f'\r\n<Oracle4 ID="3817" Texture="{OLD_TEXTURE}" Icon="108,900" BindType="1"/>\r\n'
                f'<VIPbag14047 ID="14047" Texture="{OLD_TEXTURE}" Icon="108,900" Overlap="99"/>\r\n'
                '<HolyStone ID="9030" Texture="Icon2.gwo" Icon="252,0"/>\r\n</Items>\r\n')
        for locale in ("en_us", "zh_cn"):
            base = client / "Localization" / locale
            path = base / "Settings/Sys/ItemBaseAttribute.xml"
            path.parent.mkdir(parents=True)
            encoding, bom = ("utf-16-le", b"\xff\xfe") if locale == "en_us" else ("utf-8", b"\xef\xbb\xbf")
            path.write_bytes(bom + xml.encode(encoding))
            (base / "UI/Texture").mkdir(parents=True)
            for name in ("Icon.gwo", "Icon2.gwo", "Icon5.gwo", "HolyStoneReagents.gwo"):
                (base / "UI/Texture" / name).write_bytes(b"existing approved atlas:" + name.encode())
        return client

    def test_pack_is_reproducible_and_only_four_native_cells_have_pixels(self):
        self.assertEqual(pack(self.assets), self.outputs)
        atlas = parse_tga(verify_release(self.assets), ATLAS)
        cleared = bytearray(atlas.pixels)
        colors = set()
        for index in range(4):
            for y in range(36):
                start = display_pixel_index(atlas, index * 36, y) * 4
                cleared[start:start + 36 * 4] = bytes(36 * 4)
            point = display_pixel_index(atlas, index * 36 + 18, 18) * 4
            colors.add(atlas.pixels[point:point + 4])
        self.assertEqual(len(colors), 4)
        self.assertEqual(cleared, bytes(1024 * 1024 * 4))

    def test_four_file_install_preserves_aliases_other_art_and_encoding(self):
        client = self.fixture("valid")
        plan = build_plan(client, self.assets)
        self.assertEqual(len(plan), 4)
        self.assertTrue(all(change.changed for change in plan))
        result = install(client, plan)
        self.assertEqual(result["files_changed"], 4)
        backup = Path(result["backup_manifest"]).parent
        for change in plan:
            if change.before is not None:
                self.assertEqual((backup / change.path.relative_to(client)).read_bytes(), change.before)
                self.assertEqual(change.after.startswith(b"\xff\xfe"), change.before.startswith(b"\xff\xfe"))
                self.assertEqual(change.after.startswith(b"\xef\xbb\xbf"), change.before.startswith(b"\xef\xbb\xbf"))
        for locale in ("en_us", "zh_cn"):
            base = client / "Localization" / locale
            xml = Document.read(base / "Settings/Sys/ItemBaseAttribute.xml").text
            self.assertIn(f'<Oracle4 ID="3817" Texture="{OLD_TEXTURE}" Icon="108,900" BindType="1"/>', xml)
            self.assertIn(f'<VIPbag14047 ID="14047" Texture="{OLD_TEXTURE}" Icon="108,900" Overlap="99"/>', xml)
            self.assertIn('<HolyStone ID="9030" Texture="Icon2.gwo" Icon="252,0"/>', xml)
            for index, item_id in enumerate(IDS):
                self.assertIn(f'ID="{item_id}" Type="consume item" Texture="{TEXTURE}" '
                              f'Icon="{index * 36},0" Money="0" Overlap="99"', xml)
            for name in ("Icon.gwo", "Icon2.gwo", "Icon5.gwo", "HolyStoneReagents.gwo"):
                self.assertEqual((base / "UI/Texture" / name).read_bytes(), b"existing approved atlas:" + name.encode())
        self.assertFalse(any(change.changed for change in build_plan(client, self.assets)))

    def test_unknown_atlas_mapping_or_new_alias_is_rejected(self):
        client = self.fixture("unknown")
        (client / "Localization/en_us/UI/Texture" / ATLAS).write_bytes(b"unknown art")
        with self.assertRaisesRegex(InstallError, "unknown Socket Spell atlas"):
            build_plan(client, self.assets)
        xml = Document.read(client / "Localization/en_us/Settings/Sys/ItemBaseAttribute.xml").text
        with self.assertRaisesRegex(PatchError, "reviewed old or new"):
            patch_items(xml.replace('Icon="108,900"', 'Icon="144,900"', 1))
        with self.assertRaisesRegex(PatchError, "Unrelated item"):
            patch_items(xml.replace(f'<Oracle4 ID="3817" Texture="{OLD_TEXTURE}"',
                                    f'<Oracle4 ID="3817" Texture="{TEXTURE}"'))


if __name__ == "__main__":
    unittest.main()
