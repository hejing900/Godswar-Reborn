# Wonderland sack opening rewards

Sacks are now collected from their boss corpses. Island treasure boxes grant
four gems separately; see the [corpse-loot release](wonderland-corpse-loot-and-gems-20260911.md).
The opening rewards below are unchanged.

Right-clicking any original Wonderland sack, items 4450–4461, consumes one
sack and grants exactly one of the following rewards. The user confirmed a
single outcome and Grade IV gems. Supplied percentages are treated as relative
weights, normalized within each table without an empty outcome.

| Sacks | Reward | Quantity | Weight / total | Chance |
| --- | --- | --- | --- | --- |
| 4450–4455, islands 1–5 | Morning Dew IV, 10133 | 25 | 10 / 82 | 12.1951% |
| 4450–4455 | EXP Pill, 4174 | 25 | 15 / 82 | 18.2927% |
| 4450–4455 | Morning Dew IV, 10133 | 10 | 25 / 82 | 30.4878% |
| 4450–4455 | Morning Dew IV, 10133 | 5 | 30 / 82 | 36.5854% |
| 4450–4455 | Spring Water, 10107 | 1 | 2 / 82 | 2.4390% |
| 4456–4460, islands 6–8 before Scorpion | Morning Dew V, 10134 | 10 | 20 / 60 | 33.3333% |
| 4456–4460 | Morning Dew IV, 10133 | 50 | 20 / 60 | 33.3333% |
| 4456–4460 | Morning Dew V, 10134 | 20 | 10 / 60 | 16.6667% |
| 4456–4460 | Spring Water, 10107 | 1 | 10 / 60 | 16.6667% |
| 4461, Scorpion King | Morning Dew V, 10134 | 99 | 50 / 200 | 25% |
| 4461 | Spring Water, 10107 | 3 | 50 / 200 | 25% |
| 4461 | Sapphire IV, 4213 | 1 | 50 / 200 | 25% |
| 4461 | Emerald IV, 4223 | 1 | 50 / 200 | 25% |

The server draws one cryptographically uniform integer in `[0, total)` and
selects the cumulative interval. The committed receipt retains the roll,
selected row, exact quantity, binding, source item identity and pinned item
content revision. Duplicate operations replay that receipt without RNG or
another inventory mutation.

Before rolling, the server checks that every possible **single** outcome can
fit, including any slot released by consuming the final sack. A full-bag
rejection preserves the sack and draws no reward. After making room, a new
item-use operation can retry. Bound sacks produce bound rewards; template
binding also remains enforced. Existing partial stacks fill up to 99, retaining
their owned attributes. All reward stacks and the consumed sack share one
inventory revision, one transaction, audit/inbox evidence and inventory outbox.

Native skills 5400–5411 enforce their existing one-second bag-use cooldown.
The handler reloads the authoritative bag and uses a narrow bag projection
without rebuilding the active pet list. Durable bag receipts advance to v5,
while historical v1–v4 bytes remain decodable and hash-verifiable. The compact
inventory receipt shape is unchanged; its ledger-count bound allows all 96
bag slots plus source consumption for highly fragmented reward stacks.

EXP Pill 4174 uses its native skill 5149 and the existing one-second cooldown.
It grants 1,000,000 character EXP per pill, respects level sealing and native
progression, and preserves the pill if the full credit cannot be accepted.
The other five reward definitions were already published; 4174 is published
as a forward immutable native item addition.

Tests cover every integer interval for all twelve sacks, all thirteen reward
rows through PostgreSQL, binding and stack rollover, 97-entry fragmented
grants, concurrent/restarted replay, full-bag refusal before RNG, released-slot
reuse, cooldown, and injected transactional failure. EXP Pill checks cover
level-up, sealed storage, exact UInt32 saturation, partial-credit and level-cap
refusal, ownership fencing, cooldown, replay, and inventory/EXP rollback.

## Deployed release

Deployed to `godswar-dev-tempest-openworld-01` on September 11, 2026 at
02:55:56 UTC. Image:
`sha256:91a6d019a2f0c10d1a7774ca93b608b98d041e4cfa0aed12a21ad1883f8b6a3e`.
The process reached healthy status with zero restarts. Dwargon remains stopped.

The item publication is
`A45EA650680C8EA4D5D2FCAA831E97EEEF652BAB55351D860BFB95330FA97EB1`,
with 1,787 entries. Its sole definition delta from the previous live catalog
is native EXP Pill 4174. Schema remains at 149 migrations, ending with
`20260911_148_wonderland_chest_claims`. Existing item definitions, Holy Suit
policies, ports and owned inventory were unchanged across deployment.

Validation: Release build with zero warnings/errors, 20 protocol checks,
13 distinct PostgreSQL checks, and an item-publication rehearsal against a
copy of the live database. The rehearsal and stopped-server deployment each
preserved the complete owned-inventory fingerprint. Reports and backups are
in `artifacts/wonderland-sack-opening-20260911`; `validation-summary.json`
records the evidence. The previous image is retained as
`reborn-server:before-wonderland-sacks-20260911`.

This release also includes the exact entrance and native death/revival
corrections documented in [the native audit](wonderland-native-death-revival-20260911.md).
The installed-client revival window still needs a player playtest; automated
checks exercised the real handler and both combat engines.

Validation on 2026-09-11: Release built with zero warnings/errors. Both focused
PostgreSQL item-use suites passed (2 passed, 0 failed, 0 skipped). The sack
receipt/handler checks and EXP Pill policy check passed. Results and the
separate native item publication checks are in
`artifacts/wonderland-sack-opening-20260911/`.
