# External Wonderland capture, 11 September 2026

This document records the investigation before implementation. The subsequent
changes and release verification are tracked in
[the external-match release note](wonderland-external-match-20260911.md).

The new capture confirms that Alpha Demon's Treasure is a fixed NPC at
**(173.600006, -153)**, present before Alpha Demon dies. It is separate from
the boss's dropped sacks. The earlier suggestion that this coordinate might
identify the Chest Guard was incorrect for the external server.

The most significant protocol difference is opcode 10027. The external
server sends boss loot immediately and sends 10027 about twenty seconds
later. Our Wonderland path sends 10027 immediately, including an additional
copy before presenting corpse loot. Native client inspection confirms that
the non-player monster branch of 10027 clears loot slots. Its local-player
branch is separate; this evidence does not invalidate the Wonderland player
death/revival fix.

## Source and scope

- Source: `C:\Users\Iamc1\Downloads\GodsWar Private Server\GodsWar Private Server\PacketCaptures\external-20260907-194130-562.log`.
- Size: 4,230,255 bytes.
- SHA-256: `cfdc5025ac07b42a198bb06716ed291ee97c36f7b6266cd979508e69329dde73`.
- The filename retains September 7, but the Wonderland traffic is September
  11, approximately 16:14:44 through 16:24:38 at UTC+12.
- Reassembled 13,412 game frames with no unfinished directional bytes.
  Login/authentication frames were not exported into the analysis artifacts.
- The observed route enters island 1, revives there twice, advances to island
  2, then reaches island 3. This capture does not establish islands 4–8 or
  final completion behavior.
- External appearance packets are 104 bytes. Their object ID, position and
  template offsets match the existing layout; requiring 108 bytes would
  incorrectly discard these appearances during research.

## Boss loot and fixed treasure

| Event | Capture time (UTC+12) | Evidence |
|---|---|---|
| Island 1 chest appears | 16:14:56.230 | Frame 1797, opcode 10020, object 5212, `gwprivate_Fane_008_Male15`, (173.600006, -153) |
| Alpha Demon appears | 16:14:57.918 | Frame 1838, object 22521, `gwprivate_B_boss_xerxer_001`, (171.267, -151.701) |
| Final observed Alpha damage | 16:20:21.918 | Frame 7136, opcode 10045, target 22521 |
| Alpha loot becomes available | 16:20:21.918 | Frame 7148, opcode 10029, same object 22521 |
| Alpha receives 10027 | 16:20:41.917 | Frame 7494, same object, 19.999 seconds after loot |
| Island 1 chest is opened | 16:20:49.438 | Frame 7645, client opcode 10067, object 5212 |
| Island 1 reward action | 16:20:50.567 | Frame 7671, client opcode 10069, function 58 |
| Island 2 boss loot | 16:23:30.182 | Frame 11769, object 21471, dryad boss, two item 4451 sack entries |
| Island 2 reward action | 16:23:42.483 | Frame 11992, object 5213, function 58 |
| Island 2 boss receives 10027 | 16:23:50.159 | Frame 12140, 19.978 seconds after loot |

Alpha's five loot slots contain two separate Alpha Demon's Sack entries
(4450, quantity 1 each), plus 4033, 4002 and 4030, quantity 1 each. There is
no separate treasure actor spawned by the Alpha kill. The sack is attached
to the existing boss object. This recording contains no opcode 10048 pickup
request or acknowledgment, so it does not prove that the player collected
either boss's corpse loot.

The first external sack's entire 72-byte item body is identical to our
`PacketBuilder.MonsterLoot` encoding, including five `FFFFFFFF` sentinels and
packed item flags/quantity `01010001`. The discrepancy is lifecycle/order,
not that item-body format. Two external sacks do not establish a requested
change to our configured one-sack-per-boss-per-character reward rule.

## Native monster loot clearing

Installed `Origin.exe` SHA-256:
`3d9715424f94f05c852ae691d446d52a9f51732d0a94112438f7cacc45581447`.

At the opcode 10027 non-local branch `0x4DED9B`, an object ID above 9999
enters `0x485220`. This iterates eight item slots at actor `+0x638` with
stride `0xF8`, clears them through `0x434F30`, and resets actor `+0xDF8`.
This proves loot clearing; it does not by itself prove scene-object removal.
The local-player path is reached earlier at `0x4DEAB1` / `0x4DEABD`.

Current server sends originate from `SendMonsterDeathProgressionAsync` and
`SendWonderlandBossLootPresentationAsync`. An immediate progression 10027
arriving after independently scheduled loot can clear that loot. The extra
10027 in corpse presentation is also inconsistent with the captured
sequence. Client-visible behavior still requires verification after a fix;
this read-only investigation did not change or deploy gameplay code.

## Treasure interaction and positions

The external server advertises native function 58 for `Fane_008` and
`Fane_009`: open 10067, page request 10068, explicit reward action 10069,
then response 10070. Our current code instead grants gems during the initial
10067 click and opens only a description dialog with no reward function.

The observed positions are:

| Object | External position (X, Z) |
|---|---|
| Alpha Demon's Treasure, Fane_008 | (173.600006, -153) |
| Island 2 treasure, Fane_009 | (23.6, -151) |
| Island 3 treasure, Fane_010 | (-113.599998, -129) |
| Island 1 transporter, Fane_001 | (153, -125) |
| Island 2 transporter, Fane_002 | (-5, -168.5) |
| Blackmarket Teleporter, Fane_017 | (165, -219) |

Our authored island 1 treasure is currently at (188, -162). The external
coordinates above are evidence for matching placement. Do not infer later
island positions from this partial run.

The external client's `NpcFunFane.lua` decodes the function-58 response into
reward text: encoded values 41001/14002 on island 1 and 12001/50002 on
island 2 represent EXP-pill and restricted Morning Dew quantities, with a
static Level 4 Sapphire Piece string. These are client display semantics,
not independently verified inventory grants. They do not replace the user's
confirmed custom treasure reward: four Grade IV gems, independently random
Sapphire or Emerald.

Artifacts, decoders and source-line/frame references are in
`artifacts/wonderland-external-20260911/`. No capture helper, external client,
database, running instance, reward balance or server deployment was changed.
