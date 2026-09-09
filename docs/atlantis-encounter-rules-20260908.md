# Atlantis encounter rules

The four requested rules are copied from the [Atlantis Portal guide](https://godswar.online/node/121):

| Rule | Value |
| --- | --- |
| Party size | 1â€“5 players, including solo entry |
| Duration | 40 minutes |
| Kill points | Normal 1, elite 10, boss 50 |
| Completion | At least 850 shared team points before the deadline |

Each exact map-205 dungeon owns its clock and score. The clock starts after entry payment, immediately before the leader's transfer. The native scene-224 panel shows the remaining time, party roster, and team score. Completion and timeout freeze the result. A kill at the deadline cannot complete the run.

Scoring uses the published monster rank and the original instance, object ID, and spawn generation. It runs on an explicit committed reward receipt, before claimant ownership revalidation or pet projection, and counts replayed death receipts only once. A disconnect after commit cannot lose the remaining party's point; ownership guards still apply to the claimant's response.

Atlantis admits players at level 90 or above, with no upper entry limit. Daily allowances, Opal payments, and other dungeons retain their existing rules. Dialogue release V23 updates the two capital Instance Caller descriptions to say Level 90+; historical sealed releases remain intact.

The admitted leader can terminate unfinished Atlantis using either native instance control. Termination freezes scoring and combat, then returns remaining members to their faction capital through authoritative transfers. A member who teleports out has their Atlantis panel cleared; the remaining party can continue. When the last member leaves or disconnects, an unfinished run is cancelled and its empty runtime is retired on the next world tick. Failed transfers retain membership and the panel. Preparing an empty instance before its first admission does not count as abandonment. Completed runs retain pending reward settlement before retirement.

Native teardown uses opcode 10231 with zero seconds (`08 00 F7 27 00 00 00 00`). The installed `Origin.exe` handler at `0x004BEE9F` hides RepQueUI, clears repetition state and its roster, and resets the leader flag. A state-zero opcode-10232 sync creates a pending icon instead. An empty opcode-10218 roster must not be sent: its native handler at `0x004B5000` still reads a first member when count is zero.

The stock client also owns a separate description token, `NF_L0_R208`. After copying stock localization into the client, run `tools/PatchClientAtlantisLevel90Plus.ps1 -Mode Apply -ClientRoot 'C:\Godswar Origin'`, then `-Mode Verify`. This small installer overlay backs up the installed resource and changes only its `90-140` fragment to `90+`, preserving its encoding and every other byte. The large original localization resource stays intact in the repository.

## Approved monster roster

This is an authored roster approved by the user, not a recovered original-server wave sequence. Each stage has four groups of five of each normal species and two elites, followed by one boss. A group must have all twelve kills successfully settled before the next group can appear. Bosses unlock after the fourth group.

| Stage | Normal species (20 each) | Elite species (8) | Boss (1) |
| --- | --- | --- | --- |
| 1 | Mudskipper, Crab Eating Frog | Mudskipper | Dinna |
| 2 | Fiery Turtle, Deep Sea Spider | Shoal Crocodile | 3-headed Sea Serpent |
| 3 | Skeletal Swordsman, Evil Spirit | Evil Spirit | Raging Spirit |
| 4 | Defensive Witch, Bewitching Mage | Bewitching Mage | Prophet |
| 5 | Mudskipper, Evil Spirit | Defensive Witch | Dinna the Sea Guard |

There are 25 groups/boss encounters, 245 monsters, and exactly 850 points: 200 normal kills + 40 elite kills Ã— 10 + 5 boss kills Ã— 50. Dinna the Sea Guard unlocks at 800 points. Monsters never respawn or reuse a death identity during the run. Mermaid capture spawns are not part of this roster.

Groups appear around the requested center (-74,31), connected to entrance (171,24). The twelve positions use X=-78/-74/-70 and Z=25/29/33/37, with four-unit spacing and at least 3.20 units of clearance from blocked terrain. Atlantis alone uses two-unit idle roaming, a 112-unit aggro radius and a 128-unit pursuit boundary. The center-to-player distance at (19,53) is `sqrt(93^2 + 22^2) = 95.5667306`; the farthest member is 100.961 units away before roaming. Both monster engines use these limits, while other maps retain their existing settings.

The installed Atlantis HMP and all selected models/textures were verified; reproducible placement and connectivity evidence is in `artifacts/atlantis-grouping-20260908/`. Spawn Y=0 is within 0.02 units of the rendered ground at the new positions. Monster appearance packets must include content map 205 in the high word at offset 6; the native client rejects packets with another map before creating the monster. Empty completed, timed-out or cancelled runs release their runtime and placement slot.

Two separate passive pets spawn once per run: Mermaid at (-59,88), object 42245, and Siren at (-54,-7), object 42246. Their existing published templates represent female and male Merman pets. A successful capture with net 10084 grants the existing Merman egg 10158 at authored quality 1. Neither pet belongs to a combat wave or contributes points, and neither respawns. Medusa pet capture retains its existing eligibility, protocol and rarity rules.

The second playtest exposed an invalid test-fixture Talent EXP value of 2147483647 in a field that must remain 0..99. All twelve reward transactions failed validation, so the score correctly stayed zero and the next wave remained locked. The fixture now uses 99. Talent rewards saturate at the representable point/remainder ceiling and report only the credited EXP, allowing the surrounding death settlement to commit. Fixing test25's invalid remainder preserves its current Talent Points rather than converting the fixture sentinel into new points. A cleared group contributes 30 points (ten normal plus two elite kills); its twelve committed deaths unlock the next group.

## Initial balance

Monster level is the highest level in the party snapshot taken for admission. The authored level-90 solo HP baselines are 15,000 normal, 75,000 elite, and 500,000 boss. HP scales by `(highest level / 90)Â²`, by an additional 5% per stage after the first, and by an additional 50% per party member after the first. Damage and defence retain the existing published monster combat profile. Counts and points stay identical for 1â€“5 players.

These are initial Reborn balance values. Neither the installed client nor the published spawn data supplies original Atlantis HP. The proposed 30â€“35-minute clear time requires gameplay testing and is not a measured result.

The initial rule/dialogue change passed nine focused checks in Debug and Release, plus all 56 required disposable PostgreSQL checks and six migration scenarios through migration 143. A separate upgrade check passed for both V21 publication identities, preserving sealed rows and proving V22 publication is idempotent. The subsequent monster-wave change does not modify the database schema or sealed publication.

The complete wave implementation passed 20 focused checks in both Debug and Release with no failures or skips; both solution builds completed without warnings or errors. Coverage includes all 245 kills in Legacy and ECS runtimes, stationary-player wave visibility, the final 800-to-850-point transition, duplicate receipts, timeout ordering, and empty terminal instance retirement. The real PostgreSQL 17 exactly-once reward check also passed without skips, including rollback, changed ownership after commit, and duplicate replay. Its disposable container and volume were removed and verified. Reports are in `artifacts/atlantis-waves-20260908/`.

Deployed to `godswar-dev-tempest-openworld-01` on 2026-09-08 (New Zealand time), image `sha256:038cc121aa53505671525ffd2890292ee399650de917b54cc9ebe1e6e22cabc7`. Startup reached healthy with zero restarts; the live development-isolation check passed. The previous image is retained as `reborn-server:before-atlantis-waves-20260908`. In-game difficulty and client presentation still require a fresh Atlantis playtest.

The later level-90+ update is deployed as image `sha256:83f976d608870e32b5f8b66ac3e386a7a63c10eaf661a5e79b7ab175aff0cc06`, with V23 dialogue release `2533BF0747E36F8EC83C0D5D06A54BF49574C5EFE126AB7AA2A6C841B0B23665`. All 20 focused checks pass in Debug and Release, including level-141/160 solo and five-player entry with live first-wave spawning; level 89 is rejected. Both PostgreSQL publication/upgrade checks pass without skips, preserving V21/V22 sealed data. The server reached healthy after seven coordination startup retries, and live isolation passed. The stock-client level label is patched and verified. Backup and deployment evidence are in `artifacts/atlantis-level90plus-20260908/`.

The subsequent playtest fixes are deployed as image `sha256:aa325e1acd59cc06ede8eaf77063e4290a5e8eff7afc635bb957fca8908dd828`. Corrected appearance map fields, native termination, committed departure cleanup and delayed UI fencing pass all 28 focused checks in Debug and Release, with no skips. Both builds have zero warnings/errors. The development server reached healthy with zero restarts and passed live isolation; sampled usage was 2.58% CPU and 131 MiB. The prior image is retained as `reborn-server:before-atlantis-playtest-fixes-20260908`. Evidence is in `artifacts/atlantis-playtest-fixes-20260908/`; a new in-game playtest remains necessary to confirm presentation.

The scoring, pet and aggro update is deployed as image `sha256:29cd44e68812bb352ad663988b55a9cae6983b5c341ce31c295972a6da5fa2c7`. All 35 focused checks pass in Debug and Release, including every group member acquiring the requested distant target and attacking. Long pursuit exposed inconsistent float tolerances between arrival and attack eligibility; both engines now use the existing 0.0001-unit arrival tolerance for both decisions. Three disposable PostgreSQL checks pass: full-group reward commits/wave progression at capped Talent Points, atomic Merman capture/replay/rollback, and unchanged Medusa rarity. The temporary database container and volume were removed. No schema or content publication changed.

After a validated backup, the development server was stopped and test25's observed invalid Talent EXP was corrected to remainder 47 with a compare-and-swap update. Its existing 2143127489 Talent Points were preserved; progression revision advanced from 0 to 1. Startup reached healthy with zero retries, and live isolation passed. The prior image is `reborn-server:before-atlantis-score-pets-aggro-20260908`; backup, repair, test and deployment evidence is in `artifacts/atlantis-score-pets-aggro-20260908/`. A fresh in-game run is needed after the restart.

## Completion rewards and return countdown

Completing 850 points within 40 minutes awards 2,800 HardPoints to each eligible finisher. This follows the published [Atlantis guide](https://godswar.online/node/121) and its [reward table](https://godsarena.online/sites/default/files/guide_images/Screenshot_14.png). The complete 850-point row is identical for solo and party; no undocumented time multiplier is added. Partial-score termination/timeout payouts are outside this completion change.

An actual solo admission earns native title 5014, **Deep Sea Hunter**. A party admission earns 5013, **Seabed Explorer**. These stock names are present in the installed client's DesigName.dat and Atlantis completion notification strings. Successful completion announces the solo player or party to the realm. The existing native title list, selected title and HardPoints display are refreshed.

The native Terminate control changes to the same completion state and 30-second countdown used by Medusa. The countdown is anchored to the final committed kill; opening the panel late does not restart it. The world owner stops encounter combat, then members return to their faction capital when the delay expires. Completion control requests cannot bypass pending rewards. Failed database writes or transfers retry while the source runtime remains available.

Eligibility is frozen from authoritative instance membership when the score reaches 850. A player who leaves before completion receives no completion reward; a disconnect or teleport afterwards does not erase an earned reward. The title classification uses the original successfully admitted roster, so a party reduced to one player still earns the party title. Reservation identity, realm, admitted roster, eligible account/character identities, timestamps and score are bound to the durable settlement. Replaying one instance or its admission reservation cannot pay twice. HardPoints use the existing shared wallet and revision; Atlantis title ownership has separate durable provenance and is loaded alongside Medusa titles.

Completion update verification:40 focused checks pass in both Debug and Release with no skips; both solution builds have zero warnings/errors. The new PostgreSQL completion check covers solo/party awards, original-party eligibility, concurrent/restarted replay, invalid evidence, rollback, overflow and title rehydration. Schema release checks pass from an empty database and from a restored backup of the live143-migration database, including repeated initialization. The final head is144 (`20260908_143_atlantis_completion_rewards`).

Deployed on2026-09-08 at21:50 New Zealand time, image `sha256:ce009967efe82623d7b4fe497d5c387cdb530a12b296ed035b7ea556af9f750a`. The server is healthy with zero restarts and the live isolation check passes. The previous image is retained as `reborn-server:before-atlantis-completion-20260908`; the verified database backup and all reports are in `artifacts/atlantis-completion-20260908/`. The disposable PostgreSQL container, volume and temporary credential were removed and verified. Native visual presentation still needs the next in-game completion playtest.
