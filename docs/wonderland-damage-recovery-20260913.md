# Wonderland damage recovery: what the external capture establishes

The three recorded Wonderland runs contain **1,676 normal boss hits**, including
714 in the latest complete run. Their damage values are directly observed. The
external server's original raw physical/magical attack values are **not yet
identified**. The deployed `WonderlandCapturedAttackPolicy` contains effective
ratings fitted to a reference target, not recovered original monster stats.

This investigation makes no changes to server balance or client files. It
supersedes any interpretation of the September 13 comparison as establishing
the original attack values or their behavior against different defenses.

## Today's two characters are already in the evidence

The capture filename retains its September 7 proxy-start date, but the stream
contains separate September 13 sessions. Native character-entry and stat packets
identify the two characters; the changing world object IDs are not being used
as character identities.

| Character | Class / level | September 13 Wonderland interval, NZST | Normal boss hits | Stable PD / MD / displayed Absorb |
|---|---|---|---:|---|
| -Alboz- | Mage / 139 | 12:53:11–13:26:33 | 753 | 4,566 / 2,630 / 3,995 |
| xPade | Mage / 143 | 13:30:24–13:59:42 | 714 | 5,379 / 2,920 / 4,791 |

The remaining 209 observations are -Alboz-'s September 11 run. Four of today's
753 -Alboz- hits reference lower early scene stats; the stable same-stat
comparison below uses the other 749. Both today's characters were already
included in the 1,676-hit analysis. Referring to an unspecified older target
obscured that fact; the table makes the existing comparison explicit.

| Same boss, primary attack with Shield active | -Alboz-, today | xPade, today | Difference |
|---|---:|---:|---:|
| Alpha Demon | 5,325 | 3,953 | 1,372 |
| Capritaur Derskey | 8,125 | 6,753 | 1,372 |
| Depraved Monkeyface | 8,125 | 6,753 | 1,372 |
| Outrageous Rock Spirit | 15,825 | 14,453 | 1,372 |
| Depraved Platinum Dragon | 16,525 | 15,153 | 1,372 |

This is real cross-character evidence and is used in the formula checks below.
PD, MD and displayed absorption change simultaneously, so it constrains the
combined mitigation difference without separately identifying each contribution.
The two sessions do not by themselves supply a unique raw-attack solution.

An independent scan grouped by actual connection and character entry confirms
that every boss-sourced 10026 damage packet is present in the earlier analysis:
209 / 753 / 714 by session, all result 1 / damage type 1. There are no additional
boss-sourced 10040, 10045 or 10047 packets in these sessions and no excluded
critical/miss boss-hit groups. -Alboz-'s September 13 session reaches island 6,
returns to the entrance and exits; it has no island 7 or 8 boss appearances.
The missing second-character late-boss samples are therefore absent from the
stream, rather than lost by the paired-hit filter.

## Observed boss damage

The latest target reports level 143, physical defense 5,379, magical defense
2,920 and displayed Absorb 4,791. Celestial Shield 234 is active. The following
numbers are damage **received by that character**, after whatever calculation
the external server performed. They are not damage against an undefended target.
All entries below are normal damage results; critical hits are not mixed in.

| Boss | Primary skill ID | Primary hit | Basic hit while silenced |
|---|---:|---:|---:|
| Alpha Demon | 2805 | 3,953 | Not observed |
| Capritaur Derskey | 2022 | 6,753 | Not observed |
| Depraved Monkeyface | 2803 | 6,753 | Not observed |
| Flame Rooster | 2000 | 4,713 | Same generic attack; no separate skill observed |
| Outrageous Rock Spirit | 2178 | 14,453 | Not observed |
| Spartan Marshal Knocker | 2004 | 15,993 | 4,813 |
| Depraved Platinum Dragon | 2022 | 15,153 | 4,213 |
| Iberian Multi-Head | 2021 | 15,153 | 4,213 |
| Minotaur | 2803 | 12,353 | 2,213 |
| Titan's Xmas Deer | 2178 | 15,153 | 4,213 |
| Iberian Dragon King | 2021 | 15,853 | 4,713 |
| Scorpion King | 2192 | 22,153 | 9,213; 10,980 with Internal Injury 133 |

Athenian Marshal Addis was observed in the earlier opposite-faction run:
17,365 primary damage against the stable level-139 reference with PD 4,566,
MD 2,630 and displayed Absorb 3,995. It was not measured against the latest
target. The user's exception retaining our custom island-3 boss damage/Fire
Blast remains; the Rooster row above documents the external server only.

## Relationships supported by repeated observations

For all seven bosses with both primary and silenced basic hits in the latest
run, the paired outputs satisfy exactly:

`primary damage = 1.4 × basic damage + 9,254.8`

Scorpion's basic hit in that relation is the 9,213 value before Internal Injury.
The seven bosses supply five distinct basic-damage values. This establishes a
relationship between observed outputs in one target state, not a raw skill
coefficient of 1.4. Native skill IDs with different client Power fields all
follow the same relationship; those tooltip coefficients alone do not explain
the NPC hits.

Across the two stable shielded target configurations, Alpha, Derskey,
Monkeyface, Rock Spirit and Platinum Dragon each deal exactly **1,372 less**
damage to the latest character. With the earlier stats held constant,
Celestial Shield changes Alpha's 6,586 to 5,325 and Rock's 17,086 to 15,825:
the same **1,261** reduction despite their very different hit strengths.
Rooster's shield change is 8,569 to 6,880, a **1,689** reduction.

Internal Injury changes Scorpion's basic hit from 9,213 to 10,980, while its
primary 2192 hit remains 22,153. The numerical PD/MD/Absorb fields do not change.
The relevant status timers are unambiguously active at the recorded hits.
Therefore the client skill's physical Property field cannot, by itself,
establish how the external server applies this defensive modifier to NPC skills.

## Why adding defense and absorption back does not recover raw attack

Adding the displayed defense and full Absorb back to each primary hit gives
different putative attacks for the same boss in the earlier and latest runs:

| Boss | Earlier reconstructed attack | Latest reconstructed attack |
|---|---:|---:|
| Alpha, using physical defense | 13,886 | 14,123 |
| Derskey, using magical defense | 14,750 | 14,464 |
| Monkeyface, using physical defense | 16,686 | 16,923 |
| Rock Spirit, using magical defense | 22,450 | 22,164 |
| Platinum Dragon, using magical defense | 23,150 | 22,864 |

These are examples of the rejected simple inversion, **not replacement stats**.
The reference calibration remains useful for matching a reference test setup,
but it cannot establish the original attack rating or correct scaling against
other defense configurations.

The supplied external client defines Shield 234 as 17%; Origin defines it as
20%. Applying a final 17% multiplier to the whole Rock hit before a nonnegative
flat absorption cannot fit its shield toggle: it would require negative
absorption. A defense-dependent calculation or a separately appended skill
component can still fit. The external Chocolate 571 is a 2% outgoing-damage
effect and must not be counted as incoming mitigation.

Displayed Absorb does not disclose an independently verified physical/magical
split. Local projection and status catalogs are authored implementations, not
proof of the external server's formula. Its monster spawn/damage packets and
supplied model definitions do not provide original PA/MA values.

Even the exact paired relationship leaves an unknown baseline. For example,
the illustrative family `B = A - P`, `S = 1.4A - M` only determines
`1.4P - M = 9,254.8`. Different positive P, M and A values reproduce the same
observations. The cross-run and shield differences constrain changes in those
terms without fixing their absolute values. These equations demonstrate why
multiple reconstructions fit; they are not asserted as the native formula.

## Next measurement needed

A controlled external recording should keep the same boss, character and pet
state while deliberately changing one defensive variable at a time. Prefer
Platinum Dragon or Minotaur, whose primary and silenced basic attacks are both
already observed. At each state, obtain a fresh character-stat snapshot and
several normal hits in each attack mode:

1. Establish an unbuffed baseline, with Celestial Shield and defensive food
   absent and no merge/unmerge transition during the sample.
2. Change only physical defense with equipment whose actual modifiers are
   known; restore it, then separately change magical defense.
3. Separately test an absorption change, preserving the other defensive terms.
4. Restore baseline equipment and repeat with Celestial Shield active.

Equipment changes that alter several stats must be recorded as such; they are
not single-variable experiments. A fresh stat frame is required after each
change. The four early lower-stat boss hits in run 2 occur around scene/stat
publication and are not treated as controlled equipment measurements.

These observations can discriminate formulas and validate damage across
defenses. Identifying the *original* database PA/MA additionally requires an
absolute formula/stat anchor; further hits do not automatically guarantee it.
Until then, report captured damage as observed and reconstructed ratings as
estimates. Preserve fixed stats regardless of party size.

## Reproduction and evidence

The immutable input is
`artifacts/wonderland-full-external-20260913/external-full.log`, SHA-256
`81ea111739f43e90319b64b777fe6a0f1d4cfeeb9e2de34997692aaad666df44`.
Combat-only outputs and reproducible scripts are in
`artifacts/wonderland-damage-inversion-20260913/`:

- `collect.py`: reconstruct the three runs and 45 normal-hit cohorts.
- `audit_character_runs.py`: independently split real connections, identify
  both characters from native packets, and verify all 96,375 frame bytes and
  every boss-damage sequence against the original analysis.
- `audit_target_status.py`: independently check all 1,676 hit references against
  raw stat/status frames, external definitions and status-timer boundaries.
- `fit_models.py`: check output relationships, reject simple formulas and
  demonstrate multiple fitting reconstructions.
- `audit_client_damage_data.py`: pin native definitions and inventory the
  supplied client files for raw stats/formula evidence.
- `TARGET-STATUS-EVIDENCE.md`, `client-damage-data-audit.md`, cohort/model JSON:
  exact values, packet references and limitations.

The analysis scripts and document assertions were checked against the pinned
capture. No production build or deployment is needed for this evidence-only
update.
