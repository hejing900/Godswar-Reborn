# Player critical chance against monsters

Player attacks now use the same critical chance against monsters as against players:

`min(90%, Critical / (Critical + CriticalResistance))`

Negative ratings clamp to zero. Both ratings zero means zero critical chance. The result truncates to whole basis points, so 200 Critical against 100 Resistance gives **66.66%**, independent of level. The roll occurs only after an attack lands.

`AuthoredPlayerPveCurrent` shares the exact critical policy used by `AuthoredCombatV2`, while retaining the existing PvE Hit/Dodge curve. Both legacy and ECS player basic attacks route through it. The common player skill formula and its fallback use the same policy, including Fireball, Flame Blast pulses, and other damaging skills. Version 5 records the changed critical policy; the normal/critical damage calculations, defense, damage modifiers and database resistance ratings are unchanged.

The request concerned the player's chance against mobs. Incoming monster attacks and historical capture replay keep their previous formula. PvP retains its existing behavior.

Validation includes independent rating/level endpoints, deterministic rolls, miss handling, actual legacy/ECS basic attack delivery, critical packet flags, and skill DTO/snapshot parity. The detailed reports are `artifacts/player-pve-critical-policy-20260915-checks.json` and `artifacts/wonderland-revive-crit-20260915/`.
