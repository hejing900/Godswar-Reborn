# Wonderland chest interaction

An in-range, living player's click on an island treasure chest now opens the native NPC description window and then reports the existing claim result. A locked chest opens its description but cannot grant its reward. The claim transaction, entitlements, and reward selection are unchanged by this UI correction.

The previous handler accepted the native 48-byte opcode 10067 click but replied only with a server note. It omitted the opcode 10067 acknowledgment used to open the NPC window. The corrected acknowledgment carries the chest's own object ID and original `Fane_008` through `Fane_016` description key, with zero function flags. It advertises no shop, exchange, or additional reward action. Dead, distant, non-finite-position, malformed, and unowned clicks do not open the window.

Read-only inspection of installed `Origin.exe` (SHA-256 `3d9715424f94f05c852ae691d446d52a9f51732d0a94112438f7cacc45581447`) confirms:

- The NPC click branch emits length 48/opcode 10067 at `0x47DD59` and `0x47DD63` after the normal NPC identity and distance checks.
- The opcode 10067 receive branch at `0x4E0AE2` reads the description key at wire `+16`, resolves its text at `0x4E0B04`–`0x4E0B0A`, resolves the NPC object, and opens the native NPC UI through `0x5ACE90` and `0x5AE370`.
- Both installed locales have all nine original chest description keys in `Text/NPCDescription.dat`. The English text describes defeating the boss for the guarded treasure, so no new client text or asset is needed.

The native interaction dispatcher also rejects logical actor state 4 at `0x47DBD0`–`0x47DBDB`. This is not proof that the reported lying-down animation caused the chest issue: the native scene reset can store logical state 0 while selecting the death animation because HP arrived late. The separate revival correction fixes that proven packet-order problem. The chest change fixes the independently observed missing dialog acknowledgment; an installed-client click playtest remains necessary to confirm the complete mesh selection path.

The existing check `Wonderland native treasure chests require settled island clears, proximity, and exact admitted ownership` now verifies the exact native acknowledgment before the claim result on all eight islands, description access while locked, and no window or claim for dead, distant, non-finite, or malformed clicks. Integrated build/test results belong to the release report. Native excerpts and locale evidence are retained under `artifacts/wonderland-revive-pose-20260911/`.
