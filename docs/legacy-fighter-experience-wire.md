# Legacy fighter EXP wire experiment

## Decision

The original protocol remains four bytes wide. Fighter EXP is serialized as a
little-endian unsigned 32-bit value in the range `0..4,294,967,295`. The server
rejects negative or larger values; it does not silently wrap or clamp durable
state.

This widens the usable wire range without changing packet lengths or the stock
client binary. It is experimental until the stock client is exercised above
`2,147,483,647` because its internal consumers are not consistently typed.

## Client evidence

`C:\Godswar Origin\GodsWar.map` contains these decorated C++ signatures:

- `CLevelExp::Update(unsigned int, unsigned int)` (`...QAEXII@Z`)
- `CPlayer::GetNextGradeExp()` returning `unsigned int` (`...QAEIXZ`)
- `CPlayer::SetNetGradeExp(unsigned int)` (`...QAEXI@Z`)
- `CGameObject::GetExp()` returning signed `int` (`...QBEHXZ`)
- `CGameObject::GetMaxExp()` returning signed `int` (`...QBEHXZ`)
- `CGameObject::SetExp(int)` and `SetMaxExp(int)` (`...QAEXH@Z`)

The progress-bar API therefore accepts the full UInt32 range, but some general
object accessors expose the same four bytes as signed. Values above
`2,147,483,647` may still display incorrectly or trigger a signed comparison in
an untested UI/NPC path. No stock-client binary patch is included.

## Outgoing fields

| Packet builder | Field |
| --- | --- |
| `EnterMain` | current fighter EXP at offset 84; client EXP-bar maximum at offset 88 |
| `PlayerDetail` | current fighter EXP at offset 92 |
| `PlayerStatusUpdate` | current fighter EXP at offset 96 |
| `ExperienceGain` | gained fighter EXP at offset 4; resulting total at offset 8 |
| `MonsterDeathReward` | current fighter EXP at offset 48 |
| `PlayerLevelUp` | current fighter EXP at offset 16 |

For an ordinary fighter below the level cap, `EnterMain` offset 88 remains the
next-level threshold. For either a durably sealed fighter at any supported
level or a level-200 fighter, it is the unsigned storage ceiling
`4,294,967,295`. The original level-89 example matches working capture
`capture-proxy-20260514-173331.log` (`F5D0BF67 FFFFFFFF` at offsets 84 and 88).
The client therefore renders stored sealed EXP against the real accumulation
cap instead of clipping the bar against the chosen level's normal threshold.
An unsealed level 199 still uses its ordinary table threshold. Talent,
equipment, pet, Holy Box, and Zodiac experience are distinct protocol fields
and are not changed by this experiment.

Boundary golden vectors are covered by
`LegacyFighterExperienceWireChecks`: `2,147,483,647`, `2,147,483,648`,
`4,000,000,000`, and `4,294,967,295`.

## Authenticated live seal refresh

The stock NPC response does not carry EXP, and a same-level `PlayerLevelUp`
packet is unsafe because the original client also runs its level-up UI and
effects. The secure game channel therefore uses only successful Fighter Level
Seal `LegacyCommandResult` version 2 frames for the live refresh. The first 32
bytes retain the authenticated operation outcome; network-order unsigned
current and maximum fighter EXP are appended at offsets 32 and 36. The secure
shim updates only the existing EXP component after the native NPC result.

Applied seal projects `4,294,967,295` as the maximum. Applied unseal projects
the current level-table threshold (or the UInt32 ceiling at level 200) without
truncating stored current EXP. A replay projects the current durable seal state
and revision, not its historical receipt. Rejections and no-ops have no EXP
extension, remain version 1, and cannot trigger the narrow refresh.

## Raw compatibility refresh

When client activation mode is disabled, the connection remains a raw legacy
session and cannot carry `LegacyCommandResult` frames. A supported network shim
therefore opts in per Level Sealer mutation without changing the captured
92-byte request length or its eighteen `-1` arguments. It writes a version-one
capability token to the otherwise ignored duplicate-dialog dword at request
offset 12. The token has high byte `A1` and a nonzero random low 24 bits. An
older Reborn server ignores that dword and still performs the stock request.

Only an exact raw Level Sealer mutation carrying that token receives an
extended NPC result. The ordinary result fields stay unchanged through offset
12. `RXP1` and the echoed token occupy offsets 16 and 20. A successful seal or
unseal additionally carries authoritative unsigned current and maximum Fighter
EXP at offsets 24 and 28, for a total of 32 bytes. A rejection or no-op is 24
bytes and carries no EXP. Requests from stock clients continue to receive the
captured 16-byte response.

Before Origin sees an opted-in response, the shim validates the NPC, dialogue,
outcome, marker, and pending token, queues any EXP projection, then restores the
reported packet length to 16. Origin therefore consumes its stock dialogue
result. The main-thread updater changes only Fighter EXP and its maximum; it
does not send a synthetic level-up or rewrite level, HP, MP, or attributes.
This token provides bounded response correlation, not cryptographic
authentication; secure activation continues to use the authenticated result
path above.
