# Monster return and encounter reset

Living Wonderland monsters and bosses now regain full HP when their return reaches
their original spawn. They remain damaged and immune to incoming attacks during
the return. This uses the same living spawn generation, increments its health
revision once, clears threat and control effects, and permits combat after the
arrival is published. Never-respawn still means a dead instance monster stays
dead; normal timed monsters retain their existing full-health replacement.

Return movement now sends each authoritative step through native `0x2720`
continuations and an exact-home `0x2721` stop. The client field at offset 12 counts
the preceding movement segment's ticks: the earlier return sent one long start
but ended it as a one-tick segment. Chasing already emitted per-step continuations;
returning now uses the same cadence. Isle 8's optional navigation follows accepted
collision-grid steps on the way home, including around corners, and cannot heal
or snap to home merely because a waypoint was reached.

Arrival sends absolute HP through native `0x2771`, after movement-end. Native
handler `0x4ECC43` resolves any world object and writes HP/MP, so no remove/spawn,
healing animation, or notification is needed. The existing viewer transition gate
covers this packet and the health-revision acknowledgment together. Older damage
cannot be applied after this absolute refresh, and the next ordinary hit does not
mistake the reset for a missing health delta. An already-at-home reset remains in
its arrival phase until the queued stop and health update have been published.

Validation: four Release protocol groups passed with no skips: Wonderland return
and full-HP publication, Legacy/ECS shadow parity, ordinary leash replacement, and
real-socket return/replacement packet ordering. The new Wonderland check exercises
both monster engines, each return step, exact-home restoration, native absolute HP
ordering, a subsequent hit without remove/reappearance, and an immediate at-home
reset. Existing Never-respawn death coverage still proves dead monsters stay dead.

Results: `artifacts/wonderland-reset-20260915/checks.json`. Read-only native evidence:
`artifacts/wonderland-reset-20260915/native-return-health-contract.txt`.
