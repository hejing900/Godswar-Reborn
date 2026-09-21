"""Exact published-atlas migration regressions with a bounded pixel fixture."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga, patch_atlas
from holy_suit_tiers.badge_atlas import (
    PREVIOUS_BADGE_RELEASE_SHA256, NARROW_BADGE_RELEASE_SHA256, validate_badge_atlas)
from holy_suit_tiers.content import build_plan
from holy_suit_tiers.text import PatchError
from holy_suit_tiers import transaction


REPOSITORY = Path(__file__).resolve().parents[2]
WARE_ATLAS = REPOSITORY / "assets/holy-suit-wares/generated/HolySuitWare.gwo"
BASE_ATLAS = REPOSITORY / "assets/holy-suit-badges/source/main.gwo"


@lru_cache(maxsize=2)
def published_badge_release(narrow: bool = False) -> bytes:
    # Four raw30x30 BGRA cells total14,400bytes. The production packer preserves
    # all other encoded packets, so these reconstruct the full release exactly.
    suffix = "253d61" if narrow else "cc4834"
    expected = NARROW_BADGE_RELEASE_SHA256 if narrow else PREVIOUS_BADGE_RELEASE_SHA256
    pixels = (Path(__file__).parent / f"fixtures/published-badges-{suffix}.bgra").read_bytes()
    if len(pixels) != 14_400:
        raise AssertionError("Unexpected published badge fixture size")
    base = parse_tga(BASE_ATLAS.read_bytes(), "original main")
    desired = {}
    offset = 0
    for x in (774, 744, 714, 684):
        for row in range(355, 385):
            for column in range(x, x + 30):
                desired[display_pixel_index(base, column, row)] = pixels[offset:offset + 4]
                offset += 4
    data = patch_atlas(base, desired)
    if hashlib.sha256(data).hexdigest() != expected:
        raise AssertionError("Published badge fixture did not reconstruct the exact approved release")
    return data


def alter_owned_pixel(data: bytes) -> bytes:
    atlas = parse_tga(data, "badge fixture")
    for row in range(355, 385):
        for column in range(774, 804):
            index = display_pixel_index(atlas, column, row)
            pixel = atlas.pixels[index * 4:index * 4 + 4]
            if pixel[3]:
                return patch_atlas(atlas, {index: bytes([pixel[0] ^ 1]) + pixel[1:]})
    raise AssertionError("Missing visible gear fixture pixel")


class PublishedBadgeReleaseChecks:
    def test_published_badge_release_upgrade_backup_and_idempotence(self) -> None:
        transaction.install(self.root, self.plan())
        target = self.file("UI/Texture/HolySuitBadges.gwo")
        previous = published_badge_release()
        target.write_bytes(previous)
        source = self.root / "next-authored-badges.gwo"
        source.write_bytes(alter_owned_pixel(previous))
        # The new candidate remains subject to complete native/outside-cell
        # verification; only the exact old installed release gains admission.
        plan = build_plan(self.root, WARE_ATLAS, badge_atlas_source=source)
        self.assertEqual([target], [change.path for change in plan if change.changed])
        result = transaction.install(self.root, plan)
        manifest = Path(result["backup_manifest"])
        self.assertEqual(previous, (manifest.parent / target.relative_to(self.root)).read_bytes())
        self.assertEqual(source.read_bytes(), target.read_bytes())
        self.assertEqual("Verified", json.loads(manifest.read_text())["status"])
        repeated = build_plan(self.root, WARE_ATLAS, badge_atlas_source=source)
        self.assertFalse(any(change.changed for change in repeated))
        self.assertEqual("AlreadyMatches", transaction.install(self.root, repeated)["status"])

    def test_modified_published_badge_release_remains_a_collision(self) -> None:
        transaction.install(self.root, self.plan())
        for narrow in (False, True):
            with self.subTest(narrow=narrow):
                original = published_badge_release(narrow)
                tampered = alter_owned_pixel(original)
                # Valid native art inside the owned cells is not sufficient
                # to authorize replacing an unknown installed copy.
                validate_badge_atlas(tampered, BASE_ATLAS.read_bytes())
                target = self.file("UI/Texture/HolySuitBadges.gwo")
                target.write_bytes(tampered)
                source = self.root / "approved-source-badges.gwo"
                source.write_bytes(original)
                before = self.snapshot()
                with self.assertRaisesRegex(PatchError, "badge atlas is occupied"):
                    build_plan(self.root, WARE_ATLAS, badge_atlas_source=source)
                self.assertEqual(before, self.snapshot())

    def test_narrow_badge_release_upgrade_preserves_every_other_file(self) -> None:
        transaction.install(self.root, self.plan())
        target = self.file("UI/Texture/HolySuitBadges.gwo")
        prior = published_badge_release(narrow=True)
        target.write_bytes(prior)
        before = self.snapshot()
        planned = self.plan()
        self.assertEqual([target], [change.path for change in planned if change.changed])
        result = transaction.install(self.root, planned)
        backup = Path(result["backup_manifest"]).parent
        self.assertEqual(prior, (backup / target.relative_to(self.root)).read_bytes())
        for path, data in before.items():
            if path != target:
                self.assertEqual(data, path.read_bytes())
        self.assertFalse(any(change.changed for change in self.plan()))
        self.assertEqual("AlreadyMatches", transaction.install(self.root, self.plan())["status"])

    def test_advanced_badges_match_common_opaque_coverage(self) -> None:
        atlas = parse_tga((REPOSITORY / "assets/holy-suit-badges/generated/HolySuitBadges.gwo").read_bytes(),
                          "current badges")

        def solid_count(left: int, top: int, start: int = 0, end: int = 30) -> int:
            return sum(atlas.pixels[display_pixel_index(atlas, x, y) * 4 + 3] >= 128
                       for y in range(top + start, top + end) for x in range(left, left + 30))

        for tier, x in enumerate((774, 744, 714, 684), 5):
            with self.subTest(tier=tier):
                self.assertGreaterEqual(solid_count(x, 355), solid_count(864, 165))
                self.assertGreaterEqual(solid_count(x, 355, 10, 20), solid_count(864, 165, 10, 20))
