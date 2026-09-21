# Flame Blast recurring damage

Flame Blast ranks I–V (570–574) now retain a ground field after the accepted
initial cast. Four additional damage passes are scheduled at +4, +8, +12 and
+16 seconds. Each cast retains its own field when recast. Fire Blast (580–584)
is a different spell and does not use this policy.

## Evidence and timing choice

The external capture contains seven rank-V fields against a stationary tower
that survived the observation window. Each field produced five total positive
damage frames, including its immediate hit: 35 matching hits, with no unmatched
hits. The maximum timing deviation from four-second spacing was 0.102 seconds.
Earlier fields continued after later casts at the same location.

For example, the field at 2026-09-11 16:17:44.740929 damaged the tower at
44.7409, 48.7484, 52.7730, 56.7594 and 16:18:00.7691. There was no sixth hit,
while the tower continued attacking through 16:18:11.124. Independent isolated
September 13 casts also show the initial/+4/+8 sequence.

This differs from client `Magic.ini` values `EffectTurn=10`, `TimeInterval=1`
and its ten-second tooltip. The runtime policy follows observed rank-V server
behavior. Applying it to earlier ranks is a family inference; their captured
casts do not provide a complete independent timing series. Damage, radius,
cast time, MP cost and cooldown still come from the existing published skill
definition, including the accepted cast's effective skill modifiers.

Evidence source: the frozen `external-full.log` in
`artifacts/wonderland-full-external-20260913`, SHA-256
`81EA111739F43E90319B64B777FE6A0F1D4CFEEB9E2DE34997692AAAD666DF44`.
Recurring external damage is opcode 10045, wire skill 250. Cast/impact packets
identify 574. Periodic damage must not replay the casting animation or charge
MP again. All 4,397 positive skill-250 frames use result flags zero, including
26 last-hit cases immediately followed by monster loot packets. The recurring
damage publisher preserves that encoding on lethal hits too.

## Settlement and lifetime

Each pulse acquires fresh targets around the original ground position. Damage
uses current authoritative monster state and combat modifiers. Only real
committed damage can trigger the shared per-target lifesteal, elemental effects
and kill rewards. Event identities distinguish fields, pulse ordinals, target
order and monster generations. Momentum scope is shared within one pulse.

Fields retain the caster's original session, character, account ownership,
realm, instance, world membership and life revision. Routine movement revisions
are allowed; death/revival, leaving/rejoining, disconnect or ownership changes
invalidate the field. Timers wait outside the character gate, which is acquired
only for settlement. Session cleanup cancels and joins all fields before gate
disposal. Expired intervals are skipped after a stall rather than released as a
burst of overdue damage.

No database schema, content publication, character progression or inventory
change is needed for this repair.

## Validation

Release compilation passed with zero warnings or errors. The final combined
protocol run passed all six selected checks without skips: ordinary intonation,
single-target miss completion, actual lifesteal, per-monster AOE feedback,
independent Flame Blast pulses and Flame Blast lifecycle/admission.

Both Legacy and ECS were exercised. Checks verify five total pulses, overlapping
recasts, exact recurring damage packets, healing per actually damaged monster,
mana charged only for accepted initial casts, normal cooldown and low-MP
rejection, empty placement, moving targets entering/leaving the original area,
routine caster movement, death, new life, map exit, disconnect, repeated cleanup
and suppression of expired damage after a stall. Tests use the same command
gate as real ingress and a controllable pulse clock. There was no manual native
client rendering test.

Evidence: `artifacts/flame-blast-pulses-20260913/verified-checks.json`,
`final-build.log`, `source-manifest.json` and the Docker build receipt. Earlier
failed test-setup runs remain as historical evidence; `verified-checks.json`
is the final complete result. All new or edited task code files remain below
20 KB.

## Deployment

Deployed to `godswar-dev-tempest-openworld-01` at 2026-09-13 09:22:34 UTC,
image `sha256:57ac4db77e56ce4f90d10962b57a4b7b598c5cb01dd7c64b999406dca53ea953`.
The container is healthy with zero restarts and both native endpoints listening.
Schema, all eleven content publications, inventory, talents, ports, runtime
configuration and the other containers compare unchanged across the release.

The stopped database backup is 78,997,057 bytes, SHA-256
`8d15d04228d427670ff0d14edc70109a2d672b9b6aa41dbc55415c363f63d54a`.
The previous image remains available as
`reborn-server:before-flame-blast-pulses-20260913`. The private release directory
contains the backup and deployment/invariant receipts.
