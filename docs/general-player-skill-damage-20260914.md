# Shared player skill damage — September 14, 2026

Status: implemented, validated and deployed to Tempest on September 14, 2026.

The user explicitly selected a common rule for damaging player skills:
retain the normal attack contribution and add the skill's contribution on top.
Version4 applies this design across currently admitted player DPS skills,
including physical and magical classes, single-target and area skills,
periodic damage, PvE and supported PvP/training-dummy contexts. Existing
profession, target, ownership and network admission rules still decide whether
a skill may execute. This formula change does not open new PvP targets.

This is an authorized gameplay design. The external Flame Blast analysis
motivated it, but the available captures do not verify the complete formula
for every skill or class. The recorded outgoing characters were Mages, and
direct Fireball/Fire Lotus/Thundercloud show target-dependent damage. Their
observations must not be labeled exact validation of a universal external
formula. See the bounded [skill coverage artifact](../artifacts/skill-formula-alignment-20260914/README.md).

## Version4 calculation

Skill `Property` selects physical or magical attack, defense, penetration,
damage bonus, append, reduction and absorption. Character profession does not
override a skill's channel. For a landed hit:

```text
effectiveDefense = typed defense after existing capped penetration
effectiveAttack  = max(0, typed attack - effectiveDefense)
coefficient      = max(0, 1 + projected Power1)
authoredFlat     = projected Power2 - flat Zodiac contribution
skillAdditional  = (effectiveAttack + authoredFlat) * coefficient
core             = effectiveAttack + skillAdditional + flat Zodiac contribution
typedDamage      = core * (1 + typed damage bonus)
```

Each rank keeps its own published coefficient and authored flat power.
`Power1=-0.5` means an additional50%; it does not replace the entire normal
attack contribution with50%. Percentage Zodiac training adjusts the skill's
coefficient once. Flat Zodiac training for DPS contributes95 per selected
rank after that coefficient; it is kept separate from the authored flat power
to avoid multiplying it twice or treating it as a different native rank.
Healing and non-DPS training retain their own existing rules.

Hit and critical chance remain conditional. This September 14 release used V1
chance for PvE and V2 for PvP/training. The September 15 player critical-policy
update supersedes PvE critical chance with the PvP ratio while keeping its
accuracy curve; see `player-pve-critical-policy-20260915.md`.
A miss commits zero damage and no on-hit effects.
Flame Blast no longer uses an automatic critical outcome merely because all
observed external frames were critical-coded.

On a critical hit, the unmitigated critical total is:

```text
typedDamage * 1.5 * (1 + critical damage percentage) + critical flat damage
```

Critical percentage and fixed cancellation reduce only the bonus above
`typedDamage`, clamped at zero. Normal hits do not gain these critical-only
modifiers. The remaining order is:

1. Add the selected physical/magic flat append damage once, after critical
   calculation. It is not multiplied by critical damage.
2. Apply the target's typed percentage reduction and damage-taken increase.
3. Subtract typed flat absorption.
4. Round once at the final boundary, preserving saturation and the positive
   landed minimum-one rule.

Keeping append preserves the effects of valid equipment, Fire Spirits and
pet Merge attributes. For example, the previously audited AresMage state had
3036 magic append from equipment and Merge; removing that channel from every
skill would silently disable those bonuses. It remains a separate modifier
outside the user-selected attack-plus-skill core.

An authored zero-damage control cannot become DPS through the added base
attack term, Zodiac training or flat append. Heal, Area Heal and beneficial
status skills retain their dedicated handlers. Malformed projection metadata
does not authorize a new damage path.

## Known client display limitation

The installed `en_us` and `zh_cn` Zodiac slot tooltips still show the local
`SkillTrainConfig.lua` flat table at 100 per rank. For DPS this overstates the
V4 contribution: rank 23 displays 2300 instead of 2185, and rank 50 displays
5000 instead of 4750. Healing and control training retain 100 per rank. This
is a display mismatch; the server uses 95 per rank for DPS.

`SkillTrainProc.lua` reads only grid rank. The registered native
`GetSKGirdAttr` function at `0x695650` returns one rank byte from the grid
record, with no selected-skill accessor; the existing `GetConsAttr` switch
also exposes no grid selection. A bounded search found no supported Lua
getter for the selected skill kind, so no selective client correction was
made. The prior Type-2 MP tooltip repair remains unchanged.

## Runtime boundaries

Legacy and ECS adapters must consume the same immutable skill projection and
produce the same version4 result for identical admitted inputs. Existing event
identity, source/target life and membership checks, damage commit order,
per-target lifesteal, mana/cooldown charging, rewards and packet visibility
remain authoritative.

Flame Blast's initial hit and existing four scheduled continuations use the
same shared resolver. This task does not add pulses, change their timing,
replace animations, or charge resources per continuation. The changed damage
can affect kills, actual lifesteal and subsequent rewards through their
existing rules; tests must check those consequences without inventing extra
damage packets.

Historical V1/V2 formula implementations remain available for prior evidence.
The earlier captured Flame profile is retained explicitly as historical V3,
rather than silently rewriting what its recorded version means. Incoming
monster attacks and basic attacks keep their existing formulas.

## Validation and deployment

The new `GeneralPlayerSkillDamageFormulaChecks` covers25 published rank rows
across Warrior Light Chop, Champion Spear Hit, Priest Ice Shot, Mage Fireball
and Flame Blast. Literal independently calculated normal/critical endpoints
check base attack, each rank's powers, channel selection, typed mitigation,
critical cancellation, append order and flat training. It also checks that
the chosen PvE/PvP chance policies and Legacy/ECS scalar evidence agree,
including normal, critical and miss outcomes and zero-damage controls.

Current-route assertions requiring intentional updates include the direct
Zodiac skill endpoints, training-dummy version/evidence checks and the former
automatic-critical Flame integration fixture. Historical tests must call the
historical version explicitly and keep their original numeric expectations.
The V1 parity file contained current resolver calls despite its filename;
those historical setup calls are now anchored to V1, while its current adapter
comparison is updated separately.

Release builds of the server and protocol checks passed with zero warnings and
zero errors. All 16 selected checks passed with no skips or unmatched filters.
The first run passed 14 checks and exposed two stale current-formula test
expectations. After updating those expectations, both affected checks passed.
The original reports and the composed latest-result summary are retained in
`artifacts/general-player-skill-damage-20260914/`.

Coverage includes the general formula and catalog, historical V3 replay,
Legacy/ECS parity and live adapters, admitted training-dummy combat, defensive
and offensive Zodiac, support/control routing, basic PvP, cast lifecycle,
Flame Blast placement and scheduled pulses, and per-monster actual lifesteal.
No external-server parity for every class or live client rendering is claimed.

Deployed to `godswar-dev-tempest-openworld-01` at
2026-09-14 12:40:14 NZST (00:40:14 UTC), image
`sha256:d7c83f7eabf9a07e1d0c114de0265bd37d871fb4e242d7dd69661f74ca6ba474`.
Startup verified healthy with zero restarts. The deployed assembly contains
the V4 resolver and projection metadata; all 11 recorded source hashes stayed
unchanged. Schema, all 11 publications, inventory, talents, ports and other
services matched the pre-deployment invariants. The release folder contains
the verified database backup, checksummed reports and deployment receipt.
The preceding V3 image is retained under
`reborn-server:before-general-player-skill-damage-20260914`.
