"""Forward migration from the exact installed ingot release to distinct materials."""
from functools import lru_cache
import hashlib
from pathlib import Path
import re
from unittest.mock import patch

from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga, patch_atlas
from holy_suit_tiers.content import build_plan, validate_atlas
from holy_suit_tiers.material_release import (
    DISTINCT_MATERIAL_ATLAS_SHA256, PREVIOUS_DIVINIUM_DESCRIPTION,
    PREVIOUS_DIVINIUM_HELP, PREVIOUS_MATERIAL_ATLAS_SHA256)
from holy_suit_tiers.text import Document, PatchError, managed_block, replace_rows
from holy_suit_tiers import transaction


REPOSITORY = Path(__file__).resolve().parents[2]
ATLAS = REPOSITORY / "assets/holy-suit-wares/generated/HolySuitWare.gwo"
MATERIALS = {9014: "RuneSteel Ingot", 9015: "Arcanite Crystal",
             9016: "Seraphite Core", 9017: "Divinium Essence"}
PREVIOUS_NAMES = {9014: "RuneSteel Ware", 9015: "Arcanite Ware",
                  9016: "Seraphite Ware", 9017: "Divinium Ware"}
PREVIOUS_NPC = (
    '|cffF14187Use the ware matching the target Holy Suit tier. The target level determines '
    'the quantity. RuneSteel, Arcanite, Seraphite, and Divinium upgrades require Experience '
    'Prisms when specified.|cffffffff')


@lru_cache(maxsize=1)
def published_material_release() -> bytes:
    data = (REPOSITORY / "assets/holy-suit-wares/source/legacy-ingot-atlas.gwo").read_bytes()
    if hashlib.sha256(data).hexdigest() != PREVIOUS_MATERIAL_ATLAS_SHA256:
        raise AssertionError("Published material fixture must match the exact installed release")
    return data


class PublishedMaterialReleaseChecks:
    def test_ascension_core_presentation_survives_the_older_tier_installer(self) -> None:
        from ascension_core_text import patch_descriptions, patch_help, patch_lua
        transaction.install(self.root, self.plan())
        for locale in ("en_us", "zh_cn"):
            target = self.file("Text/EquipDescription.dat", locale)
            document = Document.read(target)
            text = document.text + document.newline + "SuitUpGradeExp\tEXP or Experience Prism needed"
            target.write_bytes(document.encode(patch_descriptions(text, document.newline)))
            target = self.file("UI/Base/LuaText.lua", locale)
            document = Document.read(target)
            target.write_bytes(document.encode(patch_lua(document.text, document.newline)))
            target = self.file("UI/XML/HelpSystemConfig.lua", locale)
            document = Document.read(target)
            target.write_bytes(document.encode(patch_help(document.text)))
        before = self.snapshot()
        self.assertFalse(any(change.changed for change in self.plan()))
        self.assertEqual("AlreadyMatches", transaction.install(self.root, self.plan())["status"])
        self.assertEqual(before, self.snapshot())

    def test_distinct_material_release_migrates_only_artwork(self) -> None:
        transaction.install(self.root, self.plan())
        prior = (REPOSITORY / "assets/holy-suit-wares/source/distinct-material-atlas.gwo").read_bytes()
        self.assertEqual(DISTINCT_MATERIAL_ATLAS_SHA256, hashlib.sha256(prior).hexdigest())
        atlas_paths = {self.file("UI/Texture/HolySuitWare.gwo", locale) for locale in ("en_us", "zh_cn")}
        for path in atlas_paths:
            path.write_bytes(prior)
        before = self.snapshot()
        planned = self.plan()
        self.assertEqual(atlas_paths, {change.path for change in planned if change.changed})
        receipt = transaction.install(self.root, planned)
        backup = Path(receipt["backup_manifest"]).parent
        for path, data in before.items():
            self.assertEqual(data, (backup / path.relative_to(self.root)).read_bytes())
            if path not in atlas_paths:
                self.assertEqual(data, path.read_bytes(), "material names, recipes and gear badges stay identical")
        self.assertFalse(any(change.changed for change in self.plan()))

    def previous_material_installation(self) -> dict[Path, bytes]:
        # Start with the complete current client shape, then restore the only
        # presentation fields that differ in the prior released installation.
        transaction.install(self.root, self.plan())
        for locale in ("en_us", "zh_cn"):
            for relative in ("Text/EquipName.dat", "Text/EquipDescription.dat"):
                target = self.file(relative, locale)
                document = Document.read(target)
                values = {}
                for item, old_name in PREVIOUS_NAMES.items():
                    if relative.endswith("EquipName.dat"):
                        value = old_name
                    else:
                        tier = old_name.split()[0]
                        previous = ("Platinum", "RuneSteel", "Arcanite", "Seraphite")[item - 9014]
                        value = (f"The Master Vestment Forger uses {old_name} to advance Level 10 {previous} "
                                 f"equipment into {tier} and upgrade {tier} Levels 1-10. "
                                 "The target level determines the ware quantity. "
                                 "Experience Prisms are required when specified.")
                    values[f"Shenqi{item}"] = value
                target.write_bytes(document.encode(replace_rows(document.text, values, document.newline)))
            target = self.file("UI/XML/HelpSystemConfig.lua", locale)
            document = Document.read(target)
            prior = managed_block("", "Holy Suit Divinium help", PREVIOUS_DIVINIUM_HELP, document.newline)
            text = re.sub(r"-- Reborn Holy Suit Divinium help: BEGIN[\s\S]*?"
                          r"-- Reborn Holy Suit Divinium help: END", lambda _: prior, document.text)
            target.write_bytes(document.encode(text))
            target = self.file("UI/Base/LuaText.lua", locale)
            document = Document.read(target)
            text = re.sub(r'^NF_L0_ZBJY8[^\r\n]*', lambda _: f'NF_L0_ZBJY8 = "{PREVIOUS_NPC}"',
                          document.text, flags=re.MULTILINE)
            target.write_bytes(document.encode(text))
            self.file("UI/Texture/HolySuitWare.gwo", locale).write_bytes(published_material_release())
        return self.snapshot()

    def assert_material_conflict(self, pattern: str) -> None:
        before = self.snapshot()
        manifests = sorted(self.root.glob("backups/holy-suit-tiers/*/manifest.json"))
        with self.assertRaisesRegex(PatchError, pattern):
            self.plan()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(manifests, sorted(self.root.glob("backups/holy-suit-tiers/*/manifest.json")))

    def test_published_material_release_upgrade_backup_and_idempotence(self) -> None:
        before = self.previous_material_installation()
        planned = self.plan()
        allowed = {self.file(relative, locale) for locale in ("en_us", "zh_cn") for relative in (
            "Text/EquipName.dat", "Text/EquipDescription.dat", "UI/Base/LuaText.lua",
            "UI/XML/HelpSystemConfig.lua", "UI/Texture/HolySuitWare.gwo")}
        self.assertEqual(allowed, {change.path for change in planned if change.changed})
        result = transaction.install(self.root, planned)
        self.assertEqual("Verified", result["status"])
        backup = Path(result["backup_manifest"]).parent
        for target, data in before.items():
            if target in allowed:
                self.assertEqual(data, (backup / target.relative_to(self.root)).read_bytes())
            else:
                self.assertEqual(data, target.read_bytes(), "gear badges, recipes and unrelated text are preserved")
        for locale in ("en_us", "zh_cn"):
            names = self.text("Text/EquipName.dat", locale)
            descriptions = self.text("Text/EquipDescription.dat", locale)
            for item, name in MATERIALS.items():
                self.assertIn(f"Shenqi{item}\t{name}", names)
                self.assertIn(f"The Master Vestment Forger uses {name}", descriptions)
                self.assertNotIn(PREVIOUS_NAMES[item], names)
                self.assertNotIn(PREVIOUS_NAMES[item], descriptions)
            help_text = self.text("UI/XML/HelpSystemConfig.lua", locale)
            self.assertIn("99 Experience Prisms + 1 Divinium Essence.", help_text)
            self.assertIn("126 Experience Prisms + 10 Divinium Essence.", help_text)
            self.assertNotIn("Divinium Ware", help_text)
            self.assertEqual(ATLAS.read_bytes(), self.file("UI/Texture/HolySuitWare.gwo", locale).read_bytes())
        after = self.snapshot()
        repeated = self.plan()
        self.assertFalse(any(change.changed for change in repeated))
        self.assertEqual("AlreadyMatches", transaction.install(self.root, repeated)["status"])
        self.assertEqual(after, self.snapshot())

    def test_modified_published_material_atlas_remains_a_collision(self) -> None:
        self.previous_material_installation()
        original = published_material_release()
        atlas = parse_tga(original, "old material fixture")
        index = next(index for index in range(atlas.width * atlas.height) if atlas.pixels[index * 4 + 3])
        pixel = atlas.pixels[index * 4:index * 4 + 4]
        tampered = patch_atlas(atlas, {index: bytes([pixel[0] ^ 1]) + pixel[1:]})
        validate_atlas(tampered)
        self.file("UI/Texture/HolySuitWare.gwo").write_bytes(tampered)
        self.assert_material_conflict("Dedicated atlas is occupied")

    def test_unknown_divinium_description_remains_a_collision(self) -> None:
        self.previous_material_installation()
        target = self.file("Text/EquipDescription.dat")
        document = Document.read(target)
        target.write_bytes(document.encode(document.text.replace(PREVIOUS_DIVINIUM_DESCRIPTION,
                                                                 PREVIOUS_DIVINIUM_DESCRIPTION + " Changed.")))
        self.assert_material_conflict("New text key is occupied.*Shenqi9017")

    def test_unknown_divinium_help_remains_a_collision(self) -> None:
        self.previous_material_installation()
        target = self.file("UI/XML/HelpSystemConfig.lua", "zh_cn")
        document = Document.read(target)
        target.write_bytes(document.encode(document.text.replace("99 Experience Prisms + 1 Divinium Ware.",
                                                                 "98 Experience Prisms + 1 Divinium Ware.")))
        self.assert_material_conflict("Managed block differs from authored content")

    def test_material_atlas_does_not_require_obsolete_badge_cells(self) -> None:
        atlas = parse_tga(published_material_release(), "old material fixture")
        cleared = {display_pixel_index(atlas, column, row): bytes(4)
                   for row in range(36, 66) for column in range(138)}
        source = self.root / "material-only-atlas.gwo"
        source.write_bytes(patch_atlas(atlas, cleared))
        validate_atlas(source.read_bytes())
        self.assertTrue(build_plan(self.root, source))

    def test_missing_material_cell_rejected(self) -> None:
        atlas = parse_tga(published_material_release(), "old material fixture")
        cleared = {display_pixel_index(atlas, column, row): bytes(4)
                   for row in range(36) for column in range(108, 144)}
        with self.assertRaisesRegex(PatchError, "Missing material pixels at 108,0"):
            validate_atlas(patch_atlas(atlas, cleared))

    def test_prior_material_release_failure_restores_every_published_byte(self) -> None:
        before = self.previous_material_installation()
        original = transaction.atomic_write
        failed = False

        def fail_once(path: Path, data: bytes) -> None:
            nonlocal failed
            if path == self.file("UI/XML/HelpSystemConfig.lua", "zh_cn") and not failed:
                failed = True
                raise OSError("Injected material publication failure")
            original(path, data)

        with patch.object(transaction, "atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "Injected material publication failure"):
                transaction.install(self.root, self.plan())
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], list(self.root.rglob("*.stage")))
