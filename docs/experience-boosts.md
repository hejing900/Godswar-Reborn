# Monster-kill EXP boosts

Fighter, Talent, and pet EXP use separate additive bonus stacks after the
monster tier and player-level falloff calculation. Different kinds within a
channel add their bonus rates together; only the highest-priority status within
one kind is active.

```text
channel additive multiplier = max(0, 1 + sum(active channel bonus rates))
awarded channel EXP = truncate(base channel EXP
                               * channel additive multiplier
                               * global EXP multiplier)
```

The server evaluates that expression as one integer calculation and truncates
only once, after both multipliers. It does not truncate the additive result and
then apply the global multiplier. Overflow saturates at the signed 32-bit
maximum.

The global multiplier is deliberately separate from the additive statuses. It
is stored in
`monster_reward_settings.global_experience_multiplier_basis_points`, accepts
`10000` through `50000` (`1x` through `5x`), and defaults to `1x`. The policy is
pinned at server startup, so changing it requires a coordinated realm restart.
It affects Fighter, Talent, and pet monster-kill EXP, but is not included in the
fighter-status aggregate or represented by a client status icon.

## Supported families

| Family | Kind | Maximum configured bonus | Fighter | Talent | Pet | Notes |
|---|---:|---:|:---:|:---:|:---:|---|
| Potion, mooncake, or Passion Rose | 14 | +300% | Yes | No | Yes | Exactly one consumable status |
| Talent Potion or Talent EXP Boost | 20 | +400% | No | Yes | No | Exactly one Talent-only status |
| Weekend | 22 | +200% | Yes | No | Yes | Stock status 511 |
| Trick or Treat | 23 | +10% | Yes | No | No | Stock status 512 |
| Pet EXP | 24 | +300% | No | No | Yes | One grant; `PetExperienceBoostPolicy` owns the tiers and replacement rule |
| Enduring experience potion | 25 | +400% | Yes | No | Yes | One grant; `ExperienceBoostPotionPolicy` owns the tiers. Feeds the fighter **and** pet stacks, so it adds to a running pet potion |
| Guild | 100 | +100% | Yes | No | Yes | One duration variant |
| Guild Talent | 101 | +100% | No | Yes | No | Talent-only |
| Donator | 1008 | +5/10/15/20/25% | Yes | No | No | One account-wide tier; statuses 1500-1503 and 1506 |
| Faction area control | 1009 | Up to +350% | Yes | Yes | Yes | Configured area rate; status 1504; matching faction and current map only |
| Premium Battle Pass | 1010 | +5% | Yes | Yes | Yes | Status 1507 |

Donator and Trick or Treat remain Fighter-only. Premium Battle Pass and the
configured faction-area rate enter all three channel stacks.

Using the agreed `+350%` faction-area ceiling, the maximum additive stacks are:

| Channel | Additive bonus | Additive multiplier | With `5x` global | Example maximum award |
|---|---:|---:|---:|---:|
| Fighter | +990% | 10.90x | 54.50x | base 531 becomes 28,939 |
| Talent | +855% | 9.55x | 47.75x | base 10 becomes 477 |
| Pet | +1,255% | 13.55x | 67.75x | base 531 becomes 35,975 |

The example awards demonstrate the single final truncation. Party distribution
is a separate reward calculation.

## Pet-experience potions

The five reviewed pet-experience potions (items `4529`-`4533`, skills
`4752`-`4756`, all kind `24`) are granted by
`PostgresPetDurableCommandExecutor.ApplyPetExperienceBoostPotionAsync`. Their
tiers and durations are the client's own `Text/EquipDescription.dat` lines, and
the client status each one grants comes from `Magic.ini`'s `Status=`:

| Skill | Item | Client name | Pet EXP | Duration | Status |
|---:|---:|---|---:|---:|---:|
| 4752 | 4529 | Weak Pet Exp Potion | +50% | 60 min | 513 |
| 4753 | 4530 | Strong Pet Exp Potion | +100% | 60 min | 514 |
| 4754 | 4531 | Super Pet Exp Potion | +300% | 60 min | 515 |
| 4755 | 4532 | Durable Strong Pet Exp Potion | +100% | 8 hours | 516 |
| 4756 | 4533 | Durable Super Pet Exp Potion | +300% | 8 hours | 517 |

`PetExperienceBoostPolicy.ResolveGrant` applies the tier rule against whatever
is already active, and the committed row is `(character_id, kind = 24)`, so a
character holds exactly one pet grant:

- A **strictly higher** tier replaces the active grant outright. The bonus, the
  status, and the duration all come from the new potion; the previous remaining
  time is dropped rather than carried over. This is the one path that can
  shorten the timer, which is why the 24-hour ceiling below never truncates an
  upgrade.
- The **same** tier extends the timer: the incoming online duration is added to
  the remaining budget and clamped to `MaximumOnlineTicks` (24 hours of online
  time).
- A **lower** tier is inert. It neither downgrades the active grant nor extends
  it, and the potion still spends a second of cooldown and one stack.

The tier comparison key is `bonus_basis_points` itself (`5,000 < 10,000 <
30,000`), which is also what `PostgresExperienceBoostStateReader` orders by
within a kind. `priority` is derived as basis points / 1,000 so the two agree.

Because the grant is pet-only, it reaches `ApplyToPet` and neither the fighter
nor the talent stack; the `10167` aggregate at wire offset 300 is a
fighter-channel total and deliberately does not include it. Consuming a potion
republishes the recomposed status snapshot under reason
`pet-experience-boost-potion`, and the ordinary 30-second status reconciliation
carries the icon and countdown from there.

## Enduring experience potions

The eight reviewed experience potions raise the character's own monster-kill
experience and the pet's at the same time. Tiers and durations come from
`Text/EquipDescription.dat`; each granted status comes from `Magic.ini`'s
`Status=`. The family is split across two client item ranges and two durations,
so it is keyed by description text rather than by item contiguity:

| Skill | Item | Client name | Effect | Duration | Status |
|---:|---:|---|---:|---:|---:|
| 4800 | 4500 | Primary EXP Potion | +25% | 15 min | 504 |
| 4807 | 4501 | Weak EXP Potion | +50% | 60 min | 505 |
| 4808 | 4502 | Medium Exp Potion | +100% | 60 min | 506 |
| 4809 | 4503 | Strong Exp Potion | +300% | 60 min | 507 |
| 4759 | 4534 | Enduring Weak Exp Potion | +50% | 8 hours | 585 |
| 4747 | 4506 | Enduring Medium Exp Potion | +100% | 8 hours | 508 |
| 4760 | 4535 | Enduring Strong Exp Potion | +300% | 8 hours | 586 |
| 4764 | 4539 | Enduring Holy Exp Potion | +400% | 8 hours | 590 |

All eight live in `ExperienceBoostKinds.PersistentExperiencePotion` (kind `25`)
rather than in the fighter `Consumable` channel or the pet `Pet` channel. A
channel of its own is what makes them **stack** with a running pet-experience
potion and what gives them an independently tracked online duration, because
`character_experience_modifiers` is keyed by `(character_id, kind)`:

| Active grants | Fighter | Pet |
|---|---:|---:|
| Pet potion `+300%` (kind 24) | — | +300% (x4) |
| Experience potion `+300%` (kind 25) | +300% (x4) | +300% (x4) |
| Both at once | +300% (x4) | **+600% (x7)** |

The pet total is the sum of the two channels, so the two bonuses add rather than
replace. The fighter total takes only the kind-25 grant, because kind 24 is
pet-only (`ExperienceBoostKinds.AffectsFighter`).

Both durations share kind 25 deliberately. A 60-minute grant and an eight-hour
grant of the same tier therefore resolve through one tier rule, so reusing the
same tier extends the timer (60 min then 8 h is 9 h) while a higher tier
replaces it. Keeping the short grants out of kind 14 also stops them competing
with the mooncake and Passion Rose consumables, which share that channel through
the same primary key.

`ExperienceBoostPotionPolicy.ResolveGrant` applies the family tier rule through
the shared `ExperienceBoostTierRule`, scoped to this channel: a strictly higher
tier replaces the grant and drops its remaining time, the same tier extends the
timer up to the same 24-hour online ceiling, and a lower tier is inert. Duration
is online time, so logging out stops the clock.

The equivalent pet-side family (kind `24`) is the six pet-experience potions;
see [experience-boost-potions.md](experience-boost-potions.md).
The whole experience-item implementation, including both potion trees, the live
database state, and the parts still to build, is summarised in
[experience-items-implementation.md](experience-items-implementation.md)
(经验相关物品的实现).

## Online-only duration

Every timed row in `character_experience_modifiers` is a character-owned grant.
Its authoritative `remaining_online_ticks` budget starts only after the
character enters the world, checkpoints every status-reconciliation cycle and
when a reward resolves, and saves its final partial interval on logout or
session replacement. Merely logging into an account, remaining at character
selection, being disconnected, or restarting the server consumes no duration.
The status packet derives its displayed remaining seconds from this same
persisted budget.

The pet-experience potions use exactly this mechanism: their advertised "8
hours" is eight hours of online time, and logging out stops the clock. No
wall-clock variant exists for them, and no per-row duration-mode column is
needed.

Legacy `expires_at` rows migrate to the complete originally granted duration
(`expires_at - activated_at`). Historical online usage cannot be reconstructed,
so this restores rows that expired under the old offline-burning behavior. The
old field remains only as migration input.

The client-defined Talent statuses supported by this model are IDs `580`,
`587`, `581`, `509`, `582`, `588`, `583`, `589`, `584`, and `590` (kind `20`,
50-400%, one- or eight-hour variants).

Donator expiration, Premium Battle Pass, and faction world-boss area control
are external calendar entitlements, not character-owned duration rows, so their
clocks continue while the character is offline. A future server-wide weekend
schedule should use the same calendar-entitlement path; an explicitly granted
per-character weekend row remains an online-only personal duration.

## World-boss area control

`WorldBossCatalog` selects one non-elite world boss in each eligible outdoor
area. Athens and Sparta (`0/1`), their Newbie suburbs (`2/4`), and dungeon or
timed event/instance maps are excluded. The nineteen ready primary areas are
maps `3`, `5-22`. Parnassus (`68`) is also classified as an eligible outdoor
area, but remains explicitly pending until a distinct neutral boss is authored;
its Athenian and Spartan Generals are faction quest objectives, not world bosses.
A selected boss respawns after 43,200 seconds.
Its killer's faction controls that boss's map until the same 12-hour expiry.
The area status and its Fighter, Talent, and pet bonuses resolve only when the
character's faction and current map match the persisted control row.

The catalog and control state do not fabricate monster appearances. The live
database must contain a captured or authored spawn packet for a selected boss
before the runtime can display or fight it.

Lelantine Farm (`42`) is a scheduled faction-scoring event whose Cerberus is
already its event final boss. Troy (`44`) is the timed Trojan Expedition with
sequential bosses and guild rewards. Heracles (`210`) is a twelve-stage,
server-driven challenge with no static monster catalog. They remain outside the
generic area-control lifecycle.

Area-control resolution also validates the currently enabled catalog entry and
its selected template, so a stale row cannot continue granting EXP after a
catalog change. Online clients reconcile their personalized EXP status set
every 30 seconds; this removes expired membership icons and picks up
administrative boost changes without requiring a new login.
