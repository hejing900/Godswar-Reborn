# Socket Spell artwork and vendor order

Socket Spells I-IV are the final four listings of the Bound Gold Vendor's
H.Ward tab, in ascending tier order. Heated, Cooled and Zephyr Holy Stones stay
together at the beginning. All other listings retain their relative order.

| Spell | Item ID | B-Gold each | Atlas coordinate |
| --- | ---: | ---: | --- |
| I | 4270 | 23,000 | 0,0 |
| II | 4271 | 98,000 | 36,0 |
| III | 4272 | 392,000 | 72,0 |
| IV | 4273 | 1,568,000 | 108,0 |

I and II retain their exact captured listing records and prices. III and IV
are new listings at the user-approved prices. The H.Ward tab contains 35 items;
the complete vendor catalog contains 112 items in nine native frames.

Each spell receives a distinct 36-pixel cell in
`./Localization/en_us/UI/Texture/SocketSpells.gwo`. The stock `Icon.gwo` cell
108,900 is shared with unrelated items, so it is preserved. Names, IDs,
descriptions, binding rules, stack caps and socket mechanics are unchanged.

## Immutable server publication

The new publication source appends `+sockets-v2`. Its exact deployed predecessor
is `560FC88EA04674F54B4F73165AE975FEB113E4849C426B99CF698FAEA1080111`.
The tested 1,774-item successor is
`7CD94D179AA38A51A075B6AFDA3FB3176230A0B8A09AE6360D3F11551B941440`.
`SocketSpellItemContentBaseline` retains the historical shared-icon definitions;
`SocketSpellItemContentV2` changes only the four texture paths and coordinates.

Published historical rows remain sealed. Mutable foreign-key definitions can
advance only from the exact reviewed predecessor or already-current definition.
Unknown metadata aborts the serializable publication transaction. No migration
or character-item update is required; owned spell identities and stacks survive.
The developer-grant catalog accepts both exact historical and current artwork
pairs while retaining its existing item-name/type/stack validation.

## Verification

Protocol checks cover all four final listing positions, approved prices,
preserved relative order, native frame sizes, current artwork and developer
grants. PostgreSQL checks cover the exact deployed predecessor, historical
catalog hashes, poisoned-fourth-row rollback, owned I-IV stacks, repeat
publication, and actual III/IV purchases charged only to B-Gold.

Evidence is saved under `artifacts/socket-spells-20260911/`.
The Release solution build has zero warnings/errors. Two targeted protocol
checks and six PostgreSQL checks passed with no failures or skips. A separate
exact-predecessor run records the successor revision above. Disposable test
containers were removed; the schema remains at 148 migrations/head 147.

## Installed release

The four masters were created with built-in ImageGen. Exact prompts and source
hashes are in `assets/socket-spells/generation.json`. Each icon has one through
four socket marks; visual review checked both enlarged and native 36px sizes.
All eight generated outputs reproduced without changes. Three new client
regressions and six existing reagent regressions passed.

Both client locales have atlas SHA256
`eac1002d1ae9ecc782b070e00234134bc2bc9b96da9d7b40c3fdfa71a0b85124`.
Installation changed only two item XML files and two new atlas files, with
exact backup/readback verification. Previous Holy Stone, spirit, and reagent
releases still verify unchanged.

Tempest was deployed with image
`sha256:2edc9410b59010d72ab7ea8ae1ab7535e7671642ea4d8c6d7900171bfbe7c86f`.
It is healthy with zero restarts and publishes the expected successor above.
Only four Socket Spell definitions differ; owned inventory, sealed predecessor
definitions, schema and Holy Suit policy fingerprints match the stopped
pre-deployment snapshot. The previous image is retained as
`reborn-server:before-socket-spells-20260911`. Deployment and client backup
receipts are in the evidence directory above.

Fully restart the game client to reload the icons and reconnect to the updated
vendor. Native price handling was reviewed; no interactive in-game playtest
was performed during installation.
