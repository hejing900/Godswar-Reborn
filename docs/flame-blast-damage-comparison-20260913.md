# AresMage Flame Blast comparison — September 13, 2026

Initial read-only investigation of the reported 16k ticks, before the later
Holy Stone grants. No combat formula tuning was performed. The subsequent
percentage-stone result is recorded below.

## Observed comparison

| Field | Local AresMage | External xPade |
| --- | ---: | ---: |
| Character level | 140 | 143 |
| Merged magic attack | 8,560 | 7,914 |
| Magic damage bonus | 105.4% | 106.4% |
| Flame Blast rank | V / 574 | V / 574 |
| Selected flat Flame Blast Zodiac training | 31 | 23 |
| Selected percentage Flame Blast training | None | None |
| Initial damage and recurring tick | 16,818 | 49,960 |

Local logs place the field at `(172.51, -169.76)`, beside the stationary
first-island tower at `(172.889282, -171.086075)`. The local observations have
one target and repeat 16,818 on both the initial hit and later wire-250 pulses.
The external capture has five separate 49,960 hits from its first clean field
against tower 20870, at approximately 0, 4, 8, 12 and 16 seconds. Alpha Demon
22522 also repeatedly receives 49,960. These are individual hits, not a sum
of overlapping fields. Island 3's much higher damage has a separate buffed
stat state and is not used in this comparison.

## Exact local arithmetic

The SQL compatibility view omits per-item Holy Suit bonuses and active Merge.
Reconstructing the live attacker gives:

- Magic attack: 6,742 compatibility + 535 Platinum I + 1,283 Merge = **8,560**.
- Magic append damage: 1,080 equipment + 1,956 Merge = **3,036**.
- Magic damage bonus: **10,540 basis points**, a 2.054 multiplier.
- Magic penetration: **3,200 basis points**, leaving 1,700 of the tower's
  authored 2,500 magic defense.
- Skill coefficient: `1 + Power1 = 1 - 0.5 = 0.5`.
- Flat skill power: `180 + 31 * 100 = 3,280`.

The current PvE formula therefore produces:

```text
round((((8560 - 1700) * 0.5) + 3280) * 2.054 + 3036)
= round(16818.34)
= 16818
```

The same reconstruction yields HP `69,990 + 4,365 + 22,075 = 96,430` and MP
`7,033 + 990 + 2,706 = 10,729`, matching the live merged combat logs. Initial
and recurring damage use the same calculated stats, projected Zodiac power
and skill damage resolver; no pulse-only omission was found.

## Heated Holy Stones and remaining uncertainty

At the initial comparison, AresMage's 17 equipped items had no Holy sockets or elemental attributes.
The external main equipment has two sockets per piece. Its captured offensive
socket effects are 7 and 8, the critical percentage and flat damage effects;
the raw totals are 1,010 and 1,740 respectively. It has no captured equipped
socket effects 2, 4 or 6 for magic penetration, magic damage percentage or
flat magic append damage. Other captured sockets supply defensive effects.

A Heated Holy Stone is a socket carrier. Its embedded Fire Spirit determines
which statistic it adds; possession of the stone does not itself imply a
general fire-spell multiplier.

External wire-250 positive damage frames all use result flags zero. That
encoding does **not** establish whether the server internally resolved a
critical hit. The earlier preliminary description of those ticks as normal
hits was too strong. Critical stones may contribute; the evidence does not
prove they explain the full difference.

The external server's complete damage formula, target mitigation and some
additional attacker channels remain unobserved. Reborn's current PvE formula
is explicitly project-authored, as documented in `base-combat-roadmap.md`;
it is not a recovered external formula. Matching client Power1/Power2 values
does not prove matching server arithmetic. No arbitrary damage multiplier
should be inferred from the approximately 2.97x observed ratio.

## Observed result after percentage stones

The later user-authorized five Grade X percentage stones add 3,000 basis
points to magic damage bonus, taking it from 105.4% to 135.4%. The five
critical stones add 30 percentage points of critical damage; they do not
increase critical chance or ordinary-hit damage. See
`ares-mage-heated-sockets-20260913.md` for the grant and correction history.

Post-correction live Flame Blast logs show **18,831** on both the initial
hit and recurring pulses, agreeing exactly with the unchanged formula:

```text
Before: 6710 * 2.054 + 3036 = 16818.34 -> 16818
After:  6710 * 2.354 + 3036 = 18831.34 -> 18831
Gain:   2013, approximately 12% of the prior final damage
```

The bonus adds to the existing percentage channel and does not multiply
the final tick by 1.30. The 3,036 flat append component is added afterward.
These stones therefore do not account for the external 49,960 observation;
the external formula and additional unobserved factors remain unresolved.

## Follow-up controlled Fireball test, September 14

The appended capture was frozen in
`artifacts/flame-blast-controlled-20260914/external-controlled.log`, SHA-256
`009badaf9cf4f6629d65fee13fa5b730267d6d2df86187aea0104a6e45933b6c`.
It uses a level-139 mage, local object37, rather than the earlier level-143
xPade state. All qualifying hits are on the same Arrow Tower20869.

| State | Magic attack | Magic damage bonus | Fireball IV503 | Flame Blast V574 |
| --- | ---: | ---: | ---: | ---: |
| Unmerged | 6,772 | 81.2% | 28,446, six hits | No cast in this appended test |
| Merged | 7,488 | 81.2% | 31,482, three hits | 37,228, ten hits across two fields |

The mage has no equipped Holy sockets in this controlled test. No Fireball
family is selected in its Zodiac; Flame Blast's selected flat grid is25.
Thus this test's discrepancy does not require a missing Heated Stone bonus.

The controlled pet record is available through10250. Its six Basic+Added
Savvy totals and Soul Contract stage6 permit a native Pet_Alter table
reconstruction. Using marginal bands and the eight-point contract bonus
reproduces eight visible Merge stat deltas after truncation and the existing
Chocolate attack modifier; HP is one point higher than the observed delta.
The same method predicts effect24 magical append damage1,348.742, approximately
1,348 after truncation. That append amount is inferred from the client table,
not directly transmitted as an authoritative damage component.

Fireball's observed increase is3,036. Reborn's normal-hit ordering, using
coefficient0.9 and the inferred integer append increment, predicts
`716 * 0.9 * 1.812 + 1348 = 2515.6528`. A critical outcome or another
ordering/modifier changes that prediction. Subtracting append first yields
an effective coefficient near1.30, but that is conditional on append being
outside the damage and critical multipliers. It is not a recovered universal
coefficient and does not justify replacing0.9 with1.3 in production.

The user cannot repeat this instance on the same character because of its
daily entry limit. Use the captured Fireball comparison and existing Flame
Blast evidence; no additional instance run is required for these analyses.

## Subsequent level-143 Flame comparison, September 14

The newer capture now includes both unmerged and merged Flame Blast V.
It records 44,059 at MA 6,760 and 49,960 at MA 7,914, with a 106.4% magic
damage bonus in both states. The merged result is identical on level-1/2
creatures, the Wonderland Arrow Tower and Alpha Demon.

A candidate using `1.5 * MA + 90 + 95 * FlameZodiacRank`, followed by the
typed bonus, a 1.5 factor, multiplicative critical percentage and flat
critical damage, reproduces the clean level-139/143 observations within one
damage point. This considerably narrows the earlier uncertainty above.
See [the new comparison](flame-blast-level143-formula-20260914.md) for exact
inputs, residuals, scope and evidence. The runtime formula remains unchanged.

## Original evidence anchors

- Frozen external capture: `artifacts/wonderland-full-external-20260913/external-full.log`.
  SHA-256: `81EA111739F43E90319B64B777FE6A0F1D4CFEEB9E2DE34997692AAAD666DF44`.
- External equipment: sequence 56748; merged stats: 60559; Zodiac: 60467.
- First clean external field hits: 60814, 60870, 60935, 61075, 61203.
- `src/Godswar.Server/World/Systems/Combat/AuthoredCombatFormula.cs`.
- `src/Godswar.Server/World/Systems/Combat/AuthoredCombatVersions.cs`.
- `src/Godswar.Server/State/ZodiacOffensiveSkillProjection.cs`.
- `src/Godswar.Server/Application/WorldInstances/WonderlandMonsterPlan.cs`.
- `src/Godswar.Server/Application/WorldInstances/WonderlandTerrainPolicy.cs`.
- `src/Godswar.Server/Game/GameClientHandler.FlameBlastPulse.cs`.
- `src/Godswar.Server/Game/GameClientHandler.HostileMonsterSkillResolution.cs`.
