# Pet-experience boost potions (items 4529-4533, 4540)

Server-side implementation of the six stock pet-experience potions. Using one
grants a timed, pet-only experience bonus that the client shows as a status
icon with a countdown.

- **Status**: implemented and persisted; the awarded multiplier is **not yet
  observed in game** (see [Verification status](#verification-status)).
- **Channel**: the ordinary bag-item-use path, `C2S 10051` (`Opcodes.BreakItem`).
- **Duration basis**: online time, not wall-clock time.

## Functional summary

Using one of the five potions consumes one stack unit and writes a single row
into `character_experience_modifiers` with `kind = 24`. The row carries the
client status, the bonus rate, and the remaining online duration. The status is
then republished to the client as part of the composed `S2C 10167` snapshot.

The bonus applies to pet experience awarded from monster kills. It does not
affect fighter experience or talent experience.

## Data sources

Every number is taken from a reviewed client file. Nothing is inferred from a
range.

| Source | Supplies |
|---|---|
| `Localization/en_us/Text/EquipDescription.dat` | tier and duration per potion |
| `Localization/en_us/Text/EquipName.dat` | the client display name |
| `Localization/en_us/Settings/Sys/Magic.ini` | the carrying item skill and its `Status=` |
| `Localization/en_us/Settings/Sys/ItemBaseAttribute.xml` | item `Type`, `Use`, `Skill`, `Overlap` |
| `Localization/en_us/Settings/Sys/Status.ini` | the client-rendered status text and icon (**not mirrored in this repository**) |

### Reviewed table

| Skill | Item | Client name | Pet EXP | Duration | Status | Basis points | Online ticks |
|---:|---:|---|---:|---:|---:|---:|---:|
| 4752 | 4529 | Weak Pet Exp Potion | +50% | 60 min | 513 | 5,000 | 3.6e9 |
| 4753 | 4530 | Strong Pet Exp Potion | +100% | 60 min | 514 | 10,000 | 3.6e9 |
| 4754 | 4531 | Super Pet Exp Potion | +300% | 60 min | 515 | 30,000 | 3.6e9 |
| 4755 | 4532 | Durable Strong Pet Exp Potion | +100% | 8 h | 516 | 10,000 | 2.88e10 |
| 4756 | 4533 | Durable Super Pet Exp Potion | +300% | 8 h | 517 | 30,000 | 2.88e10 |
| 4765 | 4540 | Enduring Weak Pet Exp Potion | +50% | 8 h | 591 | 5,000 | 2.88e10 |

`1` online tick = 100 ns, so 1 hour is `3_600 * TimeSpan.TicksPerSecond` =
`36_000_000_000`.

The status IDs follow `Magic.ini`'s `Status=` on skills 4752-4756 in order, and
skill 4752's mapping was already transcribed before this change.

## Tier rule

A character holds exactly one pet grant, because the storage key is
`(character_id, kind = 24)`.

| Incoming vs. active | Outcome |
|---|---|
| **Strictly higher** tier | Replaces the grant outright: new bonus, new status, new duration. The previous remaining time is **discarded**. |
| **Same** tier | Extends: incoming online duration is added to the remaining budget, clamped to the ceiling. |
| **Lower** tier | Inert: neither downgrades nor extends. The stack unit and the cooldown second are still spent. |

The ceiling is `PetExperienceBoostPolicy.MaximumOnlineTicks` = **24 hours** of
online time. Only the same-tier path can reach it, so it never truncates an
upgrade.

The tier comparison key is `bonus_basis_points` itself
(`5,000 < 10,000 < 30,000`), which is also what the state reader orders by
within a kind. `priority` is derived as `basisPoints / 1_000`, so the two agree.

## Interaction with the enduring experience potions

A second family, the eight experience potions (items
4500/4501/4502/4503/4506/4534/4535/4539), raises the character's experience and
the pet's at the same time. It lives on its own channel,
`ExperienceBoostKinds.PersistentExperiencePotion` (kind `25`), so the two
families **stack** instead of competing:

| Active grants | Fighter | Pet |
|---|---:|---:|
| This family, `+300%` (kind 24) | — | +300% (x4) |
| Enduring, `+300%` (kind 25) | +300% (x4) | +300% (x4) |
| Both at once | +300% (x4) | **+600% (x7)** |

Because `character_experience_modifiers` is keyed by `(character_id, kind)`, each
family keeps its own row and therefore its own online clock. See
[experience-boosts.md](experience-boosts.md#enduring-experience-potions) for the
enduring family's own tier table.

## Request path

`C2S 10051` is shared by equipment activation and item use, so the item must be
classified before anything else happens.

```text
GamePacket(10051)
  -> GameClientHandler.Dispatch.cs        case Opcodes.BreakItem
  -> GameClientHandler.InventoryActivation.HandleBreakItemAsync
       |-- payload.ClientOperationId present?  -> HandleDurableBagItemActivationAsync
       |-- _session.IsSecure and no token      -> rejected (identity downgrade)
       `-- compatibility branch:
             classify the item from the locked kit bag
             AllowLegacyPlayerMutationFallback("pet_experience_boost_potion")
             PetCommandOperationIdentity.RawLocalServer(...)
             -> HandleDurableBagItemActivationAsync
  -> PostgresPetDurableCommandExecutor.ExecuteBagItemActivationAsync
       `-- PetExperienceBoostPolicy.TryResolveItem
             -> ApplyPetExperienceBoostPotionAsync
```

The compatibility branch is reachable only under the explicitly enabled
`LocalDevelopment` raw-TCP profile. `CanUseLegacyPlayerMutationFallback`
returns true there because `requiresDurablePlayerCommands` is false. A secure or
production session cannot reach it.

`ExecuteWithBagConsumableCooldownAsync` wraps the activation, so skills
4752-4765 keep their stock 1-second cooldown from
`BagConsumableCooldownPolicy`.

## Implementation components

### Catalog data

`src/Godswar.Server/State/BagConsumableEffectCatalog.Generated.cs`

- Adds transcribed entries for skills 4753-4756 alongside the existing 4752.
- Extends `StatusBonusBasisPoints` with statuses 514-517.
- The transcribed set is now 29 entries.

This table is the reviewed record of what `Magic.ini` and `Status.ini` say. The
live potion path does not read it; it is pinned by the protocol checks.

### Policy

`src/Godswar.Server/State/PetExperienceBoostPolicy.cs`

- `Reviewed` holds the five `(item, skill, status, basis points, ticks)` rows.
- `TryResolveSkill(skillId, out definition)` resolves by item skill.
- `TryResolveItem(templates, itemId, out definition)` resolves a locked bag
  item and re-validates the published template (`consume item`, `ID`, `Use=1`,
  matching `Skill`). A mismatch throws rather than silently ignoring.
- `ResolveGrant(activeBonus, activeTicks, incoming)` returns the tier-rule
  outcome as `PetExperienceBoostGrant`.
- `MaximumOnlineTicks` is the 24-hour ceiling.

The reviewed item set is also exposed narrowly for the routing classifier as
`IsReviewedPetExperienceBoostPotion` in `GameClientHandler.InventoryActivation.cs`,
which reads the five item IDs without the pinned template so the classifier
cannot throw on an unknown ID.

### Persistence

`src/Godswar.Server/Infrastructure/Pets/PostgresPetDurableCommandExecutor.PetExperienceBoost.cs`

`ApplyPetExperienceBoostPotionAsync` runs inside the existing command
transaction, which already holds the character row lock and ownership fence:

1. Re-check `item.PropId` against the resolved definition.
2. `ReadPetExperienceBoostAsync` reads the active `(character_id, kind = 24)`
   row's bonus and remaining online ticks. More than one row for the kind is
   treated as corrupt.
3. `PetExperienceBoostPolicy.ResolveGrant` applies the tier rule.
4. `WritePetExperienceBoostAsync` upserts the row.
5. `ConsumeOneStackItemAsync` removes one unit.
6. `AdvanceInventoryRevisionAsync` advances the inventory revision.
7. Returns `PetDurableReceiptStatus.PetExperienceBoostActivated`.

The upsert:

```sql
INSERT INTO public.character_experience_modifiers (
    character_id, status_id, kind, bonus_basis_points,
    priority, source, activated_at, expires_at, remaining_online_ticks
) VALUES (
    @characterId, @statusId, @kind, @bonusBasisPoints,
    @priority, @source, transaction_timestamp(),
    transaction_timestamp() + (@onlineTicks::bigint / 10000000) * INTERVAL '1 second',
    @onlineTicks
)
ON CONFLICT (character_id, kind) DO UPDATE
SET status_id = EXCLUDED.status_id,
    bonus_basis_points = EXCLUDED.bonus_basis_points,
    priority = EXCLUDED.priority,
    source = EXCLUDED.source,
    activated_at = EXCLUDED.activated_at,
    expires_at = EXCLUDED.expires_at,
    remaining_online_ticks = EXCLUDED.remaining_online_ticks
WHERE EXCLUDED.bonus_basis_points >=
    public.character_experience_modifiers.bonus_basis_points
RETURNING remaining_online_ticks;
```

Notes on the SQL:

- The `WHERE` clause makes the **lower-tier-is-inert** rule atomic. A losing
  conflict updates nothing, `RETURNING` yields no row, and the executor throws.
  Lower tiers are therefore rejected by the policy before reaching this
  statement; the clause is defence in depth.
- `activated_at` and `expires_at` are both derived from
  `transaction_timestamp()`, so the 8-hour window and the online-tick budget
  stay consistent even if the wall clock jumps mid-transaction.
- `source` is `pet-exp-potion:<skillId>`, e.g. `pet-exp-potion:4756`. It stays
  inside the column's 64-character bound and makes the grant traceable.
- `remaining_online_ticks` is always written explicitly. This matters because
  of the migration-068 trigger below.

### Receipt status

`PetDurableReceiptStatus.PetExperienceBoostActivated = 117` is registered in
three places:

- `Application/Pets/PetDurableExecution.cs` - the enum and the receipt's
  `Succeeded` set.
- `Application/Pets/PetDurableReceipt.Families.cs` - `MatchesBagActivation()`
  for the `BagItemActivation` command family.
- `Infrastructure/Pets/PostgresPetDurableCommandExecutor.cs` - the transition's
  `Succeeded` set, which the cooldown wrapper reads before advancing the
  cooldown.

### Client projection

`src/Godswar.Server/Game/GameClientHandler.DurablePets.Projection.cs`

Inside the `CommandFamily.BagItemActivation` branch, after the existing
empty-slot clear and kit-bag refresh, `PetExperienceBoostActivated` triggers
`SendExperienceBoostStatusAsync("pet-experience-boost-potion")`, which:

1. Re-reads `ExperienceBoostState` through `GameSessionRegistry`.
2. Recomposes and publishes the full `10167` snapshot with the granted status,
   its countdown, and every other active source preserved.
3. Normally also sends the `10166` game-data block, which refreshes the derived
   stat panel and closes any pending native use animation.

A pet-experience potion is a **bag item, not a skill**, so this path emits no
skill-cast frames. `BagConsumableActivation` (the `10051` reply),
`BagConsumableSkillCastVisual` (`10040`) and `SkillCastImpact` (`10046`) belong
to the parked HP/MP/silver implementation and are not used here. A working
consumable in this codebase sends only: slot clear, kit-bag refresh, and the
status republish.

## Database contract

Table: `character_experience_modifiers`
(created by `database/postgres/065_experience_boosts.sql`, duration column added
by `database/postgres/068_online_progression_boost_duration.sql` and mirrored in
`PostgresSchemaMigrationCatalog.ProgressionIntervals.cs`).

| Column | Type | Relevance |
|---|---|---|
| `character_id` | `integer` | part of the primary key |
| `kind` | `integer` | `24` for the pet channel; part of the primary key |
| `status_id` | `integer` | 513-517, selects the client icon and text |
| `bonus_basis_points` | `integer` | 5,000 / 10,000 / 30,000 |
| `priority` | `integer` | `bonus_basis_points / 1_000` |
| `source` | `varchar(64)` | `pet-exp-potion:<skillId>` |
| `activated_at` | `timestamptz` | `transaction_timestamp()` |
| `expires_at` | `timestamptz` | display/settlement co-ordinate |
| `remaining_online_ticks` | `bigint` | **authoritative online duration** |

Constraints and triggers that constrain this write:

- `PRIMARY KEY (character_id, kind)` - one pet grant per character.
- `ck_character_experience_modifiers_online_ticks` -
  `remaining_online_ticks IS NULL OR remaining_online_ticks >= 0`.
- `trg_character_progression_boost_online_duration` - a `BEFORE INSERT OR
  UPDATE` trigger that recomputes `remaining_online_ticks` from
  `expires_at - activated_at` **only when the new value is not distinct from the
  old one**. Writing the column explicitly bypasses it, which is what the
  executor does; the accumulated same-tier total therefore survives.

### Duration accounting

The budget is spent by the ordinary online progression interval settlement:

- `PostgresProgressionIntervalSettlementCommandExecutor.State.cs`
  (`ConsumeBoostOnlineTimeAsync`) decrements `remaining_online_ticks` for every
  active row.
- `GameSessionRegistry.Progression.cs` checkpoints the elapsed interval when a
  boost is read and when a session ends.
- `PostgresExperienceBoostStateReader` maps the tick budget back to an expiry
  and `ExperienceBoostContract` validates it.

The clock therefore runs only while the character is in the world. Logging out,
sitting at character selection, being disconnected, or restarting the server
consumes nothing. This is unchanged from every other timed boost in the
codebase; no wall-clock mode and no per-row duration discriminator exist.

### Bonus application

```text
basePetExperience            = MonsterRewardCatalog.ResolvePetExperience(...)
bonusBasisPoints             = ExperienceBoostState.TotalPetBonusBasisPoints
awardedPetExperience         = MonsterRewardPolicySnapshot.ApplyExperienceMultipliers(
                                   basePetExperience, bonusBasisPoints)
```

- `GameClientHandler.Progression.cs` builds all three channel amounts before
  settlement.
- `ExperienceBoostKinds.AffectsPet(24)` is true, so the pet row joins
  `TotalPetBonusBasisPoints` and **not** `TotalBonusBasisPoints`
  (fighter) or `TotalTalentBonusBasisPoints`.
- `ApplyExperienceMultipliers` computes
  `base * (10_000 + bonus) * globalMultiplier / 100_000_000`. With
  `bonus = 30_000` the additive factor is exactly **4x**.
- `PostgresMonsterRewardExtrasStore.MonsterDeathPetExperience.cs` writes the
  result to `character_pets.experience`. It only awards when the pet is
  `activity_state = 'owned'`, `is_carried`, and `is_summoned`; otherwise the
  settlement records `requested_experience = 0` with a null pet.

The `10167` aggregate at wire offset 300 is a **fighter-channel** total, so a
pet-only grant correctly leaves it at `0`.

## Verification status

### Confirmed

- **Routing**: before the change, `C2S 10051` for these items fell through to
  `[equip-re] BreakItem ignored: ... is not genuine equipment`, and the
  transaction never opened. The five items are now classified into the
  compatibility branch.
- **Persistence**: a live use wrote exactly one row.

  ```text
  character_id | status_id | kind | bonus_basis_points | source              | remaining_online_ticks
             2 |       517 |   24 |              30000 | pet-exp-potion:4756 |        286685962200
  ```

  `286685962200 / 10000000 = 28668.6 s`, i.e. 7.96 of the granted 8 hours,
  with the difference already spent by interval settlement. `bonus-basis-points`
  is the expected `+300%`.
- **Status display**: the client showed the icon, and the server logged
  `[status] EXP boost sync character=test reason=pet-experience-boost-potion count=1`.
- **Diagnostics**: `bonus-bps=0` in that same log line is correct - it is the
  fighter aggregate, which a pet-only grant must not enter.

### Not confirmed

The **awarded multiplier has not been observed in game.** This is the one
remaining gap and it is a test-conditions problem, not a known defect:

- `monster_death_pet_experience` holds 52 rows, every one with
  `requested_experience = 0` and a null `pet_id`.
- The test character's pet was `is_summoned = false` for every record up to
  `01:59:45`; the pet was summoned at `01:59:43`, so no kill has yet run with
  both an active grant and a summoned pet.
- The reporting player is above the monster-reward level band, so ordinary
  kills yield no pet experience to multiply
  (`MonsterRewardCatalog.ResolvePetExperience` returns `0` when
  `policy.IsEligible` is false).

To close it, run one kill with an active grant **and** a summoned pet, then:

```powershell
docker exec godswar-postgres psql -U godswar -d godswar_local -c `
  "SELECT requested_experience, pet_id, experience_before, experience_after, created_at FROM monster_death_pet_experience ORDER BY created_at DESC LIMIT 3;"
```

A row with `requested_experience > 0` and a non-null `pet_id` confirms the
award, and `experience_after - experience_before` should equal
`requested_experience`. To confirm the 4x factor, compare
`requested_experience` against the base value for the killed monster's tier:
`MonsterRewardCatalog` derives it as
`MonsterExperience[tier - 1] * CapturedNormalMonsterMultiplier` (the multiplier
is `4`), and both that array and `BaseExperience` are private, so read the
values from `MonsterRewardCatalog.cs` rather than calling them.

Database queries must target **`godswar_local`**. The `godswar` database also
exists in the same container but is unused by the running server; the
container's `GODSWAR_POSTGRES_CONNECTION_STRING` selects the database.

## Tests

`tests/Godswar.Server.ProtocolChecks/BagConsumableUseChecks.cs`:

- `CheckTranscribedMagicEffects` - 4753-4756 are no longer in the
  must-not-resolve list, and the transcribed count is 29.
- `CheckTranscribedStatusEffects` - statuses 514-517 resolve to their tiers;
  500-504 remain approved-out.
- `CheckPetExperienceBoostPotionTiers` - new. Asserts the six reviewed rows,
  that the transcribed table agrees with the policy, and exercises
  `ResolveGrant`: higher replaces and resets, same extends to 16 h, a third
  8-hour grant clamps to 24 h, lower is inert, and a `+300%` grant quadruples
  pet experience while leaving the fighter and talent stacks at zero.

**This check class is not registered in `Program.cs`** - it is parked with the
paused bag-consumable feature (its frame builder does not reproduce the
captured `10040` cast, and the runtime wiring it was written against is
inactive). The new check compiles and is reviewed, but it does not run as part
of the suite. Wire it into the catalog when that feature resumes.

## Out of scope

- `BagConsumableEffectCatalog.ActivationEnabled` stays `false`; the HP/MP and
  silver path is untouched.
- `BagConsumableEvidence` is not extended. It belongs to that parked path, and
  this implementation persists state and republishes the status snapshot
  instead of emitting a capture-shaped frame sequence.
- `GrantExperience` (instant-EXP stones) remains deliberately unimplemented.
- No migration was added: `character_experience_modifiers`, its check
  constraint, and its trigger already cover this grant.

## Change inventory

| File | Change |
|---|---|
| `src/Godswar.Server/State/PetExperienceBoostPolicy.cs` | new - reviewed table, tier rule, 24 h ceiling |
| `src/Godswar.Server/Infrastructure/Pets/PostgresPetDurableCommandExecutor.PetExperienceBoost.cs` | new - read, upsert, consume |
| `src/Godswar.Server/State/BagConsumableEffectCatalog.Generated.cs` | skills 4753-4756 and statuses 514-517 transcribed |
| `src/Godswar.Server/Infrastructure/Pets/PostgresPetDurableCommandExecutor.BagActivation.cs` | dispatch branch |
| `src/Godswar.Server/Infrastructure/Pets/PostgresPetDurableCommandExecutor.cs` | receipt status is a success |
| `src/Godswar.Server/Application/Pets/PetDurableExecution.cs` | `PetExperienceBoostActivated = 117` |
| `src/Godswar.Server/Application/Pets/PetDurableReceipt.Families.cs` | family match |
| `src/Godswar.Server/Game/GameClientHandler.InventoryActivation.cs` | `10051` compatibility routing |
| `src/Godswar.Server/Game/GameClientHandler.DurablePets.Projection.cs` | status republish |
| `src/Godswar.Server/State/ExperienceBoostPotionPolicy.cs` | new - the enduring experience family (items 4506/4534/4535/4539) |
| `src/Godswar.Server/Infrastructure/Pets/PostgresPetDurableCommandExecutor.ExperienceBoostPotion.cs` | new - the enduring row read/upsert/consume |
| `src/Godswar.Server/State/ExperienceBoostState.cs`, `src/Godswar.Server/Application/Progression/ExperienceBoostContracts.cs` | kind `25`, its pet participation, and the 508/585/590 status names |
| `tests/Godswar.Server.ProtocolChecks/BagConsumableUseChecks.cs` | assertions updated, tier check added |
| `docs/experience-boosts.md` | pet potion section and online-duration note |
| `tests/.../GameStoreTestStub.cs`, `tests/.../JsonAuthority/JsonGameStore.Inventory.cs` | pre-existing build blocker: `IGameStore.AddWishingPoolSkillBookAsync` was declared but unimplemented in both stubs |
