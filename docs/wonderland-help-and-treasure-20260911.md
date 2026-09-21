# Wonderland route, treasure boxes, and Holy Spirit help

The September 11 follow-up uses the player's island anchors `(159,-163)` and `(-15,-185)` to identify islands 1 and 2. The seven outer islands now progress southeast, south, southwest, west, northwest, northeast, east, followed by the central eighth island. Entrances, exits, all 70 monster positions, random fire positions, and eight chest anchors were checked against the installed `Fane.hmp` block table. The supplied coordinates identify the islands; admission uses an audited walkable entrance on each island.

Clearing the required bosses unlocks the next island without removing living support monsters. Already published islands retain their surviving actors, HP, combat, and pending skills. Player effects clear on that player's actual travel. Monsters target players on their own island, and reviving a player uses that player's physical island when the party is split. Run termination, timeout, and completion retain their terminal combat handling.

## Treasure rewards

Each island has a clickable treasure box. Its reward unlocks after the island's required kills and title milestone settle. An eligible original participant can claim once per island per run. A full bag leaves the claim available for retry. Repeated requests cannot grant more items; claim, inventory changes, revision, and ledger evidence commit together under the current character ownership lock.

Wonderland's completion countdown is five minutes so the final chest remains reachable when the bosses die out of order. Already unlocked forward portals and physical-island revival remain available during this same window; combat stays finished. The instance exits players when that window expires. Other dungeons retain their existing countdowns.

| Island | Original item reward per player |
|---|---|
| 1 | 4450 — Alpha Demon's Sack |
| 2 | 4451 — Capritaur Ajax's Sack |
| 3 | 4452 — Flamingo King's Sack |
| 4 | 4453 — Angry Cyclops' Treasure |
| 5 | 4455 — General Aeson's Treasure (Athens) for a Spartan party; 4454 — General Nyx's Treasure (Sparta) for an Athenian party |
| 6 | 4456 — Platinum Dragon's Collection |
| 7 | 4457 — Dracoladon's Chest |
| 8 | One each: 4458 Minotaur King's Envelope, 4459 Titan's Xmas Deer Chest, 4460 Dracolord's Chest, 4461 Scorpion King's Chest |

These are the original client names, including names that differ from the authored encounter bosses. Each reward is bound and stacks to 99. The client already has all twelve item rows, textures, and activation links (5400–5411). The live server lacked these item definitions, so the forward immutable publication adds only IDs 4450–4461, from 1,774 to 1,786 definitions. Existing definitions and Holy Suit policies are preserved. Schema migration `20260911_148_wonderland_chest_claims` records durable claims.

The original sack contents and an opening handler have not been recovered or implemented. This change awards and stores the original sacks; it does not invent a replacement reward table.

## Help List

`tools/PatchClientHolySpiritHelp.py` adds a reachable Zephyr Spirits navigation entry and page, and corrects the Fire/Water pages and overview in both locales. It changes eight text/UI files, preserves their encoding, backs up every changed file, and verifies readback and repeat-run idempotence. It leaves icons and item definitions untouched.

The pages show Grade 1 and Grade 10 ranges with grade scaling and Goddess' Stone explanation. Cooled maxima use the audited live settings revision 1: Darkness and Mist reach 7% at Grade 10, Intent reaches 6%. Fire Destruction ignores physical defense; Blood increases critical damage. Ice and Frost rebound only to players.

Zephyr Attunement and Tempering explain the mount-gear scope and strongest-two-piece selection. Preservation and Continuity accurately state that their rolls can be stored but have no current combat producer. Fire Flow/Tranquility and Water Renewal/Vitality are identified as legacy items without supported implementation effects. No new combat effects are introduced by this help update.

Client help install backup: `C:\Godswar Origin\backups\holy-suit-tiers\20260911-013239-91f5168d224742ae9a2f4b90e04fe217\manifest.json`. Restart the client to reload the Help List.

Validation and deployment receipts are collected under `artifacts/wonderland-help-chests-20260911/`. Native visual rendering and a complete player-driven run still require an in-client playthrough.

## Verified deployment

Release build passed with zero warnings/errors. Four help tests, 13 Wonderland runtime/protocol checks, and nine PostgreSQL suites passed. The PostgreSQL checks include historical content upgrades, original-sack publication, durable titles, and chest claims. The initial ledger-label bug was corrected and its full chest suite rerun successfully; the earlier failing reports are retained beside the final reports. A separate rehearsal on a copy of the live database applied migration 149 and preserved the complete owned-inventory fingerprint.

Tempest started the new image at `2026-09-11T01:51:24.4604833Z`: `sha256:18fe88e2f5efe3ef05c8c80f9a0913a0714d94159cf94c8cd3b1cce9e3b06e70`. Health is healthy with zero restarts. Live isolation passed; endpoints remain `127.1.1.111:5998` and `127.1.1.111:7000`, and Dwargon remains stopped.

The published item revision is `38161E6B26E30F671B90ABAE6A0F3BB1879777D5FD6F78712A9BA2F76596E404`, with 1,786 definitions. Live before/after comparison confirms that only IDs 4450–4461 were added, every previous item definition and Holy Suit policy remains unchanged, and no owned inventory rows changed during deployment. The stopped database backup and prior-image tag `reborn-server:before-wonderland-chests-20260911` are retained for recovery.
