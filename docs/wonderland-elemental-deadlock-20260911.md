# Wonderland stopped updating during combat

At 06:57:03 UTC on 11 September, Wonderland combat and movement updates
stopped. The client subsequently closed, but the server retained three TCP
connections in CLOSE_WAIT, including unread client data. Docker still marked
the process healthy because its management endpoint and process remained up.
The recent combat log was historical; hits were not continuing after closure.

Two managed thread snapshots from the still-stalled server establish the
cause. Thread 0x12 was processing a basic attack's derived elemental damage.
`CommitPveElementalHits` held its elemental transaction lock, character vitals,
and elemental state, then waited for the registry lock in
`TryApplyWonderlandMonsterDamage`. Thread 0x361 was running periodic player
recovery, holding that registry lock while waiting for the same character's
vitals/state. World updates, later login attempts, and membership cleanup
then also waited for the registry lock.

Evidence is retained in
`artifacts/wonderland-mobs-visual-20260911/live-server-stacks.txt` and
`live-server-stacks-confirmation.txt`. These contain managed method stacks,
not a heap dump. The diagnostic collector was installed in a task-local
directory and copied temporarily into the affected container.

## Fix and verification

Direct PvE elemental commits acquire the registry lock before their existing
transaction, character-vitals, and elemental-state locks. This matches
periodic recovery and the Wonderland mutation path. The six basic, single
skill, and area attack callers were reviewed, along with monster burns,
player burns, kill recovery, and reflection. Captured entitlement, replay
protection, damage values, effect packets, and attack timing are preserved.

The focused regression primes the actual first-island Zeus fourth-hit effect
and crosses the competing periodic-recovery lock boundary with a bounded
probe. Before the fix, the probe acquired the registry lock but could not
acquire vitals while the elemental hit retained them. That failing result is
saved in `artifacts/wonderland-elemental-deadlock-20260911/protocol-red.json`.
The check also verifies actual derived damage, replay rejection, and usable
recovery, monster-world, and membership operations after the commit.

The earlier owner/vitals regression is retained with its focused projection
barrier, so the registry serialization cannot conceal a return of that
separate bug. The new release's checks and deployment evidence are retained
under `artifacts/wonderland-elemental-deadlock-20260911/`.

Release verification completed with zero build warnings/errors, 48 passing
protocol checks, and five passing isolated PostgreSQL checks, with no skips.
The new regression also verifies that actual session removal completes and
leaves the instance population at zero after elemental combat and recovery.

## Deployment

Tempest restarted at `2026-09-11T07:17:46.6853711Z` with image
`sha256:bf0fc24f1d73bef786f13093329cda402845a72d179a086211a743bfc8537ea7`.
The live post-deployment stack snapshot has no registry threads blocked on
monitors; the game port has its listener and no retained CLOSE_WAIT sockets.
The process has zero restarts and reports ready. This supplements, rather
than relies solely on, the management health status that missed the deadlock.

The full stopped database was backed up, and the preceding image remains
tagged `reborn-server:before-wonderland-elemental-deadlock-20260911`.
Item publication, schema, Holy Suit policies, owned inventory, and port
bindings were verified unchanged. Only test25's failed entry for run
`ca7cd18247eb4991b8de0d9866872a67`, reservation
`b1ea91d5-312a-4c87-85d5-54df20d78b20`, was compensated; two used entries remain
for the current realm day. Temporary diagnostic and database deployment files
were removed from the containers after verification.
