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
| Pet EXP | 24 | +300% | No | No | Yes | Pet-only |
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

## Online-only duration

Every timed row in `character_experience_modifiers` is a character-owned grant.
Its authoritative `remaining_online_ticks` budget starts only after the
character enters the world, checkpoints every status-reconciliation cycle and
when a reward resolves, and saves its final partial interval on logout or
session replacement. Merely logging into an account, remaining at character
selection, being disconnected, or restarting the server consumes no duration.
The status packet derives its displayed remaining seconds from this same
persisted budget.

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
