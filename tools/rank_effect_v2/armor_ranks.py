"""Rank identities, palettes, and reviewed mixed-donor routing.

AR13/AR14 combine native AR4's orbit, the approved AR12 butterfly, and native
AR5's animated flame. Their canonical remains AR9-based while the native-UV
AR5 flame crop is copied from the AR5 canonical into both runtime textures;
the incompatible complete AR5 canonical atlas is never installed wholesale.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping


ARMOR_ORBIT_SOURCE_RANK = 4
ARMOR_CLONE_SOURCE_RANK = 9
ARMOR_RANKS = (10, 11, 12, 13, 14)
AR9_DERIVED_ARMOR_RANKS = (10, 11, 12)
CAPSTONE_ARMOR_RANKS = (13, 14)

CLONE_SLOT_ROLES = (
    "animated-core",
    "animated-butterfly",
    "animated-rune",
)
_CAPSTONE_ROLES = (
    "animated-rune",
    "animated-butterfly",
    "animated-flame",
)
CAPSTONE_SLOT_ROLES: Mapping[int, tuple[str, str, str]] = MappingProxyType(
    {rank: _CAPSTONE_ROLES for rank in CAPSTONE_ARMOR_RANKS}
)
SLOT_SOURCE_RANKS: Mapping[int, tuple[int, int, int]] = MappingProxyType(
    {
        10: (9, 9, 9),
        11: (9, 9, 9),
        # AR12 starts from AR9 slot 2 and proves native-AR4 completion
        # separately in its focused role contract.
        12: (9, 9, 9),
        13: (4, 9, 5),
        14: (4, 9, 5),
    }
)

Rgb = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class AtlasPalette:
    """Luminance-preserving colours for one semantic effect atlas."""

    shadow: Rgb
    middle: Rgb
    highlight: Rgb
    strength: float = 1.0
    region: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class RoleAtlasDesign:
    """One role's palette, luma gain, and hard channel ceiling."""

    palette: AtlasPalette
    luma_gain: float
    maximum_channel: int


@dataclass(frozen=True, slots=True)
class ArmorRankDesign:
    rank: int
    name: str
    intent: str
    palette: AtlasPalette
    # Compatibility marker for focused tests: the rejected native-AR12 card
    # placement authoring path is deliberately absent for every active design.
    placements: None = None


def _palette(shadow: int, middle: int, highlight: int) -> AtlasPalette:
    def colour(value: int) -> Rgb:
        return (
            ((value >> 16) & 0xFF) / 255.0,
            ((value >> 8) & 0xFF) / 255.0,
            (value & 0xFF) / 255.0,
        )

    return AtlasPalette(colour(shadow), colour(middle), colour(highlight))


_AR11_WINGS = _palette(0x244A70, 0x5D9FD0, 0xA9D7EA)
_AR11_OUTER_WING = _palette(0x0D294B, 0x285F94, 0x6F9FC7)
_AR11_HALO = _palette(0x182F49, 0x386B91, 0x72ACC5)
_AR11_RUNE = _palette(0x276D87, 0x63C4DE, 0xBFEFFF)

_DESIGNS = {
    10: ArmorRankDesign(
        10,
        "Titansteel Inheritance",
        "exact AR9 structure and animation with a neutral-steel recolour",
        _palette(0x626970, 0xAAB2B9, 0xF5F7F8),
    ),
    11: ArmorRankDesign(
        11,
        "Aetherwing Ascendant",
        "animated stormsteel bridge with anchored inner wings",
        _AR11_WINGS,
    ),
    12: ArmorRankDesign(
        12,
        "Aetherwing Zenith",
        "expanded AR9 butterfly with native-AR4 orbit ribbons",
        _palette(0x092E68, 0x1768B8, 0x43A1DE),
    ),
    13: ArmorRankDesign(
        13,
        "Crimson Phoenix",
        "molten-gold native-AR5 flame, crimson AR12 wings, and crimson AR4 orbit",
        _palette(0x200207, 0x700B1A, 0xBE2335),
    ),
    14: ArmorRankDesign(
        14,
        "Olympian Apotheosis",
        "larger celestial-blue AR5 flame, white-gold AR12 wings, and white-gold AR4 orbit",
        _palette(0x3A3422, 0xB7A66D, 0xF8EBC5),
    ),
}

ARMOR_RANK_DESIGNS: Mapping[int, ArmorRankDesign] = MappingProxyType(_DESIGNS)
AR11_ROLE_ATLASES: Mapping[str, RoleAtlasDesign] = MappingProxyType(
    {
        "animated-core": RoleAtlasDesign(_AR11_HALO, 0.94, 200),
        "animated-butterfly": RoleAtlasDesign(_AR11_WINGS, 1.0, 220),
        "animated-rune": RoleAtlasDesign(_AR11_RUNE, 1.08, 230),
        "outer-wing": RoleAtlasDesign(_AR11_OUTER_WING, 0.95, 208),
    }
)


def design_for_rank(rank: int) -> ArmorRankDesign:
    try:
        return ARMOR_RANK_DESIGNS[rank]
    except KeyError as error:
        raise ValueError(f"Role-aware armor rank must be AR10..AR14, got {rank}") from error


def source_rank_for(rank: int) -> int:
    """Return the primary (slot-0) donor for one authored rank."""

    design_for_rank(rank)
    return SLOT_SOURCE_RANKS[rank][0]


def source_rank_for_slot(rank: int, slot: int) -> int:
    """Return the exact reviewed donor rank for a model slot."""

    design_for_rank(rank)
    if slot not in (0, 1, 2):
        raise ValueError(f"Armor model slot must be 0..2, got {slot}")
    return SLOT_SOURCE_RANKS[rank][slot]


def slot_roles_for_rank(rank: int) -> tuple[str, str, str]:
    design_for_rank(rank)
    return CAPSTONE_SLOT_ROLES.get(rank, CLONE_SLOT_ROLES)


def validate_design_catalogue() -> None:
    if tuple(ARMOR_RANK_DESIGNS) != ARMOR_RANKS:
        raise ValueError("Armor design catalogue must cover AR10 through AR14")
    if tuple(CAPSTONE_SLOT_ROLES) != CAPSTONE_ARMOR_RANKS:
        raise ValueError("Capstone slot roles must cover AR13 and AR14")
    if any(roles != _CAPSTONE_ROLES for roles in CAPSTONE_SLOT_ROLES.values()):
        raise ValueError("Capstones must pin flame/butterfly/orbit slot roles")
    if tuple(SLOT_SOURCE_RANKS) != ARMOR_RANKS:
        raise ValueError("Every armor rank must pin three donor slots")
    for rank, design in ARMOR_RANK_DESIGNS.items():
        if rank != design.rank or len(slot_roles_for_rank(rank)) != 3:
            raise ValueError(f"Incomplete role-aware armor design: AR{rank}")
        palette = design.palette
        channels = (*palette.shadow, *palette.middle, *palette.highlight)
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in channels):
            raise ValueError(f"AR{rank} palette channel is outside 0..1")
        if not math.isfinite(palette.strength) or not 0.5 <= palette.strength <= 1.0:
            raise ValueError(f"AR{rank} palette strength is unsafe")
        if palette.region != (0.0, 1.0, 0.0, 1.0):
            raise ValueError(f"AR{rank} must recolour a complete private atlas")
        if any(source not in (4, 5, 9) for source in SLOT_SOURCE_RANKS[rank]):
            raise ValueError(f"AR{rank} has an unreviewed model donor")
    for rank in CAPSTONE_ARMOR_RANKS:
        if SLOT_SOURCE_RANKS[rank] != (4, 9, 5):
            raise ValueError(f"AR{rank} must route native AR4/AR9/AR5")
    if set(AR11_ROLE_ATLASES) != {*CLONE_SLOT_ROLES, "outer-wing"}:
        raise ValueError("AR11 role palette catalogue is incomplete")
    for role, atlas in AR11_ROLE_ATLASES.items():
        if atlas.palette.region != (0.0, 1.0, 0.0, 1.0):
            raise ValueError(f"AR11 {role} must recolour the complete atlas")
        if not 0.9 <= atlas.luma_gain <= 1.1 or not 180 <= atlas.maximum_channel <= 235:
            raise ValueError(f"AR11 {role} luminance hierarchy is unsafe")


validate_design_catalogue()


__all__ = [
    "AR11_ROLE_ATLASES",
    "AR9_DERIVED_ARMOR_RANKS",
    "ARMOR_CLONE_SOURCE_RANK",
    "ARMOR_ORBIT_SOURCE_RANK",
    "ARMOR_RANK_DESIGNS",
    "ARMOR_RANKS",
    "AtlasPalette",
    "CAPSTONE_ARMOR_RANKS",
    "CAPSTONE_SLOT_ROLES",
    "CLONE_SLOT_ROLES",
    "RoleAtlasDesign",
    "design_for_rank",
    "slot_roles_for_rank",
    "source_rank_for",
    "source_rank_for_slot",
    "validate_design_catalogue",
]
