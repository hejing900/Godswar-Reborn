# On-hit lifesteal feedback

During the initial audit AresMage's pet was summoned but not merged, and the
equipped gear had no Life Absorption affix. Pet Merge enables its flat
life-absorption contribution. The subsequent live run demonstrated on-hit healing: at
08:28:09 UTC, Flame Blast V (574) damaged two mobs and restored 3,576 HP
(1,788 each). Fire Blast I (580), used in the first AOE regression, is a
different spell; neither spell's definition or animation was changed.
HP rose from 28,547 to 32,123 before the next monster dealt one damage; maximum
HP was 80,430, so this example was not limited by missing HP.

The existing PVE code already heals the attacker for committed basic attacks,
single-target skills and AOE hits through both Legacy and ECS combat. It combines
percentage and flat healing, applies healing-received modifiers, caps at missing
HP, and rejects duplicate hits, zero damage and dead attackers. Previously its
publisher sent only an HP/MP update, so actual healing had no floating number.

The shared publisher now sends native green healing (`10045`, signed negative
amount, result `0x101`, skill zero) immediately before authoritative vitals
(`10097`). Each damaged monster retains its own healing contribution and
produces its own healing number. Three targets healing 37 each produce
37, 37, 37 and restore 111 HP; with only 90 HP missing they produce 37, 37, 16.
The initial release incorrectly displayed an AOE's combined healing as one
number. Total authoritative healing was already calculated per target.
It sends no cast/impact packet and requires no client assets. Zero applied
healing, including hits after reaching full HP, emits no feedback.

Native display evidence: the 10045 receiver processes each identical healing
frame separately. Its floating-number renderer has five simultaneous slots;
larger bursts can replace older visible numbers, while every healing frame is
still applied. The server preserves all per-monster ticks in one ordered byte
stream queue entry, so large AOEs do not consume one queue item per heal.

The heal captures its player's world membership and life at the HP mutation.
Publication revalidates player and recipient identity, ownership, instance and
life. It admits the ordered healing frames and final vitals while holding registry and vitals locks,
then observes completion and performs any disconnect cleanup outside locks.
World-owner snapshots also run outside the registry lock. Final vitals reflect
the latest same-life HP/MP, so intervening mana or healing changes are retained.

Initial-release validation: Release build passed with zero warnings/errors. Three selected
protocol checks passed with no skips: secondary-combat projection, ordinary
intoned skill lifecycle, and the new PVE life-absorption feedback check. Real
basic attacks and mage Thunder casts were exercised in both engines, including
flat/percentage sources, capped healing, full HP, no source and repeated input.
Shared-commit tests cover replay, zero damage, dead attackers, and delayed
publication rejected after life revision or world transfer. Native packet
decoding verifies negative healing, self IDs, skill zero, packet order, and
the final authoritative HP/MP. No manual client rendering was tested.
Evidence: `artifacts/lifesteal-feedback-20260913/protocol-checks.json`.

The initial feedback release reached `godswar-dev-tempest-openworld-01` at 2026-09-13 08:18:50 UTC,
image `sha256:95bcd0777f88fad60594006c0a7b32d89684ef4cb2ffa8fb7c17f14dfc41d6b4`.
Tempest is healthy with zero restarts. Schema, all eleven publication tables,
inventory and talents were identical across the update; ports, configuration,
PostgreSQL, Redis and stopped Dwargon were preserved. A validated 78,988,414-byte
database backup and the previous runtime image are retained. The private
release directory contains build, backup, invariant and deployment receipts.

Per-monster correction validation: Release build passed with zero warnings or
errors and all four selected protocol checks passed without skips. Native
Fire Blast dispatch in both Legacy and ECS damaged three mobs and missed a
fourth; it emitted 37/37/37 or, with 90 HP missing, 37/37/16 followed by one
authoritative vitals frame and one save. Full HP, no source and replay produced
no extra healing. A 140-hit burst in each engine retained every event/monster/
spawn identity and emitted 140 distinct healing frames without disconnecting,
with exactly 140 HP restored. The native five-slot display limit remains.
Evidence: `artifacts/lifesteal-per-mob-20260913/protocol-checks.json`.

Flame Blast confirmation: a subsequent focused run also passed native skill
574 at Mage level 140/rank 5 in both engines, using ground center (3.5, 0),
three actual hits plus one miss, and 37/37/37 or 37/37/16 healing. The emitted
cast, impact and damage packets retained skill 574 and the correct ground
coordinates. Fire Blast 580 remains a separate test case. Evidence:
`artifacts/lifesteal-per-mob-20260913/flame-blast-checks.json`.

Separate Flame Blast limitation at the time of that release: the installed Magic.ini entry
574 specifies EffectTurn=10 and TimeInterval=1, matching a tooltip describing
repeated damage over ten seconds. The server's SkillCombatDefinition carries
cast time and cooldown but no ground-field duration/tick interval; its 0.5-second
cast completion executes one area damage pass. The lifesteal fix covers every
actual committed hit in that pass. It does not implement the missing repeated
ground-field damage. Generic elemental burn procs use another periodic system.
The subsequent [Flame Blast pulse repair](flame-blast-pulses-20260913.md)
restores recurring damage using the timing found in the external capture.

The per-monster correction was deployed at 2026-09-13 08:44:05 UTC as image
`sha256:9bb7d8dc30d04f67f95f7edf5d73317822b986163de630d9d10f694855a6f4b4`.
Tempest is healthy with zero restarts. All eleven content publications, schema,
inventory and talents compare unchanged, as do ports, runtime configuration
and the other containers. The validated 78,997,059-byte stopped database backup
has SHA-256 `c1f746bceb73076c43d48f4b1f97a90fa35c6b0dd6a4cef12beb01602ce10914`.
Its predecessor image is preserved as `reborn-server:before-lifesteal-per-mob-20260913`.

The level-140 talent repair is documented separately in
[AresMage provisioning](ares-mage-provisioning-20260913.md).
