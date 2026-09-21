# Title list ordering

Owned titles are sent in descending cosmetic rarity: Sovereign, Mythic, Legendary, Epic, Rare, Uncommon, then Ordinary. Wonderland titles use the authored island progression below. Within one rarity, later Wonderland islands come first; titles without an island progression use ascending title ID. Enumeration order and repeated refreshes cannot shuffle the list. The selected title header, owned IDs, permanent-title representation and attributes are unchanged; sorting never equips a title.

These rarity classes are newly authored server presentation policy, not pre-existing native client metadata. Existing Medusa colors align with Mythic for Heir of Perseus (5152, crimson), Legendary for Bane of the Three Sisters and Gorgon Breaker (5153/5154, orange), and Epic for the three Enhanced Medusa titles (5009-5011, purple). Other titles, including Atlantis, retain Ordinary rarity and their stable ID order. The shared policy resolves Wonderland IDs through WonderlandTitlePolicy so the title mapping cannot drift. The user subsequently approved the palette below; it was installed in both client locales on September 12.

The installed client stores title names in DesigName.dat and descriptions in DesigInfo.dat. Native opcode10196 is a selected-title header followed by 12-byte owned-title records. Receiver0x4E343C calls0x4211D0; the record loop0x421290-0x4212DA groups by category and appends each row using0x421670. That append writes at the vector end and advances it by12. The title dialog loop0x554E90-0x5550A6 reads vector entries in increasing index order. No title-ID or color sort intervenes, so changing wire order changes the displayed order without a client patch.

The focused check is `Medusa owned-title dialog protocol`. It verifies a mixed list containing all eight Wonderland titles, all six Medusa titles, ordinary and unknown IDs, every Wonderland rarity class, later-island ties, deterministic refreshes, unchanged selection and permanent-record framing. Native excerpts and the pre-palette localized color rows are under `artifacts/title-rarity-order-20260912`. Sorting itself needs no client patch. The separate color installation and exact backup evidence are described in [Wonderland title colors](wonderland-title-colors-20260912.md).

## Approved Wonderland colors

| Island | Title | Cosmetic rarity | Color | Hex |
|---|---|---|---|---|
| 1 | Gatebreaker | Uncommon | Emerald green | #4FD17B |
| 2 | Demonbreaker | Rare | Sapphire blue | #4AA8FF |
| 3 | Flamebreaker | Rare | Bright azure | #56C5FF |
| 4 | Stonebreaker | Epic | Amethyst | #A875FF |
| 5 | Marshal's Bane | Epic | Royal violet | #CB7CFF |
| 6 | Dragonbane | Legendary | Dragonfire orange | #FF9F32 |
| 7 | Hydra's Bane | Mythic | Crimson | #F45D76 |
| 8 | Wonderland Sovereign | Sovereign | Radiant gold | #FFE49A |

This palette makes later milestones more prominent, with the final title distinct from ordinary white titles. Rarity sorting is implemented independently of color. The palette changes only display text markup, without selecting a title or changing ownership, attributes, descriptions or rewards.
