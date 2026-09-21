# Wonderland native death and revival audit

Wonderland now sends the installed client's death notification instead of loading a scene when a player dies. Its free revival request returns the admitted player to their physical island entrance in the same run, with the existing ten-percent HP/MP recovery. The first landing is `(169,-216)`. The first forward transporter is at the captured `(153,-125)`, and the entrance Blackmarket actor is at `(165,-219)`; both require a deliberate native dialogue action. See the [transporter audit](wonderland-transporters-20260911.md). Other maps retain their existing packet handling.

### Revival animation correction

The first deployment restored server life but sent the scene reset before the client received the restored HP. An installed-client playtest then showed the revived character still lying down. The correction sends the existing sixteen-byte `MSG_RESUNE` (10097) with restored local HP/MP immediately before the revival scene change, after the same-map relocation is durable and the player has been hidden from the source scene. It uses no invented animation flag or binary patch. Ordinary teleporters do not send this extra frame.

The native causal chain is explicit:

- The 10097 receiver at `0x4ECC43` resolves wire object ID `+4`, copies HP at wire `+8` into actor `+0x2BC`, and MP at wire `+12` into actor `+0x2C0` (`0x4ECC7E`–`0x4ECC87`).
- Scene-change receiver `0x4EBA08` calls `0x46B1B0`. That routine retains the local actor (`0x46B219`–`0x46B222`), clears the rest of the scene, and requests local `SetState(0)` at `0x46B825`–`0x46B84D`.
- `SetState` at `0x490C80` checks current HP at `0x490CDE`. If it is zero, `0x490CF5` substitutes animation state 4; otherwise state 0 reaches the `%s_stand_01` branch at `0x490D0C`. Thus the restored vitals must precede the scene frame. Sending a positive HP snapshot later does not repeat that animation choice.

Observers continue to receive removal of the old world avatar, followed by a fresh avatar with restored HP only after scene readiness. They do not receive the local identity's revival preparation. The focused handler regression asserts this observer lifecycle, exact HP/MP payload, and preparation-before-scene ordering, alongside invalid/repeated request rejection and preservation of the run. Bounded disassembly evidence is retained in `artifacts/wonderland-revive-pose-20260911/`. Integrated build and test results are reported with the release; the revised ordering still needs an installed-client death/revive playtest.

## Native evidence

Read-only analysis used `C:\Godswar Origin\Origin.exe`, SHA-256 `3d9715424f94f05c852ae691d446d52a9f51732d0a94112438f7cacc45581447`. Addresses below refer to that installed executable. No client binary patch is needed. The ignored `artifacts/wonderland-entry-revive-20260911` directory retains bounded disassembly excerpts; `artifacts/vendor-visibility-20260911/inspect-native.py` regenerates them using pefile and Capstone.

The incoming dispatcher loads the opcode at `0x4DE894`, subtracts 10015 at `0x4DE89E`, then uses selector bytes at `0x4E3FD8` and targets at `0x4E3E2C`. Opcode 10027 selects branch 3, address `0x4DEA61`.

| Native path | Evidence | Server behavior |
|---|---|---|
| Death, 10027 / `0x272B` | `0x4DEA65` logs `MSG_DEAD ID=%d`; local-object branch `0x4DEAB1` calls `0x5ECBD0` to open `Revive_Init()` | Send the full 116-byte native death frame on map 207 |
| Scene change, 10018 / `0x2722` | `0x4EB9B2` logs `MSG_SCENE_CHANGE`; local-object match at `0x4EB9E5` reaches scene loading at `0x4EBA08` | Use only for the actual Wonderland relocation after successful revival or portal travel |
| Free revival, 10028 / `0x272C` | Sender `0x5ECD50` writes opcode at `0x5ECD64`, length 12 at `0x5ECD6B`, local object at wire +4, selected type at +8, then sends at `0x5ECD93` | Accept on map 207 alongside the preserved historical opcode 10019 |
| Revival timer | `TimeStart` callback `0x5AA0E0` initializes ten seconds; timer path `0x5ECC90` calls the sender at `0x5ECCD1` | Accept the native request when it arrives; server ownership, dead state and supported type remain authoritative |

The native receive functions see a four-byte internal prefix before the wire frame, so native structure offsets are four bytes greater than the wire offsets below.

The death frame carries dead object ID at +4, five optional reward recipients at +8 through +24, reward arrays through +104, killer object at +108 and prestige at +112. All five recipients are `-1`: native `0x4DEC9A` loops those slots and skips `-1` at `0x4DECA4`. The arrays and prestige are zero, and the unspecified killer is `-1`. This opens the local death UI without treating the player as a monster-reward recipient or overwriting experience/talent totals. Other nearby players receive the same native death message with the world object ID.

The parser requires exactly twelve declared and actual bytes, and the handler retains the local-object check, dead-player check, current life authority and free type `2`. Types `0` and `1` remain unsupported. The new opcode dispatch is restricted to Wonderland; other maps do not acquire a new revival path. Successful revival advances life once and uses the existing same-instance scene transition. It does not reset admission, daily claims, enemies, progression or the forty-minute run clock. The existing five-minute completion treasure window and physical-island revival rules remain shared.

## Observed live sequence and remaining uncertainty

Tempest logs on September 11 (UTC) show AresTempest entering run `f00d1a077ece484da2625e80452693fb` at `02:21:34.102`. Chest guard 46104 delivered the lethal 20,660 damage hit at `02:27:41.813406`, leaving `0/221380` HP. `ClientReady` followed at `02:27:42.382263`, approximately 0.57 seconds later. This is consistent with the proven wrong scene-change death packet, rather than the native revival window.

The actual city transfer occurred at `02:28:10.450577`, after about six minutes and thirty-six seconds in the instance. That excludes the forty-minute timeout. The first boss remained alive, excluding completion. The historical log does not contain the exact incoming termination action, and no corresponding live packet capture was available, so it cannot establish whether the later exit followed a deliberate user action or another UI path.

Native termination sender `0x4B5490` builds opcode 10221, and the inspected caller at `0x5EB4EB` is inside an instance UI click handler. This audit found no proof of an automatic death-to-termination call. The server therefore preserves valid leader termination and adds explicit accepted-termination, revival and terminal-egress reason logs for future diagnosis.

## Verification

The existing clockwise route and split-party checks now submit the installed native 10028 request. The new handler check rejects spoofed IDs, unsupported types, malformed length and trailing bytes; verifies one same-instance scene transition, exact arrival, ten-percent recovery and once-only life advancement; and confirms that the new dispatch does not affect city maps. It also preserves the exact historical city death vector and both revival request layouts.

The combat suite applies a real lethal tower hit under all four combinations of Legacy/ECS monster and player runtimes. It checks the native death layout and absence of a death-time scene reload, then advances the world beyond the observed 28-second city-transfer delay and verifies that a dead admitted player remains inside the active run. The handler suite separately checks native revival after that interval, with unchanged roster, clock, monsters and claims. Build/test results belong to the integrated release report; these tests do not substitute for an installed-client playtest of the actual window.
