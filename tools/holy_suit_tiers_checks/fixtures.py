"""Portable synthetic client files shared by Holy Suit patch checks."""
from pathlib import Path

from holy_suit_tiers.policy import TIERS
from holy_suit_tiers.badges import main_atlas_path


def save(path: Path, text: str, *, wide: bool = False, bom: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = b"\xff\xfe" if wide else b"\xef\xbb\xbf" if bom else b""
    path.write_bytes(prefix + text.encode("utf-16-le" if wide else "utf-8"))


def fixture(root: Path) -> None:
    for locale in ("en_us", "zh_cn"):
        base = root / "Localization" / locale
        nl = "\r\n" if locale == "en_us" else "\n"
        name_rows = ["Untouched\tSea \u6d77\u795e \U0001f30a", "Lifing12062\tMithril Ingot"]
        description_rows = ["Untouched\tPreserve Unicode \u6d77\u795e \U0001f30a",
                            "Lifing12062\tUnrelated profession Mithril Ingot.", "Congregation6\tLegacy Prism"]
        item_rows = ['<Other ID="42" Type="unrelated"/>']
        badge_rows = ['<Suitpt MtPath="old.gwo" Type="0" Conditions="1" IcoPos="864,165"/>']
        for tier in TIERS[:3]:
            name_rows.append(f"Shenqi{9009 + tier.number}\t{tier.old_name} Ingot")
            description_rows.append(f"Shenqi{9009 + tier.number}\tOld {tier.old_name} ware description.")
            item_rows.append(f'<Shenqi{9009 + tier.number} ID="{9009 + tier.number}" Type="consume item" '
                             'Texture="old.gwo" Icon="972,0" Random="0" Distribution="0,0" Money="0" Overlap="99"/>')
            for index, condition in enumerate((1, 5, 8, 10), 1):
                key = tier.badge_key + str(index)
                name_rows.append(f"{key}\tOld {tier.old_name} Suit")
                description_rows.append(f"{key}\tA {tier.old_name} Holy Suit.")
                badge_rows.append(f'<{key} MtPath="{main_atlas_path("en_us")}" Type="{tier.number}" '
                                  f'Conditions="{condition}" IcoPos="714,165"/>')
            for level in range(1, 11):
                description_rows.append(f"Suit{tier.number * 100 + level}\tLevel {level} {tier.old_name}")
        # Retain a legacy CRCRLF in an unowned row, and no final newline for
        # names. Encoding differs exactly like the currently installed locales.
        save(base / "Text/EquipName.dat", nl.join(name_rows) + "\r\r\nUnownedTail\tKeep", wide=locale == "en_us")
        save(base / "Text/EquipDescription.dat", nl.join(description_rows) + nl, wide=locale == "en_us")
        save(base / "Settings/Sys/ItemBaseAttribute.xml", '<Items>' + nl + nl.join(item_rows) + nl + '</Items>' + nl)
        for folder in ("Settings/Sys", "UI/XML"):
            save(base / folder / "EquipSuitInfoIni.xml",
                 "<EquipSuitInfoIni>" + nl + nl.join(badge_rows) + nl + "</EquipSuitInfoIni>" + nl)
        save(base / "UI/XML/ItemBagsExUI.xml", '<UIConfig><ItemBagsExUI>'
             f'<SuButton ID="110038" BtnTopTexture="{main_atlas_path("en_us")}" '
             'BtnTopPos="864,165" BtnTopRect="0,0,30,30"/>'
             '</ItemBagsExUI></UIConfig>' + nl)
        effects = ['<Eqpt LvId="0" Effect="0" Exp="9688" Fun="0"/>']
        for tier in range(1, 8):
            for level in range(1, 11):
                tag = "Exsslv10" if (tier, level) == (7, 10) else f"E{tier}lv{level}"
                percent = (tier - 1) * 10 + level
                value = format(percent / 100, ".2f").rstrip("0")
                effects.append(f'<{tag} LvId="{tier * 100 + level}" Effect="{value}" Exp="999999999" Fun="{percent}"/>')
        save(base / "Settings/Sys/EquipEffect.xml", "<EquipEff>" + nl + nl.join(effects) + nl + "</EquipEff>" + nl)
        save(base / "UI/Base/font.lua", "UNRELATED_COLOR={r=1,g=2,b=3,a=255}\r\n" + nl.join(
            key + "={r=1,g=2,b=3,a=255}" for key in ("MITHRIL_COLOR", "ORICHALCUM_COLOR", "ADAMANTIUM_COLOR")))
        labels = ['HS_X0_32 = "Fire Spirits"', 'OTHER_TEXT = "Keep the old context"']
        if locale == "en_us":
            labels.extend(f'HS_X0_{29 + index} = "{tier.old_name} Suit"' for index, tier in enumerate(TIERS[:3]))
        save(base / "UI/Base/text.lua", nl.join(labels) + nl, bom=locale != "en_us")
        save(base / "UI/Base/LuaText.lua", nl.join(('NF_L0_ZBJY8 = "Old ware instructions"',
             'NF_LO_L01 = "Orichalcum socket four"', 'NF_LO_L05 = "Orichalcum socket failure"',
             'NF_OTHER = "Leave unrelated daily/reward wording"')) + nl)
        help_entries = ['local HelpSystem_Cofig = {};', 'HelpSystem_Cofig[0] = { static_text=[[Keep unrelated]] }']
        for index, tier in enumerate(TIERS[:3], 16):
            help_entries.append(f'HelpSystem_Cofig[{index}] = {{{nl}  static_text=[[{nl}'
                                f'{tier.old_name} Suit: maximum bonus of {tier.number * 10}%.{nl}'
                                f'Level 9-10 | {36 + (index - 16) * 30} Experience Prism{nl}  ]]{nl}}}')
        help_entries.append('function Get_HelpSystem_Cofig(level) return HelpSystem_Cofig[level]; end')
        save(base / "UI/XML/HelpSystemConfig.lua", nl.join(help_entries) + nl)
        save(base / "UI/XML/HelpSystemProc.lua", 'function HelpSystem_OnClickAdamantiumBtn() end' + nl)
        layout = ('<UIConfig><HelpSystem><Container Rectangle="16,94,182,510">' + nl +
                  '<StoleBtn Rectangle="20,520,120,540" SText="HS_X0_31"/>' + nl +
                  '<StoneBtn Rectangle="10,545,80,565" SText="HS_X0_19"/>' + nl +
                  '<StoneBtn Rectangle="20,570,80,590" SText="HS_X0_32"/>' + nl +
                  '<PetsystemBtn Rectangle="10,620,80,640" SText="HS_X0_20"/>' + nl +
                  '</Container><Other Rectangle="0,600,10,620"/></HelpSystem></UIConfig>' + nl)
        save(base / "UI/XML/HelpSystem.xml", layout)
    baseline = Path(__file__).resolve().parents[2] / "assets/holy-suit-badges/source/main.gwo"
    target = root / "Localization/en_us/UI/Texture/main.gwo"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(baseline.read_bytes())
