"""Synthetic Holy Suit installation, failure, and lossless-edit regressions."""
from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from level5_forge_icons.tga_atlas import parse_tga, patch_atlas
from holy_suit_tiers.content import build_plan
from holy_suit_tiers.badges import BADGE_ATLAS_PATH
from holy_suit_tiers_checks.fixtures import fixture, save
from holy_suit_tiers_checks.releases import PublishedBadgeReleaseChecks
from holy_suit_tiers_checks.materials import PublishedMaterialReleaseChecks
from holy_suit_tiers.policy import DIVINIUM_PERCENTAGES, TIERS, material_name
from holy_suit_tiers.text import Document, PatchError, element, set_attributes
from holy_suit_tiers import transaction


REPOSITORY = Path(__file__).resolve().parent.parent
ATLAS = REPOSITORY / "assets/holy-suit-wares/generated/HolySuitWare.gwo"
BADGE_ATLAS = REPOSITORY / "assets/holy-suit-badges/generated/HolySuitBadges.gwo"
ARTIFACTS = REPOSITORY / "artifacts/holy-suit-tiers-20260910"


class HolySuitPatchChecks(PublishedMaterialReleaseChecks, PublishedBadgeReleaseChecks, unittest.TestCase):
    def setUp(self) -> None:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-", dir=ARTIFACTS))
        fixture(self.root)

    def plan(self):
        return build_plan(self.root, ATLAS)

    def file(self, relative: str, locale: str = "en_us") -> Path:
        return self.root / "Localization" / locale / relative

    def text(self, relative: str, locale: str = "en_us") -> str:
        return Document.read(self.file(relative, locale)).text

    def snapshot(self) -> dict[Path, bytes]:
        return {path: path.read_bytes() for path in self.root.glob("Localization/**/*") if path.is_file()}

    def assert_rejected(self, expected: str) -> None:
        before = self.snapshot()
        with self.assertRaisesRegex(PatchError, expected):
            self.plan()
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "backups").exists())

    def test_complete_install_backup_and_idempotence(self) -> None:
        before = self.snapshot()
        planned = self.plan()
        self.assertEqual(30, len(planned))
        self.assertEqual(before, self.snapshot(), "planning is read-only")
        result = transaction.install(self.root, planned)
        self.assertEqual("Verified", result["status"])
        manifest_path = Path(result["backup_manifest"])
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual("Verified", manifest["status"])
        for path, data in before.items():
            backup = manifest_path.parent / path.relative_to(self.root)
            self.assertEqual(data, backup.read_bytes())
        after = self.snapshot()
        self.assertFalse(any(change.changed for change in self.plan()))
        self.assertEqual("AlreadyMatches", transaction.install(self.root, self.plan())["status"])
        self.assertEqual(after, self.snapshot())
        for locale in ("en_us", "zh_cn"):
            names = self.text("Text/EquipName.dat", locale)
            for tier in TIERS:
                self.assertIn(f"Shenqi{9009 + tier.number}\t{material_name(tier)}", names)
            self.assertIn("Lifing12062\tMithril Ingot", names)
            self.assertIn("\r\r\nUnownedTail\tKeep", names)
            self.assertIn("Sea \u6d77\u795e \U0001f30a", names)
            prefix = b"\xff\xfe" if locale == "en_us" else b"\xef\xbb\xbf"
            self.assertTrue(self.file("Text/EquipName.dat", locale).read_bytes().startswith(prefix))
            self.assertFalse(names.endswith("\n"))
            self.assertIn('HS_X0_32 = "Fire Spirits"', self.text("UI/Base/text.lua", locale))
            self.assertIn("Arcanite", self.text("UI/Base/LuaText.lua", locale))
            self.assertIn("Leave unrelated daily/reward wording", self.text("UI/Base/LuaText.lua", locale))
            effects = self.text("Settings/Sys/EquipEffect.xml", locale)
            for index, percent in enumerate(DIVINIUM_PERCENTAGES):
                self.assertIn(f'LvId="{801 + index}" Effect="0.{percent}"', effects)
                self.assertIn(f'Fun="{percent}"', effects)
            self.assertIn('LvId="710" Effect="0.7" Exp="99" Fun="70"', effects)
            self.assertIn('LvId="809" Effect="0.88" Exp="126" Fun="88"', effects)
            self.assertIn('LvId="810" Effect="0.90" Exp="999999999" Fun="90"', effects)
            for folder in ("Settings/Sys", "UI/XML"):
                self.assertIn('Type="8" Conditions="10" IcoPos="684,355"', self.text(folder + "/EquipSuitInfoIni.xml", locale))
            layout = self.text("UI/XML/HelpSystem.xml", locale)
            self.assertIn('<DiviniumBtn ', layout)
            self.assertIn('Rectangle="10,570,80,590" SText="HS_X0_19"', layout)
            self.assertIn('<Other Rectangle="0,600,10,620"', layout)
            help_text = self.text("UI/XML/HelpSystemConfig.lua", locale)
            self.assertIn("maximum bonus of 50%", help_text)
            self.assertIn("maximum bonus of 70%", help_text)
            self.assertIn("71%-90%", help_text)
            self.assertIn("99 Experience Prism", help_text)
            self.assertNotIn("Mithril Suit", help_text)

    def test_existing_effects_unchanged_except710_cost(self) -> None:
        original = self.text("Settings/Sys/EquipEffect.xml")
        after = next(change.after for change in self.plan() if change.path == self.file("Settings/Sys/EquipEffect.xml"))
        current = after.decode("utf-8-sig")
        for row in re.findall(r"<[^<>]+/>", original):
            if 'LvId="710"' not in row:
                self.assertIn(row, current)

    def test_only_selected_locale(self) -> None:
        before = self.snapshot()
        transaction.install(self.root, build_plan(self.root, ATLAS, ("en_us",)))
        for path, value in before.items():
            if "zh_cn" in path.parts:
                self.assertEqual(value, path.read_bytes())

    def test_material_id_collision(self) -> None:
        path = self.file("Settings/Sys/ItemBaseAttribute.xml", "zh_cn")
        save(path, self.text("Settings/Sys/ItemBaseAttribute.xml", "zh_cn").replace("</Items>", '<Unrelated ID="9017"/></Items>'))
        self.assert_rejected("ID9017")

    def test_material_key_collision(self) -> None:
        path = self.file("Text/EquipName.dat")
        save(path, self.text("Text/EquipName.dat") + "\r\nShenqi9017\tUnrelated ware", wide=True)
        self.assert_rejected("occupied")

    def test_duplicate_existing_key(self) -> None:
        path = self.file("Text/EquipName.dat")
        save(path, self.text("Text/EquipName.dat") + "\r\nShenqi9014\tDuplicate", wide=True)
        self.assert_rejected("Duplicate")

    def test_missing_existing_key(self) -> None:
        path = self.file("Text/EquipName.dat")
        save(path, re.sub(r"Shenqi9014\t[^\r\n]*", "Gone\tKeep", self.text("Text/EquipName.dat")), wide=True)
        self.assert_rejected("Missing")

    def test_effect_collision(self) -> None:
        path = self.file("Settings/Sys/EquipEffect.xml")
        save(path, self.text("Settings/Sys/EquipEffect.xml").replace("</EquipEff>", '<Other LvId="801"/></EquipEff>'))
        self.assert_rejected("effect code")

    def test_badge_collision(self) -> None:
        path = self.file("UI/XML/EquipSuitInfoIni.xml")
        save(path, self.text("UI/XML/EquipSuitInfoIni.xml").replace("</EquipSuitInfoIni>", '<Other Type="8"/></EquipSuitInfoIni>'))
        self.assert_rejected("Type8")

    def test_badges_match_actual_native_bag_texture(self) -> None:
        # This catches the regression that content-only per-row MtPath tests
        # missed: hover and normal refresh change UV, not the control texture.
        transaction.install(self.root, self.plan())
        for locale in ("en_us", "zh_cn"):
            _, control = element(self.text("UI/XML/ItemBagsExUI.xml", locale), "SuButton")
            self.assertEqual(BADGE_ATLAS_PATH, control.get("BtnTopTexture"))
            for folder in ("Settings/Sys", "UI/XML"):
                text = self.text(folder + "/EquipSuitInfoIni.xml", locale)
                for tier, position in zip(TIERS, ("774,355", "744,355", "714,355", "684,355")):
                    for index in range(1, 5):
                        _, row = element(text, tier.badge_key + str(index))
                        self.assertEqual(control.get("BtnTopTexture"), row.get("MtPath"))
                        self.assertEqual(position, row.get("IcoPos"))
            items = self.text("Settings/Sys/ItemBaseAttribute.xml", locale)
            self.assertIn('HolySuitWare.gwo" Icon="108,0"', items, "ware icon keeps its dedicated atlas")

    def test_known_broken_badges_migrate_without_other_edits(self) -> None:
        transaction.install(self.root, self.plan())
        for locale in ("en_us", "zh_cn"):
            relative = "UI/XML/ItemBagsExUI.xml"
            save(self.file(relative, locale), set_attributes(self.text(relative, locale), "SuButton", {
                "BtnTopTexture": "./Localization/en_us/UI/Texture/main.gwo"}))
            for folder in ("Settings/Sys", "UI/XML"):
                relative = folder + "/EquipSuitInfoIni.xml"
                text = self.text(relative, locale)
                for tier in TIERS:
                    for index in range(1, 5):
                        text = set_attributes(text, tier.badge_key + str(index), {
                            "MtPath": f"./Localization/{locale}/UI/Texture/HolySuitWare.gwo",
                            "IcoPos": f"{tier.x},36"})
                document = Document.read(self.file(relative, locale))
                self.file(relative, locale).write_bytes(document.encode(text))
        self.file("UI/Texture/HolySuitBadges.gwo").unlink()
        broken = self.snapshot()
        plan = self.plan()
        self.assertEqual(7, sum(change.changed for change in plan))
        transaction.install(self.root, plan)
        for path, data in broken.items():
            if path.name not in ("EquipSuitInfoIni.xml", "ItemBagsExUI.xml"):
                self.assertEqual(data, path.read_bytes())
        self.assertFalse(any(change.changed for change in self.plan()))
        self.assertEqual("AlreadyMatches", transaction.install(self.root, self.plan())["status"])

    def test_unrelated_divinium_badge_not_migrated(self) -> None:
        transaction.install(self.root, self.plan())
        relative = "UI/XML/EquipSuitInfoIni.xml"
        save(self.file(relative), set_attributes(self.text(relative), "Suitdiv1", {"IcoPos": "109,36"}))
        before = self.snapshot()
        with self.assertRaisesRegex(PatchError, "occupied"):
            self.plan()
        self.assertEqual(before, self.snapshot())

    def test_native_control_texture_mismatch_rejected(self) -> None:
        relative = "UI/XML/ItemBagsExUI.xml"
        save(self.file(relative), self.text(relative).replace("main.gwo", "Other.gwo"))
        self.assert_rejected("control texture")

    def test_reviewed_chinese_control_texture_form_migrates(self) -> None:
        relative = "UI/XML/ItemBagsExUI.xml"
        path = self.file(relative, "zh_cn")
        path.write_bytes(path.read_bytes().replace(b"/en_us/", b"/zh_cn/"))
        chinese_main = self.file("UI/Texture/main.gwo", "zh_cn")
        chinese_main.parent.mkdir(parents=True, exist_ok=True)
        chinese_main.write_bytes(self.file("UI/Texture/main.gwo").read_bytes())
        before = path.read_bytes()
        transaction.install(self.root, self.plan())
        self.assertEqual(before.replace(b"./Localization/zh_cn/UI/Texture/main.gwo", BADGE_ATLAS_PATH.encode()),
                         path.read_bytes())

    def test_repaired_stock_badges_migrate_with_material_icons_unchanged(self) -> None:
        transaction.install(self.root, self.plan())
        for locale in ("en_us", "zh_cn"):
            relative = "UI/XML/ItemBagsExUI.xml"
            save(self.file(relative, locale), set_attributes(self.text(relative, locale), "SuButton", {
                "BtnTopTexture": "./Localization/en_us/UI/Texture/main.gwo"}))
            for folder in ("Settings/Sys", "UI/XML"):
                relative = folder + "/EquipSuitInfoIni.xml"
                text = self.text(relative, locale)
                for tier in TIERS:
                    for index in range(1, 5):
                        attributes = {"MtPath": "./Localization/en_us/UI/Texture/main.gwo"}
                        if tier.number == 8:
                            attributes["IcoPos"] = "804,165"
                        text = set_attributes(text, tier.badge_key + str(index), attributes)
                save(self.file(relative, locale), text)
        self.file("UI/Texture/HolySuitBadges.gwo").unlink()
        before = self.snapshot()
        plan = self.plan()
        self.assertEqual(7, sum(change.changed for change in plan))
        transaction.install(self.root, plan)
        for path, data in before.items():
            if path.name not in ("EquipSuitInfoIni.xml", "ItemBagsExUI.xml"):
                self.assertEqual(data, path.read_bytes())
        self.assertFalse(any(change.changed for change in self.plan()))

    def test_badge_atlas_collision_rejected(self) -> None:
        self.file("UI/Texture/HolySuitBadges.gwo").write_bytes(b"Unrelated badge atlas")
        self.assert_rejected("badge atlas is occupied")

    def test_badge_atlas_source_preserves_all_unowned_pixels(self) -> None:
        # A valid native TGA can still carry unrelated artwork changes. Change
        # one pixel outside the owned cells and require preflight rejection.
        source = self.root / "custom-badge-source.gwo"
        atlas = parse_tga(BADGE_ATLAS.read_bytes(), "badge fixture")
        changed_pixel = bytes([atlas.pixels[0] ^ 0xFF]) + atlas.pixels[1:4]
        source.write_bytes(patch_atlas(atlas, {0: changed_pixel}))
        before = self.snapshot()
        with self.assertRaisesRegex(PatchError, "outside the four owned"):
            build_plan(self.root, ATLAS, badge_atlas_source=source)
        self.assertEqual(before, self.snapshot())
        source.write_bytes(BADGE_ATLAS.read_bytes())
        plan = build_plan(self.root, ATLAS, badge_atlas_source=source)
        self.assertTrue(any(change.path.name == "HolySuitBadges.gwo" and change.changed for change in plan))

    def test_main_atlas_unchanged_and_guarded_against_concurrent_edit(self) -> None:
        path = self.file("UI/Texture/main.gwo")
        original = path.read_bytes()
        plan = self.plan()
        main_change = next(change for change in plan if change.path == path)
        self.assertFalse(main_change.changed)
        path.write_bytes(original + b"Other artwork change")
        before = self.snapshot()
        with self.assertRaisesRegex(PatchError, "changed after preflight"):
            transaction.install(self.root, plan)
        self.assertEqual(before, self.snapshot())

    def test_native_control_change_after_preflight_rejected(self) -> None:
        plan = self.plan()
        target = self.file("UI/XML/ItemBagsExUI.xml")
        target.write_bytes(target.read_bytes().replace(b"main.gwo", b"Other.gwo"))
        before = self.snapshot()
        with self.assertRaisesRegex(PatchError, "changed after preflight"):
            transaction.install(self.root, plan)
        self.assertEqual(before, self.snapshot())

    def test_unknown_help_layout(self) -> None:
        path = self.file("UI/XML/HelpSystem.xml")
        save(path, self.text("UI/XML/HelpSystem.xml").replace('10,545,80,565', '10,546,80,566'))
        self.assert_rejected("geometry")

    def test_malformed_encoding(self) -> None:
        path = self.file("Text/EquipName.dat")
        path.write_bytes(path.read_bytes() + b"\x00")
        self.assert_rejected("Invalid utf-16")

    def test_atlas_collision(self) -> None:
        path = self.file("UI/Texture/HolySuitWare.gwo")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Unrelated image")
        self.assert_rejected("Dedicated atlas")

    def test_path_escape(self) -> None:
        with self.assertRaisesRegex(PatchError, "escaped"):
            transaction.contained(self.root, self.root / ".." / "outside")

    def test_preflight_race_preserves_newer_file(self) -> None:
        plan = self.plan()
        target = self.file("UI/Base/text.lua")
        target.write_bytes(target.read_bytes() + b"\n-- Another patch\n")
        before = self.snapshot()
        with self.assertRaisesRegex(PatchError, "changed after preflight"):
            transaction.install(self.root, plan)
        self.assertEqual(before, self.snapshot())

    def test_partial_failure_removes_new_atlas_and_restores_all_old_bytes(self) -> None:
        before = self.snapshot()
        original = transaction.atomic_write
        failure_path = self.file("UI/Base/font.lua", "zh_cn")
        failed = False

        def fail_once(path: Path, data: bytes) -> None:
            nonlocal failed
            if path == failure_path and not failed:
                failed = True
                raise OSError("Injected locked client file")
            original(path, data)

        with patch.object(transaction, "atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "Injected"):
                transaction.install(self.root, self.plan())
        self.assertEqual(before, self.snapshot())
        manifests = list(self.root.glob("backups/holy-suit-tiers/*/manifest.json"))
        self.assertEqual("RolledBack", json.loads(manifests[0].read_text())["status"])
        self.assertEqual([], list(self.root.rglob("*.stage")))
        self.assertEqual("Verified", transaction.install(self.root, self.plan())["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
