# Bloodfang merge crash repair

The September 15 crash occurred while loading Bloodfang's owner-merge aura. Its new `Pet.xml` definitions used single backslashes in `unitefile`, unlike the stock pets' literal doubled backslashes. The native effect loader removes the first character of that value, then appends the remainder directly to the executable directory. Bloodfang therefore attempted `C:\Godswar OriginCharacters\PetUniteEffect\...`, which does not exist.

The saved dump `20260915084452.dmp` reports an access violation reading address `0x14` at `0x0049183B`, with caller `0x006A1780`. Disassembly connects this directly to the failure: `0x00684C20` fails to open the aura, `0x00491813` clears the effect pointer, and the caller displays a file-error dialog before dereferencing that null pointer. This is separate from loading the miniature dragon's mesh or texture.

The v5 content repair copies the stock path convention into all four aura stages for both Bloodfang genders and both locales. The installer now validates the paths using the native loader's actual concatenation rule, so merely having the effect files on disk cannot hide this defect. Existing exact v2, v3 and v4 definitions remain upgradeable; mixed or modified definitions are rejected.

Installed and verified in `C:\Godswar Origin`: exactly the two locale `Pet.xml` files changed. Each contains eight repaired paths. The model, texture, scale, portrait, executable, server and pet records are unchanged.

Validation: 5 focused merge-path checks, 12 legacy upgrade checks, and 15 installer checks passed. All 16 installed merge references resolve to existing aura assets, all 31 planned file hashes match readback, and the post-install plan requires no further changes. A fresh in-game merge still needs user confirmation; the tests do not simulate the full game session.

Evidence: `artifacts/bloodfang-merge-crash-20260915/` contains the crash excerpt/dump, disassembly, before/after path validation, and installation receipt. Backup manifest: `C:\Godswar Origin\backups\bloodfang\20260914-205033-1dfa77e583cf41039485a904a31f02c1\manifest.json` (UTC timestamp).
