# Holy Stone reagents and Platinum Evasion Signet

The H.Ward tab of the Bound Gold Vendor now begins with Heated, Cooled and
Zephyr Holy Stones in that order. Their original item records and prices are
preserved: only the shop order changes.

The separate second Gold Evasion Signet (item 9054) becomes **Platinum Evasion
Signet**, with protection for the next Holy Stone transition. Existing owned
9054 stacks retain their IDs and quantities.

| Signet | ID | Protected transition | Effective success chance |
| --- | ---: | --- | ---: |
| Copper | 9051 | 4 to 5 | 35% |
| Silver | 9052 | 5 to 6 | 35% |
| Gold | 9053 | 6 to 7 | 35% |
| Platinum | 9054 | 7 to 8 | 20% |

These rules apply to all three Holy Stone elements. A matching signet adds ten
percentage points to the existing base chance and prevents a downgrade on
failure. An attempt consumes one Eclipse Stone and one signet whether it
succeeds or fails. Platinum uses Level 3 Eclipse Stone. No signet protects the
8-to-9 or 9-to-10 transition; legacy items 9055/9056 remain unavailable as upgrade
catalysts. Goddess Stone still adds ten percentage points without protection.

The authoritative policy and persisted receipt validator both recognize
Platinum. Stored rejected receipts from the older release still replay their
original rejection; duplicate commands never recalculate the decision or roll.
Previously committed Copper/Silver/Gold receipts remain valid.

## Content publication

The immutable content source gains `+holy-stones-v3`. The exact deployed
predecessor remains sealed at
`2948180014012F2DD38CDC89FD0172071F49BC765BA55E0AD13410571484E791`.
For that 1,774-item predecessor the forward revision is
`560FC88EA04674F54B4F73165AE975FEB113E4849C426B99CF698FAEA1080111`.
The historical `HolyStoneMaterialItemContentBaseline` is retained. The new
`HolyStoneMaterialItemContentV3` changes only these eight presentation records:

| ID | Item | `HolyStoneReagents.gwo` coordinate |
| ---: | --- | --- |
| 9040 | Level 1 Eclipse Stone | 0,0 |
| 9041 | Level 2 Eclipse Stone | 36,0 |
| 9042 | Level 3 Eclipse Stone | 72,0 |
| 9050 | Goddess' Stone | 108,0 |
| 9051 | Copper Evasion Signet | 144,0 |
| 9052 | Silver Evasion Signet | 180,0 |
| 9053 | Gold Evasion Signet | 216,0 |
| 9054 | Platinum Evasion Signet | 252,0 |

The native texture path is
`./Localization/en_us/UI/Texture/HolyStoneReagents.gwo`; every cell is 36 pixels.
Stack caps and all other item attributes are unchanged.

No schema migration is needed. Within the publisher's existing serializable
transaction, mutable item-template compatibility rows may advance only from
their exact reviewed predecessor to the new presentation. An unknown local
field causes the entire publication to roll back. The update never touches
`character_items` or modifies an already sealed content definition.

## Verification

Targeted protocol checks cover shop ordering and prices, all protected
transitions, the level-eight protection boundary, unchanged base rates and
receipt evidence. PostgreSQL checks cover Platinum success and protected
failure for all three elements, single consumption and duplicate replay,
exact deployed-revision upgrade, poison-row atomic rollback, immutable
historical catalogs and complete owned-item row preservation.

Release solution build: zero warnings/errors. Four targeted protocol checks
and four PostgreSQL checks passed, with no failures or skips. Evidence is saved
under `artifacts/holy-stone-reagents-20260911/`; the disposable PostgreSQL
container was removed after verification. Schema count stays 148, with head
`20260910_147_holy_suit_combat_projection`.

## Installed release

The eight icons were generated through built-in ImageGen; exact prompts and
master hashes are in `assets/holy-stone-reagents/generation.json`. Visual review
used the native 36px icons and an enlarged contact sheet. Packing reproduced
all twelve outputs without changes. Six client regression checks passed.
Both locale copies use atlas SHA256
`79d2ab61119ec5908c5a1f0c55b5a2f9ce888ef386c514b0c8f35504826f7e01`.
Previously approved Holy Stone and spirit artwork still verifies unchanged.

Tempest was deployed with image
`sha256:40d117606cbdc609371655d4078311e444c1e17f5a27ff103a30dcf003f645fe`.
It became healthy with zero restarts. The expected 1,774-item revision is live;
only the eight reviewed definitions differ from its predecessor. Owned item
rows, sealed predecessor definitions, schema, and Holy Suit policy hashes
match the stopped pre-deployment snapshot. Development stack isolation passes.

The stopped database backup, client backup receipts, and deployment verification
are under `artifacts/holy-stone-reagents-20260911/`. The previous server image
is tagged `reborn-server:before-holy-stone-reagents-20260911`.

Native submission paths were reviewed, but this release has not had an
interactive in-game playtest. Fully restart the game client to load the icons,
names, and updated Holy Stone help.
