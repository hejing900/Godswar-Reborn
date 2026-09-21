# Wonderland controls, travel and presentation — 12 September 2026

Wonderland completion and termination announcements now wait until every session has left the exact run and connected participants have finished loading their destination. Final title settlement remains required. The five-minute treasure countdown still begins at completion. A small pending notice survives empty runtime retirement, so loading the capital cannot swallow the announcement; publication remains once per run, scoped to the same realm and participating factions.

The announcement regression drives two completed party runs, delays final title persistence, replays settlement, exits members separately and checks both sides of destination readiness. It also exercises solo termination and timeout through retirement and verifies that later ticks do not duplicate the notice.

The native title formatter supplies one pair of brackets for overhead and character title display. Title catalogue names remain plain within their color markup, so the selection list has no brackets. The change uses the existing formatter hooks and width helper, with a transactional executable and locale backup. It does not change title selection or ownership.

Locked treasure claims emit a text message through the same native personal-log destination used by daily rewards. They do not send a result dialogue or notification box. Successful acquisitions retain their existing item notifications and authoritative inventory reconciliation.

Ordinary runtime stuns and freezes join the movement gate already used for Wonderland and Medusa restrictions. Stun wins over simultaneous silence. Blocked legacy movement receives an authoritative idle-position correction; queued realtime movement is rechecked after cast interruption, before its final position commit. Silence by itself still permits movement.

Transporters use the requested coordinates:

| Island | X | Z |
| --- | ---: | ---: |
| 3 | -152 | -102 |
| 4 | -170 | 87 |
| 5 | -81 | 143 |
| 6 | 192 | 147 |

All four points are walkable on their respective native island components. Two optional island 4 support spawns move from (-176,81) to (-178,79), and from (-166,81) to (-164,78), to preserve the transporter's ten-unit safe zone.

Island 6 ground fire uses the native coordinate-capable Flame Blast visual (570), with the actual platinum dragon admitted as its source. Each scheduled circle publishes its detonation even when no player is hit. The damage remains the existing ability; player hit feedback does not duplicate the ground effect. The hazard retains its existing lifetime while the dragon is alive and the run active, and source visibility does not change corpse loot.

Validation and deployment evidence is recorded under `artifacts/wonderland-ui-controls-20260912`:

- Final Release build: zero warnings and errors; 39 protocol checks passed, zero failed or skipped. New title patch fixtures: 6 passed; existing palette fixtures: 12 passed; Medusa patch compatibility fixture and installed readbacks passed.
- Tempest deployed at 2026-09-12 07:09:55 UTC (19:09:55 NZST), image `sha256:f5767cd9a40ddf7dd8f355354869fc3760327ff9ac9a096c6355b69664fd899a`. Healthy, zero restarts, no OOM; startup reports ready on the existing login/game bindings. Dwargon remains stopped.
- Item definitions, upgrade policies, schema and owned-inventory fingerprints match the stopped pre-deployment snapshot. No entry attempts were reset.
- Database backup: `artifacts/wonderland-ui-controls-20260912/before-deploy-database.dump`, verified SHA256 `37e00b628d5905761e88acf418184aedf5b555189320dc5bdc636a6c36fdaee0`. Rollback image: `reborn-server:before-wonderland-ui-controls-20260912`.
- Installed `Origin.exe` SHA256: `3461A256334D00352A7A0C274A876FB223A0F32B8CE4A3EF9C5D478F7FFF8CF8`. Client backup manifest: `C:\Godswar Origin\backups\title-display-brackets\20260912-065853-553dd9be3ae64c19b7b6b0d19c256eb9\manifest.json`.

The client was closed for the transactional patch. Native disassembly, packet fixtures and installed-byte readbacks verify the presentation paths; this release does not claim an interactive in-game visual test. Reopen the client to load the title formatter change.
