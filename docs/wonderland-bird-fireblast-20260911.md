# Wonderland first-island attack effects, 11 September 2026

All first-island roles now publish their external captured visual pairs
before one damage result. For the Demonic Raider, this is native skill 2179
(Fire Blast), normal attack 2000, then damage. Both skill presentations use
opcode **10046**. The earlier capture analysis checked 10040 and 10045 but
omitted 10046, incorrectly concluding that the bird had no separate fire
effect. The same omission hid every role's presentation pair; matching
model files alone did not support removing those packets.

## Captured sequence

The 4,230,255-byte external capture has SHA-256
`cfdc5025ac07b42a198bb06716ed291ee97c36f7b6266cd979508e69329dde73`.
All eleven recorded attacks from Raider objects 21625/21639 contain this
ordered sequence at the same capture timestamp:

| Packet | Length | Meaning |
|---|---:|---|
| 10046 | 24 | Bird-sourced native skill 2179 presentation |
| 10046 | 24 | Bird-sourced native normal attack 2000 presentation |
| 10026 | 32 | One authoritative damage result, trailing bytes `[1,1,0,0]` |

The first is at 16:15:00.4647145, the last at 16:17:41.3176560. The damage
values are 27,586 or 26,325; continuous attacks are approximately 1.92
seconds apart. There are 22 bird-sourced 10046 packets, exactly two per
attack. Some unrelated packets interleave, but the bird's ordering and
timestamp relationship are consistent. No bird-sourced 10040 cast is
needed for this effect. Opcode 10045 is skill damage, while 10046 is the
native skill presentation handled by `PacketBuilder.SkillCastImpact`.

The complete first-island roster audit finds 564 presentations for 282
attacks, with an exact two-packet prefix for every observed attack:

| Role | Observed attacking actors | Attacks | Ordered presentation skills |
|---|---|---:|---|
| Alpha Demon | 22521 | 90 | 2805,2000 |
| Arrow Tower | 20869,20897,20911 | 136 | 2015,2000 |
| Demonic Stooge | All eight captured actors | 31 | 2000,2000 |
| Demonic Raider | 21625,21639 | 11 | 2179,2000 |
| Demonic Assaulter | 21485,21513 | 14 | 2000,2000 |

Tower 20883 is present in the roster but has no observed attack. The local
tower role uses the pair observed from the other three towers. Repeated
2000 packets for stooges/assaulters are retained exactly. The scoped report
`first-island-presentation-audit.json` records every actor's counts and
prefix association; it does not infer additional damage from a visual.

Sanitized packet findings, initialized presentation headers and reassembly
assertions are under `artifacts/wonderland-bird-fireblast-20260911/`.
The parser independently requires the preceding bird presentations to be
2179 then 2000 at each of the eleven attack timestamps. Account/player
packets and unused coordinate fields are omitted from this artifact.

## Installed client binding

The external and Origin flamingo model, texture and normalized Monster.ini
section match. The expanded model contains `nomal_stand`, `nomal_run`,
`nomal_attack_01` and `nomal_die`; the fire comes from the skill effect,
not an embedded model effect. The relevant installed binding is:

| Native skill | Action | Effect | Script |
|---:|---|---|---|
| 2179 | `nomal_attack_01` | `effect_fire_002_b.gwm` | `MagicAttack` |
| 2000 | `nomal_attack_01` | `effect_hit_005_all.gwm` | `PlayerAttack` |
| 2015 | `nomal_attack_01` | `effect_fire_001_all.gwm` | `MagicAttack` |
| 2805 | `nomal_attack_09` | `effect_conjuration_005_all.gwm` | `PlayerAttack` |

Skill 2179 has TypeFlag 2 and TrackType 4, with no cast time. This is the
captured monster Fire Blast presentation. Its external/Origin semantic
bindings match; only the displayed Name encoding differs. The effect file
is 195,079 bytes in both clients, SHA-256
`271ad42dc402f0b935f9bb28e808fe108b5595f57d5edb543e15aa09265cc874`.
Player skill 580 is a different binding and is not used by this correction.
No client asset patch or schema migration is required.
Installed 2015 and 2805 were also checked before use: their action, effect,
script and TypeFlag match the external client, and both referenced effect
files have identical hashes. `first-island-bindings.json` retains these
bindings, file hashes and literal captured presentation headers per role.

## Why consecutive presentations coexist

The strongest evidence is the repeated external sequence itself. Native
inspection also distinguishes immediate monster effects from a player's
single pending action:

- The opcode table routes 10046 to `0x4E8C48`, whose receiver dispatches the
  source actor's skill method using the packet's skill ID.
- The monster branch at `0x496C93` invokes `0x4973F0` and returns before the
  nonmonster pending-action replacement at `0x496CF3`.
- The effect path calls `0x664700`; `0x664530` obtains an independent effect
  instance from the skill's pool. `0x6644E1` links that instance into the
  global active effect list. Consecutive skills 2179 and 2000 do not share
  one pending-effect slot that the second packet simply overwrites.
- `0x665210` applies the skill's pose immediately. Both captured skills use
  the bird's supported `nomal_attack_01`, and the following 10026 attack
  state does not replace the monster's selected animation.

The artifact retains the opcode-table check, bounded disassembly and
relevant executable code-window hashes. The external client also loads
packed extensions, so static inspection is not a substitute for a native
client playtest; no speculative extension behavior is needed for this fix.

## Server behavior and verification

Both legacy and ECS publication paths emit the captured presentation pair
before the existing single 32-byte damage result, using the source and
per-viewer target identities. ECS admits the sequence through its existing
authoritative packet batch. The legacy path uses its existing guarded
world-instance publication. Normal combat and visibility decisions still
control the recipients.

The presentation packets do not execute the client skill's damage formula,
range, cooldown or casting rules. The Raider's calibrated magic attack
remains 34,211 and its interval remains 1.92 seconds. A miss still presents
the attempted attack and retains one native miss result. No extra spell is
scheduled and no area damage or second HP mutation is added. The same rule
applies to the other first-island roles: their attack values and cadence
remain unchanged. Later-island abilities retain their existing policies.

The focused check is
`Wonderland captured first-island attack effects preserve single damage and native timing`.
It covers all four legacy/ECS monster/player combinations, hit and miss,
an admitted target and observer, literal captured headers per role, exact
packet order and identities, one HP delta and unchanged attack policy for
Alpha, towers, stooges, Raiders and assaulters. The existing
Wonderland combat check verifies that an earlier-island bird retains its
effect after the boss dies. Build/test outcomes are recorded by the
coordinated release process; visible appearance still needs client playtest.
