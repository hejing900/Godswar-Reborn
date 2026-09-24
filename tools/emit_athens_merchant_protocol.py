"""Emit the protocol-layer fragments for the captured Athens merchants.

Reads the capture exports plus the generated catalog source and prints the three
pieces that have to be hand-integrated into CapitalNpcServiceProtocol.cs:

  1. the CapitalNpcServiceKind members
  2. the (npcKey, interactionId) -> kind arms for TryResolve
  3. the TryGetShopCurrency arms

Doing it from the capture rather than by hand keeps the interaction ids exact.

Usage: python tools/emit_athens_merchant_protocol.py
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

CAPTURE = pathlib.Path(r"D:\Godswar-Reborn-main\artifacts\npc-port")
SOURCE = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Packets"
    r"\PacketBuilder.CapturedAthensMerchantShops.cs")

# npc id -> (npcKey, service member). The charge currency is derived from the
# captured frames below rather than restated here, so the protocol table cannot
# disagree with the catalog it serves.
MERCHANTS = [
    (5166, "Athens_026", "AthensWarriorEquipmentVendor"),
    (5167, "Athens_027", "AthensScholarEquipmentVendor"),
    (5168, "Athens_028", "AthensJewelryEquipmentVendor"),
    (5169, "Athens_029", "AthensArmorEquipmentVendor"),
    (5234, "Athens_096", "AthensWarriorSupplier"),
    (5237, "Athens_099", "AthensSkillMerchant"),
    (5240, "Athens_102", "AthensArmorMerchant"),
    (5245, "Athens_107", "AthensScholarSupplier"),
    (5246, "Athens_108", "AthensJewelryMerchant"),
    (5259, "Athens_121", "AthensAlchemyRecipeVendor"),
    (5260, "Athens_122", "AthensIngredientsVendor"),
    (5273, "Athens_135", "AthensForgingRecipeVendor"),
    (5274, "Athens_136", "AthensMythcraftingRecipeVendor"),
    (5275, "Athens_137", "AthensScholarshipRecipeVendor"),
]

CURRENCY_NAME = {2: "Gold", 3: "Silver", 4: "BindingGold"}


def currency_of(npc_id: int, catalogs: dict) -> str:
    """The CapitalNpcShopCurrency the captured frames charge, by frame byte 9."""
    import base64
    import gzip
    import struct
    blob = gzip.decompress(base64.b64decode(
        catalogs[str(npc_id)]["gzipBase64"]))
    codes = set()
    offset = 0
    while offset + 16 <= len(blob):
        codes.add(blob[offset + 9])
        offset += struct.unpack_from("<H", blob, offset)[0]
    if len(codes) != 1:
        raise SystemExit(f"npc {npc_id} carries mixed currency codes {codes}")
    code = codes.pop()
    if code not in CURRENCY_NAME:
        raise SystemExit(f"npc {npc_id} carries unmapped currency 0x{code:02x}")
    return CURRENCY_NAME[code]


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    import json
    catalogs = json.loads(
        (CAPTURE / "shop-catalogs.json").read_text(encoding="utf-8"))

    # Verify every claimed (npcKey, interactionId) against the reference.
    placements = {}
    for path in CAPTURE.glob("captured-npcs-map*.txt"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("|")
            if len(parts) == 6:
                placements[int(parts[0])] = parts[1]

    published = {}
    for line in psql("SELECT object_id, npc_key FROM npc_spawn_definitions "
                     "WHERE map_id = 1;"):
        object_id, key = line.split("|")
        published[int(object_id)] = key

    print("### 1. CapitalNpcServiceKind members\n")
    for _, _, member in MERCHANTS:
        print(f"    {member},")

    print("\n### 2. TryResolve arms (npcKey, interactionId)\n")
    ok = True
    for npc_id, key, member in MERCHANTS:
        template = placements.get(npc_id, "")
        if not template.startswith(key + "_"):
            ok = False
            print(f"            // !! capture says npc {npc_id} is {template!r}")
        print(f'            ("{key}", {npc_id}u) =>')
        print(f"                CapitalNpcServiceKind.{member},")

    print("\n### 3. IsShop - add these to the pattern\n")
    print("            " + "\n            or ".join(
        f"CapitalNpcServiceKind.{m}" for _, _, m in MERCHANTS))

    print("\n### 4. TryGetShopCurrency arms\n")
    for npc_id, _, member in MERCHANTS:
        print(f"            CapitalNpcServiceKind.{member} =>")
        print(f"                CapitalNpcShopCurrency."
              f"{currency_of(npc_id, catalogs)},")

    print("\n### cross-check: published object id vs captured id\n")
    for npc_id, key, _ in MERCHANTS:
        pub = published.get(npc_id)
        status = "OK" if pub == key else f"pre-capture published={pub}"
        print(f"    npc {npc_id:>5}  expected {key:<14} {status}")

    print(f"\ncapture template check: {'all matched' if ok else 'SEE WARNINGS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
