# Wonderland status icons, terminal announcements, and boss loot

The encounter's combat buffs and debuffs belong in the native status strip. Island clears continue to update the instance panel and earned-title list without notification boxes. Wonderland's centered, faction-scoped announcer is reserved for a finished or ended run.

## Combat status display

The normal full `10167` status snapshot combines Wonderland's encounter timers with existing class statuses, including Sacred Zeal. The encounter remains responsible for gameplay effects; the new client entries apply no additional stat modifiers.

| Status | Client ID | Duration |
| --- | --- | --- |
| Petbird Blessing | 1510 | 15 seconds |
| Putrid Bird Blessing | 1511 | 15 seconds |
| Wonderland Stun | 1512 | 2 seconds |
| Wonderland Silence | 1513 | 2 seconds |
| Spear Blast: Weakened Armor | 1514 | 8 seconds |
| Armor Rend | 1515 | 10 seconds |

The six definitions use existing native status-atlas icons and unique kinds. `Effect=-1`, `Values=0`, and `EffectDisplay=-1` prevent client-side stat or visual-effect duplication. The guarded installer preserves UTF-16LE files and installs matching English and Chinese entries. It checks that the client is closed, verifies exact backups/readback, and rolls back a failed multi-file write.

Client install evidence: `artifacts/wonderland-status-20260911/client-status-install.json`; nine hermetic checks, including server-ID parity and rollback, passed. The exact before-images are in `C:\Godswar Origin\backups\wonderland-status\20260911-073828-f6b317b16d9646e8968662025b1bdddf\manifest.json`.

## Announcements

- Removed the entry/island-clear `ServerNote` and milestone-title `ServerNote`. Durable per-island title ownership and the selected title remain unchanged.
- Successful eighth-island completion retains the existing settlement gate before the centered announcement. Replayed settlements cannot publish again.
- Explicit leader termination captures the terminal message before egress. Time expiry also publishes the actual completed-island count. Neither message claims completion or awards unfinished titles.
- The existing exact-session, realm, and faction recipient checks apply to both terminal paths. A failed member exit may retry without repeating the announcement.

## Apparent duplicate Flamingo sack

Read-only live evidence showed character 7005 owned one Flamingo sack (4452), with one boss 46300 receipt and one inventory-ledger add. The second visible sack was a native inventory projection error.

The local-player `10050` pickup acknowledgment inserts an item into a client-selected free slot. The server then sent the durable inventory through `10033`. Native `10033` skips empty records, so it cannot remove the first item if the client selected a different slot from the database. `10056` updates quick-equip metadata; it does not clear inventory slots.

The handler now projects the durable inventory once and uses the existing bag-neutral corpse-clear sequence (`10029` followed by a player-zero `10050`). The neutral acknowledgment clears the loot slot, window, and sparkle without adding a second bag item. Reconnect clears a ghost left by the previous implementation; no real item is removed or compensated.

The regression models the audited native branches with differing free slots on multiple bag pages. It reproduces the old extra item and checks actual handler packets, durable binding, replay, and loot-count safety.

## Release evidence

Validation and deployment artifacts are stored under `artifacts/wonderland-status-loot-20260911/`.

- Release build: zero warnings and errors.
- 52 distinct protocol checks passed, plus five isolated PostgreSQL checks and nine client patch checks, with no skips. `validation-summary.json` maps each final result to its report. The last status rerun corrected a test that reused an attack event ID; production correctly rejected that duplicate.
- Status regressions cover all four Legacy/ECS engine combinations, class-buff composition, timer refresh/expiry, life/account replacement, query-before-pump clearing, late clearing after a successful write, and delayed viewer admission. No client status is applied as a second gameplay modifier.
- Tempest image: `sha256:aca0c61faa8f1bdd3315261fd668d42d58722e1e7a62c3ff0c173136933ce77b`, started `2026-09-11T07:48:29.5309374Z`, healthy with zero restarts and no startup/runtime failure events at verification.
- Item publication remains `A45EA650680C8EA4D5D2FCAA831E97EEEF652BAB55351D860BFB95330FA97EB1` (1,787 entries). Migration count/head remains 150 / `20260911_149_wonderland_boss_loot_claims`.
- Owned-inventory fingerprints match before and after deployment. Ports remain `127.1.1.111:5998` and `127.1.1.111:7000`; Dwargon remains stopped. No daily attempts were edited.
- Full stopped database backup: `before-deploy-database.dump`, 78,514,384 bytes, with digest in `backup-sha256.json`. Previous image retained as `reborn-server:before-wonderland-status-loot-20260911`.

The client must be reopened to load its installed status entries and discard any old display-only sack. Packet and native-definition checks passed; no GUI playthrough is claimed.
