# Wonderland crash and bird Fireblast investigation — 11 September 2026

The reported disconnect coincides with Tempest's `monster_world` task faulting
at `2026-09-11T06:11:04.6314085Z`, followed by a process restart. Docker reported
no OOM. The existing runtime catch discarded the exception, so the original
failure's type and stack cannot be recovered from that log. No fresh Origin
crash dump or Windows application-error record was found; that does not prove
the client itself could not also have closed.

The player was on Wonderland island 1 and had just cast Meteor Blast V (334).
The authoritative log contains valid HP maxima of 221,380 and 731,455. Review
found no plausible HP arithmetic overflow at those values.

## Bird presentation

The external capture contains eleven Demonic Raider attacks. Every attack has
two 24-byte **10046** effect packets, skill **2179** followed by **2000**, before
the existing 32-byte **10026** damage packet. The previous analysis searched
10045 and missed 10046, which caused the missing Fireblast animation.

Both server combat engines now prepend the captured effect sequence for these
first-island birds. Origin already contains skill 2179's monster Fireblast
effect and its normal attack pose. Damage, the 1.92-second attack interval,
target selection, and HP mutation remain unchanged. The implementation sends
one damage event, including correct local-player and observer identities.

The same omitted opcode affected the remaining first-island roles. The full
capture audit found 564 presentation packets for 282 attacks. Their native
pairs are restored as well: Alpha 2805/2000, towers 2015/2000, and Stooges and
Assaulters 2000/2000. Installed effect bindings were checked against external.
Each pair still precedes a single damage result and adds no server ability.

See [capture and client evidence](wonderland-bird-fireblast-20260911.md).

## Monster owner and player vitals lock order

An elemental secondary effect holds the attacking character's `VitalsSync`
lock while submitting its monster mutation to the world owner. The monster
tick previously ran target projection on that owner and waited for the same
vitals lock. The two operations could block each other until the one-second
owner invocation deadline stopped `monster_world`.

The deterministic regression uses a real committed primary hit and elemental
Shock, then starts the monster tick while that effect owns the vitals lock.
Before the fix it raises `TimeoutException` in `BoundedSingleOwnerMailbox.Invoke`
through `AdvanceMonsterWorldOnceAsync`, retained in `protocol-lock-red.json`.
This reproduces a server-stopping path reachable during elemental area attacks;
the discarded original exception prevents claiming that incident's exact stack.

Target projection now occurs outside the owner. The owner revalidates object,
ownership, world revision, membership epoch, and life before advancing with the
captured scalar targets. Final damage authority checks are retained. A guard
prevents the convenience projection API from being called inside a mailbox.

## Scheduled target removal

A deterministic regression reproduces an uncaught
`MonsterAttackTargetUnavailableException` when a Wonderland scheduled skill
loses its target while waiting for status lookup. Ordinary monster attacks
already tolerate this expected race; scheduled casts and queued reflections
now do too. The test also ensures unexpected simulation faults still reach
supervision. First-island actors have no scheduled skills, so this separate
proven bug is not established as the original crash's cause.

See [race evidence](wonderland-scheduled-target-race-20260911.md).

## Runtime diagnostics

The host now records `runtime_failure` with the exception type and up to eight
`runtime_failure_frame` method identities. Async method names are retained
instead of collapsing to `unknown` during telemetry sanitization. Exception
messages, SQL, connection details, argument values, and file paths are omitted.
Startup diagnostics retain their existing event identities.

Validation and deployment evidence is retained under
`artifacts/wonderland-crash-fireblast-20260911/`. Release status is recorded
there after the final checks and Tempest-only deployment finish.

Release validation: solution build has zero warnings/errors; all 47 selected
protocol checks and five isolated PostgreSQL integration checks passed, with
no skips. This includes both lock-order and stale-target regressions, prepared
target identity/life rejection, both combat engines, Medusa ownership, corpse
loot, transport, revival, entry countdowns, item rewards, and safe diagnostics.

## Deployed result

Tempest restarted at `2026-09-11T06:44:22.0743347Z` with image
`sha256:157e7495a688943a7c19c251f3584ef7caad1179d5e20274c34aef711972a003`.
Health checks passed with zero restarts. Existing port bindings, item-content
revision, 150-migration schema, Holy Suit policies, and owned inventory were
verified unchanged across the stopped deployment. Dwargon remained stopped.

A full database backup was taken before deployment and the previous image was
retained as `reborn-server:before-wonderland-crash-fireblast-20260911`.
Only test25's confirmed crashed Wonderland entry at `06:10:33Z` (reservation
`e32bd412-2de1-4b18-9e01-1e8b4008eace`) was compensated, leaving two used entries
for the current realm day. The exact row and compensation script are retained
with the backup. Native in-client rendering still requires the user's retry;
the checks validate captured bytes, installed bindings, and server behavior.
