# Holy Suit ware quantities and Ascension Core

The Holy Suit vendor tab now begins with all eight wares as single-unit
quantity presets, Bronze through Divinium. The original 25-unit presets remain
after Opal and Goddess' Stone, with Divinium added after Seraphite. Holy Box V
remains last. The complete tab contains 19 listings.

| Ware | Item ID | B-Gold per unit |
| --- | ---: | ---: |
| Bronze | 9010 | 23 |
| Silver | 9011 | 115 |
| Gold | 9012 | 575 |
| Platinum | 9013 | 1,152 |
| RuneSteel Ingot | 9014 | 3,152 |
| Arcanite Crystal | 9015 | 8,954 |
| Seraphite Core | 9016 | 15,673 |
| Divinium Essence | 9017 | 31,346 |

Captured higher-tier single and bulk listings use the same per-unit prices but
different native quantity defaults (wire record byte 27: 1 versus 25). The new
lower-tier singles clone the corresponding captured records and change only
that default. The server grants the actual requested quantity. For example,
25 Divinium Essence cost 783,650 B-Gold and grant exactly 25 units.

The existing post-Holy-Box item 9025 (`Congregation6`) is now **Ascension Core**.
Its new artwork is the 36-pixel cell 0,0 in
`./Localization/en_us/UI/Texture/ExperienceCatalyst.gwo`. Its role, bound
status, stack cap of 99, 100,000,000 EXP conversion cost and all Holy Suit
upgrade requirements stay the same. This change adds no vendor listing for
9025 and does not change acquisition or conversion fees.

## Publication and verification

The forward immutable source appends `+ascension-v1` to the released Socket
Spell source. Its exact predecessor is
`7CD94D179AA38A51A075B6AFDA3FB3176230A0B8A09AE6360D3F11551B941440`.
The tested 1,774-item successor is
`7FF15E627A18307A8DD9B596E27BF3EA268E0DE1151DFA8C8841BB25D0584BE5`.
`HolySuitContentBaselineV3` retains the previous names and original prism
artwork. The new release changes only 9025's name, texture and coordinate.
Mutable compatibility accepts only exact reviewed historical identities;
unknown metadata rolls back the transaction. Owned item rows and sealed
historical catalogs are preserved. No schema migration is required.

Tests cover all eight single listings, both native quantity presets, existing
socket-spell and stone order, approved per-unit prices, eight actual single
purchases, a 25-unit Divinium purchase, exact deployed-revision publication,
owned core stack preservation, poisoned-row rollback, historical publications
and the complete authoritative Holy Suit workflow.

Evidence is saved in `artifacts/holy-suit-vendor-20260911/`.
Release build: zero warnings/errors. Two protocol checks and seven PostgreSQL
checks passed, with no failures or skips. The disposable database container was
removed. Schema count remains 148 with head
`20260910_147_holy_suit_combat_projection`.

## Installed release

Ascension Core's master was generated with built-in ImageGen; exact prompts and
source hashes are in `assets/ascension-core/generation.json`. Native 36px visual
review passed, and all five packed outputs reproduced without changes. Both
client locales use atlas SHA256
`f275dae393503de909824c057d4d5759be6fa142b9f627e6821eb1f755203b6c`.
Names, tooltips, creation text and upgrade help now use Ascension Core(s).
The obsolete 600 B-Gold fee claim was removed to match the existing EXP-only
conversion. Three focused client tests, a forward compatibility test and all
37 existing Holy Suit installer tests passed. Previous icon releases verify.

Tempest was deployed with image
`sha256:f58907e47bab2e7d7c459b84e8ea5e2d5654b71952d9bd404475407da33e8ae0`.
It is healthy with zero restarts, publishing the tested successor above. Only
item 9025's presentation differs; owned inventory, sealed predecessor, schema
and Holy Suit policy fingerprints match the stopped deployment snapshot.
Development stack isolation passes. Backup and installation receipts are in
`artifacts/ascension-core-20260911/`; the old image is retained as
`reborn-server:before-ascension-core-20260911`.

Wonderland's Friday rejection was traced to its existing weekend schedule in
Asia/Manila. The level-160 player qualifies, and no attempt was consumed.
Schedule rejection logging and handler tests were added. Client entry notes
now accurately describe three free entries, level 120+, one to five players,
a 40-minute run, and weekend admission before 23:00 Manila time. The weekday
rule remains unchanged pending the user's optional everyday-opening choice.
Three focused Wonderland checks passed, including successful entry and
schedule denial without consuming an attempt. No interactive playtest was
performed during deployment. Fully restart the client to load the new text
and artwork.
