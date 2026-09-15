# Client gear quality and grade palette

Status: revised, regression-validated, and applied to the local development
client at `C:\Godswar Origin`. The apply changed the two locale `font.lua`
files and created rollback backup
`C:\Reborn\backups\client-gear-palette-20260830-111710740`; its second plan
reported zero pending changes. The B20H client was not modified.

## Scope

The client previously reused general UI constants such as `TEAM_COLOR`,
`GUILD_COLOR`, and `WHISPER_COLOR` for equipment quality and grade. Changing
one of those values could also recolor chat, guild, party, pet, or other UI.

`tools/PatchClientGearPalette.ps1` gives equipment its own namespace:

- `QUALITY_Q01` through `QUALITY_Q20` control equipment name quality.
- `GRADE_G01` through `GRADE_G25` control the displayed grade.
- Grade attribute text remains `GREEN_TEXTCOLOR`; this patch only separates
  the grade label/star color.
- Existing legacy constants remain available to their existing consumers.
- Elemental tooltip sentinels `AppLevel26` through `AppLevel32` and all seven
  `ELEMENT_*_COLOR` definitions are byte-for-byte protected by validation.

The same definitions are written to both `en_us` and `zh_cn` resources.

## Quality palette

| Quality | Name | Constant | RGB |
|---:|---|---|---:|
| 1 | Common | `QUALITY_Q01` | 220, 224, 232 |
| 2 | Enhanced | `QUALITY_Q02` | 168, 208, 232 |
| 3 | Delicate | `QUALITY_Q03` | 83, 214, 199 |
| 4 | Good | `QUALITY_Q04` | 92, 220, 112 |
| 5 | Superior | `QUALITY_Q05` | 255, 153, 0 |
| 6 | Classic | `QUALITY_Q06` | 229, 194, 62 |
| 7 | Eternal | `QUALITY_Q07` | 255, 218, 77 |
| 8 | Epic | `QUALITY_Q08` | 255, 139, 223 |
| 9 | Legendary | `QUALITY_Q09` | 255, 105, 55 |
| 10 | Mystic | `QUALITY_Q10` | 218, 85, 238 |
| 11 | Divine | `QUALITY_Q11` | 255, 240, 176 |
| 12 | Celestial | `QUALITY_Q12` | 196, 220, 242 |
| 13 | Mythical | `QUALITY_Q13` | 141, 188, 227 |
| 14 | Astral | `QUALITY_Q14` | 127, 145, 217 |
| 15 | Arcane | `QUALITY_Q15` | 145, 120, 200 |
| 16 | Ethereal | `QUALITY_Q16` | 168, 223, 216 |
| 17 | Transcendent | `QUALITY_Q17` | 232, 214, 111 |
| 18 | Ancient | `QUALITY_Q18` | 214, 154, 80 |
| 19 | Primordial | `QUALITY_Q19` | 227, 96, 51 |
| 20 | Boundless | `QUALITY_Q20` | 255, 59, 48 |

Superior restores the native `GUILD_COLOR` orange. Q11 through Q16 use a
restrained celestial range, while Q17 through Q20 move through electrum,
bronze, ember, and imperial scarlet. Boundless keeps the native crimson
identity but raises it from the legacy `150, 0, 32` to a value that remains
clear on the client's black and charcoal panels. It is also far from Common
(`220, 224, 232`) without relying on neon magenta.

## Grade palette

Each four-grade milestone has a recognizable color family and becomes brighter
inside that family. G25 finishes the forged-metal progression in crown gold.

| Grades | Family | Constants | RGB progression |
|---|---|---|---|
| 1–4 | Silver | `GRADE_G01`–`GRADE_G04` | 176/184/200 → 220/226/236 |
| 5–8 | Jade | `GRADE_G05`–`GRADE_G08` | 66/170/118 → 82/220/148 |
| 9–12 | Azure | `GRADE_G09`–`GRADE_G12` | 64/132/220 → 82/180/255 |
| 13–16 | Royal steel | `GRADE_G13`–`GRADE_G16` | 113/129/208 → 151/170/241 |
| 17–20 | Bronze | `GRADE_G17`–`GRADE_G20` | 191/118/64 → 230/157/78 |
| 21–24 | Gold | `GRADE_G21`–`GRADE_G24` | 211/154/45 → 255/206/73 |
| 25 | Crown gold | `GRADE_G25` | 255, 240, 106 |

The exact per-grade values are the authoritative entries in
`tools/PatchClientGearPalette/Palette.ps1`.

The G13–G25 ladder now reads as royal steel, bronze, gold, and a crown-gold
cap instead of cycling through unrelated neon families. The patch validation
still requires both terminal colors to have high chroma, remain far from
Common/white, and remain far from each other. Imperial-scarlet Boundless and
crown-gold G25 therefore remain distinct when they appear together on a
Q20/G25 tooltip. The affected colors retain at least approximately 4.5:1
contrast against a `#15191E` reference panel; the original client renderer
remains the final small-font acceptance gate.

## Usage

Preview and validate without changing the client (the default):

```powershell
.\tools\PatchClientGearPalette.ps1
```

Apply after the visual package is approved and the client is closed:

```powershell
.\tools\PatchClientGearPalette.ps1 -Apply
```

The apply mode backs up every changed file under
`C:\Reborn\backups\client-gear-palette-<timestamp>`. It rejects an active copy
of that client's `Origin.exe`, concurrent file changes, unexpected encodings,
malformed or duplicate rows, and altered elemental sentinels. A second apply
must report zero changed files.

Run the isolated regression test with:

```powershell
.\tools\TestClientGearPalettePatch.ps1
```

The test proves plan mode is read-only, the first fixture apply changes four
files, the second apply changes zero files, unrelated UI and pet colors remain
unchanged, and corrupt elemental sentinel data is rejected.

## Files patched when applied

- `Localization/en_us/Settings/Sys/ItemColor.xml`
- `Localization/zh_cn/Settings/Sys/ItemColor.xml`
- `Localization/en_us/UI/Base/font.lua`
- `Localization/zh_cn/UI/Base/font.lua`

Armor-rank and weapon-rank visual assets are a separate patch surface. This
palette tool intentionally cannot alter rank thresholds, rank effect IDs,
textures, models, executables, gameplay calculations, or server state.
