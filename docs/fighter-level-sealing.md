# Fighter level sealing

The durable fighter-level seal is stored in PostgreSQL as
`public.character_base.fighter_level_sealed`. A player may opt to seal any
supported fighter level from 1 through 200. The local dialog keeps the stock
client's function-116 wire IDs, but its wording and economy follow the external
Level Sealmaster: sealing is free and unsealing costs 10,000 Bound Gold.

When sealed, monster rewards do not advance fighter level. Fighter EXP still
accumulates and saturates at `4,294,967,295`, the complete unsigned 32-bit
range carried by the original four-byte client field. PostgreSQL and the C#
runtime use signed 64-bit storage so the value cannot wrap internally. The
server reports only EXP actually credited at that ceiling. It never uses `-1`,
a sentinel, wraparound, or an "infinite" wire value. Talent EXP and Talent Point
progression are unchanged. Holy Box EXP deductions remain permitted.

At world entry, an ordinary fighter below level 200 receives the next-level EXP
threshold as the progress-bar maximum. A sealed fighter at any level and any
level-200 fighter receive `4,294,967,295` as that maximum. The durable seal is
loaded into the runtime character and ECS projection, so the locked-level choice
is authoritative rather than inferred from a large current EXP value. After a
successful live seal or unseal, a bound TLS game channel sends an authenticated
40-byte command result carrying current fighter EXP and its new maximum. When
secure activation is disabled, the paired network shim instead opts into a
correlated raw NPC-result extension and removes that extension before Origin
sees the stock reply. The shim applies either projection to the existing EXP
state immediately, so an online character does not need to relog. No level-up
packet or synthetic world-entry packet is used.

The unsigned client interpretation above `2,147,483,647` is experimental; see
`legacy-fighter-experience-wire.md` for the stock-client evidence and known
risk.

## Local test2 fixture

The offline helper can seal or unseal a test character:

```powershell
.\tools\SetLocalDevelopmentFighterLevelSeal.ps1 `
    -State Seal -AccountId 13 -CharacterName test2 -Confirm:$false

.\tools\SetLocalDevelopmentFighterLevelSeal.ps1 `
    -State Unseal -AccountId 13 -CharacterName test2 -Confirm:$false
```

The helper refuses to run unless the configured game-server container is
stopped and explicitly configured with
`GODSWAR_RUNTIME_PROFILE=LocalDevelopment`. It also refuses an active
checkpoint owner and a corrupt fighter level outside the supported range of
1 through 200.
Each invocation writes a permanent `command_audit` record, including an
idempotent `already_sealed` or `already_unsealed` outcome.

Because the helper runs only while there is no world/checkpoint owner, it
does not advance `progression_reward_revision`: no live runtime, cache
projection, or outbox consumer can observe an intermediate fixture state.
Normal monster rewards continue advancing that revision after server start.

Unsealing only removes the durable seal. It does not immediately spend stored
EXP or recalculate the fighter level. The next positive fighter-EXP reward uses
the normal progression rules and may apply multiple earned level-ups. The live
NPC's 10,000 Bound Gold debit and seal transition are one row-locked PostgreSQL
transaction, so a duplicate click cannot charge twice.

The offline fixture does not charge currency. It exists for stopped-server
testing only; the live NPC is the authoritative player-facing economy path.

## Live command safety

The live Level Sealer uses the secure client's stable operation ID. PostgreSQL
locks the current player-ownership fence and character row, records every
terminal result in the durable command inbox, and advances the dedicated
`fighter_level_seal_revision` only when the seal state changes. Retrying the
same click replays its original result; it cannot repeat the Bound Gold debit.
Reusing an operation ID for the opposite action is rejected as a request-hash
conflict, and a session that has lost world ownership cannot mutate the row.
The monster-settlement `progression_reward_revision` is deliberately preserved.
Only successful `Applied` or `Replayed` seal/unseal results carry the EXP-bar
extension. A replay uses the current durable seal projection and its current
seal revision, never the historical receipt's state. Rejections, conflicts, and
already-sealed/already-unsealed results remain the original 32-byte command
result and cannot drive an EXP refresh.
