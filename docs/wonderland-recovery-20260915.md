# Wonderland revival and Blackmarket recovery

Free revival anywhere in Wonderland now returns the player to the first-island entry at `(169,-216)`, with the existing 10% HP/MP recovery. Admission, free revival, and the first-island recovery destination now agree on that landing. The encounter timer, island progress, enemies, rewards, and daily admission are preserved. Revival during the completion treasure window follows the same rule.

The entrance Blackmarket Teleporter keeps the installed client's actual choices:

| Choice | Silver | Recovery |
|---|---:|---|
| Speedy Teleport (59) | 5,000 | Preserve current HP/MP |
| Teletransport with full HP (62) | 6,000 | Restore HP |
| Teletransport with full HP and full MP (63) | 8,000 | Restore HP/MP |

All choices travel to the entry of the furthest unlocked island, capped at island eight. Before Alpha Demon is defeated, they recover the player at island one's entry. The previous first-boss prerequisite prevented that initial recovery service. The server now passes the exact admitted reservation from the active run; PostgreSQL verifies the character's durable admission before permitting a first-island debit. Further-island shortcuts retain the existing settled-completion proof. No schema change is required.

The external capture also proves that failures for selections 62 and 63 use shared response function 59 with result 141, rather than responding under the chosen function. The response writer now follows those bytes. The request contract already matched the native 92-byte action, repeated function, and sub-ID -1. Existing single-use dialogue, proximity, ownership, life, wallet, replay, and exact refund checks remain in force.

Verification: Release build passed with zero warnings/errors. Seven handler groups cover every island's revival, the completion window, all eight transporters, admission and claim preservation, every paid choice immediately after revival both before Alpha and after two cleared islands, insufficient silver, replay, and life/registration compensation. The terrain/roster/death-ledger group also passed, retaining the original capture vectors and documenting the first-entry override. The PostgreSQL paid-transport group passed in an independently migrated/seeded disposable database, including first-entry admission failures and concurrent debit/refund replay. The disposable database was removed afterward; no live data was changed during verification.

Reports are in `artifacts/wonderland-recovery-20260915/`. Deployment and installed-client playtesting are reported separately by the release owner.
