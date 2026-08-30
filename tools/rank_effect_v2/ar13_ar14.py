"""Palette and authoritative AR9-atlas contracts for AR13/AR14."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from rank_effect_packages.baseline import sha256_bytes
from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import validate_tga_texture
from .ar12_atlas import (
    AR12_CANONICAL_REGIONS,
    AuthoredAr12Atlas,
    author_segmented_canonical,
    author_segmented_private,
)
from .armor_ranks import AtlasPalette, RoleAtlasDesign


NATIVE_AR9_CANONICAL_SHA256 = (
    "0167bf3a56b55cd360a3a59ceb7331f3f369ec4ebe784e990fd855458283cadf"
)
CAPSTONE_CANONICAL_REGIONS = AR12_CANONICAL_REGIONS
CAPSTONE_FLAME_SCALE: Mapping[int, float] = MappingProxyType({13: 1.0, 14: 1.06})


def _rgb(value: int) -> tuple[float, float, float]:
    return (
        ((value >> 16) & 0xFF) / 255.0,
        ((value >> 8) & 0xFF) / 255.0,
        (value & 0xFF) / 255.0,
    )


def _role(
    shadow: int, middle: int, highlight: int, gain: float, cap: int
) -> RoleAtlasDesign:
    return RoleAtlasDesign(
        AtlasPalette(_rgb(shadow), _rgb(middle), _rgb(highlight)), gain, cap
    )


AR13_ROLE_ATLASES: Mapping[str, RoleAtlasDesign] = MappingProxyType(
    {
        "animated-core": _role(0x1A0206, 0x620916, 0xB01D30, 0.50, 150),
        "animated-rune": _role(0x120104, 0x4D0711, 0x8F1525, 0.51, 155),
        "animated-butterfly": _role(0x200207, 0x700B1A, 0xBE2335, 0.52, 160),
        "outer-wing": _role(0x2A0204, 0x8E0913, 0xDA1D28, 0.58, 180),
        # Separate the native flame from the crimson wing/orbit silhouette:
        # orange-gold base -> molten gold -> white-gold tip.
        "animated-flame": _role(0x5A2800, 0xE6A000, 0xFFF080, 0.86, 238),
    }
)
AR14_ROLE_ATLASES: Mapping[str, RoleAtlasDesign] = MappingProxyType(
    {
        "animated-core": _role(0x29261C, 0x8F835A, 0xE5D7A8, 0.94, 218),
        "animated-rune": _role(0x24221B, 0x746B4C, 0xC9BB8F, 0.96, 220),
        "animated-butterfly": _role(0x3A3422, 0xB7A66D, 0xF8EBC5, 1.00, 232),
        "outer-wing": _role(0x55481F, 0xDDC371, 0xFFFBE6, 1.06, 245),
        # Keep the white-gold silhouette while making the flame read as
        # celestial cobalt/azure with an icy-white core.
        "animated-flame": _role(0x071F5B, 0x178ED6, 0xBDEFFF, 1.03, 245),
    }
)
CAPSTONE_ROLE_ATLASES: Mapping[int, Mapping[str, RoleAtlasDesign]] = (
    MappingProxyType({13: AR13_ROLE_ATLASES, 14: AR14_ROLE_ATLASES})
)


def _designs(rank: int) -> Mapping[str, RoleAtlasDesign]:
    try:
        return CAPSTONE_ROLE_ATLASES[rank]
    except KeyError as error:
        raise RankEffectError(f"Unsupported AR9-family capstone rank: {rank}") from error


def verify_native_ar9_canonical(source: bytes, label: str) -> None:
    """Pin the runtime-authoritative canonical donor and its raw layout."""

    info = validate_tga_texture(source, label)
    if (
        sha256_bytes(source) != NATIVE_AR9_CANONICAL_SHA256
        or info.image_type != 2
        or (info.width, info.height, info.bits_per_pixel) != (64, 64, 24)
        or source[0] != 0
        or source[1] != 0
    ):
        raise RankEffectError(f"Native AR9 canonical contract changed: {label}")


def author_capstone_private(
    source: bytes, rank: int, role: str
) -> AuthoredAr12Atlas:
    return author_segmented_private(
        source, role, _designs(rank), family=f"AR{rank}"
    )


def author_capstone_canonical(source: bytes, rank: int) -> AuthoredAr12Atlas:
    verify_native_ar9_canonical(source, f"AR{rank} canonical donor")
    return author_segmented_canonical(
        source,
        _designs(rank),
        family=f"AR{rank}",
        regions=CAPSTONE_CANONICAL_REGIONS,
    )


def author_capstone_atlas(
    source: bytes, rank: int, role: str
) -> AuthoredAr12Atlas:
    """Compatibility name for the private, full-atlas authoring path."""

    return author_capstone_private(source, rank, role)


def validate_capstone_catalogue() -> None:
    expected = {
        "animated-core",
        "animated-rune",
        "animated-butterfly",
        "outer-wing",
        "animated-flame",
    }
    for rank, roles in CAPSTONE_ROLE_ATLASES.items():
        if set(roles) != expected:
            raise ValueError(f"AR{rank} AR9-family role palettes are incomplete")
        ordered = ("animated-core", "animated-rune", "animated-butterfly")
        gains = [roles[role].luma_gain for role in ordered]
        caps = [roles[role].maximum_channel for role in ordered]
        if gains != sorted(gains) or caps != sorted(caps):
            raise ValueError(f"AR{rank} AR9 palette hierarchy changed")
        for role, design in roles.items():
            if design.palette.region != (0.0, 1.0, 0.0, 1.0):
                raise ValueError(f"AR{rank} {role} must cover the full private atlas")
            if not 0.5 <= design.luma_gain <= 1.1:
                raise ValueError(f"AR{rank} {role} luma gain is unsafe")
            if not 150 <= design.maximum_channel <= 245:
                raise ValueError(f"AR{rank} {role} channel ceiling is unsafe")


validate_capstone_catalogue()


__all__ = [
    "AR13_ROLE_ATLASES",
    "AR14_ROLE_ATLASES",
    "CAPSTONE_CANONICAL_REGIONS",
    "CAPSTONE_FLAME_SCALE",
    "CAPSTONE_ROLE_ATLASES",
    "NATIVE_AR9_CANONICAL_SHA256",
    "author_capstone_atlas",
    "author_capstone_canonical",
    "author_capstone_private",
    "validate_capstone_catalogue",
    "verify_native_ar9_canonical",
]
