# Wonderland island treasure claims

This document describes the earlier sack-from-box release. The subsequent
[corpse-loot and gem release](wonderland-corpse-loot-and-gems-20260911.md)
moves boss sacks to their corpses and makes island boxes grant four gems.

Each island has a native treasure-chest NPC at its audited
`WonderlandIslandGeometry.TreasureChest` position. Objects 5710 through 5717
use the existing `Fane_008_Male15` through `Fane_016_Male15` chest templates
and `monster_ark_003` mesh/texture. Existing NPC visibility, canonical catalog
lookup and 48-byte click handling are retained. No new client model or Lua
route is required.

Clicking a chest claims its island's original boss sack reward after that
island's required enemies are defeated. Optional surviving monsters do not
block the claim. The player must be alive, within eight units of the chest,
in the current instance, an original admitted participant, and eligible at
the island clear. Each eligible player may claim once per island per run.
Completing a later run creates a new entitlement.

After completion, a shared five-minute treasure window keeps chest claims and
island portals available before automatic exit. This allows the final chest
to be reached when a distant final-island boss is defeated last. The same
deadline controls the completion UI and runtime exit.

| Island | Native reward IDs | Quantity |
| --- | --- | --- |
| 1 | 4450, Alpha Demon's Sack | 1 |
| 2 | 4451, Capritaur Ajax's Sack | 1 |
| 3 | 4452, Flamingo King's Sack | 1 |
| 4 | 4453, Angry Cyclops' Treasure | 1 |
| 5, Sparta-led party | 4455, General Aeson's Treasure (Athens) | 1 |
| 5, Athens-led party | 4454, General Nyx's Treasure (Sparta) | 1 |
| 6 | 4456, Platinum Dragon's Collection | 1 |
| 7 | 4457, Dracoladon's Chest | 1 |
| 8 | 4458, 4459, 4460, 4461: all four final boss containers | 1 each |

The user selected original sacks, so original native names are retained even
where the authored encounter uses different boss names. All sacks are bound
and stack to 99. Their original opening skill IDs are retained. The subsequent
user-defined opening table and atomic item-use behavior are documented in
`wonderland-sack-openings-20260911.md`.

`PostgresWonderlandChestClaimStore` checks the persisted title milestone and
its frozen eligible members, locks the current player ownership fence, and
plans the complete grant before changing inventory. A full bag leaves the
claim available for retry. Inventory, its revision, the claim receipt,
command audit/inbox, and inventory ledger commit in one transaction. Duplicate
clicks and store restarts return the original receipt. Currency, EXP, selected
titles and existing item attributes are preserved.

Forward migration `20260911_148_wonderland_chest_claims` adds the unique
instance/island/character receipt table with a foreign key to the earned
Wonderland milestone. The catalog now contains 149 migrations. The original
12 item definitions are added through a separate immutable item publication;
existing sealed catalogs and owned items are preserved.

PostgreSQL regressions cover absent clear evidence, forged instance/island/hash
or realm, stale ownership, absent-at-clear members, concurrent and restarted
replay, independent party claims, stack-cap rollover across runs, all-or-nothing
four-sack capacity, inventory-full retry, an injected receipt-write failure,
and both faction rewards. Registry/handler tests separately cover the native
chests and current run, proximity, life and completion-window gates.

Validation on 2026-09-11: the Release build completed with no warnings or
errors. The focused PostgreSQL chest suite passed with no failures or skips;
the 13 Wonderland protocol/runtime checks also passed with no failures or
skips. Evidence is in `artifacts/wonderland-help-chests-20260911/`.
An in-game native chest click remains the final client interaction check.
