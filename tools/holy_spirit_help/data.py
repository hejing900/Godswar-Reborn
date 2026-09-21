"""Player-facing copy from implementation policy and audited live balance revision 1."""
from __future__ import annotations

from dataclasses import dataclass

HELP_KEY = "RebornHolySpiritZephyr"
LABEL_KEY = "HS_HOLY_ZEPHYR"
CALLBACK = "HelpSystem_OnClickZephyrSpiritBtn"
LIVE_COOLED_MAXIMA = {9: 70, 10: 70, 13: 60}


@dataclass(frozen=True)
class Spirit:
    item: int
    effect: int
    minimum: int
    maximum: int
    percent: bool
    name: str
    description: str

    def bracket(self, grade: int) -> str:
        def value(raw: int) -> str:
            return f"{raw * grade / 100:.2f}%" if self.percent else str(raw * grade)
        return f"{value(self.minimum)}-{value(self.maximum)}"


FIRE = (
    Spirit(9060, 1, 32, 80, True, "Destruction", "Ignores a percentage of the target's physical defense."),
    Spirit(9061, 2, 32, 80, True, "Penetration", "Ignores a percentage of the target's magic defense."),
    Spirit(9062, 5, 16, 40, False, "Fist", "Adds flat physical damage."),
    Spirit(9063, 6, 12, 30, False, "Fiery", "Adds flat magic damage."),
    Spirit(9064, 7, 24, 60, True, "Blood", "Increases critical damage by a percentage; does not increase critical chance."),
    Spirit(9065, 8, 40, 100, False, "Pressure", "Adds flat critical damage."),
    Spirit(9066, 3, 20, 50, True, "Assail", "Increases physical damage by a percentage."),
    Spirit(9067, 4, 24, 60, True, "Lightning", "Increases magic damage by a percentage."),
)
WATER = (
    Spirit(9080, 9, 22, 70, True, "Darkness", "Reduces incoming physical damage by a percentage."),
    Spirit(9081, 10, 22, 70, True, "Mist", "Reduces incoming magic damage by a percentage."),
    Spirit(9082, 11, 16, 40, False, "Silence", "Absorbs a flat amount of physical damage; does not apply silence."),
    Spirit(9083, 12, 14, 35, False, "Chillness", "Absorbs a flat amount of magic damage."),
    Spirit(9084, 19, 16, 40, True, "Ice", "Reflects a percentage of damage to attacking players. Never damages monsters."),
    Spirit(9085, 20, 16, 40, False, "Frost", "Reflects flat damage to attacking players. Never damages monsters."),
    Spirit(9086, 13, 28, 60, True, "Intent", "Reduces incoming critical damage by a percentage."),
    Spirit(9087, 14, 40, 100, False, "Resilience", "Reduces incoming critical damage by a flat amount."),
)
ZEPHYR = (
    Spirit(9090, 21, 15, 30, True, "Daedalus Spirit of Attunement",
           "Increases the host mount gear's base attribute by a percentage."),
    Spirit(9091, 22, 10, 20, True, "Hephaestus Spirit of Tempering",
           "Increases the host mount gear's appended attributes by a percentage."),
    Spirit(9092, 23, 100, 200, True, "Mnemosyne Spirit of Preservation",
           "Stores a mana-burn reduction roll. Currently has no combat effect."),
    Spirit(9093, 24, 75, 150, True, "Themis Spirit of Continuity",
           "Stores a hostile cooldown-extension reduction roll. Currently has no combat effect."),
)

CHOICES = (
    "2.|cffFFBBFF Holy Stone Choices|cffffffff: Heated, Cooled and Zephyr Holy Stones.\n"
    "Heated Holy Stones: weapons, gloves, helmets and rings.\n"
    "Cooled Holy Stones: armor, shields, sleeves, leggings, shoes, belts and amulets.\n"
    "Zephyr Holy Stones: mount headgear, armor, soul, ornament and amulet.\n"
)
OVERVIEW = (
    "4.|cffFFBBFF Choice of Holy Spirit|cffffffff: Implement a matching Spirit into a Holy Stone.\n"
    "Heated Holy Stones use Fire Spirits for defense penetration and damage bonuses. "
    "Destruction ignores physical defense; it does not grant immunity. Blood increases critical damage, not critical chance.\n"
    "Cooled Holy Stones use Water Spirits for damage reduction, absorption and player-only rebound. "
    "Ice and Frost never reflect damage to monsters.\n"
    "Zephyr Holy Stones use Zephyr Spirits on mount gear. Attunement improves base attributes; "
    "Tempering improves appended attributes. Preservation and Continuity can be implemented, "
    "but currently have no combat effect.\n"
    "Choose Fire Spirits, Water Spirits or Zephyr Spirits in this Help List for each spirit's Grade 1 and Grade 10 ranges.\n"
)


def page(family: str) -> str:
    spirits, prefix, color = {
        "Fire": (FIRE, "Fire Spirit of ", "C040FF"),
        "Water": (WATER, "Water Spirit of ", "A080FF"),
        "Zephyr": (ZEPHYR, "", "80E8CF"),
    }[family]
    lines = [f"|cFF{color}{family} Spirits|cFFFFFFFF", "",
             {"Fire": "Implement these spirits into Heated Holy Stones.",
              "Water": "Implement these spirits into Cooled Holy Stones.",
              "Zephyr": "Implement these spirits into Zephyr Holy Stones for mount gear."}[family],
             "Ranges below are per spirit, before Goddess' Stone.",
             "Grade 1 is the starting range. At Grades 2-10, multiply both Grade 1 values by the Grade.",
             "A Goddess' Stone raises the minimum roll, not the maximum.", ""]
    for spirit in spirits:
        lines.extend((f"|cFF{color}{prefix}{spirit.name}|cFFFFFFFF", spirit.description,
                      f"Grade 1: {spirit.bracket(1)}", f"Grade 10: {spirit.bracket(10)}", ""))
    if family == "Fire":
        lines.append("Flow and Tranquility are legacy items without a supported implementation effect.")
    elif family == "Water":
        lines.append("Renewal and Vitality are legacy items without a supported implementation effect.")
    else:
        lines.extend((
            "Equip a compatible mount and mount gear. These bonuses do not require riding.",
            "Attunement: headgear improves hit; armor and ornament improve HP; soul improves damage absorption; amulet improves dodge.",
            "Only the strongest two mount gear pieces contribute Attunement, and the strongest two contribute Tempering. "
            "The two selections are independent. Duplicate copies of the same spirit on one piece use only the strongest roll.",
            "Attunement is capped at 3% per piece; Tempering at 2% per piece. Bonuses apply to that piece, not the character's total attributes.",
            "Preservation and Continuity have no active mana-burn or hostile cooldown-extension attacks to protect against yet. "
            "Their stored rolls do not restore mana or shorten normal skill cooldowns.",
        ))
    return "\n".join(lines) + "\n"
