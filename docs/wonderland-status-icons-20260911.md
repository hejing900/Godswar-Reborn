# Wonderland status icons, 11 September 2026

This records the original v1 installation. The current guarded v2 upgrade enables native stun and silence controls, with a distinct silence icon; see [the v2 audit](wonderland-native-control-statuses-20260911.md). The original installation hashes below remain historical evidence.

Wonderland encounter effects use dedicated native status-bar entries in the
complete 10167 snapshot. Ordinary buffs such as Sacred Zeal remain in the same
snapshot. Existing encounter timers remain the gameplay authority; the new
client definitions contain `Effect=-1`, `Values=0`, and `EffectDisplay=-1`.

These are authored labels for the implemented encounter mechanics. They are
not claimed as status IDs recovered from the external capture.

| Status ID | Effect | Duration | Existing icon position |
|---:|---|---:|---|
| 1510 | Petbird Blessing: physical and magical attack x5 | 15 seconds | 216,0 |
| 1511 | Putrid Bird Blessing: Hit +25000 | 15 seconds | 324,72 |
| 1512 | Wonderland Stun | 2 seconds | 252,108 |
| 1513 | Wonderland Silence: skills disabled, basic attacks and potions available | 2 seconds | 252,108 |
| 1514 | Spear Blast: physical defense -40% | 8 seconds | 144,36 |
| 1515 | Armor Rend: physical defense -50% | 10 seconds | 144,36 |

The definitions use distinct kinds 1011–1016. Neither inspected client had
these IDs or matching Petbird/Putrid Bird descriptions. Reusing stock Sledge
Hammer, Charged, Confounded, or Broken Armor would show different magnitudes
or disabled actions and could overlap ordinary class statuses.

The maintained definition source is
`tools/client_patch_helpers/WonderlandStatuses.json`; the guarded installer is
`tools/PatchClientWonderlandStatus.py`. It appends only the six owned sections
to English and Chinese `Status.ini`, preserves the UTF-16LE BOM and all prior
bytes, rejects conflicting or partial definitions, and requires the client to
be closed before installation. It backs up both exact inputs, checks for
concurrent changes, reads back installed bytes, and rolls back a partial
failure. No executable, texture, external client, or server content release is
modified by this patch.

```powershell
python tools/PatchClientWonderlandStatus.py --mode preview
python tools/PatchClientWonderlandStatus.py --mode apply
python tools/PatchClientWonderlandStatus.py --mode verify
python tools/TestClientWonderlandStatus.py
```

Nine hermetic checks passed, including server/manifest ID parity, labels and
durations, unchanged preexisting bytes, idempotence, backups, encoding and
collision rejection, the running-client guard, concurrent input changes, and
partial-write rollback. The focused test also runs in the native Windows CI
job. It does not require an installed client.

The installed Origin files were verified at 07:38 UTC on 11 September:

| Locale | Before SHA-256 | Installed SHA-256 |
|---|---|---|
| en_us | 262AE5BCBCFAB6940A56E46E222FA145DA183101FD9B0E00DD6AAE3442FB24E8 | 36DA205342B5688B11C33505617A69AF7CBE77A152FC6710E9A30967C38C9FF2 |
| zh_cn | 79E1250AA8CA242022C88DBE6D4AA0226A036551EDCF40E2075CA40188D0DBA5 | 62EA77C1DBBCC401FB2ACD3AC4B876B43F2A2035E05345677A27F4F7EED788AC |

The exact backup manifest is
`C:\Godswar Origin\backups\wonderland-status\20260911-073828-f6b317b16d9646e8968662025b1bdddf\manifest.json`.
Installer and test reports are under `artifacts/wonderland-status-20260911`.
Both process checks reported the game closed before replacement. New
definitions are loaded at the next client start; this verification does not
claim an in-game visual playtest.
