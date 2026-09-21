# Wonderland corpse pickup and transporter corrections

This release fixes the native interaction regressions reported after the
external-match update. It retains the captured first-island monster roster,
the existing entrance countdown, boss sack contents and four-gem box rewards.

## Boss pickup

Live Tempest logs contained repeated ignored `MoveItem` requests for Alpha
Demon (46100) and Derskey (46200). The actual Alpha packet, including its
uninitialized native padding, is now a regression fixture. Native inspection
confirmed that the request is opcode **10050, 20 bytes**: corpse ID at +4,
zero-based loot slot at +12 and action byte 0 at +16. +8 and bytes 17–19
are not initialized authority. The previous handler expected 10048 instead.

Wonderland now resolves that native request against the exact owned run,
dead boss, spawn generation, life, range and loot lifetime before claiming
the original sack. Unrelated inventory moves retain their existing routing.
The durable claim remains one sack per boss/character/run, with full-bag
retries permitted while the corpse is available.

The native acknowledgment is also **10050**, but 16 bytes. It performs an
optimistic client bag addition, so it now precedes the authoritative bag
refresh. Claimed-corpse refresh uses a controlled one-slot publication and
neutral-player acknowledgment to clear the native loot window and sparkle
without adding another item, including full-bag and replay cases.

Evidence: `artifacts/wonderland-native-loot-20260911/` contains the sanitized
ignored requests and native sender/receiver addresses. There is no new raw
local capture; the live ignored-request log is direct reproduction evidence.

## Corpse lifetime

Each boss corpse and its loot expire **20 seconds after death**, matching
the external cleanup timing. Run completion cannot extend an old corpse to
the five-minute treasure window. Native loot cleanup (10027) is sent before
scene-object removal; expired corpses cannot grant or republish loot.
Fixed island treasure boxes remain separate from these corpses.

## Transporters and entrance service

The first two onward NPCs now use captured identities and positions:

| NPC | Object | Position X, Z |
|---|---:|---|
| First island transporter, Fane_001 | 5205 | 153, -125 |
| Second island transporter, Fane_002 | 5206 | -5, -168.5 |
| Entrance Blackmarket Teleporter, Fane_017 | 5221 | 165, -219 |

All seven onward transporters open the native function-57 dialogue. Travel
requires its Teleport button after the island is cleared. Approaching an
NPC or treasure no longer triggers automatic island travel. Captured NPC
positions are separate from the authored combat-safe-zone anchors; existing
protected arrival locations are retained because later-island monster
positions have not yet been matched to the external capture.

The entrance NPC shows its native 59/62/63 choices: 5,000 silver for a
shortcut, 6,000 with full HP, or 8,000 with full HP and MP. The menu and fees
are established by the capture/client. Its paid destination was not captured;
the local policy is the furthest unlocked island, using its protected arrival.
It remains locked before defeating Alpha Demon. Dialogue authority is
one-use, expires, and is scoped to NPC, character, instance, life and owner.

Payment advances the durable wallet and currency ledger exactly once.
Retries use the same operation identity. A rejected relocation refunds the
exact debit, and failed healing rollback cannot overwrite newer vitals.
Opening the dialogue, stale requests and insufficient funds charge nothing.
No new client assets or schema migration are needed.

## Verification and release

- Release solution build: zero warnings/errors.
- Gameplay/protocol checks: 30 passed, zero failed/skipped.
- Isolated PostgreSQL checks: five passed, zero failed/skipped. The test
  container was removed afterward.
- Checks include actual native loot-click bytes, Take All, repeat pickup,
  acknowledgment ordering, expiry/removal, NPC publication during readiness
  and visibility updates, native dialogue actions, fee variants, ambiguous
  commit recovery, ownership/life changes and compensating refunds.

Deployment verification is recorded in
`artifacts/wonderland-transport-loot-20260911/`. Tempest was recreated at
2026-09-11 06:05:21 UTC and is healthy with zero restarts. Its image is
`sha256:7c97c3e3ad17d0efe868df833d8cf81c1ad135a23d525c2f3fe3c50454a115a8`.
Ports are unchanged and Dwargon remains stopped. The previous running image
is retained as `reborn-server:before-wonderland-transport-loot-20260911`.

Owned inventory fingerprints match before/after deployment. The item
publication remains at 1,787 entries and revision
`A45EA650680C8EA4D5D2FCAA831E97EEEF652BAB55351D860BFB95330FA97EB1`;
schema remains at 150 migrations with head
`20260911_149_wonderland_boss_loot_claims`. A stopped database backup is
retained locally with its SHA-256 record. No GUI playtest, commit or push
has been performed.
