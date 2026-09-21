# Wonderland combat and controls follow-up

> Historical record: the design, placements, roster and party HP scaling below are superseded where they differ from the [September 13 full external comparison](wonderland-external-comparison-20260913.md). Preserve the recorded evidence and release results as history.


This change fixes missing lethal AOE numbers, restores the actual Fire Blast ground effect, enables the completed countdown's Leave controls, and removes position-packet vibration while stunned. It preserves authoritative combat, reward settlement and instance ownership rules.

## Lethal AOE numbers

At **2026-09-12 23:16:17 UTC**, AresTempest's skill 314 hit all six island-three pet birds with **zero misses**. The first resolved hit was **3,078,181**; the six remaining health pools lost **375,000 HP** in total. The damage was committed. Relevant lines are preserved in [aoe-island3-evidence.log](../artifacts/wonderland-followup-20260913/aoe-island3-evidence.log).

The native **10047 / MSG_MAGIC_CLUSTER_DAMAGE** receiver at `0x4E8F27` applies its HP delta independently of AttackType. Positive floating numbers require AttackType at most 2. The server incorrectly used type 5 for lethal entries, suppressing their numbers; the full receiver contains no type-5 death branch. It reads the complete DWORD damage value, so this incident was not a 16-bit overflow. See [native-cluster-audit.md](../artifacts/wonderland-followup-20260913/native-cluster-audit.md) and the linked disassembly artifacts in that directory.

Monster AOE publication now keeps normal **AttackType 1**, including lethal hits. Original caster, skill, damage amount, target filtering, health revisions and corpse handling remain unchanged. The change applies to the shared monster AOE delivery path, not only Wonderland. It adds neither a second damage packet nor another HP mutation. The existing visibility lease still filters unknown actors and suppresses replay; this matters because the native receiver traverses entries backwards and aborts a cluster on an unresolved target. Native floating numbers are shown only when the source or target is the local player.

## Actual Fire Blast on island six

The previous coordinate presentation used **570 / Flame Blast**, whose asset is `effect_fire_004_all.gwm`. The requested **580 / Fire Blast** uses `effect_fire_002_all.gwm`, but its native `Target=1` cannot render the target-zero coordinate path.

The guarded client patch adds presentation-only **589**, cloning each locale's entire native 580 section and changing only the section ID and **Target 1 → 17**. That adds the native coordinate bit while preserving the exact Fire Blast effect, animation, scale and other fields. Original skill 580 remains byte-identical; ordinary player/NPC targeting and authoritative terrain damage still use 580. Alias 589 is used only for the server's island-six ground warning and impact presentation.

The existing real-dragon source hydration, island-local visibility, ownership/life/membership checks, safe zones, three-second schedule and 1.5-second windup are preserved. Each circle renders once regardless of victim count. The hazard still stops when its dragon dies or the run terminates; ordinary corpse and loot visibility remain unchanged.

Installer: [PatchClientWonderlandGroundFire.py](../tools/PatchClientWonderlandGroundFire.py). It checks the exact native source and unused or already-correct alias in both locales, retains UTF-16LE and all original bytes, verifies the Fire Blast asset exists, and requires a closed client before installation. Writes have exact backups, preimage checks, readback and guarded rollback. Ten hermetic installer checks passed, and the two-locale live preview passed. **Both locales were installed and verified**; the exact backup receipt is `C:\Godswar Origin\backups\wonderland-ground-fire\20260912-234031-c9d1946bb284447bae53a3a8b60670c3\manifest.json`. [client-fire-preview.json](../artifacts/wonderland-followup-20260913/client-fire-preview.json) records the reviewed hashes. The next client launch loads the alias before receiving the new presentation ID.

## Completed countdown Leave

The native **10221** request carries the repetition scene/index; supported **10232** panel action 0 is the other Leave control. Both previously reached an Active-only termination operation, so completed-run clicks were consumed without leaving.

The new completed-Leave path requires the exact admitted participant, canonical scene **227 / index 0** where supplied, completion of all eight islands, and settled title milestones. It checkpoints and transfers only that participant to their capital. A failed checkpoint leaves membership and the panel intact for retry. Successful committed departure clears the panel through the existing path.

It does not cancel the party's completed run, move another member, claim leftover loot, or shorten the other members' treasure window. A dead finisher can leave without an invented heal, matching terminal dungeon egress. Active leader-only cancellation remains unchanged. The completion announcement still waits for the captured departing members' destination scenes to become ready. Details: [completed-leave-source.md](../artifacts/wonderland-followup-20260913/completed-leave-source.md).

## Stun movement vibration

Repeated native **10194** position corrections rewrite the local actor and camera. Sending one for every held movement input produced the reported vibration. Control-blocked Begin/End/Walk input now rejects silently; the existing native NonMoving status and server movement/skill gates remain authoritative. Silence continues to allow movement.

Realtime rejection retains its sequenced snapshot/ACK and the final-commit rebase when stun arrives during an awaited cast interruption. Those snapshots are metadata, not native movement injection. Repeated native position corrections are suppressed while control is active; death and unrelated movement-validation/transport corrections remain. No status definition, timer, damage, ownership lock or interruption ordering changed. See [stun-movement-vibration-20260913.md](stun-movement-vibration-20260913.md).

## Validation and release record

The Release build passed with **zero warnings** and **42 protocol checks passed, zero failed, zero skipped**. Deployment completed successfully. The live image is `sha256:0c9c7e90a488310cc87743c82d03512b62724eda93e44bdc3090fee4d1450b64`, started at `2026-09-12T23:41:07.9024802Z`, healthy with zero restarts at verification. Verification found no item, inventory or schema drift. Its pre-deploy database backup SHA-256 is `6070e5f52ca7ddca3f3871f1bbe12254edeef543d0accbaa2d1a4736bea02e72`; release artifacts retain the dump and verification receipts. These results do not constitute an in-game rendering observation.

Key exact check names:

- `Wonderland lethal six-bird AOE preserves native floating damage and exact health once`
- `Monster area-damage AOI revision delivery`
- `Wonderland island-wide ground fire hydrates its native source and fences delayed visuals`
- `Wonderland completion countdown Leave exits only its settled participant and preserves party treasure`
- `Universal native stun and silence movement authority`
- `Queued movement rejects stun at final commit`
- `Medusa controlled movement reconciliation`
- `Secure Phase 4 game-handler movement integration`
- `Wonderland real combat controls, buffs, reflection, and timed skills across both engines`

The full selected list and receipts are under [artifacts/wonderland-followup-20260913](../artifacts/wonderland-followup-20260913). Independent source reviews found no material issue in the AOE, ground-fire authority or stun-rejection changes. **No new manual in-game rendering confirmation has been performed.**

Any subsequent manual visual observations should be recorded separately from the completed automated and deployment checks.

## Current boss HP

No HP values changed in this followup. The monster plan and encounter scaling
policy give the following values:

| Island | Boss | Solo HP | Five-player HP |
| --- | --- | ---: | ---: |
| 1 | Alpha Demon | 8,000,000 | 8,000,000 |
| 2 | Capritaur Derskey | 1,125,000 | 4,500,000 |
| 2 | Depraved Monkeyface | 1,125,000 | 4,500,000 |
| 3 | Flame Rooster | 7,500,000 | 30,000,000 |
| 4 | Outrageous Rock Spirit | 2,250,000 | 9,000,000 |
| 5 | Athenian Marshal Addis | 3,000,000 | 12,000,000 |
| 5 | Spartan Marshal Knocker | 3,000,000 | 12,000,000 |
| 6 | Depraved Platinum Dragon | 3,750,000 | 15,000,000 |
| 7 | Iberian Multi-Head | 6,000,000 | 24,000,000 |
| 8 | Minotaur | 2,250,000 | 9,000,000 |
| 8 | Titan's Xmas Deer | 2,625,000 | 10,500,000 |
| 8 | Iberian Dragon King | 3,750,000 | 15,000,000 |
| 8 | Scorpion King | 4,500,000 | 18,000,000 |

Except for Alpha Demon, party sizes 1/2/3/4/5 use 25/45/65/85/100 percent of
five-player HP. Alpha stays fixed. On island 5 the same-faction marshal is
allied; the opposing marshal is required for completion.
