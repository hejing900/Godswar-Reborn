# Wonderland entry rejection and test25 daily allowance

The client text `Instance info verification failed.` is `RepCheckErr`, emitted by native queue result `10222 / 2`. Previously, the countdown sent that result whenever legacy admission returned without a transfer, including ordinary daily-limit rejection.

## Live evidence

At the reported attempt, test25 / character 7005 had three admitted Wonderland entries for realm day 2026-09-11. The live policy in `legacy_instance_settings` is three free entries and zero paid retries. That is a definite admission blocker; the old log did not distinguish it from the other rejection branches.

The existing three admissions were at 04:08:53, 05:37:01, and 07:19:25 UTC. The reported attempt around 08:55 UTC created no new admitted entry or dungeon. The server stayed healthy with no restart, and the character's disconnect cleanup completed; this report is separate from the previously diagnosed combat deadlock.

## Change

Legacy admission reports a typed outcome to its countdown caller. A failed pending entry closes its queue with the existing native `RepetitionReset` (`10231`, payload zero), then presents the applicable reason. Native disassembly confirms that this closes the waiting/Enter window and clears its queue flags without displaying `RepCheckErr`.

Wonderland daily-limit rejection states the configured entry limit and distinguishes solo from party rejection. Authority rejection explains revival, distance, or party/session changes. Diagnostics record the rejection stage, scene, and NPC without changing the admission, payment, or ownership checks. A full repetition reset must never clear a run the leader already entered.

The post-leader follower-transfer block was extracted unchanged to keep the modified production files below 20 KB.

## Deadlock assurance

The known registry/vitals lock cycle was reproduced with old code and prevented by registry-first acquisition. The separate owner/vitals cycle is covered by the prepared-target regression. A bounded review of current combat, periodic recovery, elemental reflection, and Wonderland status publication found no remaining inversion in those paths. This supports confidence in those specific fixes; it does not prove the entire server is free of every possible deadlock.

## Verification and test entry

Release evidence belongs under `artifacts/wonderland-entry-verification-20260911/`.

- Release build passed with zero warnings/errors. All 14 selected protocol checks and both isolated PostgreSQL checks passed, with no skips.
- Protocol checks include both deadlock regressions, countdown click/timeout/replay, solo/party daily-limit rejection, successful retry, current ownership, late rejection after actual Wonderland/Medusa entry, and Atlantis paid/free admission flows.
- The PostgreSQL checks verify historical daily-policy migration, atomic daily claims, Opal charge/replay, refunds, ownership recovery, and scoped recovery. Two stale test assumptions were repaired: current Holy Suit content must be seeded after the historical migration sequence reaches the current schema, and the current sealed Opal publication may retain later reviewed lineage suffixes. Business assertions remain intact.
- Native reset evidence is retained in `artifacts/wonderland-entry-rejection-20260911/`.

A single captured test25 entry is restored only after the stopped database backup. This is a scoped reset for continued development testing, not a claim that the most recent successful run deadlocked. Earned inventory, titles, loot receipts, other characters, and the normal three-entry policy are preserved.

Deployed image `sha256:598483becb2afdb06bc26009b412dc6a3ea3c4028260c07ec09eeb6083e669f0` started at `2026-09-11T09:14:17.5063462Z`. Tempest is healthy, with zero restarts/OOM and no runtime failure event at verification. Ports remain unchanged, and Dwargon remains stopped.

The exact captured reservation `bec2d4bf-2850-4988-9366-7b0adebaeb50` was reset after the full stopped backup. Live readback confirms two used entries and one available for test25. Owned-inventory fingerprints, item revision, policies, and migration head remain unchanged. The database backup's host/container SHA-256 digests match; temporary container backup/SQL files were removed. Backup receipt: `backup-sha256.json`; rollback image: `reborn-server:before-wonderland-entry-verification-20260911`.
