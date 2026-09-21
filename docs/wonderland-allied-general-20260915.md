# Wonderland allied marshal help — September 15, 2026

The helping marshal on Isle 5 now attacks the opposing marshal within 12 map
units. The previous three-unit reach required the models to nearly overlap,
so a nearby lure could fail to receive help. When both soldiers and the enemy
marshal are in reach, the allied marshal prioritizes its opposing marshal.
Supporting soldiers retain their existing target selection and reach.

The opposing marshal has 42,500,000 HP, five times its original 8,500,000. The
allied marshal remains at 8,500,000 HP. This corrects the initial application
of the fivefold increase to the allied marshal. The allied role follows the admitted
party faction, and these values are independent of party size.

Each allied attacker reads current target snapshots. This avoids rejecting a
valid later attack merely because an earlier allied hit changed the target's
health revision during the same tick. Native skill 2004/2000 presentation,
attack cadence, stun blocking, protected allied actors, and absence of player
kill rewards for NPC aid are preserved.

Validation: `Wonderland real combat controls` and `Wonderland boss balance`
protocol groups. The real combat check covers both factions and all four
Legacy/ECS monster/player combinations, lures the enemy using the live monster
engine, verifies attacks outside the old reach, preserves competing soldiers,
checks damage and native packets, blocks a stunned ally, and checks the HP
presented by the actual runtime. The policy check validates all five party
sizes. Corrected HP results: `artifacts/wonderland-enemy-hp-20260915/checks.json`.
