"""Reviewed client identities and the matching ten-level Divinium curve."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    number: int
    name: str
    old_name: str
    badge_key: str
    color: str
    x: int
    adjectives: tuple[str, ...]


TIERS = (
    Tier(5, "RuneSteel", "Mithril", "Suithm", "007F4F", 0,
         ("Worn", "Sturdy", "Gleaming", "Majestic")),
    Tier(6, "Arcanite", "Orichalcum", "Suitho", "8A2BE2", 36,
         ("Weathered", "Polished", "Legendary", "Ancient")),
    Tier(7, "Seraphite", "Adamantium", "Suithx", "DC143C", 72,
         ("Celestial", "Fortified", "Resplendent", "Divine")),
    Tier(8, "Divinium", "", "Suitdiv", "FFF8E7", 108,
         ("Worn", "Gleaming", "Resplendent", "Divine")),
)
DIVINIUM_PERCENTAGES = (71, 73, 75, 77, 79, 82, 84, 86, 88, 90)
CONDITIONS = (1, 5, 8, 10)
ATLAS_NAME = "HolySuitWare.gwo"
DIVINIUM_HELP_KEY = "RebornHolySuitDivinium"
DIVINIUM_TEXT_KEY = "HS_HOLY_DIVINIUM"
MATERIAL_NAMES = ("RuneSteel Ingot", "Arcanite Crystal", "Seraphite Core", "Divinium Essence")


def atlas_path(locale: str) -> str:
    return f"./Localization/{locale}/UI/Texture/{ATLAS_NAME}"


def material_name(tier: Tier) -> str:
    return MATERIAL_NAMES[tier.number - 5]


def material_description(tier: Tier) -> str:
    previous = "Platinum" if tier.number == 5 else TIERS[tier.number - 6].name
    return (f"The Master Vestment Forger uses {material_name(tier)} to advance Level 10 {previous} "
            f"equipment into {tier.name} and upgrade {tier.name} Levels 1-10. "
            "The target level determines the material quantity. Experience Prisms are required when specified.")


def divinium_effect_rows() -> list[dict[str, str]]:
    return [{"LvId": str(801 + index), "Effect": f"0.{percent:02d}",
             "Exp": str(102 + index * 3) if index < 9 else "999999999", "Fun": str(percent)}
            for index, percent in enumerate(DIVINIUM_PERCENTAGES)]
