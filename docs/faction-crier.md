# Faction Crier

The Faction Crier is the stock `NpcFunSignact` dialogue (wire dialog `15`) at
Athens `Athens_055`/5194 and Sparta `Sparta_055`/5052. The published Sparta
spawn ID is authoritative at runtime; 5054 is retained only as source
provenance behind the normal map/NPC ownership check.

## Nameplates

Nameplate I through VI are item IDs 3820 through 3825. They are bound
consumables with a maximum stack of 99.

- Monday through Saturday award I through VI respectively, once per realm
  calendar day. Sunday returns the stock closed result because there is no
  Nameplate VII.
- The weekly recovery page can reclaim a selected I–VI once per realm week
  for 230 Gold.
- Renewal consumes one selected source Nameplate and 105 Gold, then grants a
  different requested Nameplate.

Daily and weekly uniqueness is enforced in PostgreSQL, not by the client or
an in-memory clock. The active realm row supplies the shared IANA game
calendar. Tempest and Dwargon currently use `Asia/Manila` (UTC+8).

## Turn-ins

The stock nested menu offers:

- one selected Nameplate for its tier's base fighter EXP;
- I+III+V or II+IV+VI for 6x, 9x, or 12x EXP or direct Talent Points;
- all six for both EXP and direct Talent Points at 12x, 18x, or 24x.

Silver prices are level-tiered. The premium actions use the reviewed clickable
menu prices: 312/459 for triple exchanges and 936/1377 for all-six exchanges.
The conflicting 680/1000/2040/3000 help copy is stale and is not authority.
B-Gold is a distinct persisted wallet; it is never aliased to Gold.

The stock terminal 131–140 balance tier is deliberately extended through the
server level cap of 200. Levels below 20 are rejected. At level 200 (or while
fighter progression is sealed), an EXP exchange still consumes the selected
bound Nameplates and currency once, but records the actually credited EXP as
zero and emits no EXP-gain or level-up projection.

## Durability

Every mutation is one PostgreSQL transaction. It locks player ownership,
character revisions, and the kit bag; validates exact currency and Nameplate
inputs; changes inventory, wallet, fighter EXP, and direct Talent Points;
advances revisions; and writes command inbox/audit, inventory/currency ledgers,
an outbox event, and an immutable Faction Crier settlement.

Secure commands use the client operation ID. Raw-local compatibility uses a
server operation ID tied to the connection and is accepted only by the existing
development fallback policy. Durable replay sends authoritative state without
replaying level-up or reward animations.

## Management

`faction_crier_balance_settings` points to one sealed immutable revision.
Level tiers and exchange options are database rows, so a management surface can
publish a new revision with compare-and-swap semantics. Both realm workers pin
the same revision at startup; changing the pointer requires a coordinated
worker restart before it becomes active.

The stock client hard-codes the displayed prices, reward labels, and result
sub-IDs. The current management contract therefore must not expose numeric
costs, tier rewards, or multipliers as independently hot-safe settings. Any
non-stock numeric publication requires a synchronized client
localization/content revision and a coordinated worker restart. Currency and
reward kind are fixed per stock action sub-ID; PostgreSQL rejects a changed
shape, and publication rejects any tier reward multiplied by an option beyond
the signed 32-bit reward range.

Migration `20260821_100_faction_crier_foundation` owns the database contract:

- `faction_crier_balance_revisions` retains its historical UTC-offset field
  for immutable migration compatibility, but that field is no longer runtime
  calendar authority. It also stores minimum level, Gold costs, and declared
  child-row counts.
- `faction_crier_balance_tiers` stores the seven contiguous level tiers from
  20 through 200. `faction_crier_balance_options` stores paid menu sub-IDs
  110 through 134.
- `faction_crier_balance_settings` is the singleton publication pointer.
  Publishing seals the selected revision; sealed headers, tiers, and options
  reject all later mutations and child inserts.

Migration `20260821_102_faction_crier_nzst_calendar` preserves immutable
revision 0 as history and publishes revision 1 with the corrected UTC+12 realm
calendar used during that rollout. Its seven tiers and 25 stock options are
copied unchanged. Migration `20260821_103_realm_calendar_authority` supersedes
that feature-local clock with the global per-realm `Asia/Manila` calendar.

A management write must use one transaction: insert revision
`expectedRevision + 1`, insert all seven tiers and all 25 options, then update
the singleton pointer with `WHERE revision = expectedRevision`. A zero-row
pointer update is a stale compare-and-swap and the whole transaction must roll
back. Once committed, drain and restart all realm workers together; workers do
not hot-reload this balance.

## Database evidence

`character_base."BindingGold"` is the authoritative B-Gold wallet column.
`character_economy_baseline.binding_gold`, `character_currency_ledger` code
`binding_gold`, and `character_wallet_reconciliation` preserve the same audit
chain as Silver and Gold. `character_base.faction_crier_revision` is the strict
aggregate/outbox version advanced by every committed Crier mutation.

Daily claims, weekly reclaims, and turn-in/renewal settlements are append-only
rows in `faction_crier_daily_claims`, `faction_crier_weekly_reclaims`, and
`faction_crier_exchange_settlements`. They retain the realm period, balance and
item-content revisions, exact wallet/inventory/progression/Crier revisions, and
command inbox, audit, and outbox identities.

Nameplates 3820 through 3825 are also published into immutable item manifest
V9 content under source suffix `pets-v4+nameplates-v1`; the mutable rows exist
only as the foreign-key compatibility projection.
