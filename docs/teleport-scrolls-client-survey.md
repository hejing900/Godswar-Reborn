# Teleport scrolls (`FlyBook*`): what the client carries, and where the
# coordinates actually live.
#
# Source files:
#   D:\Godswar Origin\Localization\en_us\Settings\Sys\ItemBaseAttribute.xml
#   D:\Godswar Origin\Localization\en_us\Settings\Sys\Magic.ini
#   D:\Godswar Origin\Localization\en_us\Text\EquipName.dat
#   D:\Godswar Origin\Localization\<lang>\Monster\<Scene>\Address.ini
#   godswar.packet_transactions (opcode 10018 S2C = the server's landing frame)
#
# Finding: the client identifies a scroll's destination by ScriptID only
# (`FlyToAthens1` ...). No client file carries coordinates for those script
# names - a full scan of all 4,707 client text files and of Origin.exe,
# Launch.exe, gworiginsv.exe, patcher.exe and GodsWar.map finds `FlyTo` in
# Magic.ini and nowhere else. The coordinates are server-side.

## The 29 scroll items

| item | key | camp | skill | scroll name | skill name | ScriptID |
|-----:|-----|------|------:|-------------|------------|----------|
| 4300 | FlyBook1  | Athens | 3000 | Athens Portal Scroll | Athens Portal Roll | FlyToAthens1 |
| 4301 | FlyBook2  | Athens | 3001 | Athens Suburb Scroll | Athens Suburb Roll | FlyToAthens2 |
| 4302 | FlyBook3  | Athens | 3002 | Marathon Portal Scroll | Marathon Roll | FlyToAthens3 |
| 4303 | FlyBook4  | Athens | 3003 | Plataea Portal Scroll | Bladia Portal Roll | FlyToAthens4 |
| 4304 | FlyBook5  | Sparta | 3025 | Sparta Portal Scroll | Sparta Portal Roll | FlyToSparta1 |
| 4305 | FlyBook6  | Sparta | 3026 | Sparta Suburb Scroll | Sparta Suburb Roll | FlyToSparta2 |
| 4306 | FlyBook7  | Sparta | 3027 | Peloponnesus Portal Scroll | Peloponnesus Portal Roll | FlyToSparta3 |
| 4307 | FlyBook8  | Sparta | 3028 | Derveni Portal Scroll | Deerweini Portal Roll | FlyToSparta4 |
| 4308 | FlyBook9  | any    | 3050 | Hermes Stone | Escape Scroll | FlyToRandom |
| 4311 | FlyBook11 | Athens | 3031 | Parnitha Portal Scroll | (cn) | FlyToNew1 |
| 4312 | FlyBook12 | Athens | 3032 | Megara Coast Portal Scroll | (cn) | FlyToNew2 |
| 4313 | FlyBook13 | any    | 3033 | Corinth Portal Scroll | (cn) | FlyToNew3 |
| 4314 | FlyBook14 | Sparta | 3034 | Argolis Portal Scroll | (cn) | FlyToNew4 |
| 4315 | FlyBook15 | Sparta | 3035 | Nemea Portal Scroll | (cn) | FlyToNew5 |
| 4316 | FlyBook16 | Sparta | 3036 | Advanced Derveni Portal Scroll | (cn) | FlyToNew6 |
| 4317 | FlyBook17 | Athens | 3037 | Mystic Plataea Portal Scroll | (cn) | FlyToNew7 |
| 4318 | FlyBook18 | Athens | 3038 | Athenian Corinth Scroll | (cn) | FlyToNew8 |
| 4319 | FlyBook19 | Sparta | 3039 | Spartan Corinth Scroll | (cn) | FlyToNew9 |
| 4320 | FlyBook20 | Athens | 3004 | Parnitha Port Portal Scroll | Parnitha Portal Scroll | FlyToAthens6 |
| 4321 | FlyBook21 | Sparta | 3029 | Nemea Forest Portal Scroll | Nemea Portal Scroll | FlyToSparta6 |
| 4322 | FlyBook22 | Athens | 3005 | Athens Thermopylae Portal Scroll | Athens Thermopylae Portal Scroll | FlyToAthens7 |
| 4323 | FlyBook23 | Sparta | 3030 | Sparta Thermopylae Portal Scroll | Sparta Thermopylae Portal Scroll | FlyToSparta7 |
| 4324 | FlyBook24 | Athens | 5626 | Athens Delphi Forest Portal Scroll | idem | FlyToAthens8 |
| 4325 | FlyBook25 | Sparta | 5627 | Sparta Delphi Forest Portal Scroll | idem | FlyToSparta8 |
| 4326 | FlyBook26 | Athens | 5628 | Athens Elasson Portal Scroll | idem | FlyToAthens9 |
| 4327 | FlyBook27 | Sparta | 5629 | Sparta Elasson Portal Scroll | idem | FlyToSparta9 |
| 4328 | FlyBook28 | Athens | 5630 | Athens Olympus Portal Scroll | idem | FlyToAthens10 |
| 4329 | FlyBook29 | Sparta | 5631 | Sparta Olympus Portal Scroll | idem | FlyToSparta10 |

`FlyBook9` (Hermes Stone, 4308) is the escape scroll: `FlyToRandom`, so it has
no fixed destination.

## Landing coordinates recovered from the capture

Opcode `10018` S2C is the reference server's landing frame (28 bytes: `+4`
object id, `+8` f32 X, `+16` f32 Z, `+20` map id in the low 16 bits). The
capture holds 32 of them across the 2026-09-21..24 session, 18 distinct:

| map | x | z |
|----:|---:|---:|
| 1  | 102 | -212 |
| 1  | 20  | -100 |
| 1  | 120 | -200 |
| 2  | 209 | 22   |
| 2  | 20  | -100 |
| 2  | 120 | -200 |
| 2  | 150 | -146 |
| 2  | 186 | -122 |
| 3  | 66  | 190  |
| 9  | 47  | 107  |
| 9  | 150 | -146 |
| 11 | 15  | -30  |
| 11 | 150 | -146 |
| 11 | 182 | -36  |
| 15 | -167 | -217 |
| 18 | -30 | -202 |
| 18 | 56  | 88   |
| 19 | -194 | 192  |

Map 18 `(56, 88)` is the Megara landing already ported into
`ReviveLandingCatalog`; the capture confirms it.

## The client's own named landing points

`Address.ini` per scene holds `AddressNameN` / `CoordinateN` pairs; these are the
client's named points, which is what a scroll's destination name refers to:

| map | scene | name | x | z |
|----:|-------|------|---:|---:|
| 1 | Athens | Athens | 102 | -217 |
| 1 | Athens | Foggy Field | 25 | -115 |
| 1 | Athens | Southern Field | 132 | -188 |
| 1 | Athens | Suburbs | 184 | -114 |

Note `Athens (102, -217)` against the captured landing `(102, -212)`: the server
lands 5 units off the client's address point on the same axis. Every other map's
`Address.ini` (maps 2, 3, 9, 11, 15, 18, 19, ...) ships **no coordinates at
all** - only maps 0 and 1 have any.

## What this means for the server

`BackhaulSkillCatalog` implements 4 of the 28 teleport skills today:

| skill | scroll | target |
|------:|--------|--------|
| 3000 | FlyBook1 | Athens city, `GameDefaults.StartingPosition*` |
| 3001 | FlyBook2 | map 2, `(102, -217)` |
| 3025 | FlyBook5 | Sparta city, `GameDefaults.StartingPosition*` |
| 3026 | FlyBook6 | map 4, `(102, -217)` |

The remaining 24 skills have no definition, so those scrolls do nothing. Two of
the implemented targets are worth checking against the capture: the capture
lands Athens at `(102, -212)` on map 1, and Athens Suburb at `(209, 22)` on map 2,
whereas the catalog uses `(102, -217)`.
