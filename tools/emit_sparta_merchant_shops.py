"""Emit the captured Sparta merchant stock as a server packet-builder partial.

Source: artifacts/npc-port/today-shop-catalogs.json, which
tools/gen_captured_shop_catalogs.py harvested from the reference capture session
c202c633 (2026-09-28, local 01:52-02:09). Every constant below is the reference's
own opcode-10071 stream; the builder patches only the authoritative npc id, the
advertised balance and the currency byte (the user's requirement that these
shelves charge silver).

Stocks are grouped by identical bytes, so the two merchants that share a shelf
share one constant - the same reuse the Athens skill merchant already relies on.

Usage: python tools/emit_sparta_merchant_shops.py
"""
from __future__ import annotations

import base64
import gzip
import json
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CATALOGS = (r"D:\Godswar-Reborn-main\artifacts\npc-port"
            r"\today-shop-catalogs.json")
OUTPUT = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Packets"
          r"\PacketBuilder.CapturedSpartaMerchantShops.cs")

# kind name, role, provenance, the captured npc the blob came from
STOCKS = [
    ("SpartaWarriorEquipmentMerchant",
     "[Warrior] equipment merchant",
     "Sparta_028 and Sparta_096, who stream one identical shelf",
     5026),
    ("SpartaScholarEquipmentMerchant",
     "[Scholar] equipment merchant",
     "Sparta_029 and Sparta_107, who stream one identical shelf",
     5027),
    ("SpartaSkillMerchant",
     "skill merchant",
     "Sparta_034 and Sparta_099, who stream one identical shelf",
     5032),
    ("SpartaArmorMerchant",
     "[Armor] merchant",
     "Sparta_037",
     5034),
    ("SpartaJewelryMerchant",
     "[Jewelry] merchant",
     "Sparta_038",
     5035),
    ("SpartaPropsMerchant",
     "props merchant",
     "Sparta_036",
     5033),
    ("SpartaPetMerchant",
     "pet merchant",
     "Sparta_089",
     5086),
]


def main() -> int:
    data = json.load(open(CATALOGS, encoding="utf-8"))
    lines: list[str] = [
        "using Godswar.Server.Domain.World.Content;",
        "",
        "namespace Godswar.Server.Packets;",
        "",
        "internal static partial class PacketBuilder",
        "{",
        "    // Exact opcode-10071 streams the reference server sent on 2026-09-28",
        "    // (capture session c202c633, local 01:52-02:09). Only the",
        "    // authoritative npc id, the live balance and the currency byte are",
        "    // patched at egress; every item record, category, order and price",
        "    // stays byte-identical to the capture.",
        "    //",
        "    // The currency byte is the one field this port decides rather than",
        "    // copies: seven of these shelves were captured carrying 0x04. The",
        "    // user's requirement is that every item on these shelves is bought",
        "    // with silver, and the capture agrees on the price - every equipment",
        "    // listing costs the item's own silver price in the client's",
        "    // ItemBaseAttribute.xml (1000 at 58, 1001 at 129, 1002 at 188, ...).",
        "    // Byte 9 is rewritten to the client's silver code (3) on load, and",
        "    // every other captured byte is preserved.",
        "",
        "    /// <summary>The client's own silver currency byte.</summary>",
        "    private const byte SpartaMerchantSilverCurrencyByte = 3;",
        "",
    ]

    params: list[str] = []
    for kind, role, provenance, source in STOCKS:
        entry = data[str(source)]
        stream = gzip.decompress(base64.b64decode(entry["gzipBase64"]))
        blob = base64.b64encode(
            gzip.compress(stream, 9, mtime=0)).decode("ascii")
        counts = [frame["category"] for frame in entry["frames"]]
        currencies = sorted({frame["currency"] for frame in entry["frames"]})
        lines += [
            f"    /// <summary>The captured {role} shelf.</summary>",
            "    /// <remarks>",
            f"    /// <para>{provenance}.</para>",
            "    /// <para>",
            f"    /// {entry['frameCount']} frames, {entry['itemCount']} listings,",
            f"    /// categories {counts}, captured currency byte(s)",
            f"    /// {[hex(value) for value in currencies]}.",
            "    /// </para>",
            "    /// </remarks>",
            f"    private const string {kind}CatalogGzip =",
            f'        "{blob}";',
            "",
            f"    private static readonly Lazy<byte[]> {kind}Catalog = new(",
            "        () => ApplySpartaMerchantCurrency(InflateCatalog(",
            f"            {kind}CatalogGzip,",
            f"            expectedLength: {len(stream):_},",
            f"            expectedPacketCount: {entry['frameCount']},",
            f"            expectedCapturedNpcId: {source:_})));",
            "",
        ]
        params.append(
            f"            CapitalNpcServiceKind.{kind} => "
            f"{kind}Catalog.Value,")

    lines += [
        "    /// <summary>",
        "    /// Rewrites each captured frame's currency byte to silver.",
        "    /// </summary>",
        "    /// <remarks>",
        "    /// Everything else - length, opcode, npc id, category, listing count,",
        "    /// fresh flag, balance and every 88-byte record - stays as captured.",
        "    /// </remarks>",
        "    private static byte[] ApplySpartaMerchantCurrency(byte[] catalog)",
        "    {",
        "        var offset = 0;",
        "        while (offset < catalog.Length)",
        "        {",
        "            var length = System.Buffers.Binary",
        "                .BinaryPrimitives.ReadUInt16LittleEndian(",
        "                    catalog.AsSpan(offset, sizeof(ushort)));",
        "            if (length < ShopCatalogHeaderBytes ||",
        "                offset + length > catalog.Length)",
        "            {",
        "                throw new InvalidDataException(",
        '                    "Captured Sparta merchant catalogue has an " +',
        '                    "invalid frame.");',
        "            }",
        "",
        "            catalog[offset + 9] = SpartaMerchantSilverCurrencyByte;",
        "            offset += length;",
        "        }",
        "",
        "        return catalog;",
        "    }",
        "",
        "    private static byte[] GetCapturedSpartaMerchantCatalogSource(",
        "        CapitalNpcServiceKind service) =>",
        "        service switch",
        "        {",
    ]
    lines += params
    lines += [
        "            _ => throw new ArgumentOutOfRangeException(",
        "                nameof(service),",
        "                service,",
        '                "The selected Sparta merchant is not a shop.")',
        "        };",
        "}",
        "",
    ]

    text = "\n".join(lines)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {OUTPUT} ({len(text)} bytes, {len(STOCKS)} stocks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
