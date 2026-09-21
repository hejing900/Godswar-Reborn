# Bloodfang miniature Wonderland dragon

Bloodfang now uses the native Wonderland Depraved Platinum Dragon mesh and its black/platinum skin, scaled to a pet. The rejected custom mesh is retained in the installer backup.

## Appearance

- Source monster: `B_bosse_dragon_014`, from `Localization/en_us/Monster/Fane/Monster.ini`.
- Source model: `Monster/monster_dragon_014.jcs`.
- Source skin: `Monster/monster_dragon_013.gwo` (the monster definition selects 013).
- Pet scale: 0.35 base and 0.385 for rebirth, versus the boss's 3.0. Base size is approximately 12% of the boss, with idle body height around 1.61 world units.
- Native facing, geometry, bones, weights and authored animation timing are preserved. The pet retains Bloodfang's existing portrait.

The adapter only remaps embedded texture filenames and adds pet animation aliases: `nomal_attack` copies `nomal_attack_01`, `nomal_angry` copies `nomal_attack_02`, and `nomal_happy` copies `nomal_stand`. All seven original animations remain. The texture is copied byte for byte.

## Reproduce and validate

Run `tools/bloodfang_model/adapt_wonderland_dragon.py` with `--client-root` pointing to the installed client and `--output` pointing to the release asset directory. Frozen source hashes prevent silently adapting a different monster. The v4 installer defaults to `artifacts/bloodfang-platinum-dragon-20260914/native`.

Validation passed:

- Native D3DX parsing, hierarchy loading, GPU texture creation, skin conversion, controller cloning and all ten animation names.
- 18,000 animation updates simulating 300 seconds, with 150 idle/run/attack switches and finite transforms.
- Source and adapted geometry comparison; original animation blocks and original texture preserved.
- Bounds inspection of all 92 authored keyframes across seven source animations. Pet bounds include a margin; interpolated poses can differ slightly.
- 14 installer tests, 12 upgrade tests and 11 portrait tests.

Native runtime validation used the local 64-bit D3DX9 runtime. These checks do not constitute a new in-game test of the 32-bit client.

## Installed result

Installed into `C:\Godswar Origin` on 2026-09-14. The installer changed exactly four files: the two Bloodfang assets and the Bloodfang model entries in both locale `Pet.xml` files. Readback passed and a repeated plan required no further changes.

Backup manifest: `C:\Godswar Origin\backups\bloodfang\20260914-092150-c5c0d439f5194561b400f4761110858c\manifest.json`.

Reports are in `artifacts/bloodfang-platinum-dragon-20260914`: `client-install.json`, `source-inspection.json`, and the `native` adaptation/parser/runtime reports.

The original Wonderland monster assets and `Origin.exe` hashes remain unchanged. No database, pet-stat, skill, or server changes were made. Reopen the client to load the appearance.
