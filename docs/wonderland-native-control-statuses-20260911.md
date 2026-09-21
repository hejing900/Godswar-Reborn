# Wonderland native stun and silence controls, v2

Installed and verified in both Origin locales at11:50 UTC. The exact backup manifest and server deployment are recorded in [the release report](wonderland-island-controls-20260911.md).

The first Wonderland status patch supplied names and timers with no native control effects. Its stun icon therefore did not itself prevent the client from requesting movement or skills. The v2 patch gives the dedicated statuses the verified stock control behavior while leaving all encounter stat calculations on the server.

| Dedicated status | Verified native reference | Effect IDs | Icon |
|---|---|---|---|
| 1512 Wonderland Stun | Stock 330 Stuned | 0,2,3,4,5,6 | 252,108 |
| 1513 Wonderland Silence | Stock 360 Magic Locked | 3,4 | 540,72 |

The installed Status.ini header identifies 0 as cast interruption, 2 as movement lock, 3 as magic-use lock, 4 as physical-skill lock, 5 as basic-attack lock, and 6 as item-use lock. All enabled control values are 1 with interval 0. The stun matches the existing server policy that also blocks item use. Silence leaves movement, basic attacks and potions available. Both timers remain 2 seconds. EffectDisplay stays -1; no additional world effect, stat modifier or asset is introduced. Statuses 1510, 1511, 1514 and 1515 remain byte-identical, with Effect=-1 and Values=0.

`tools/PatchClientWonderlandStatus.py` now identifies itself as reborn.wonderland-status.v2. Fresh installation requires the native 330/360 effect/value/interval/icon references to match. Upgrade accepts only a complete exact v1 set, frozen in `tools/client_patch_helpers/WonderlandStatuses.v1.json`, or a complete current v2 set. Modified, foreign, partial or mixed owned sets fail before installation. Existing native sections, other statuses, encoding, BOM and section separators are preserved. Foreign use of the owned kinds is rejected even on upgrade or verification.

Installation retains the client-closed guard, exact backups of both locales, input checks, atomic writes and readback. Rollback only replaces bytes written by this transaction; an unknown concurrent edit is preserved and the receipt reports RollbackFailed with verified backup paths. Preflight binds the bytes that were actually parsed instead of adopting a later concurrent read.

All 14 hermetic checks passed via `python tools/TestClientWonderlandStatus.py`, covering native controls, server-only stat modifiers, exact v1 upgrade, idempotence, backups, native-reference/identity/kind conflicts, encoding, running-client rejection, write failure, and concurrent changes. Live preview recognizes both installed v1 locales and changes only 1512/1513. Evidence and preview hashes are under `artifacts/wonderland-native-control-status-20260911`. No client installation or in-game playtest was performed by this subtask.

```powershell
python tools/PatchClientWonderlandStatus.py --client-root 'C:\Godswar Origin' --mode preview
# After the client is closed; apply creates and verifies an exact backup first.
python tools/PatchClientWonderlandStatus.py --client-root 'C:\Godswar Origin' --mode apply
python tools/PatchClientWonderlandStatus.py --client-root 'C:\Godswar Origin' --mode verify
```
