# Bound Gold Vendor revision, 2026-09-11

The Sparta and Athens Bound Gold Vendor now uses the Binding Gold wallet
(native shop type 4). Its former captured type 2 selected ordinary Gold despite
the NPC's name and description. The separate B-GOLD Shop, mixed-currency Props
Merchant, and other shop catalogs remain unchanged.

The server retains the original captured catalog bytes as evidence and applies
an explicit stock revision. Retained item attributes, ordering, and unit prices
are preserved; caption metadata is updated and purchase indices resolve from the same revised
catalog that is sent to the client. Each category starts with a reset frame,
followed by continuation frames containing at most 16 records.

| Tab | Change |
| --- | --- |
| 1, Gears | Add the stock level-10 Leo ring (3200), normal quality/grade, no appended stats, 5,000 B-Gold. |
| 2 | Add Phoenix's Feather (11005), 5,000 B-Gold each. |
| 3 | Remove portal scrolls 4302, 4306, 4324–4327; war materials 4262–4265; Magic Healing Potion 4011. Add Zephyr Holy Stone 9032 for 460 B-Gold, and all four Zephyr Spirits 9090–9093 for 230 each. |
| 4, Holy Suit | Remove Fire/Water Spirits 9060–9067 and 9080–9087, Super Healing Potion 4010, and Magic Mana Potion 4041. |

The ring price follows the cheaper existing gear listing price. Zephyr prices
follow the existing Heated/Cooled Holy Stone and elemental spirit price families.
Other prices are unchanged. The tabs contain 33, 31, 33, and 13 listings, within
the native 45-slot category limit.

All added identities already exist in the item publication: no schema migration,
template replacement, or owned inventory conversion is required. Existing Holy
Suit ware/material icons are resolved by their unchanged item IDs and client
item definitions.

Protocol coverage checks all additions, prices, currency, removed IDs, category
boundaries, and capture replay isolation. The disposable PostgreSQL purchase
check buys two feathers, verifies an exact 10,000 B-Gold debit with Gold and
Silver preserved, retries the same operation to prove no duplicate debit/grant,
and verifies insufficient B-Gold cannot fall back to an ample Gold balance.

## Native tab captions

`tools/PatchClientBoundGoldVendor.py` appends numeric keys `44 = Gears` and
`45 = Holy Suit` to both locales' `Text/EquipDescription.dat`. Existing shared
labels (including Hot, Gem, and H.Ward) remain untouched. The installer preserves
all other bytes and the encoding/BOM, rejects occupied or duplicate keys, backs
up both files, and supports preview/apply/verify with idempotent readback.

On the current Origin.exe (SHA256
`3d9715424f94f05c852ae691d446d52a9f51732d0a94112438f7cacc45581447`),
CNPC's catalog import at `0x48C1ED` sets EBX to record + 25; `0x48C2E1`
reads byte [EBX + 39] (wire record byte 64), and `0x48C2E4` stores it
at native item + 4. NPCTrade at `0x5B010D-0x5B0110` reads that byte from
the first category item, formats its numeric key, and calls EquipDescription
lookup `0x42B300` at `0x5B0151`. No executable patch is needed.

All records in this vendor now use caption keys 44, 26, 30, 45 by tab. Native
caption IDs are independent of the four category/purchase indices, which remain
0 through 3. The shop protocol regression checks the exact wire caption byte.
