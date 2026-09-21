# Wonderland treasure opening and island transporters

Successful island treasure claims and boss-sack openings now update the bag without a confirmation dialogue, including replayed successful claims. Chest success no longer sends either ServerNote or the native function58 result response. The native extended-function click already closes the original claim menu, so no replacement close packet is needed. The initial claim button and useful failure messages remain available. Grants, current-inventory projection, consumed-slot clearing, ownership checks and durable replay behavior are unchanged.

The reported third-island transporter was published by the server but positioned at the remote authored combat exit (-126,-99). Test25 reached island3 at (-68,-125), where two NPCs were streamed, and then walked to (-96.13,-128.53) before killing the Flame Rooster. There was no transporter click. The transporter model is identical to the working first two. Its new location is beside the treasure, six units away and inside the eight-unit interaction radius.

## Transporter locations

The first two coordinates are preserved from external capture. Later coordinates are authored placements checked against the installed Fane walkable block table; they are not claimed as external-server observations. Combat safe-zone and arrival anchors are unchanged.

| Island | NPC | Position | Action |
|---|---|---|---|
| 1 | Isle-to-Isle Teleporter | 153, -125 | Island2 after the required clear |
| 2 | Isle-to-Isle Teleporter | -5, -168.5 | Island3 after the required clear |
| 3 | Isle-to-Isle Teleporter | -107.6, -129 | Island4 after the required clear |
| 4 | Isle-to-Isle Teleporter | -164, 67 | Island5 after the required clear |
| 5 | Isle-to-Isle Teleporter | -96, 184 | Island6 after the required clear |
| 6 | Isle-to-Isle Teleporter | 172, 126.75 | Island7 after the required clear |
| 7 | Isle-to-Isle Teleporter | 210, 27 | Island8 after the required clear |
| 8 | Returning Helper | 62, -101 | The clicking player's faction capital after completion and reward settlement |

The entrance Blackmarket Teleporter remains at165,-219 with its existing menu and furthest-unlocked-island behavior. All transporters require an explicit native Teleport action; walking near a chest or NPC does not teleport the player.

The final helper uses existing native identity `Lelantine_Farm_005`, template `Lelantine_Farm_005_WarField1`, and distinct object5720. Its description already refers to returning to the main city. Its NPC appearance still carries Wonderland map207. The model, assembled avatar parts and referenced textures were checked in the installed client; no client patch is needed. See `artifacts/wonderland-transporter-audit-20260911/README.md` and its hash manifests for native dialogue, model, texture and terrain evidence.

## Final exit authority

The final service requires the exact current living admitted player, completed island8, a settled final title and no pending titles. It returns only the clicking player through the existing authoritative instance transition; other party members retain their completed run and treasure window.

A voluntary exit additionally carries `RequiredLivingLifeRevision`. It is checked before persistence and again inside the registry membership mutation immediately before transfer. Death or death followed by revival during the destination checkpoint rejects that exit and uses the existing source-position checkpoint compensation. The nullable fence defaults to absent for ordinary forced egress, preserving the earlier fix that permits dead players to leave an expired instance and revive in the city. No new locks were added. Independent review verified the commit check closes the asynchronous gap.

Native function57/sub107 is a medal result, so the final helper does not reuse it as a fabricated island8 rejection. A locked final exit gives a short centered explanation after validating the current owner.

## Verification and release

Focused checks exercise quiet native and secure sack use/replay, chest claim/retry/replay, all eight visible and clickable NPCs, seven gated next-island hops, final reward settlement and per-player exit, death during checkpoint persistence, existing forced dead egress/revival, map transition readiness and rollback, instance completion/retirement and unchanged terminal announcements.

The coordinated Release build completed with zero warnings and zero errors. All 17 selected protocol checks passed, with no failures, skips or unmatched filters. Source and native assets were inspected; no installed-client playthrough was performed during this task. All changed production files remain below20KB.

Release artifacts are under `artifacts/wonderland-treasure-transporters-20260911`. Deployment preserves a stopped database backup and rollback image `reborn-server:before-wonderland-treasure-transporters-20260911`, and compares item publication, policies, schema and owned inventory before and after. This release does not reset attempt counters, change rewards, or modify client files. Only Tempest is recreated; Dwargon stays stopped. No commit or push was requested.

Deployed at11:20:27 UTC as image `sha256:c562d712c47fb4ef4eb143f1e8d20c12ee06590a2d227ff34b34d5d25c54f02d`. Tempest is healthy with zero restarts and no OOM; inspected startup logs show both listeners ready and no failures. Ports remain127.1.1.111:5998 and:7000. Item publication, policy and inventory fingerprints and migration head150 are unchanged. The stopped backup SHA-256 is `c56fdcac606aec77840d0a41574eef9df10205527b82b6b1e74ee877369865f0`, verified against the PostgreSQL copy before its temporary duplicate was removed.
