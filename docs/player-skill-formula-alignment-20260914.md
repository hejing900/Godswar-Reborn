# Player skill damage alignment, September 14

Historical V3 release record. Superseded by the deployed
[shared V4 player skill damage formula](general-player-skill-damage-20260914.md),
which applies the user-selected base-plus-skill rule across damaging skills.
The text below records the earlier release and its narrower scope.

Flame Blast V now has a versioned player-to-monster damage profile based on
the external captures. All player damaging skills pass through the same
selection point, but only the verified Flame V definition selects this new
profile. Other skills retain their previous formulas. This is not a claim
that every skill has been matched to the external server.

Deployed to `godswar-dev-tempest-openworld-01` at 2026-09-14 11:22:45 NZST.
Image: `sha256:b2ced68dec829582fff6d95fe941dec3f9bc6c19544ce6d2d1f9bb831dee44b8`.
The container is healthy with zero restarts. Schema, all11 content publications,
inventory, talents, ports and other services matched the pre-deployment
fingerprints. A verified database backup and the previous runtime image are
retained in the release evidence. Deployed assembly metadata and the eight
source-file hashes were verified after startup.

## Implemented behavior

For a landed Flame V hit, before explicit encounter modifiers:

```text
core = MATK + (MATK + 180) * 0.5 + 95 * FlameZodiacRank
damage = core * (1 + MagicDamageBonus) * 1.5
              * (1 + CriticalDamagePercentage) + CriticalFlatDamage
```

The profile applies to both the initial hit and recurring pulses. It uses
the captured critical-style damage curve for landed Flame V hits. Existing
deterministic Hit/Dodge admission remains: absent damage in the capture
cannot distinguish a miss from an empty field or a lost target. This policy
does not assert a universal critical-chance formula.

Ordinary magic defense and separate magical append do not enter this Flame
profile. Explicit encounter reductions, critical reductions, damage-taken
modifiers and absorption still apply. For example, the requested Wonderland
Monkeyface magic reduction remains active. These retained encounter rules
can change the raw projection shown above.

`PlayerSkillDamageFormula` reports formula version 3 for the new profile.
It validates skill 574, magic property, the ground-target shape, 50% power,
authored flat180 and consistent Zodiac metadata before selecting it. Lower
Flame ranks, altered definitions and all unverified families use the existing
formula. Historical V1/V2, basic attacks, incoming boss skills, healing and
PvP were not rerouted.

Zodiac projection now carries its flat addition and rank separately through
both runtime snapshots. The new formula can recover authored180 without
mistaking the combined skill-plus-Zodiac value for a native base. Existing
Zodiac UI values, MP costs and other skill projections are unchanged; the
capture profile specifically uses95/rank instead of the existing100/rank.

## Why there is no blanket multiplier

The audited damaging Power1/Power2 definitions match the external client
across all four professions. Their interpretation still needs combat evidence.
The available five captured sessions are all Mage characters:

| Family | Clean initial target hits | Finding |
| --- | ---: | --- |
| Flame Blast V574 | 548 | 546 stable hits and two windup transitions fit the candidate within one damage point |
| Fireball IV503 | 13 | Its same-target Merge increase is3036; copying Flame's complete pipeline predicts3697.5672 |
| Fire Lotus IV543 | 3 | Damage depends on the target; no unique recovered formula |
| Thundercloud IV563 | 101 | Damage depends on the target, including a retained1-damage result |
| Warrior, Champion, Priest damage | 0 | No player combat capture for these professions in this source |

Fire Lotus and Thundercloud differ by26316 on each of two identical target
pairs. That is useful evidence of a shared direct-spell component, but target
defense values and all modifier ordering remain unknown. An invented1.56
Fireball coefficient would merely fit one comparison; it is not implemented.

Status-only hostile skills also use zero-damage sentinels. A blanket added
base-attack term would accidentally turn some controls into damaging skills.
Other catalog differences, such as Priest healing amounts and Expose Armor
cooldown, are recorded separately and were not bundled into this change.

## Validation

- Release server and protocol-check builds: zero warnings and errors.
- Fifteen selected checks pass, covering captured scalar outcomes, both
  runtime paths, historical formulas, status-only fallback, healing, PvP,
  Zodiac metadata, mana/cooldowns, field ownership and stale-session cleanup.
- A real-handler regression in both Legacy and ECS uses MA6760, bonus106.4%,
  crit10.1% plus1740, and Zodiac23. Initial damage and all four later pulses
  are44059; each damaged mob contributes its own healing and mana is charged
  once. Large living targets prevent corpse/reward effects from masking pulses.
- Independent replay checked the original16 numeric checkpoints and the
  broader548-hit capture comparison. External merged143 is49960; final
  nearest rounding gives49959 in the implemented candidate. No fitted offset
  was added to hide that one-point difference.
- AresMage's last verified stats project72871 before explicit encounter
  modifiers. That is a conditional model result, not a new live-client hit.

The first run exposed a test attempting to convert a negative skill ID to
the unsigned ECS wire identity. The test now asserts the existing rejection;
production validation was not weakened. The other14 checks passed, and the
corrected formula check passed after rebuilding.

Evidence: `artifacts/skill-formula-release-20260914`,
`artifacts/skill-formula-alignment-20260914` and
`artifacts/skill-formula-audit-20260914`. The release directory preserves the
build identity, source hashes, individual check reports and deployment receipt.

Remaining work for matching every skill is direct-spell mitigation and
modifier-order recovery, then combat validation for the other professions.
The current capture does not establish those formulas.
