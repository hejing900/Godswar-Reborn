"""Strict full-blue private/canonical atlas authoring for AR12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import validate_tga_texture

from .ar12_aether import AR12_ROLE_ATLASES
from .armor_ranks import AtlasPalette, RoleAtlasDesign
from .atlas import RecolourResult, Region, recolour_luminance


FULL_ATLAS = Region(0.0, 1.0, 0.0, 1.0)
AR12_CANONICAL_REGIONS = (
    ("animated-core", Region(0.0, 0.27, 0.0, 1.0)),
    ("animated-rune", Region(0.27, 0.39, 0.0, 1.0)),
    ("animated-butterfly", Region(0.39, 1.0, 0.0, 1.0)),
)


def _palette_metadata(palette: AtlasPalette | None) -> dict[str, object] | None:
    if palette is None:
        return None
    return {
        "shadow": list(palette.shadow),
        "middle": list(palette.middle),
        "highlight": list(palette.highlight),
        "strength": palette.strength,
    }


@dataclass(frozen=True, slots=True)
class Ar12AtlasSegment:
    role: str
    region: Region
    palette: AtlasPalette | None
    luma_gain: float | None
    maximum_channel: int | None
    active_pixels: int
    changed_pixels: int

    @property
    def strength(self) -> float | None:
        return None if self.palette is None else self.palette.strength

    def contract_metadata(self) -> dict[str, object]:
        return {
            "role": self.role,
            "region": [
                self.region.minimum_u,
                self.region.maximum_u,
                self.region.minimum_v,
                self.region.maximum_v,
            ],
            "palette": _palette_metadata(self.palette),
            "strength": self.strength,
            "luma_gain": self.luma_gain,
            "maximum_channel": self.maximum_channel,
            "active_pixels": self.active_pixels,
            "changed_pixels": self.changed_pixels,
        }


@dataclass(frozen=True, slots=True)
class AuthoredAr12Atlas:
    recolour: RecolourResult
    segments: tuple[Ar12AtlasSegment, ...]

    @property
    def active_pixels(self) -> int:
        return sum(segment.active_pixels for segment in self.segments)

    def contract_metadata(self) -> dict[str, object]:
        uniform = self.segments[0] if len(self.segments) == 1 else None
        return {
            "active_pixels": self.active_pixels,
            "changed_pixels": self.recolour.changed_pixels,
            "palette": _palette_metadata(uniform.palette) if uniform else None,
            "strength": uniform.strength if uniform else None,
            "luma_gain": uniform.luma_gain if uniform else None,
            "maximum_channel": uniform.maximum_channel if uniform else None,
            "segments": [segment.contract_metadata() for segment in self.segments],
        }


@dataclass(frozen=True, slots=True)
class _RawAtlas:
    width: int
    height: int
    bytes_per_pixel: int
    top_origin: bool
    right_origin: bool
    payload_end: int


def _raw_atlas(data: bytes, label: str) -> _RawAtlas:
    info = validate_tga_texture(data, label)
    if (
        info.width != 64
        or info.height != 64
        or data[0] != 0
        or data[1] != 0
        or info.image_type != 2
    ):
        raise RankEffectError(f"Role atlas requires a raw 64x64 image: {label}")
    bytes_per_pixel = info.bits_per_pixel // 8
    return _RawAtlas(
        info.width,
        info.height,
        bytes_per_pixel,
        bool(info.descriptor & 0x20),
        bool(info.descriptor & 0x10),
        18 + info.width * info.height * bytes_per_pixel,
    )


def _pixels(layout: _RawAtlas):
    for y in range(layout.height):
        source_y = y if layout.top_origin else layout.height - 1 - y
        v = y / (layout.height - 1)
        for x in range(layout.width):
            source_x = layout.width - 1 - x if layout.right_origin else x
            u = x / (layout.width - 1)
            offset = 18 + (
                source_y * layout.width + source_x
            ) * layout.bytes_per_pixel
            yield u, v, offset


def _coverage(
    source: bytes,
    output: bytes,
    region: Region,
    label: str,
) -> tuple[int, int]:
    source_layout = _raw_atlas(source, f"{label}:source")
    output_layout = _raw_atlas(output, f"{label}:output")
    if source_layout != output_layout or len(source) != len(output):
        raise RankEffectError(f"Role-atlas layout changed: {label}")
    if source[:18] != output[:18] or source[source_layout.payload_end :] != output[
        source_layout.payload_end :
    ]:
        raise RankEffectError(f"Role-atlas header/footer changed: {label}")

    active = changed = 0
    for u, v, offset in _pixels(source_layout):
        before = source[offset : offset + 3]
        after = output[offset : offset + 3]
        is_changed = before != after
        alpha = (
            source[offset + 3] if source_layout.bytes_per_pixel == 4 else 255
        )
        if source_layout.bytes_per_pixel == 4 and output[offset + 3] != alpha:
            raise RankEffectError(f"Role-atlas alpha changed: {label}")
        selected = region.contains(u, v)
        is_active = selected and alpha != 0 and max(before) / 255.0 > 0.015
        if is_active:
            active += 1
            changed += int(is_changed)
        elif is_changed:
            raise RankEffectError(
                f"Role atlas changed an inactive or out-of-region pixel: {label}"
            )
    if active != changed:
        raise RankEffectError(f"Role atlas retained {active - changed} old-hue pixels")
    return active, changed


def _author_segment(
    source: bytes,
    role: str,
    region: Region,
    role_atlases: Mapping[str, RoleAtlasDesign],
    family: str,
) -> tuple[RecolourResult, Ar12AtlasSegment]:
    try:
        design = role_atlases[role]
    except KeyError as error:
        raise RankEffectError(f"Unknown {family} atlas role: {role}") from error
    palette = design.palette
    result = recolour_luminance(
        source,
        region,
        palette.shadow,
        palette.middle,
        palette.highlight,
        strength=palette.strength,
        preserve_luma=True,
        luma_gain=design.luma_gain,
        maximum_channel=design.maximum_channel,
    )
    active, changed = _coverage(source, result.encoded, region, role)
    if (
        result.changed_pixels != changed
        or result.alpha_changes != 0
        or result.outside_region_changes != 0
    ):
        raise RankEffectError(f"{family} atlas counters disagree for {role}")
    return result, Ar12AtlasSegment(
        role,
        region,
        palette,
        design.luma_gain,
        design.maximum_channel,
        active,
        changed,
    )


def _validate_partition(
    regions: tuple[tuple[str, Region], ...], family: str
) -> None:
    for y in range(64):
        v = y / 63.0
        for x in range(64):
            u = x / 63.0
            owners = sum(
                region.contains(u, v) for _role, region in regions
            )
            if owners != 1:
                raise RankEffectError(f"{family} canonical regions do not partition")


def author_segmented_private(
    source: bytes,
    role: str,
    role_atlases: Mapping[str, RoleAtlasDesign],
    *,
    family: str,
) -> AuthoredAr12Atlas:
    """Recolour one full private atlas with a reviewed rank-role palette."""

    result, segment = _author_segment(
        source, role, FULL_ATLAS, role_atlases, family
    )
    return AuthoredAr12Atlas(result, (segment,))


def author_segmented_canonical(
    source: bytes,
    role_atlases: Mapping[str, RoleAtlasDesign],
    *,
    family: str,
    regions: tuple[tuple[str, Region], ...] = AR12_CANONICAL_REGIONS,
) -> AuthoredAr12Atlas:
    """Recolour a native-AR9 canonical atlas without changing its layout."""

    _validate_partition(regions, family)
    encoded = source
    segments: list[Ar12AtlasSegment] = []
    for role, region in regions:
        result, segment = _author_segment(
            encoded, role, region, role_atlases, family
        )
        encoded = result.encoded
        segments.append(segment)
    active, changed = _coverage(source, encoded, FULL_ATLAS, f"{family} canonical")
    if active != sum(segment.active_pixels for segment in segments) or changed != sum(
        segment.changed_pixels for segment in segments
    ):
        raise RankEffectError(f"{family} canonical composite coverage disagrees")
    return AuthoredAr12Atlas(
        RecolourResult(encoded, changed, 0, 0),
        tuple(segments),
    )


def author_ar12_private(source: bytes, role: str) -> AuthoredAr12Atlas:
    return author_segmented_private(
        source, role, AR12_ROLE_ATLASES, family="AR12"
    )


def author_ar12_canonical(source: bytes) -> AuthoredAr12Atlas:
    return author_segmented_canonical(
        source, AR12_ROLE_ATLASES, family="AR12"
    )


__all__ = [
    "AR12_CANONICAL_REGIONS",
    "AuthoredAr12Atlas",
    "author_ar12_canonical",
    "author_ar12_private",
    "author_segmented_canonical",
    "author_segmented_private",
]
