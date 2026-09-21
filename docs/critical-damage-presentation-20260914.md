# Normal and critical damage presentation

Player attacks now retain their resolved normal/critical outcome when publishing
monster-targeted single-target skills, area skills, and recurring Flame Blast
pulses. Single-target skills previously forced normal/lethal flags, area skills
forced normal, and recurring Flame Blast forced the critical-style flag. This
could display a number in a style inconsistent with its actual damage roll.

Both Legacy and ECS paths carry the committed result to caster and observer
packets. ECS area publication associates results by object ID, spawn generation
and pre-mutation health revision, preserving the correct outcome when candidates
miss or fail their commit. Each Flame Blast target and pulse carries its own
resolution. Existing basic attack and PvP outcome handling is retained.

The native client uses outcome 0 for critical, 1 for normal and 2 for miss.
Single-target opcode 10045 reads the low result byte; area opcode 10047 reads
each target's AttackType. The existing HP resource channel remains zero.
Client template.xml assigns different fonts to normal and critical damage;
this change selects those existing styles and does not resize client fonts.
Damage calculations, HP mutation, healing flags, corpse and reward handling
are unchanged.

Validation: Release build succeeded with zero warnings/errors. All 12 selected
protocol checks passed with no failures, skips or unmatched filters, covering
both engines, normal/critical and lethal single-target packets for caster and
observer, mixed AoE outcomes and visibility, repeated Flame Blast outcomes,
per-target healing, field expiry, PvP and general skill formula regressions.
Tests assert packet styles; no interactive client screenshot was taken.

Deployed to `godswar-dev-tempest-openworld-01` at
`2026-09-14T03:05:21Z`, image
`sha256:530beb249dcf8fa8635d8087e1d06dcfb83b9b576f8d2705837ec90f0476e61a`.
The service is healthy with zero restarts. Schema, all 11 content publications,
inventory, talents, boss balance, ports and other services matched the
pre-deployment snapshot. All 26 boss balance rows remain at Critical Resistance
100, and startup loaded their expected balance revision.

Evidence is in `artifacts/critical-damage-presentation-20260914/`:
`protocol-checks.json`, `source-manifest.json`, `build-receipt.json`,
`deployment-receipt.json`, before/after invariants and server receipts.
The prior image is preserved as
`reborn-server:before-critical-damage-presentation-20260914`; the private
pre-deployment database archive was validated and its local/container SHA-256
matched. No database migration or client binary patch was needed.
