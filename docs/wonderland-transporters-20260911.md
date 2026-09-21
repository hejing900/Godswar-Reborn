# Wonderland transporter matching, 11 September 2026

The first two forward transporters and the entrance Blackmarket NPC now use
the external capture's identities, positions, facing and native dialogue.
Forward travel requires the dialogue's **Teleport** button. Opening an NPC
or walking near a portal cannot move the player.

## Captured actors and dialogue

Source: `external-20260907-194130-562.log`, opened on 11 September, 4,230,255
bytes, SHA-256
`cfdc5025ac07b42a198bb06716ed291ee97c36f7b6266cd979508e69329dde73`.
Reassembly produced 13,412 GAME frames with no incomplete bytes. Sanitized
NPC evidence is in `artifacts/wonderland-external-20260911/transport-golden.json`.
The capture's filename date does not describe these September 11 events.

| NPC key | Object ID | Captured X/Z | Facing bits | First appearance | Menu functions |
|---|---:|---|---|---|---|
| Fane_001 | 5205 | 153,-125 | `4044999A` | 16:20:54.5560289 | 57 |
| Fane_002 | 5206 | -5,-168.5 | `4014999A` | 16:21:30.5074955 | 57 |
| Fane_017 | 5221 | 165,-219 | `3FD9999A` | 16:14:45.2946630 | 59,62,63 |

Their captured 10020 spawn frames are 104 bytes, map 207, appearance
`0x0211`. Reborn retains its compatible NPC spawn writer while reproducing
the meaningful actor fields. The installed Origin client already contains
the canonical `Fane_001_Male15`, `Fane_002_Male15` and
`Fane_017_Male15` templates and dialogue scripts. The external server's
`gwprivate_` template prefix is omitted locally. This correction needs no
client asset patch.

The previous first transporter used synthetic object 5700 at `(170,-205)`.
That location placed it near entry rather than in the captured boss area,
so normal spatial visibility did not show it where the player expected it.
The entrance actor was missing from the injected NPC roster. The roster
now contains seven forward transporters plus the Blackmarket actor.
Islands 3-7 retain their authored positions and facing zero; their local
5207-5211 IDs extend the observed contiguous range. Those later placements
and identities are a local continuation, not independently captured facts.

Opening a forward NPC sends a 48-byte 10067 acknowledgement, flags 512,
function 57 and the exact `Fane_001` or `Fane_002` script. The client's
10068 page request does not travel. Its explicit 92-byte 10069 action has
function 57, repeated function 57 and sub-ID -1. Remaining argument bytes
are uninitialized native client memory and are ignored. Tests use an
arbitrary nonzero tail to ensure it does not become an accidental contract.

The server binds the open dialogue to the NPC, character, exact instance,
ownership fence and life revision for two minutes. An admitted, living
participant must still be within eight units when selecting a choice. The
action consumes that context before awaiting work; replay, stale life,
changed ownership, an unrelated NPC page and an expired page cannot travel
or charge again. Locked forward travel uses the native numbered-island
prerequisite result, 100 through 106.

## Entrance choices

The captured Fane_017 acknowledgement uses flags 512 and packed functions
63,062,059. Both the external and installed `NPCDescription.dat` define:

| Function | Native choice | Silver | Local service |
|---:|---|---:|---|
| 59 | Speedy Teleport | 5,000 | Travel, retain current HP/MP |
| 62 | Teletransport with full HP | 6,000 | Travel and restore HP |
| 63 | Teletransport with full HP and full MP | 8,000 | Travel and restore HP/MP |

The capture includes opening this menu, but no paid selection or resulting
destination. The local destination policy is the **furthest unlocked
island**, inferred for the entrance shortcut. It uses the protected island
arrival and requires at least one completed island. Native result 142
explains the first-boss prerequisite, and 141 explains insufficient silver.

Payment uses the existing durable wallet/receipt tables with an ownership
fence and an exact operation ID. A rejected relocation compensates the
matching debit. Ambiguous debit completion is resolved by replaying the
same operation before any relocation. Once the destination checkpoint is
durable, a later transport failure requires reconnecting at that destination
and does not refund an already completed service. Life and vitals revisions
prevent rejected healing from overwriting a newer death or combat update.
This service introduces no schema migration.

## Arrival and combat boundaries

The capture proves forward arrivals `(20,-194)` at 16:21:28.7157371 and
`(-63,-115)` at 16:23:50.4934616. Both are walkable in the pinned Fane block
table. They are recorded without replacing the current protected landings:
later-island monsters still use authored positions, including an island-two
monster at `(17,-191)`, only about 4.2 units from the first captured arrival.

The user's initial `(169,-216)` landing and the protected island-two/three
landings `(-21,-201)` and `(-68,-125)` remain. The old terrain `Exit` points
remain combat safe-zone anchors; the first two NPC positions are independent
of them. No movement segment automatically triggers island travel. The
terrain foundation's historical portal coordinates must not be read as
the current captured NPC roster.

## Focused verification

The handler checks cover actual spatial NPC publication at entry and the
first boss area, independent captured identity/coordinate/facing values,
initialized acknowledgement bytes, click-versus-action ordering, native
locked results and exact single-use authority. Paid-choice checks cover all
three fees and healing modes, furthest-unlocked selection, insufficient
silver, locked entry without a store call, ambiguous commit recovery,
replay resistance and compensation after registration or life changes.

Filters:

- `Wonderland captured transporters are visible and require their native dialogue actions`
- `Wonderland Blackmarket native paid choices preserve wallet, life, and relocation authority`

Build, PostgreSQL integration and deployment results are recorded by the
coordinated release process. This document does not claim a client playtest.
