"""Validate complete native badge atlases without modifying shared main.gwo."""
from __future__ import annotations

from pathlib import Path
import hashlib

from level5_forge_icons.tga_atlas import parse_tga

from .badges import (BADGE_ATLAS_NAME, BADGE_ATLAS_PATH, BADGE_POSITIONS,
                     bag_control_texture, main_atlas_path)
from .text import Document, PatchError
from .transaction import Change, contained


# Published original-size badge release, verified against both the installed
# client and repository output before widening the same four authored sprites.
PREVIOUS_BADGE_RELEASE_SHA256 = "cc4834016825ac8d0a0c26e4529517d66fb9c9be2611ba9d94815370a0e57c65"
# The subsequent19-column torso release still looked thinner than Common.
NARROW_BADGE_RELEASE_SHA256 = "253d61d4e3a8af8237276cd9f2ac0c9d6b44d19addf25d7743671e7b26566d54"


def validate_badge_atlas(data: bytes, baseline: bytes) -> None:
    try:
        atlas = parse_tga(data, BADGE_ATLAS_NAME)
        original = parse_tga(baseline, "existing main.gwo")
    except Exception as error:
        raise PatchError(f"Invalid native Holy Suit badge atlas: {error}") from error
    if atlas.prefix != original.prefix or atlas.extension != original.extension:
        raise PatchError("Badge atlas native format metadata differs from main.gwo")
    # Restore the four allowed rectangles in memory, then compare the complete
    # pixel buffers. Stock tiers0..4, fallback cells and all unrelated artwork
    # therefore remain pixel-identical; only the dedicated copy is published.
    restored = bytearray(atlas.pixels)
    for position in BADGE_POSITIONS:
        x, y = (int(value) for value in position.split(","))
        visible = 0
        for row in range(y, y + 30):
            start = ((atlas.height - 1 - row) * atlas.width + x) * 4
            end = start + 30 * 4
            visible += sum(alpha > 0 for alpha in atlas.pixels[start + 3:end:4])
            restored[start:end] = original.pixels[start:end]
        if visible < 16:
            raise PatchError(f"Missing colored gear badge at {position}")
    if restored != original.pixels:
        raise PatchError("Badge atlas changes pixels outside the four owned gear cells")


def prepare_badge_atlas(root: Path, source: Path, locales: tuple[str, ...]) -> list[Change]:
    data = source.read_bytes()
    baseline_paths = {main_atlas_path("en_us")}
    for locale in locales:
        path = contained(root, root / "Localization" / locale / "UI/XML/ItemBagsExUI.xml")
        texture = bag_control_texture(Document.read(path).text, locale)
        if texture != BADGE_ATLAS_PATH:
            baseline_paths.add(texture)
    changes = []
    for relative in sorted(baseline_paths):
        path = contained(root, root / relative.removeprefix("./"))
        before = path.read_bytes()
        validate_badge_atlas(data, before)
        changes.append(Change(path, before, before))
    target = contained(root, root / BADGE_ATLAS_PATH.removeprefix("./"))
    before = target.read_bytes() if target.exists() else None
    if (before is not None and before != data and
            hashlib.sha256(before).hexdigest() not in
            (PREVIOUS_BADGE_RELEASE_SHA256, NARROW_BADGE_RELEASE_SHA256)):
        raise PatchError("Dedicated badge atlas is occupied by different content")
    changes.append(Change(target, before, data))
    return changes
