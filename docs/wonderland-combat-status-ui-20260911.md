# Wonderland combat status UI

Wonderland's player effects now use the normal complete `10167` status list. The former Petbird, Putrid Bird, stun, silence and armor-penalty `ServerNote` notifications were removed. The encounter remains the only authority for their combat modifiers, controls and deadlines; the new client entries are presentation only.

| Client status | Effect | Duration |
| --- | --- | --- |
| 1510 | Petbird blessing, total 5x attack | 15 seconds |
| 1511 | Putrid Bird blessing, +25,000 Hit | 15 seconds |
| 1512 | Wonderland stun | 2 seconds |
| 1513 | Wonderland silence | 2 seconds |
| 1514 | Scorpion Spear Blast, physical defense -40% | 8 seconds |
| 1515 | Minotaur Armor Rend, physical defense -50% | 10 seconds |

These dedicated client definitions use separate kinds and existing native icons, with no client-side stat effects. They cannot overwrite a class buff such as Sacred Zeal by sharing its status ID or kind. Native beneficial/total presentation limits remain enforced by `PlayerStatusCapacityPolicy`.

## Publication and authority

The layer is merged by the common full-status snapshot path, including normal skill refreshes and self/viewer queries. Its fingerprint includes authoritative expiry and life identity. Refreshing an effect updates the existing icon's countdown rather than stacking copies. Final admission recomposes the layer, preventing a delayed viewer snapshot from restoring an effect that expired or cleared after capture. Wonderland viewer queries require a valid membership route and cannot use the raw fallback.

Combat only marks a session for reconciliation. The monster pump publishes after combat transactions release their locks, taking the status gate before the registry gate. No registry, player-vitals or elemental lock waits for the status gate. Ordinary socket-close errors are handled after releasing that gate.

Tracking remains until an admitted full snapshot has cleared the encounter icons. A query may expose an icon before the regular publisher updates its cache, so an inactive tracked session forces one clear even when that cache still says baseline. Conversely, clearing an effect just after an active packet commits retains tracking for the next clear. Dead lives, departed islands and replaced account sessions cannot retain authoritative effects or redirect them to a new session.

## Regression coverage

The focused check is **Wonderland timed buffs and controls merge into native status UI without notification boxes**. It exercises all four combinations of legacy/ECS player and monster engines:

- Real Petbird attacks, including misses, preserve the total 5x mechanic and Sacred Zeal while showing one timed icon.
- Real stun, silence, Putrid Bird and both armor abilities retain their server mechanics and authored native countdowns.
- Refresh, exact expiry, island departure, death, life advance and account replacement remove or reject stale presentation.
- A normal self query before the first pump still receives a subsequent clear.
- A clear just after an active packet commits still receives a subsequent clear.
- A viewer envelope captured before clear/expiry is rejected at final admission; unavailable routes send no unfenced fallback.

Release build and protocol results are recorded by the coordinated release runner under `artifacts/wonderland-status-loot-20260911/`. Persistence is unchanged by this status presentation change.
