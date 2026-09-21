# Isle 3 ranged Petbirds

The later user-requested adjustment in `wonderland-buff-birds-20260915.md`
supersedes the 25-unit bird range below with 12 units on both islands 3 and 7.

The requested behavior is for Isle 3's Disguised Petbirds to attack at the Arrow Tower's 25-unit reach using its native Fireball (skill 2015). This applies to both Petbird variants, leaving the Flame Rooster boss's abilities intact. Petbirds remain mobile and retain their attack cadence and fivefold Petbird Blessing.

The historical external capture uses skill 2782 for these birds. The Fireball behavior is an explicit local gameplay change, not new capture evidence.

Installed on the Tempest development server. All 24 birds have 25-unit attack and detection range, with their 64-unit leash, 1.92-second cadence, HP and attack ratings preserved. Fireball targets one player; it no longer fans out the old skill's area hit. Silence suppresses the Fireball and uses the existing fallback.

The focused behavior and captured-attack check groups passed with no skips. They cover both monster engines and all four monster/player engine combinations, including range, cooldown, chasing, native packets to the target and observer, single damage delivery, and Petbird Blessing. Results and deployment logs are in `artifacts/wonderland-isle3-ranged-20260915`.

Deployed image: `sha256:bf72f3cdc176bf0387c811a1e36b61a10af672db7c0f09887b8900e8e9919fab`; container `godswar-dev-tempest-openworld-01` passed its health check. The previous image is retained as `reborn-server:before-isle3-ranged-20260915`. No database or client files were changed for this update.

## Critical chance before the subsequent September 15 change

At this release, the server routed PvE and PvP through different chance policies. The later user-requested change in `player-pve-critical-policy-20260915.md` supersedes the following figures for player attacks on mobs.

For 200 Critical against 100 Critical Resistance, after a successful hit:

| Target | Current critical chance |
| --- | ---: |
| Player | 66.66% |
| Monster, with the higher combatant level at 140 | 6.15% |
| Level-200 Wonderland boss, attacker at level 140 | 5.83% |

PvP uses `critical / (critical + resistance)`, capped at 90%. PvE uses `5% + 45% * (critical - resistance) / (100 + 25 * max(attackerLevel, targetLevel) + critical + resistance)`, clamped from 0% to 50%. The implementation truncates to whole basis points. These examples assume the ratings already include active modifiers; misses never proceed to the critical roll.

Source: `AuthoredCombatChancePolicies.cs`, `AuthoredCombatVersions.cs`, and `PlayerSkillDamageFormula.Chances` under `src/Godswar.Server/World/Systems/Combat`. Numeric evidence is saved in `artifacts/wonderland-isle3-ranged-20260915/critical-chance-explanation.json`.
