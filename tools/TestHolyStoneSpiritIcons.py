"""Regression checks for native atlas isolation and reversible publication."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from holy_stone_icons.catalog import parse_baseline, read_baselines, read_catalog, sha256
from holy_stone_icons.installation import accepted_current, build_plan, validate_item_consumers
from holy_stone_icons.packing import pack, png_bytes
from holy_suit_tiers.transaction import install
from level5_forge_icons.common import InstallError
from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga, patch_atlas


class HolyStoneArtworkChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="holy-stone-artwork-")
        cls.root = Path(cls.workspace.name)
        cls.assets = cls.root / "assets"
        cls.assets.mkdir()
        repo_assets = Path(__file__).resolve().parents[1] / "assets/holy-stones-and-spirits"
        (cls.assets / "manifest.json").write_bytes((repo_assets / "manifest.json").read_bytes())
        (cls.assets / "base").mkdir()
        cls.baselines = read_baselines(repo_assets)
        for name, data in cls.baselines.items():
            (cls.assets / "base" / name).write_bytes(data)
        (cls.assets / "source").mkdir()
        cls.entries = read_catalog(cls.assets)
        generation = []
        for index, entry in enumerate(cls.entries):
            image = Image.new("RGBA", (72, 72))
            ImageDraw.Draw(image).ellipse((4, 4, 67, 67), fill=(index * 9, 170, 240, 255))
            data = png_bytes(image)
            (cls.assets / "source" / (entry["slug"] + ".png")).write_bytes(data)
            generation.append({"slug": entry["slug"], "source_sha256": sha256(data)})
        (cls.assets / "generation.json").write_text(json.dumps({"entries": generation}), encoding="utf-8")
        cls.outputs = pack(cls.assets)
        for path, data in cls.outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def test_all_unowned_pixels_and_native_container_metadata_are_preserved(self):
        for name, original in self.baselines.items():
            base = parse_baseline(original, name)
            prepared = parse_tga(self.outputs[self.assets / "generated" / name], name)
            self.assertEqual(base.prefix, prepared.prefix)
            self.assertEqual(base.extension, prepared.extension)
            self.assertEqual(base.footer[4:], prepared.footer[4:])
            normalized = bytearray(prepared.pixels)
            for entry in self.entries:
                if entry["atlas"] != name:
                    continue
                for y in range(entry["y"], entry["y"] + 36):
                    for x in range(entry["x"], entry["x"] + 36):
                        position = display_pixel_index(base, x, y) * 4
                        normalized[position:position + 4] = base.pixels[position:position + 4]
            self.assertEqual(bytes(normalized), base.pixels)
            self.assertNotEqual(prepared.pixels, base.pixels)
        with Image.open(self.assets / "generated/heated-holy-stone-36.png") as image:
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertEqual(image.getpixel((18, 18))[3], 255)

    def test_unknown_valid_atlas_is_rejected_even_inside_an_owned_cell(self):
        name = "Icon2.gwo"
        baseline = self.baselines[name]
        base = parse_baseline(baseline, name)
        position = display_pixel_index(base, 252, 0)
        unknown = patch_atlas(base, {position: b"\x01\x02\x03\xff"})
        desired = self.outputs[self.assets / "generated" / name]
        accepted_current(baseline, desired, name)
        accepted_current(desired, desired, name)
        with self.assertRaisesRegex(InstallError, "Refusing unknown"):
            accepted_current(unknown, desired, name)

    def client_fixture(self, directory: str) -> Path:
        client = self.root / directory
        items = '<ItemBaseAttribute>' + ''.join(
            f'<Item ID="{e["item_id"]}" Texture="./Localization/en_us/UI/Texture/{e["atlas"]}" '
            f'Icon="{e["x"]},{e["y"]}"/>' for e in self.entries) + '</ItemBaseAttribute>'
        sockets = '<EquipStoneInfo>' + ''.join(
            f'<Zephyr ID="{i}" Texture="./Localization/en_us/UI/Texture/Icon5.gwo" IconPos="620,8"/>'
            for i in range(21, 25)) + '</EquipStoneInfo>'
        for locale in ("en_us", "zh_cn"):
            root = client / "Localization" / locale
            (root / "Settings/Sys").mkdir(parents=True)
            (root / "UI/Texture").mkdir(parents=True)
            (root / "Settings/Sys/ItemBaseAttribute.xml").write_text(items, encoding="utf-8")
            (root / "Settings/Sys/EquipStoneInfo.xml").write_text(sockets, encoding="utf-8")
            for name, data in self.baselines.items():
                (root / "UI/Texture" / name).write_bytes(data)
        return client

    def test_four_file_install_has_exact_backups_and_is_idempotent(self):
        client = self.client_fixture("valid-client")
        plan = build_plan(client, self.assets)
        self.assertEqual(sum(change.changed for change in plan), 4)
        result = install(client, plan)
        self.assertEqual(result["files_changed"], 4)
        backup = Path(result["backup_manifest"]).parent
        for change in plan:
            self.assertEqual((backup / change.path.relative_to(client)).read_bytes(), change.before)
        repeat = build_plan(client, self.assets)
        self.assertFalse(any(change.changed for change in repeat))
        self.assertEqual(install(client, repeat)["files_changed"], 0)

    def test_unrelated_item_cannot_alias_an_owned_cell(self):
        client = self.client_fixture("aliased-client")
        path = client / "Localization/en_us/Settings/Sys/ItemBaseAttribute.xml"
        content = path.read_text().replace('</ItemBaseAttribute>',
            '<Other ID="123" Texture="Icon2.gwo" Icon="253,1"/></ItemBaseAttribute>')
        with self.assertRaisesRegex(InstallError, "Unrelated item aliases"):
            validate_item_consumers(content.encode(), "fixture")


if __name__ == "__main__":
    unittest.main()
