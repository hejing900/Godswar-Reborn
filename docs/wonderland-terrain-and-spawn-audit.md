# Wonderland terrain and spawn foundation

> Historical record: the design, placements, roster and party HP scaling below are superseded where they differ from the [September 13 full external comparison](wonderland-external-comparison-20260913.md). Preserve the recorded evidence and release results as history.


The server authors an eight-island encounter on content map 207, scene `Fane`, native scene 227. This document records the original Reborn terrain foundation, before the September 11 external capture supplied the first-island roster, first three treasure positions and first two transporters. The [external matching report](wonderland-external-match-20260911.md) and [transporter audit](wonderland-transporters-20260911.md) describe those current overrides. The client supplies the map geometry and exact monster templates; unobserved islands retain the authored encounter.

## Reproducible local evidence

Installed source: `C:\Godswar Origin\Map\Fane.hmp`, 9,175,332 bytes, SHA-256 `375B51547593B82924C6A6C809316E070B44536A853A8E75080CE5DAD49CF292`.

The header is `(128,128,4.0,4.0)`. The native binary block table starts at offset 262,432 and contains 2,048 by 2,048 bytes; 0 is walkable and 1 is blocked. World coordinates map to columns `floor((X+256)*4)` and rows `floor((256-Z)*4)`, giving quarter-unit cells. The client consumer proof and native grid-to-world converter are documented in [the existing terrain audit](medusa-island-client-terrain-audit.md).

The local, ignored `artifacts/wonderland-foundation-20260910` directory retains the original `components.json`, `labels.bin`, `walkable.png`, audit script and templates. Flood-fill found exactly eight large disconnected walkable components. The September 11 corrected route and reproducible audit are under `artifacts/wonderland-route-20260911`. That historical audit checks the source map hash, both user anchors, authored geometry coordinates and all eight distinct components. All original authored spawn and chest points had a three-unit square of block-table clearance. Monsters had at least four units of separation and remained outside the ten-unit arrival/exit safe zones. Original chest centers were over sixteen units from exit anchors. Captured NPC overrides are audited separately; current forward travel always requires a dialogue action. Nine island-six fire candidates have five-unit clearance, at least eleven units of mutual separation, and over seventeen units from the entrance and exit.

The user identified island one at `(159,-163)` and island two at `(-15,-185)`, with seven outer islands clockwise and island eight central. Those anchors resolve to southeast and south in the measured block table. The corrected route follows SE, S, SW, W, NW, NE, E, center. The supplied coordinates identify the islands; entry/exit landings retain measured walkable points within those components.

| Island | Region | Component cells | Protected entry X/Z | Exit safe-zone X/Z | Original chest X/Z |
|---|---|---:|---|---|---|
| 1 | Southeast | 62,024 | 169,-216 | 170,-205 | 188,-162 |
| 2 | South | 33,672 | -21,-201 | 21,-155 | 9,-167 |
| 3 | Southwest | 50,076 | -68,-125 | -126,-99 | -126,-117 |
| 4 | West | 68,421 | -148,-17 | -186,75 | -170,67 |
| 5 | Northwest | 90,013 | -188,192 | -90,196 | -102,184 |
| 6 | Northeast | 67,620 | 120,209 | 184,133 | 166,131 |
| 7 | East | 63,805 | 160,3 | 220,33 | 204,27 |
| 8 | Central corridor | 104,124 | 0,95 | 54,-117 | 56,-101 |

The first entrance is the user's exact September 11 starting point `(169,-216)`, on the walkable southern tail of component 60. This narrow landing does not have the three-unit square footprint used for original monster and chest placements. The nearby exit safe-zone anchor `(170,-205)` has two-unit square clearance and lies approximately 11.05 units away. It no longer determines the first transporter location: captured Fane_001 is at `(153,-125)`, and entrance Fane_017 is at `(165,-219)`. All forward transporters require their native Teleport button. The first-island monsters and first three chests now follow the separately documented external capture; the protected arrival and combat safe-zone anchors remain unchanged.

The central island is a connected sequence of chambers rather than a square. Its four boss groups occupy the separated chambers along that route. Each contains one boss and two Atlas followers. All twelve are required, with the requested detection radius 112 and leash 128. Nearby chambers can pull together at this deliberately large detection radius.

The final chest is twelve units from Scorpion King's spawn, but the required targets can die in any order. Minotaur's chamber is about 173 units away in a straight line, with a longer walking route through the central corridor. The five-minute completion window therefore leaves time to collect treasure, including for split-party members who use the still-unlocked forward portals. UI countdown, claims, travel, and runtime retention share one policy deadline. Combat remains terminal during this window; chest interaction rejects at its exact end.

The native planar converter writes Y=0. Fane includes floating road/platform meshes; its rendered ground triangles beneath several islands have strongly negative Y values. Those ground values are recorded separately in `placement.json` and are not used to bury actors beneath the gameplay plane. Appearance and transport Y remains 0. Block-table clearance proves planar traversability, not acceptance against every decorative static mesh. A native client playtest remains necessary to verify rendering over the floating platforms.

The existing monster AI follows straight chase segments. The block-table audit proves connected routes, not that every straight segment between arbitrary actors avoids scenery. No new navigation system is introduced here. Entrance and exit areas have ten-unit safe radii; monster target lists exclude these areas, other islands, nonparticipants, and other exact world instances.

## Roster and lifetime

`WonderlandMonsterPlan` pins 27 existing map-207 template keys, producing 70 distinct objects across the run. All used templates and their model/texture files exist in the installed English client. Rank validation against published gameplay content fails closed if a boss becomes a normal template or a required template disappears. The source membership rows are in `State/MonsterTemplateSeed.Generated.cs` beginning at line 1107.

IDs 46100–46811 are allocated by island and slot and never reused. The native appearance has monster flags `0x0212`, map 207 in the high word, level 130, and the authored party-scaled HP. Thirteen boss identities include one allied marshal. Twelve hostile bosses plus eight Atlas followers are progression targets; optional support mobs do not impose a kill-all gate. Boss clears now preserve every living support and allied actor, including its HP, identity, attacks, pending casts and damage eligibility. Combat remains confined to targets on that actor's own island. Later kills of earlier support cannot decrement the next island's boss counter or award a duplicate milestone. Earlier corpses retain their original runtime and generation until normal corpse expiration.

Boss HP in the approved design already includes the requested triple increase. Five-player hostile boss HP totals 154,500,000; the allied marshal adds 12,000,000. The eight Atlas followers total 3,200,000 before party scaling and are not tripled. Party factors are 25/45/65/85/100 percent for one through five admitted members. No player-level multiplier applies. Fixed baseline level 130, Hit 3500, and Dodge 2000 are initial authored defaults; Multi-headed uses the explicitly approved Dodge 18000. Magic actors approach within five units, ordinary melee within three, and towers use their approved 25/30 reach.

Configuration prepares content but publishes no monsters until admission is sealed and the first explicit stage publication occurs. Sealing fixes the successfully admitted subset, recalculates HP for its actual size, and removes failed entrants from the damage whitelist. This preserves the original leader's faction and the original run clock, including when the leader's transfer failed. Repeated identical seals are harmless; a changed seal or a roster change after publication is rejected. Every required death verifies the exact map, object ID, generation, and actual committed dead state. Each island clear emits its immutable island/time record once, before the next stage is published. The forty-minute deadline, cancellation, and completion prevent future damage, attacks, and stage publication while allowing corpse cleanup. Terminal movement stops are published to the native client. Allied faction actors never acquire players and reject player direct and periodic damage.

`WonderlandPolicyChecks`, `WonderlandMapChecks`, and `WonderlandMonsterBehaviorChecks` cover party HP, the thirteen bosses/eight followers, faction selection, exact stage bindings, duplicate/concurrent deaths, deadlines, all eight live stages, surviving support, native appearance fields, stationary tower reach/cadence, safe zones, and both Legacy/ECS engines. Combat regressions exercise an earlier chest guard's pending Fire Blast, tower attacks, bird buffs and silence after boss clears across both player/monster engines. Handler route checks cover corrected entry, all seven native portal hops, and reviving on the player's physical island when the party is split. The build owner runs those checks with the integrated gameplay and persistence suites.
