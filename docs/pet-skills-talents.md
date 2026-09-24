# Pet skills, talents, and manager dialogue

## Skill-cell model

The pet-detail UI exposes **12 learnable skill cells**. This is distinct from
the **six auto-cast cells** on the pet action bar; the auto-cast limit must not
be used as the durable learned-skill limit.

A newly hatched pet starts with its species starter skill in opened slot 1.
Aptitudes below Smart start with one available/opened slot. Smart (numeric
aptitude 10) and every higher aptitude also start with an available, opened,
but empty slot 2.

Skill-slot progression is deliberately two-step and server-authoritative:

1. Pet Enhance Spring (`10099`) expands the available-slot boundary by one.
2. Golden Apple Juice (`10100`) opens the next available slot so a skill book
   can be consumed into it.

Neither item may move a boundary above 12, skip a boundary, overwrite a
learned skill, or be trusted merely because the client displays a successful
action. The owned-pet snapshot persists the available and opened boundaries
independently.

## Learned-skill rank and Trait policy

Migration `083` publishes the reviewed installed-client skill curves as
immutable PostgreSQL content. The process will only start with normalized
revision `64748AC27B0D815B9C30CFF78A7CE8AD519AE83DF528CB5CDFF4374503ABB473`,
derived from installed `Pet_Skill.xml` SHA-256
`B2EE9219E5E804AFA34797D6D2BCB8787B7C1C6EDF7914F4C1A6AC982A553F43`.
The normalized publication has 67 families, 384 `(Type, Priority)` tier
curves, and 1,655 concrete rank steps. Startup publishes and seals it once;
later row mutation, deletion, incomplete publication, or a different official
revision fails closed.

`Type` is the stable skill-family ID and `Priority` is the learned book tier.
The durable learned state should therefore store the family and highest
learned Priority, rather than treating every concrete `NextID` row as a
separate learned skill. Learning tier N requires tier N-1 to be learned and
the six-value `Trait` threshold to be met at that moment. `Trait` uses pet
Savvy order Agility, Strength, Accuracy, Technique, Wisdom, Luck; client
hundredths are normalized to server decimals. Once a tier is learned, a Fairy
redistribution does not deactivate it or lower its effect.

Every tier has a rank-zero step, so learning has an immediate default effect.
At runtime the resolver chooses the highest `Restrict[i]` not above the
authoritative pet rank and uses `Values[i]` as the **absolute** magnitude. It
does not add the steps together. The repeated `Values[]` curve is canonical
where source metadata disagrees: for example runtime row `552` says
`fact_Value=826` but its indexed `Values[]` magnitude is `926`. Full-width
commas in rows `6020-6023`, misleading XML element names around
`1420-1429`, and the reviewed repeated-metadata discrepancy in curve
`3000-3004` are normalized deterministically.

`Genre` and `Effect` carry the same number in every row, and `Effect` selects
the owner stat channel. `Add` is proven: `Add=1` applies the effect to the
owner and `Add=2` applies it to the pet itself. Every owner effect the client
uses is projected, and its scale follows the channel's existing convention
(fraction-valued effects are stored in character basis points):

| Effect | Client text | Channel | Scale |
|---:|---|---|---|
| `0` / `1` | player HP / MP | `max_hp` / `max_mp` | value |
| `2` / `3` | hit / dodge | `hit` / `dodge` | value |
| `4` / `5` | physical attack / defense | `physical_attack` / `physical_defense` | value |
| `6` / `7` | magic attack / defense | `magic_attack` / `magic_defense` | value |
| `8` / `9` | critical / critical resistance | `critical` / `critical_resistance` | value |
| `10` | damage absorption | `damage_absorb` | value |
| `13` / `14` | HP / MP recovery | `hp_recovery` / `mp_recovery` | value |
| `15` / `16` | status hit / status dodge | `status_hit` / `status_resistance` | value |
| `19` / `20` | ignore physical / magic defense | `ignore_physical_defense` / `ignore_magic_defense` | value x 10,000 |
| `21` / `22` | physical / magic damage | `physical_damage_bonus` / `magic_damage_bonus` | value x 10,000 |
| `23` / `24` | physical / magic appended damage | `physical_append_damage` / `magic_append_damage` | value |
| `25` / `26` | critical damage percent / flat | `critical_damage_percent` / `critical_damage_flat` | value x 10,000 / value |
| `29` / `30` | incoming physical / magic reduction | `physical_flat_absorption` / `magic_flat_absorption` | value |
| `32` | incoming critical reduction | `critical_damage_flat_reduction` | value |
| `34` | on-hit owner heal (Blood Chant, Extraction, Lifedrain) | `life_absorption_flat` | value |
| `34` + family `428` | authored Vampiric percentage | `life_absorption` | value x 10,000 |
| `37` | damage rebound percent | `damage_rebound` | value x 10,000 |
| `38` | damage rebound flat | `damage_rebound_flat` | value |

Family `413` is Platypus-exclusive Focus. Stock books `10530-10535` map to
runtime tiers `4600/4604/4608/4612/4616/4620`; tiers II-VI require visible
Accuracy Savvy `64/192/235/270/305`. At pet rank 100, Focus VI resolves its
highest rank-90 step and adds `119` Hit Rating.

Only active learned rows on the character's **summoned** pet contribute. A
carried but recalled pet supplies nothing, so Call Out adds the source and
Recall removes it. Take/switch and hatch select a new source; Seal removes one.
Owner Merge is a separate additive projection and never causes learned
passives to be counted twice. All curve joins use the process-pinned learned
skill publication, the persisted tier, and the highest rank step not above
the authoritative pet rank. The client supplies none of those values.

The stage thresholds are the client's own `Restrict[]` ranks: Dark Vengeance I
(`808`) resolves `40` magic attack, `75` at pet rank 8, and `100` at pet rank
19 for a summoned Ghost. A rank change from Rebirth or pet-to-pet Merge, a
Take, a Call Out, a Recall, a learn, and an unlearn each republish the owner's
calculated stats (`10167` then `10166`). The login restore calls the durable
transition directly and publishes the complete status itself, so it needs no
extra frames.

Verified live on `2026-09-23`: `pet_presence_transition` commands `8470` and
`8471` recalled and called out the summoned Ghost (`character_pets.id = 8`,
rank `2.000000`) carrying Dark Vengeance I, and the owner's magic attack read
exactly `40` higher while the pet was summoned and returned to its previous
value after Recall. The same projection resolves `75` at rank 8 and `100` at
rank 19 for that curve.

The pet-self effects `43`-`48` (the six `符记` / Mark families `430`-`480`,
which the client describes as raising the pet's **own** Agility, Strength,
Accuracy, Technique, Wisdom and Luck) are deliberately **not** part of this
owner-stat projection: they move the pet's own effective Savvy, its native
Basic/Added wire split, and the owner-Merge contribution instead. The operator
confirms that path is already effective, so it is left untouched here and was
not re-verified in this change.

Both items are direct right-click consumables using the shared client request
opcode `10051`. The server classifies the locked authoritative bag item,
updates the currently carried pet, consumes exactly one item in the same
transaction, and then sends the verified narrow `PetSkillState` response
(`10247`). That 36-byte response updates only the available, opened and learned
boundaries plus the twelve skill IDs. Opcode `10245` is the separate 16-byte
pet-care response for satiety, amity and lifetime and must not be used for
skill cells. The full owned-pet list (`10237`) remains a bootstrap/rebuild
packet because using it as a live delta can disturb carry/summon state.

After a committed learn, upgrade, or unlearn, the server reloads the complete
calculated character snapshot and publishes `10247`, then complete status
opcode `10167`, then local GameData opcode `10166`. Rank-changing pet Merge,
Take/switch, hatch, and Seal publish the same final `10167 -> 10166` stat pair
when their carried passive source or selected rank tier changes. The `10167`
frame preserves all active runtime statuses; it is never an empty replacement
delta. Safe stat snapshots may be replayed for reconciliation, while additive
pet-Merge opcode `10269` is never replayed.

For a surviving consumable stack, the server refreshes the committed count in
place and does not send slot-clear opcode `10052`. The stock client starts its
own clock/cooldown overlay when the item is used, and preserving the item UI
object lets that animation finish. A final consumed unit still receives
`10052` before the empty-bag refresh so a stale icon cannot remain.

## Stock skill books

Every pet skill book the installed client ships is now learnable. The set is
transcribed from `Settings/Sys/ItemBaseAttribute.xml` (the rows that carry a
`PetSkill` attribute) and `Settings/Sys/Pet_Skill.xml` (`Type` is the family,
`Priority` is the learned tier). The client repeats twelve exact rows
(`10600-10605`, `10610-10615`), so its 402 book rows are **390 distinct item
IDs** across **68 families**. `PetSkillBookActivationPolicy.ReviewedBookCount`
and `SpeciesExclusiveFamilyCount` are fail-closed invariants of that set.

A family is either shared by every pet or owned by exactly one species:

- **24 shared families / 126 books.** No `PetInfo` text names a species.
- **44 species-exclusive families / 264 books.** `Message_Pet.dat` states the
  restriction in each `PetInfo<skill>` row as either `仅X可学` or `X的特有技能`,
  and `UI/Base/text.lua` `PETTYPE<n>` names the species whose numeric identity
  is `n`. All 44 names map onto species `1-44` with no unmapped row.

The restriction is evaluated against the pet's **current** `species_id`, so a
Magic Jade species change keeps every already-learned family and opens the new
species' books. A pet may additionally always advance a family that is its own
species starter skill, which keeps species `45` (Cupid, born with the Hedgehog
family) able to advance that innate skill.

Learning still requires the preceding tier, the family `Trait` threshold, an
opened and empty cell, and one consumed book — all unchanged and still executed
inside one PostgreSQL transaction with the durable receipt, inbox replay and
learn evidence.

Both family kinds were verified live on `2026-09-23` against `character_pet_skills`
and `command_inbox` after a normal deployment:

| Command | Book | Family | Result |
|---:|---|---|---|
| `8311` | `10231` Luck I | `480` shared | learned skill `2600` into cell 0 |
| `8314` | `10210` Dark Vengeance I | `62` Ghost-exclusive | learned skill `808` into cell 1 |
| `8332` | `10224` Blood Chant I | `340` shared | learned skill `2000` into cell 2 |

The same session proves the refusal path: `10464` Wild Bump I (family `408`,
Kritox-exclusive) was used on the Ghost five times (`8319`, `8320`, `8323`,
`8324`, `8325`) and every attempt was rejected as
`PetSkillBookWrongSpecies` without consuming the book and without recalling
the pet. Before this change the allow-list held five families, so `10231`,
`10224` and `10210` were all discarded as "not genuine equipment" and the
learned-skill rule compared the book family against the pet's starter family,
which no shared book could ever satisfy.

Two content identities the generated client catalogue stops short of are
published from `PetSkillBookItemContentBaseline`: `10745` (Spiky Armor VI) and
the authored `16400-16405` Vampiric tiers. Publishing them advanced the item
template revision to
`D4FEF729173DAC258ED74A1D7DEBAA9B3DB71C77EC462BAE2233777951B0A07D` with 3,484
items; the learned-skill publication is unchanged.

A refused book leaves the pet untouched, so the projection answers it with the
kit-bag refresh only. It deliberately skips owned-pet list opcode `10237`,
which resets the client's active-pet selection.

## Innate talents

Talents are built into a pet by its aptitude. They are not learned from an
inventory consumable and cannot be supplied by the client. The immutable,
database-published aptitude definition owns the exact mask used at hatch:

| Aptitude | Innate talents | Mask |
|---|---|---:|
| Weak through Zealous (`1-9`) | None | `0` |
| Smart through Almighty (`10-13`) | Quest Dispatch, Healing, Merge | `26` |
| Godly through Transcendent (`14-16`) | Random Event, Quest Dispatch, Work, Healing, Merge | `31` |

The stable implemented bits are:

| Bit | Talent |
|---:|---|
| `1` | Random Event |
| `2` | Quest Dispatch |
| `4` | Work |
| `8` | Healing |
| `16` | Merge |

The client draws a sixth talent cell, but no verified stock name, item, or
meaning exists for bit `32`. That bit remains reserved and must stay clear
until compatible client and protocol evidence is available.

Stock item IDs `10110-10114` retain their names and icons only as inert client
compatibility artifacts. Their activation metadata is deliberately absent;
right-clicking, replaying, or forging a packet for one cannot change a pet's
talents. The native-profile `NativeGenius` value is also compatibility data,
not an authority: it varies by species and conflicts with the quality rule.

An existing pet is reconciled to its aptitude mask by migration `072`. Merge's
legacy boolean projection is updated in the same transaction. New hatches use
the process-pinned database content revision, so both hatch paths receive the
same quality-derived talents and never consult mutable client state.

### Healing runtime

Healing is an authoritative passive talent. After an accepted, nonlethal
monster hit leaves the owner at or below 40% maximum HP, a carried and
summoned pet with bit `8` heals a percentage of authoritative owner maximum
HP, capped by missing HP. At pet level 120 the rates are Smart 12%,
Overbearing 14%, Ferocious 16%, Almighty 18%, Godly 20%, Celestial 22%, and
Transcendent 25%. Level 1 starts at half of the aptitude rate and scales
linearly to the full rate at level 120. A successful heal starts the
stock-derived 180-second cooldown. Replayed, stale, rejected, zero-damage,
and lethal hits cannot trigger it. The client receives only the committed
green healing number and final vitals; it cannot choose the amount or reset
the cooldown.

The exact native heal formula was not recovered, so this is explicitly
project balance V2. The current authoritative incoming-damage slice is
monster-to-player combat. PvP, damage-over-time, and environmental damage must
publish the same shared accepted-damage event before Healing can cover those
future sources. The cooldown is process-scoped until cross-instance transfer
adds a preloaded TTL coordination projection.

### Owner Merge runtime

Owner Merge is an innate pet talent. The stock client presents its action with
the legacy Merge control/artwork, but item `11004` is not an input, inventory
requirement, or consumable for opcode `10274`. The server locks the carried
pet, requires it to be summoned, at full energy, and at least 40 amity, then
calculates the contribution from all six pet Savvy values. A successful request
writes the one contributing-pet flag, 16 native typed bonus rows, and two
Reborn-only Technique reduction rows in the same transaction. The internal
rows are never serialized as native `PetUnite` fields. A second distinct Merge
activation toggles the state off; Take,
Call Out, Recall, and switching pets are rejected while the flag is active. The
dedicated command-family identity, inbox replay, optimistic pet
revision, outbox, and audit records make retries unable to duplicate or
silently clear bonuses.

The installed client emits the exact header-only request `04 00 22 28`
(opcode `10274`) from the action-bar Merge control. The legacy handler accepts
only that four-byte shape, selects the single authoritative active pet, and
executes dedicated durable family `PetOwnerMergeToggle` (`48`). The secure shim assigns the request a
stable operation UUID for retry/deduplication without accepting a client item,
bag slot, pet ID, or stat value.

The contribution curve is database-published project policy
`project-pet-unite-piecewise-marginal-v4`, based on the recovered stock
`Pet_Alter.xml` bases and curves. Its marginal-band effectiveness is
`100% / 85% / 70% / 60% / 50%`. Agility's five Damage Rebound rates are
intentionally zero; Luck remains the only Savvy source for Damage Rebound.
See
[pet-owner-merge-balance.md](pet-owner-merge-balance.md) for the complete
database ownership and publication contract. Native effects `23/24` add fixed
physical/magic damage, `29/30` cancel fixed physical/magic damage, `32` cancels
fixed critical damage, `34` restores a fixed amount of HP once per committed
direct hit, and `38` reflects a fixed amount. Effect `10` remains flat damage
absorption. Technique separately grants physical and magic percentage
reduction as `min(3000 bp, round-away(effective Technique * 0.15 bp))`; the
shared combat resolver retains its global `8000 bp` reduction cap. Fixed
on-hit healing is added to any independent percentage life absorption and is
capped at missing HP. Rebound and on-hit healing are replay-fenced secondary
effects and cannot recursively trigger another proc chain. Exact
training-dummy admission also suppresses dummy-sourced stat rebound and
elemental reflection.

The project client's owner-Merge visual policy is specified in
[pet-owner-merge-visual.md](pet-owner-merge-visual.md). Its lifecycle is:

- opcode `10275` is registered to the unite-start handler at `0x006A16F0`;
  its ten-byte frame carries the owner object ID, aptitude, and completed
  rebirth count, selects the quality-tiered `unitefile` effect, scales that
  effect by rebirth milestone, hides the companion, and changes both local and
  third-player pet managers to the merged state;
- opcode `10282` is registered to the unite-end handler at `0x006A17A0`;
  its eight-byte frame carries the owner object ID, removes the unite effect,
  and restores the manager state for local and nearby-player presentations.

The server sends `10275` to the owner with local object ID `0x1448` and to
nearby players with the authoritative world object ID. It sends `10282` in the
same two namespaces at expiry. It deliberately does not send full pet-list
opcode `10237` during either transition: that packet rebuilds active-pet
selection and provokes an immediate client Recall, which previously collapsed
the temporary stat projection. The pet stays logically carried and summoned
in PostgreSQL while its companion model is hidden.

At end, the owner's client receives its normal Call Out result and local
world-presence packet after `10282`. The installed client ignores that
world-presence packet for non-local owners, so normal companion restoration
for already-connected observers remains a native-protocol gap; the server
does not blindly broadcast the local-only packet. Join-in-progress observers
do receive `10275` when the target is currently merged. The presentation flag
and AOI world revision change atomically so map handoff reconciliation cannot
miss a concurrent Merge start or end.

Pet energy is normalized to `0..100` by the current server schema. The native
client uses `1800` units for a full bar. Retained capture
`capture-proxy-20260514-173331.log` publishes opcode `10278` at approximately
six-second intervals while unmerged (for example `18:26:24.079`,
`18:26:30.098`, and `18:26:36.120`), with `1800` in its four-byte energy field.
That evidence establishes the heartbeat cadence and wire scale, but does not
reveal a stock recovery delta. Authored project balance therefore restores five
normalized points every 6 online seconds to the one carried, unmerged pet,
whether called out or recalled. Recovery is capped at the pet's stored maximum;
there is no elapsed-time offline accrual. Separately, every ordinary login
durably resets the one carried pet to full before client bootstrap. This fixed
login rule does not estimate missed recharge intervals. A full pet keeps
receiving the captured six-second `10278` heartbeat without advancing its
durable revision.

Exact stock drain cadence is also not recovered. Project balance drains one
normalized point per 3 online Merge seconds, mapping a full bar to a 5-minute
lifetime. Both intervals are injectable for deterministic tests. Energy
recovery, decrement, and the
final transition are ownership-fenced PostgreSQL mutations. At zero the
server atomically clears `contributes_to_character`, deletes all 18 derived
bonus rows, refreshes character stats, sends `10282`, and restores the carried
companion. Disconnect ends Merge before releasing session ownership; login
also clears a stale active Merge left by an unclean process exit before the
first character-state projection.

Opcode `10278` writes the client's current pet-energy field. The server sends
it only to the owning client immediately after the login-owned-pet list, at
each unmerged recovery/heartbeat tick, Merge start, each authoritative drain
tick, and Merge end. The explicit login projection is required because opcode
`10237` selects the carried pet but does not publish its energy. Normal login
first commits the full refill through the ownership/revision-fenced pet
lifecycle, then sends `10278` immediately after `10237`; the packet therefore
matches durable state rather than painting over a partial value. Exact pinned
training dummies retain their perpetual Merge fixture and bypass this login
reset. Normalized database energy `0..100` is safely scaled to native units
`0..1800` (`percentage * 18`). It is not broadcast to observers.

## Pet Manager dialogue compatibility

The stock Pet Manager advertises two ordered top-level functions from the
same NPC script. The server publishes both for `Athens_088` and `Sparta_088`:

| Route | Dialogue index | Client label | Published menu |
|---:|---:|---|---|
| 0 | 31 | Pet Raising | 1-11 |
| 1 | 36 | Reset Pet's Points | 100, 101 |

Pet Raising routes its original menu and informational pages:

| Menu sub-ID | Function | Informational page(s) |
|---:|---|---|
| 1 | Soul Contract | 11, 101 |
| 2 | Rebirth | 12, 102 |
| 3 | Merge | 13, 103 |
| 4 | Check Growth | 14, 104 |
| 5 | Seal Spirit | 15, 105 |
| 6 | Unlearn Skill | 16, 106-111 and 114-119 |
| 7 | Bind pet/owner | 17, 112 |
| 8 | Change appearance | 113 |
| 9 | Pet Call charm | Native client page |
| 10 | Owner Merge | Native client page; innate talent, no item consumed |
| 11 | Change Gender | Native client page |

Unlearn Skill is implemented for all twelve slots. The native choices
`106-111` select slots 1-6 and `114-119` select slots 7-12. The stock client
confirms the selection with the exact 92-byte nested frame: parent sub-ID `6`,
the selected erase sub-ID in argument 0, and the remaining seventeen arguments
set to `-1`. A direct selected sub-ID with eighteen `-1` arguments remains a
compatible form. The server selects the summoned owned pet and the first
authoritative Strong Purge Potion (`10101`), deletes the selected skill,
compacts later skills left, consumes exactly one potion, and advances the pet
and inventory revisions in one PostgreSQL transaction. Retries reuse the
durable command result rather than consuming another potion. Native terminal
results are `1011` (no summoned pet), `1061` (no potion), `1062` (empty slot),
and `1063` (success); success refreshes the bag and opcode `10247` skill state.

Reset Pet's Points exposes the stock entry pages:

| Menu sub-ID | Function | Informational/action page |
|---:|---|---|
| 100 | Reset basic Savvy distribution | 111, 116 |
| 101 | Reset Growth Rate distribution | 112, 117 |

Action `117` remains a durable paid Growth preview. Fairy's Feather action
`116` is a one-phase durable reset that atomically consumes one feather and
commits a redistribution of the same total Basic Savvy;
Phoenix's Feather action `117` previews six new Growth rates. A Fairy Reset
commits immediately and page `120` shows the committed values. A Phoenix
Reset consumes its feather but does not mutate Growth until **OK** accepts its
latest session-fenced preview; **Cancel** leaves Growth unchanged. Replayed
operation identities cannot consume or apply twice. A successful Fairy Reset
or Phoenix OK sends the extended 68-byte opcode `10286` to refresh the
existing pet object without the destructive full-list opcode `10237`,
preserving carried and summoned state. The exact-hash, two-locale
installer is `tools/PatchClientPetGrowthResetDialog.ps1`. The Fairy balance
policy and provenance rules are documented in
`docs/pet-basic-savvy-reset.md`.

The client's separate Advance Pet Raising dialogue (`119`) is not published
because no working-server evidence currently binds it to these NPCs.

The menu and read-only pages are wired. Skill removal and direct right-click
use of Pet Enhance Spring and Golden Apple Juice are verified and implemented.
Skill-book learning uses the same direct right-click bag activation (opcode
`10051`) and the same durable family; its request layout is therefore the one
already captured, not a guessed modal. The remaining unimplemented surface is
informational: a refused book produces no client-visible reason text.
