# Wonderland scheduled attack target removal

The scheduled cast and queued reflection paths could stop the monster-world task
when a target session disappeared during incoming-status lookup. Ordinary
monster attacks already treated this as an expected stale-target rejection;
the Wonderland scheduler called the same attack processor without that catch.

Both scheduled dispatch paths now catch only
`MonsterAttackTargetUnavailableException`. The existing authority check rejects
the attack before any HP mutation. Later targets and subsequent world ticks can
continue. Unexpected exceptions still propagate to supervision.

The deterministic regression uses the existing
`RuntimeStatusSessionLookupHook`: queue a cast, pause its status lookup, remove
the target, and release the lookup. It also exercises the retained queued
reflection dispatch, both monster engines, and the ECS player engine. Direct
Rock reflection currently commits synchronously, so the queued reflection
fixture explicitly seeds that retained dispatch path. No production test hook
was added. Assertions cover no damage, no vitals revision, membership cleanup,
a surviving subsequent tick, and propagation of an unrelated injected fault.

Before the fix, the regression reproduced
`MonsterAttackTargetUnavailableException` through
`AdvanceWonderlandCombatAsync` and `AdvanceMonsterWorldOnceAsync`.
Evidence is in
`artifacts/wonderland-crash-fireblast-20260911/protocol-red.json` and
`protocol-red.log`. The fixture includes the reported valid maximum HP of
731,455; the trigger is session removal, not numerical overflow.

This proves a failure path, not the cause of the original September 11 restart.
The original fatal exception was not recorded. In particular, the currently
authored first-island Alpha, towers, Raiders, Stooges and Assaulters have no
scheduled abilities, so a strictly first-island incident cannot be attributed to
this scheduler solely from the timing of player skill 334.

Focused check:
`Wonderland scheduled casts and reflections tolerate removed targets without stopping the monster world`

The focused check passes after the fix in the clean Release build recorded by
`artifacts/wonderland-crash-fireblast-20260911/protocol-release.json`.
