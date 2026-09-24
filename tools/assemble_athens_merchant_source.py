"""Assemble the server source file for the captured Athens merchants.

Takes the constants emitted by emit_shop_catalog_cs.py and wraps them in the
partial class plus the service->catalog dispatch, so the generated base64 is
never retyped by hand.

Usage: python tools/assemble_athens_merchant_source.py
"""
from __future__ import annotations

import pathlib
import re
import sys

FRAGMENT = pathlib.Path(
    r"D:\Godswar-Reborn-main\artifacts\npc-port\shop-fragment.cs")
TARGET = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Packets"
    r"\PacketBuilder.CapturedAthensMerchantShops.cs")

# C# identifier stem -> CapitalNpcServiceKind member name.
SERVICE = {
    "WarriorEquipmentVendor": "AthensWarriorEquipmentVendor",
    "ScholarEquipmentVendor": "AthensScholarEquipmentVendor",
    "JewelryEquipmentVendor": "AthensJewelryEquipmentVendor",
    "ArmorEquipmentVendor": "AthensArmorEquipmentVendor",
    "WarriorSupplier": "AthensWarriorSupplier",
    "SkillMerchant": "AthensSkillMerchant",
    "ArmorMerchant": "AthensArmorMerchant",
    "ScholarSupplier": "AthensScholarSupplier",
    "JewelryMerchant": "AthensJewelryMerchant",
    "AlchemyRecipeVendor": "AthensAlchemyRecipeVendor",
    "IngredientsVendor": "AthensIngredientsVendor",
    "ForgingRecipeVendor": "AthensForgingRecipeVendor",
    "MythcraftingRecipeVendor": "AthensMythcraftingRecipeVendor",
    "ScholarshipRecipeVendor": "AthensScholarshipRecipeVendor",
}

HEADER = '''using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Packets;

internal static partial class PacketBuilder
{
    // The Athens merchant quarter, captured from the reference server on
    // 2026-09-24 between 23:29 and 23:36. Each of these npcs answers an
    // ordinary click with function number zero and then streams its stock
    // straight after the client's 10068 open request, so the merchant needs a
    // catalog and no dialog at all.
    //
    // Every byte below is the reference's own opcode-10071 stream; only the npc
    // id and the live balance are patched at egress, exactly as the older
    // captured vendors do. The charge currency rides in each frame's header byte
    // 9 and resolves through TryGetShopCurrency(byte): 2 gold, 3 silver,
    // 4 bound gold.
    //
    // Athens_095 (npc 5233) is deliberately absent: its frame carries 0x01, a
    // currency code the runtime table does not define.
'''

FOOTER = '''
    private static byte[] GetCapturedAthensMerchantCatalogSource(
        CapitalNpcServiceKind service) =>
        service switch
        {
__DISPATCH__            _ => throw new ArgumentOutOfRangeException(
                nameof(service),
                service,
                "The selected capital NPC is not an Athens merchant.")
        };
}
'''


def main() -> int:
    fragment = FRAGMENT.read_text(encoding="utf-8").rstrip("\n")
    stems = re.findall(r"private const string (\w+)CatalogGzip =", fragment)
    missing = [s for s in stems if s not in SERVICE]
    if missing:
        print(f"!! no service kind mapped for {missing}")
        return 1
    if len(stems) != len(SERVICE):
        print(f"!! expected {len(SERVICE)} merchants, fragment has {len(stems)}")
        return 1

    dispatch = "".join(
        f"            CapitalNpcServiceKind.{SERVICE[stem]} =>\n"
        f"                {stem}Catalog.Value,\n"
        for stem in stems)

    text = (HEADER + "\n" + fragment + "\n"
            + FOOTER.replace("__DISPATCH__", dispatch))
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET}")
    print(f"merchants: {len(stems)}")
    print(f"size: {len(text.encode('utf-8')):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
