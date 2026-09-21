# Red centered boss warnings

Successful Wonderland corpse-loot collection now updates the authoritative bag and clears the claimant's loot slot without a confirmation dialogue. This also applies to replayed successful claims. Inventory-full and unavailable-loot errors still explain why a pickup failed; grant, inventory revision, owner validation and native loot acknowledgement ordering are unchanged.

Hostile boss windups now use a red centered warning naming the boss, skill and reaction time, for example `Capritaur Derskey is casting Trample in 1.2s!`. Each actual scheduled cast warns again. Cooldown polling produces no repeated warning. The one-time `ServerNote` tutorial and its per-session suppression set have been removed.

Warnings go to living, admitted players on the casting island in the exact instance, with current account, membership and life authority. Native cast visuals remain in place. Terrain fire, rapid Atlas support casts, Atlas death blasts and allied marshal cleaves retain visual cues without modal messages or repeated centered danger notices. Damage, skills, windups and cooldowns are unchanged.

`PacketBuilder.CenteredRedAnnouncement(message)` uses the installed client's existing centered proclamation path. It wraps plain text in `|cFFFF0000` (opaque red) and `|cFFFFFFFF` (white reset), then uses the unchanged 137-byte PythonNote packet: opcode 10038, formatter 50, channel 0, and two terminated 64-byte text fields. The new helper accepts at most 106 printable ASCII characters, reserving 20 bytes for the two color tokens. Embedded color overrides and control bytes are rejected.

The existing `CenteredAnnouncement` method and its 126-byte capacity remain unchanged, including completion announcements. No opcode, packet color field, dialogue window, client asset patch, or executable patch is introduced. Warnings are server-authored text using a verified native presentation contract; they are not claimed to be newly captured external packets.

## Native evidence

- The 10038 receiver at `0x4EDF79` reads type at wire 4, channel at wire 8, and strings at wire 9 and 73, then calls `0x4A79F0`.
- `0x4A7A5E` selects the Lua `Broadcastmsg` function. Its arguments are passed as strings, not interpolated executable Lua.
- Installed `Localization/en_us/UI/XML/SrvMsg.lua` line 54 maps `SrvMsg_NOTE_191` to 50. Lines 975–976 concatenate `name .. note`; therefore a field split does not truncate a color token or change the rendered message.
- Channel 0 selects `GameAPI:AddProclaimMessage_UTF8(strText,1)` at lines 1140–1141. That same script constructs ARGB color spans at lines 828, 835, 911, 960, 965, 969 and 1080 before reaching this same proclamation sink. Color support is established in the centered renderer's own script path, rather than inferred from an unrelated widget.

The executable SHA-256 is `3d9715424f94f05c852ae691d446d52a9f51732d0a94112438f7cacc45581447`; the inspected SrvMsg.lua SHA-256 is `4a6bafed84c12fc845c576a9189d06fb2a33ca066db41d61c263e7015ec06540`. Bounded disassembly and selected script lines are saved under `artifacts/wonderland-red-announcement-20260911`.

## Validation

The focused check is `Native red centered announcement framing and color`. It pins a literal 137-byte example independently of the builder, verifies maximum-length field reconstruction and both terminators, verifies default announcements remain byte-identical, and checks invalid text rejection. A separate Python framing calculation confirms the literal's 137-byte size and contents. Runtime integration tests cover warning scheduling and recipients separately. No build or installed-client playtest was performed by the packet-helper subtask.

The coordinated Release build completed with zero warnings and errors. All 14 selected protocol checks passed across the initial run and a test-only rerun. They cover successful corpse-loot/replay without a popup, both second-island boss warning texts, repeated casts, exact windup boundaries, current admitted recipients, quiet support/terrain/allied visuals, both combat engines, captured first-island effects, late target removal, existing status UI, terminal/completion announcements, and the earlier combat deadlock regressions.

The new timing fixture was corrected to use the scheduler's authored `TimeSpan` deadline, checking one tick before impact and the actual damage packet at the deadline. Its unadmitted-viewer setup now expects the existing admission guard to reject the join. No production timing or admission rule was loosened to make either test pass. The initial reports and successful rerun are retained separately, with a source-linked `validation-summary.json` under `artifacts/wonderland-boss-announcements-20260911`.

No persistence policy, item content, reward amount, or entry counter is changed by this release. Deployment uses a stopped database backup, a preserved rollback image (`reborn-server:before-wonderland-boss-announcements-20260911`), and publication/inventory verification. Only Tempest is recreated; Dwargon remains stopped. There was no commit or push.

Deployed at 10:52:17 UTC with image `sha256:1a92b4b1c553f5926f37c53cf3c5d2ee1a31551727bb5f7183362da49693c934`. Tempest is healthy, with zero restarts and no OOM; login/game listeners are ready and inspected startup logs contain no failures. Ports remain 127.1.1.111:5998 and :7000. Publication, policy and inventory fingerprints and migration head 150 are unchanged. Test25's current-day legacy and Medusa usage both remain zero. The stopped backup SHA-256, verified against the PostgreSQL copy, is `6c8c481b7eca5f74ba7345d3f2b5ee917755d7a0a9490de999a2297f160c05bb`.
