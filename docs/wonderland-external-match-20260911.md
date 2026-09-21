# Wonderland external matching, 11 September 2026

> Historical record: the design, placements, roster and party HP scaling below are superseded where they differ from the [September 13 full external comparison](wonderland-external-comparison-20260913.md). Preserve the recorded evidence and release results as history.


The external capture establishes a native 60-second entry window, the first
island's 17 visible monsters, separate boss corpse loot and fixed treasure
NPCs. This change applies those findings while retaining the configured boss
sacks and four random Grade IV Sapphire/Emerald gems from each island box.

## Entry

Instance Caller admission for Wonderland, Atlantis and Medusa now publishes
10222 queue state followed by 10216 to open the client's Enter window. The
native window counts down from 60 seconds. Its Enter/Cancel callbacks send
16-byte 10217 with response 1/0. Enter admits immediately; the server timer
admits when the countdown expires. The timer runs outside the receive loop.

No daily admission is claimed while the window is pending. Completion
revalidates the frozen party, NPC distance, life/session, schedule, limits
and explicit Opal consent through the existing durable admission paths.
Repeated requests cannot replace a pending stage or extend its deadline.
Positive-ID Medusa member invitations retain their existing protocol.

The capture directly proves the solo Wonderland sequence. Atlantis/Medusa
use the same native UI through their existing local admission policies.
Evidence: `artifacts/wonderland-external-20260911/entry-countdown-evidence.md`.

## First island

| Actor | Count | HP each | Level |
|---|---:|---:|---:|
| Alpha Demon | 1 | 8,000,000 | 200 |
| Arrow Tower | 4 | 2,000,000 | 200 |
| Demonic Stooge | 8 | 100,000 | 120 |
| Demonic Raider (chicken) | 2 | 100,000 | 120 |
| Demonic Assaulter | 2 | 200,000 | 120 |

Templates, counts, HP, levels and first-visible positions match the capture.
First-island HP is fixed across party sizes because the capture establishes
no party scaling rule. Islands 2–8 retain their existing authored balance.
Towers remain stationary. Alpha and the chickens attack every 1.92 seconds.

The external server does not transmit its raw Attack stat. Against the
captured character (physical defense 4,566, magic defense 2,630 and flat
absorption 3,995), early observed normal hits were Alpha 6,586, tower 1,586
and chicken 27,586. Reborn Attack values 15,147 physical, 10,147 physical
and 34,211 magic respectively reproduce those hits using our formula.
These are calibrated values, not recovered external stats. Later hits
vary despite matching visible defenses, so hidden effects remain unknown.

The chicken's eleven captured attacks each contain native 10046 skill 2179,
10046 skill 2000, then one 32-byte 10026 damage result. The earlier analysis
omitted opcode 10046 and incorrectly assumed the matching model alone
supplied its fire effect. The [bird presentation correction](wonderland-bird-fireblast-20260911.md)
restores that exact captured pair, using Origin's existing monster Fire
Blast binding while preserving one authoritative damage event and the
existing attack interval. The common correction also restores captured
Alpha 2805/2000, tower 2015/2000 and stooge/assaulter 2000/2000 presentation
pairs. No extra area spell is executed. Unobserved custom Alpha
cleave/enrage casts are removed from island 1.

## Treasure and corpse loot

Alpha Demon's Treasure is the fixed NPC at (173.600006, -153), already
present before the boss dies. Island 2/3 boxes use their captured positions
(23.6, -151) and (-113.599998, -129). The boss kill enables claiming; it
does not spawn another box or kill surviving mobs.

All seven forward transporters now require the native function 57 Teleport
button, so walking up to a box cannot interrupt its claim dialogue. The
first two transporters and the entrance Blackmarket actor follow the
[captured NPC identities, positions and dialogues](wonderland-transporters-20260911.md).

Opening a box now displays native function 58 with its reward button.
Only an explicit valid claim can grant the four gems. The server checks
current NPC, range, life, character, world and earned island eligibility;
the durable store continues to enforce one reward per character/island/run.
Installed Origin dialogue labels are updated to show Sapphire IV/Emerald IV
counts, with exact originals retained in the release artifact backup.

Native inspection proved that monster 10027 clears loot slots. Wonderland
kill progression now uses native 10356 EXP/talent attributes, and corpse
presentation no longer prefixes loot with 10027. This prevents delayed
progression from clearing newly available boss sacks. Player death/revival
packets and other maps retain their established paths.

## Verification

Release validation and deployment results are recorded in
`artifacts/wonderland-external-match-20260911/`:

- Release solution build: zero warnings/errors.
- Focused protocol/gameplay checks: 28 passed, zero failed/skipped.
- Isolated PostgreSQL title/chest/corpse checks: four passed, zero
  failed/skipped; disposable container removed afterward.
- Origin client text patch: four files applied and read back; originals
  retained under `client-before`. Restart the client to load the Lua text.
- Only Tempest was recreated, at 2026-09-11 05:05:51 UTC. Healthy, zero
  restarts, original ports retained. Dwargon remains stopped.
- Deployed image:
  `sha256:38bf136cceadd6504e53faa83b78a3b4b2e48f1835082dd898df7a3709ddf069`.
- Previous running image retained as
  `reborn-server:before-wonderland-external-20260911`; stopped database
  backup retained locally with its SHA-256 record.
- Owned inventory fingerprints are identical across deployment. Existing
  item definitions and policies are unchanged: 1,787 items, revision
  `A45EA650680C8EA4D5D2FCAA831E97EEEF652BAB55351D860BFB95330FA97EB1`.
- Schema remains at 150 migrations, head
  `20260911_149_wonderland_boss_loot_claims`; no migration was added.

Start a fresh Wonderland run for the updated roster. This release has not
been visually playtested in the client. No commit or push was performed.
