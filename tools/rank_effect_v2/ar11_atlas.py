"""Strict AR11 private-atlas and composite-canonical authoring.

Every visible AR11 role owns a private full-atlas recolour.  The canonical
fallback is a spatial composite of the same role contracts.  Authoring fails
closed if any active, nontransparent source pixel retains its old RGB value,
or if recolouring changes an inactive/out-of-region pixel or alpha byte.
"""

from __future__ import annotations

from dataclasses import dataclass

from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import validate_tga_texture

from .armor_ranks import AR11_ROLE_ATLASES, AtlasPalette
from .atlas import RecolourResult, Region, recolour_luminance


FULL_ATLAS = Region(0.0, 1.0, 0.0, 1.0)
AR11_CANONICAL_REGIONS = (
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
class Ar11AtlasSegment:
    """Measured output contract for one role and one atlas region."""

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
class AuthoredAr11Atlas:
    """Validated recolour plus truthful top-level and segment metadata."""

    recolour: RecolourResult
    segments: tuple[Ar11AtlasSegment, ...]

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
        raise RankEffectError(f"AR11 requires a raw identifier-free 64x64 atlas: {label}")
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
    *,
    require_complete: bool,
) -> tuple[int, int]:
    source_layout = _raw_atlas(source, f"{label} source")
    output_layout = _raw_atlas(output, f"{label} output")
    if source_layout != output_layout or len(source) != len(output):
        raise RankEffectError(f"AR11 atlas layout changed: {label}")
    if source[:18] != output[:18] or source[source_layout.payload_end :] != output[
        source_layout.payload_end :
    ]:
        raise RankEffectError(f"AR11 atlas header/footer changed: {label}")

    active_pixels = 0
    changed_pixels = 0
    for u, v, offset in _pixels(source_layout):
        source_rgb = source[offset : offset + 3]
        output_rgb = output[offset : offset + 3]
        changed = source_rgb != output_rgb
        alpha = (
            source[offset + 3] if source_layout.bytes_per_pixel == 4 else 255
        )
        if source_layout.bytes_per_pixel == 4 and output[offset + 3] != alpha:
            raise RankEffectError(f"AR11 atlas alpha changed: {label}")
        selected = region.contains(u, v)
        active = selected and alpha != 0 and max(source_rgb) / 255.0 > 0.015
        if active:
            active_pixels += 1
            changed_pixels += int(changed)
        elif changed:
            raise RankEffectError(
                f"AR11 atlas changed an inactive or out-of-region pixel: {label}"
            )

    if require_complete and changed_pixels != active_pixels:
        survivors = active_pixels - changed_pixels
        raise RankEffectError(
            f"AR11 atlas retained {survivors} active old-hue pixels: {label}"
        )
    return active_pixels, changed_pixels


def _validate_partition() -> None:
    for y in range(64):
        v = y / 63.0
        for x in range(64):
            u = x / 63.0
            owners = sum(region.contains(u, v) for _role, region in AR11_CANONICAL_REGIONS)
            if owners != 1:
                raise RankEffectError("AR11 canonical regions do not partition the atlas")


def _author_segment(
    source: bytes,
    role: str,
    region: Region,
) -> tuple[RecolourResult, Ar11AtlasSegment]:
    try:
        design = AR11_ROLE_ATLASES[role]
    except KeyError as error:
        raise RankEffectError(f"Unknown AR11 atlas role: {role}") from error
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
    active, changed = _coverage(
        source,
        result.encoded,
        region,
        role,
        require_complete=True,
    )
    if (
        result.changed_pixels != changed
        or result.alpha_changes != 0
        or result.outside_region_changes != 0
    ):
        raise RankEffectError(f"AR11 atlas counters disagree for {role}")
    return result, Ar11AtlasSegment(
        role,
        region,
        palette,
        design.luma_gain,
        design.maximum_channel,
        active,
        changed,
    )


def author_ar11_private(source: bytes, role: str) -> AuthoredAr11Atlas:
    """Author one role-private full atlas with complete active-pixel coverage."""

    result, segment = _author_segment(source, role, FULL_ATLAS)
    return AuthoredAr11Atlas(result, (segment,))


def author_ar11_canonical(source: bytes) -> AuthoredAr11Atlas:
    """Author the disjoint halo/rune/wing canonical fallback composite."""

    _validate_partition()
    encoded = source
    segments: list[Ar11AtlasSegment] = []
    for role, region in AR11_CANONICAL_REGIONS:
        result, segment = _author_segment(encoded, role, region)
        encoded = result.encoded
        segments.append(segment)
    changed = sum(segment.changed_pixels for segment in segments)
    active, final_changed = _coverage(
        source,
        encoded,
        FULL_ATLAS,
        "canonical-composite",
        require_complete=True,
    )
    if active != sum(segment.active_pixels for segment in segments) or final_changed != changed:
        raise RankEffectError("AR11 canonical segment coverage does not match the composite")
    return AuthoredAr11Atlas(
        RecolourResult(encoded, changed, 0, 0),
        tuple(segments),
    )
