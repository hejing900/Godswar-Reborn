# Damage Rebound applies only to players

The authoritative game rule is that Damage Rebound affects players, never mobs. The earlier explanation correctly identified the source of the automatic Atlantis deaths but incorrectly treated that server behavior as intended.

Both Legacy and ECS monster attack paths now commit only their ordinary player damage and existing independent effects. They no longer calculate stat rebound, damage the attacking monster, prepare a rebound kill reward, send a rebound damage/death packet, or advance an instance score through rebound. The obsolete PvE rebound transaction field, commit ledger and packet helpers were removed. The generic kill-reward callback registration remains available for legitimate player attacks and other existing effects.

PvP still applies fixed and percentage Damage Rebound to the attacking player, with its existing health cap and non-recursive behavior. The max Cupid's 60,879 fixed rebound value is preserved for PvP. Player-versus-monster life absorption continues to heal from committed player damage. Gaia's separately authored elemental reflection is unchanged; it does not consume Damage Rebound stats.

Regression coverage includes both combat engines, monster attacks against players carrying large fixed/percentage rebound, and live PvP damage packets for percentage and max-Cupid fixed rebound. Verification and deployment evidence are stored in `artifacts/rebound-pvp-only-20260910/`.

Validation passed all 46 focused checks in both Debug and Release with no skips; both solution builds had zero warnings and errors. The incoming-attack regression covers all eight combinations of Legacy/ECS monster and player runtimes and physical/magical damage, including repeated hits, replay, misses and cancellation. Monster health, lifecycle revisions, kill rewards and Atlantis score remain unchanged.

Deployed image `sha256:9f12501e7a89ad3601a4ef34e7f282715c82d4d5352c7b146533dbe3318b56da` to `godswar-dev-tempest-openworld-01` at `2026-09-09T12:38:01Z` (September 10 local time). The container is healthy with zero restarts, login and game listeners ready, and the live isolation check passes. Schema remains at 144 migrations. The previous image is retained as `reborn-server:before-pvp-only-rebound-20260910`.
