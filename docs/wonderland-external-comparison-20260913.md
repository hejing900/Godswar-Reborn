# Wonderland: September 13 full external comparison

The completed external run supplies fixed monster HP, spawn locations and native
attack packet identities for all eight islands. Wonderland now uses the same HP
for one through five admitted players. Party size remains an admission limit;
it does not multiply health or any combat rating.

The selected run is September 13, 13:30:24–13:59:42 NZST, framed GAME sequences
60454–95730 in `external-20260907-194130-562.log`. The immutable local snapshot is
30,466,573 bytes, SHA256
`81ea111739f43e90319b64b777fe6a0f1d4cfeeb9e2de34997692aaad666df44`.
The parser recovered 96,375 framed
packets from the complete log without leftover bytes. Login packets and account
credentials are not included in the comparison outputs.

## Boss HP and attack bindings

HP is read directly from native 10020 spawn fields, rather than estimated from
the number of attacks needed to kill a boss. Each observed ordinary action is
two 10046 impacts followed by one 32-byte 10026 damage packet. The second impact
uses skill2000. Effect packets do not apply a second copy of damage.

| Island | Boss | Fixed HP | Primary native skill |
|---|---|---:|---:|
| 1 | Alpha Demon | 8,000,000 | 2805 |
| 2 | Capritaur Derskey | 4,500,000 | 2022 |
| 2 | Depraved Monkeyface | 4,500,000 | 2803 |
| 3 | Flame Rooster | 100,000,000 | 2000; retained custom Fire Blast580 |
| 4 | Outrageous Rock Spirit | 9,000,000 | 2178 |
| 5 | Athenian Marshal Addis | 8,500,000 | 2004 |
| 5 | Spartan Marshal Knocker | 8,500,000 | 2004 |
| 6 | Depraved Platinum Dragon | 10,000,000 | 2022 |
| 7 | Iberian Multi-Head | 10,000,000 | 2021 |
| 8 | Minotaur | 5,000,000 | 2803 |
| 8 | Titan's Xmas Deer | 5,000,000 | 2178 |
| 8 | Iberian Dragon King | 8,500,000 | 2021 |
| 8 | Scorpion King | 8,000,000 | 2192 |

The captured roster has 115 actors: **17 / 20 / 26 / 10 / 14 / 4 / 11 / 13** by
island. Initial admission and sealed admission publication now use that prepared
roster count instead of a 96-actor cap. Final island has four bosses, eight Atlas
followers and one optional guard. The existing twelve required targets remain.

Both faction rosters and island5 treasure anchors are preserved. Captured
arrivals are `(166,-214)`, `(20,-194)`, `(-63,-115)`, `(-144,-21)`, `(-186,195)`,
`(116,211)`, `(158,29)` and `(56,-112)`. All 115 actor coordinates reproduce the
captured float32 bytes. Stationary towers and the three native Firing Hoop
sources retain their captured cells, including blocked terrain. The additional
custom final return helper uses a clear walkable location at `(0,80)`.

## Skills, controls and presentation

Bosses accept the native silence, stun, freeze and shackle skill families through
the same ownership, range, live-target and spawn-generation checks as combat.
Stun and shackle stop movement and attacks. Silence blocks skill use while
allowing ordinary attacks; captured later bosses switch to2000/2000 with their
observed lower physical damage. Freeze roots movement and interrupts the current
windup; its native definition permits subsequent in-range attacks and casts.
Interruption revisions cancel attacks/casts queued before the control even if
that effect expires before dispatch resumes.

Shackle's native75% incoming damage reduction combines multiplicatively with
Derskey/Monkeyface's retained80% encounter reductions, producing95% reduction in
the protected channel rather than overwriting either modifier. Current control
icons hydrate new viewers and delayed publications resolve the latest controls.

Invented periodic boss casts are removed in favor of the captured attack pairs.
The user's island3 boss exception keeps its Fire Blast580, damage balance and
four-second cooldown. Scorpion's2192 attack applies native133: physical defense
reduced15% for20seconds. The invented island2 50% stun proc is removed; neither
matching native skill definitions nor this full run showed that proc. Island4
nonboss silence uses native361 for four seconds. The requested custom Petbird
5× blessing, Putrid Bird hit blessing, Rock25% reflection, faction ally help,
Atlas death blast and random island6 ground Fire Blast remain. Rock reflection
was subsequently reduced to 10% on 2026-09-15.

The external and Origin skill definitions match in meaningful fields for all14
used native IDs, and every referenced effect asset is byte-identical. All13 boss
definitions and26 model/texture assets also match. No new client asset copy is
required. Alpha and Minotaur's native Action1 name `nomal_attack_09` is absent
from both identical models; this shared external data is preserved. A matching
packet and asset audit does not constitute an in-game rendering test.

## Combat inference limits

The follow-up [damage recovery audit](wonderland-damage-recovery-20260913.md)
checks 1,676 boss hits across three runs. It rejects interpreting the reference
calibration as the original PA/MA: simple defense/absorption add-back does not
fit both target configurations, and external status values/mitigation semantics
are not established by Origin's definitions. The ratings below remain an
approximation; the follow-up records the observed outputs and missing evidence.

The capture exposes exact health and damage results, but not the external
server's complete attack, defense, dodge or damage formula. Fixed effective
attack ratings are calibrated against the recorded player's defenses and flat
absorption. One-damage hits only bound a rating; they do not identify its exact
value. Earlier opposite-faction observations use their own recorded reference
stats. These ratings never depend on the current opponent's stats or party size.

Typical observed ordinary cadence is about1.92seconds; Atlas about3.84seconds.
Rooster retains its prior cadence. Lost Tower did not attack in this capture,
so its prior generic attack and1.5second cadence remain. No ordinary attack was
observed from Firing Hoops, which are stationary nonattacking hazard sources.

Native skill definitions provide area radii of4,5,6 or10units. This solo run
cannot establish simultaneous party hits or exact area shape. The reconstructed
party behavior uses a source-centered circle with one independently resolved
hit per nearby admitted participant. The primary is excluded, duplicate events
cannot create another batch, and source controls, identity, target lifetime and
radius are checked again before secondary damage. Client effect power is not
applied as an additional multiplier.

## Treasure and completion

Native treasure requests10067/function58 and10069/sub-1 match the existing
clickable chest handler. Corpse pickup uses10050. Captured success packets also
include a modal10070 result, deliberately omitted to retain the user's requested
right-side acquisition log. Treasure boxes still give four random GradeIV
Sapphire/Emerald gems; corpses still give their custom boss sacks. This comparison
does not replace the requested reward economy with external random drops.

Optional surviving monsters remain attackable until the five-minute completed
treasure window ends. Boss deaths do not wipe mobs. Settled titles, the working
Leave button and announcements after the last participant departs remain.
Hostile island5 actors retain neutral presentation for mixed-faction parties;
the original leader still determines encounter allegiance.

Detailed local evidence lives in
`artifacts/wonderland-full-external-20260913/`: `COMBAT-EVIDENCE.md`,
`placement-treasure-comparison.md`, literal HP/attack prefixes, source coordinates,
status timelines, skill/effect and boss-model hashes, and release check results.

## Validation and local release

Release compilation completed with zero warnings/errors. All53 selected protocol
checks passed with zero failures/skips, covering both monster/player engines,
captured health/damage/presentation, live zero-ID area events, silence expiry,
stale controls, new-viewer status races, passive hazards, treasure/loot, revival,
completion Leave, surviving mobs and movement authority. No manual client
rendering check was performed.

Tempest was deployed at `2026-09-13T02:59:19.3939206Z` using image
`sha256:ee577d4809d700d0499d02acc0a8c0c536fcb23bbe8d0ec66c56e7ac04691126`.
Post-start readiness is healthy with zero restarts. Existing schema150,
item revision, item policies and owned inventory fingerprints are unchanged.
The stopped database backup hash was verified both inside PostgreSQL's container
and after copying locally:
`690c216b90d1497d74afe2719e4721a46beda22090c77ea78b1fab10b34fd50f`.
The prior image is retained as `reborn-server:before-wonderland-full-external-20260913`.
No daily attempts were reset and no client files were changed by this release.
