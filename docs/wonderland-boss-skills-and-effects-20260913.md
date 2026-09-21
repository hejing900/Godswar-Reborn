# Wonderland boss skills, measured damage and visual effects

## Current server damage before mitigation

These are **normal, noncritical skill-hit values with zero defense, absorption
and incoming damage modifiers**. They are exact for the current configured
server profiles, but the profiles remain estimates of the external server.
They do not claim recovery of original external raw PA/MA.

| Boss | Skill / matching effect | Current unmitigated normal damage |
|---|---|---:|
| Alpha Demon | Area melee 2805 | 14,123 |
| Capritaur Derskey | Ice area spell 2022 | 14,464 |
| Depraved Monkeyface | Area melee 2803 | 16,923 |
| Flame Rooster | Custom Fire Blast 580 | 45,000 |
| Outrageous Rock Spirit | Flame Blast effect 2178 | 22,164 |
| Athenian Marshal Addis | Area melee 2004 | 25,926 |
| Spartan Marshal Knocker | Area melee 2004 | 26,163 |
| Depraved Platinum Dragon | Ice area spell 2022 | 22,864 |
| Iberian Multi-Head | Star Shower effect 2021 | 22,864 |
| Minotaur | Area melee 2803 | 22,523 |
| Titan's Xmas Deer | Flame Blast effect 2178 | 22,864 |
| Iberian Dragon King | Star Shower effect 2021 | 23,564 |
| Scorpion King | Meteor Blast effect 2192 | 32,323 |

`ResolveWonderlandMonsterAttack` applies `WonderlandCapturedAttackPolicy` for
the copied primary attacks, then calls the basic-damage formula with coefficient
1 and no flat skill power. `MonsterCombatProfile.ToAttackerStats` supplies no
typed outgoing bonus or append damage. Therefore the effective rating is also
that copied primary skill's unmitigated normal damage. The visual skill's client
Power fields are not multiplied again. These effective ratings are not separate
measurements of a boss's raw attack stat and skill coefficient.

Rooster's custom cast instead calls the skill formula with coefficient 2.5:
`18,000 * 2.5 = 45,000` at zero defense. Its ordinary magical hit is 18,000 before
mitigation. Critical hits and silenced fallback attacks are different outcomes
and are not represented by the primary normal-hit table.

## Captured damage after mitigation and visual effects

Damage in the table is the normal HP loss recorded on external against xPade,
Mage 143, with PD 5,379, MD 2,920, displayed Absorb 4,791 and Shield 234 active.
Addis was measured against -Alboz-, Mage 139, with PD 4,566, MD 2,630 and Absorb
3,995. These are resolved hits, not original raw PA/MA or guaranteed damage to
other characters. See [damage recovery](wonderland-damage-recovery-20260913.md).

Names such as Star Shower identify the matching English player-skill effect
when the boss Magic.ini entry is only named AOE Spell. The boss uses its own
model's attack action, rather than the player's casting animation. Visual
descriptions below are supported by decoded embedded textures and matching
client skill/help definitions. They do not claim a live animation playback test.

| Island | Boss | Captured primary skill / effect | Recorded hit | Effect appearance |
|---|---|---|---:|---|
| 1 | Alpha Demon | Area melee, 2805 | 3,953 | Orange-red circular rune/sigil with amber light streaks. |
| 2 | Capritaur Derskey | Ice area spell, 2022 | 6,753 | Blue/cyan ice streaks and a glowing blue magic circle. |
| 2 | Depraved Monkeyface | Area melee, 2803 | 6,753 | Same orange-red rune-circle effect as Alpha. |
| 3 | Flame Rooster | Normal Attack, 2000 | 4,713 | Ordinary attack/hit effect; our retained custom Fire Blast is described below. |
| 4 | Outrageous Rock Spirit | Flame Blast effect, 2178 | 14,453 | Red-orange fire streaks, yellow flare and vertical fiery glow over the affected area. |
| 5 | Athenian Marshal Addis | Area melee, 2004 | 17,365 on -Alboz- | Golden-orange rune-circle burst, pointed golden streaks and orange glow. |
| 5 | Spartan Marshal Knocker | Area melee, 2004 | 15,993 | Same golden-orange area-melee effect as Addis. |
| 6 | Depraved Platinum Dragon | Ice area spell, 2022 | 15,153 | Same blue/cyan ice-and-circle effect as Derskey. |
| 7 | Iberian Multi-Head | Star Shower effect, 2021 | 15,153 | Fiery falling meteor streaks and an orange magic circle. |
| 8 | Minotaur | Area melee, 2803 | 12,353 | Same orange-red rune-circle effect as Alpha and Monkeyface. |
| 8 | Titan's Xmas Deer | Flame Blast effect, 2178 | 15,153 | Same red-orange fire-streak effect as Rock Spirit. |
| 8 | Iberian Dragon King | Star Shower effect, 2021 | 15,853 | Same fiery meteor-shower effect as Multi-Head. |
| 8 | Scorpion King | Meteor Blast effect, 2192 | 22,153 | Purple/orange circular sigil, bright streaks/sparks and a fiery layer. |

The ordinary primary skills have zero separate client cooldown and are sent with
each attack, typically about 1.92 seconds apart in the capture. Our copied attack
cadence is 1.92 seconds. Each attack is presented by its primary 10046 effect,
a 2000 impact, and one 10026 damage result; it does not apply the damage twice.
Silence can replace the primary skill with the captured basic attack.

The current server's effective ratings were fitted to a reference test setup.
Client Power1/Power2 values are not applied on top as another multiplier for
these copied ordinary boss attacks. Applying them again would not reproduce the
captured hit values. Their exact external raw attack/formula remains unresolved.

## Rooster's retained custom Fire Blast

The requested island-3 exception keeps our existing skill rather than replacing
it with the external Rooster's ordinary attack:

- Fire Blast 580, with the orange/yellow flame-burst visual used by Fire Blast
  1–3; it is distinct from Flame Blast's streak effect.
- 18,000 magic attack, 2.5 multiplier, four-second cooldown, 1.2-second windup.
- 45,000 nominal damage at zero defense, before other modifiers. The authored
  calculation applies the multiplier after subtracting effective magic defense,
  then applies the remaining damage modifiers/absorption; 45,000 is not the
  final hit against xPade.
- Its ordinary attack interval remains two seconds.

## Current additional boss mechanics

- Derskey reduces incoming physical damage by 80%.
- Monkeyface reduces incoming magical damage by 80%.
- Rock Spirit reflects 10% of the committed direct damage through its encounter
  reflection mechanic. This is separate from its Flame Blast effect.
- Scorpion's primary 2192 applies Internal Injury for 20 seconds. Our current
  implementation reduces physical defense by 15%; that exact external formula
  has not been verified. In the capture the basic hit changes from 9,213 to
  10,980 under the status, while primary 2192 remains 22,153.
- Multi-Head keeps the authored 18,000 dodge. Putrid Bird hits supply the
  requested +25,000 hit buff for 15 seconds; this is a supporting-mob mechanic.

The current Minotaur primary 2803 has no separately configured armor-break proc.
The copied island-2 bosses do not retain the former invented random-stun proc.
The latest full run shows Scorpion's Meteor Blast primary and its basic fallback;
it supplies no separate Spear Blast cast to copy. Ice visuals alone do not imply
a freeze status.

## Visual verification and sources

All eight inspected complete effect packages, including their embedded model
and texture data, are byte-identical between external and Origin:

- Area melee 2803/2805: `effect_conjuration_005_all.gwm`.
- Marshal area melee 2004: `effect_conjuration_006_all.gwm`.
- Ice area spell 2022: `effect_ice_002_all.gwm`.
- Star Shower visual 2021: `effect_fire_003_all.gwm`, also used by player 550/551.
- Flame Blast visual 2178: `effect_fire_004_b.gwm`, also used by player 573/574.
- Meteor Blast visual 2192: `effect_spear_009_b.gwm`, also used by player 332–334.
- Custom Rooster 580: `effect_fire_002_all.gwm`.
- Supporting Demonic Raider/Atlas 2179: `effect_fire_002_b.gwm`, shared with
  player Fire Blast 583/584. Their packets use this higher-rank Fire Blast visual.

The body action requested by most copied boss skills is `nomal_attack_01`.
2803/2805 request `nomal_attack_09`. Monkeyface's model includes that action;
Alpha and Minotaur's models do not, in either client. This limits claims about
their exact body motion/fallback even though their effect assets match.

Evidence is in `artifacts/wonderland-damage-inversion-20260913/`:
`boss-effect-composition.json`, `boss-effect-visual-audit.md`,
`native-fire-ice-effect-assets.json`, `FIRE-ICE-VISUAL-EVIDENCE.md` and extracted
static texture previews. Packet/skill bindings and full client comparisons are
in `artifacts/wonderland-full-external-20260913/`.

Current implementation: `WonderlandCapturedAttackPolicy.cs`,
`WonderlandBossAbilityPolicy.cs`, `WonderlandMonsterPlan.cs`, and the Wonderland
combat State, Resolution and Commits partials. This document records inspected
behavior; it makes no server or client balance changes.
