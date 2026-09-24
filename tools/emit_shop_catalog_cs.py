"""Emit the C# catalog fragment for the captured Athens merchants.

Reads artifacts/npc-port/shop-catalogs.json (produced by
gen_captured_shop_catalogs.py) and writes one gzip constant plus its lazy
inflate per merchant, in the exact shape PacketBuilder.CapturedCapitalNpcShops.cs
already uses, so the new merchants drop into the same mechanism.

Usage:
  python tools/emit_shop_catalog_cs.py --names names.txt --out fragment.cs
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

CATALOGS = pathlib.Path(
    r"D:\Godswar-Reborn-main\artifacts\npc-port\shop-catalogs.json")

# npc id -> C# identifier stem. Names come from npc_text_templates so each
# merchant reads as its role, not its object id. The charge currency is NOT
# listed here: it is read back out of the captured frames, because hand-copying
# the frame's byte 9 is exactly the kind of mistake this table cannot detect.
MERCHANTS = {
    5166: "WarriorEquipmentVendor",
    5167: "ScholarEquipmentVendor",
    5168: "JewelryEquipmentVendor",
    5169: "ArmorEquipmentVendor",
    5234: "WarriorSupplier",
    5237: "SkillMerchant",
    5240: "ArmorMerchant",
    5245: "ScholarSupplier",
    5246: "JewelryMerchant",
    5259: "AlchemyRecipeVendor",
    5260: "IngredientsVendor",
    5273: "ForgingRecipeVendor",
    5274: "MythcraftingRecipeVendor",
    5275: "ScholarshipRecipeVendor",
}

CURRENCY_NAME = {2: "Gold", 3: "Silver", 4: "BindingGold"}

# 5233 answers with frame currency 0x01, which the runtime currency table
# (2 gold / 3 silver / 4 bound gold) does not define, so it is left out until
# that code is resolved from evidence.


def frames_of(blob: bytes) -> list[tuple[int, int, int, int]]:
    """(length, category, declared records, currency byte) per frame."""
    out = []
    offset = 0
    while offset + 16 <= len(blob):
        length = struct.unpack_from("<H", blob, offset)[0]
        out.append((length, blob[offset + 8], blob[offset + 10],
                    blob[offset + 9]))
        offset += length
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/npc-port/shop-fragment.cs")
    args = parser.parse_args()

    catalogs = json.loads(CATALOGS.read_text(encoding="utf-8"))

    constants = []
    lazies = []
    emitted = []
    for npc_id, stem in MERCHANTS.items():
        entry = catalogs.get(str(npc_id))
        if entry is None:
            print(f"!! npc {npc_id} missing from the catalog JSON")
            return 1
        frames = frames_of(__import__("gzip").decompress(
            __import__("base64").b64decode(entry["gzipBase64"])))
        # The runtime table keys currency off the frame byte, so a catalog whose
        # frames disagree, or whose code has no name, cannot be served.
        codes = {frame[3] for frame in frames}
        if len(codes) != 1:
            print(f"!! npc {npc_id} frames carry mixed currency codes {codes}")
            return 1
        currency = codes.pop()
        if currency not in CURRENCY_NAME:
            print(f"!! npc {npc_id} carries unmapped currency 0x{currency:02x}")
            return 1
        emitted.append((npc_id, stem, currency, len(frames), entry))
        constants.append(
            f"    // npc {npc_id}: {len(frames)} frames, {entry['itemCount']} "
            f"records, currency 0x{currency:02x} "
            f"({CURRENCY_NAME[currency]})\n"
            f"    private const string {stem}CatalogGzip =\n"
            f"        \"{entry['gzipBase64']}\";\n")
        lazies.append(
            f"    private static readonly Lazy<byte[]> {stem}Catalog = new(\n"
            f"        () => InflateCatalog(\n"
            f"            {stem}CatalogGzip,\n"
            f"            expectedLength: {entry['totalBytes']},"
            f"\n            expectedPacketCount: {entry['frameCount']},"
            f"\n            expectedCapturedNpcId: {npc_id}));\n")

    text = ("\n".join(constants) + "\n" + "\n".join(lazies))
    pathlib.Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    print(f"merchants emitted: {len(emitted)}")
    for npc_id, stem, currency, frame_count, entry in emitted:
        print(f"    {npc_id:>5}  {stem:<28} frames={frame_count:<2} "
              f"items={entry['itemCount']:<3} bytes={entry['totalBytes']:<6} "
              f"cur=0x{currency:02x} {CURRENCY_NAME[currency]}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
