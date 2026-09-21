# Wonderland revival, boss corpse loot, and treasure gems

The follow-up release separates the two reward sources: original boss sacks
come only from defeated bosses, while each cleared island's treasure box gives
four gems. A treasure-box claim does not consume a boss-corpse claim.

The user specified four gem pieces without a grade/type. The current balance
choice, stated during implementation, is four bound Grade IV gems. Each piece
has an equal independent chance of Sapphire IV (4213) or Emerald IV (4223).
There are sixteen equally likely rolls and five possible aggregate mixes.
The store preflights every possible mix before drawing RNG, freezes the actual
reward in the durable receipt, and preserves a full-bag claim for retry.

## Boss corpses

Each hostile boss gives its original bound sack once to each eligible original
participant. Both island-two bosses give Capritaur Ajax's Sack (4451). The
enemy marshal gives its faction-specific original sack; the allied marshal
does not give one. The final four bosses individually give 4458, 4459, 4460,
and 4461. The already implemented sack-opening contents remain unchanged.

The native corpse is retained, publishes the existing 10029 drop message, and
uses the existing 10048 pickup acknowledgment to remove that player's sparkle
after collection. Other eligible party members retain their own loot. New
viewers, revived players, and players returning into view receive the dead
appearance and loot again. No new art or client patch is required.

Pickup requires a canonical 16-byte request, the claimant's object ID, the
correct loot index, an alive current admitted member in the exact instance,
and a distance of at most 12 units. The server resolves every reward field
from its committed boss-death state. A boss can be looted before the rest of
its island is cleared. Inventory, claim, audit, inbox and item-ledger changes
commit under the current ownership and character locks. Retries return the
old receipt; full bags and transaction failures preserve the entitlement.

Corpses remain through the active run, and completion extends them through the
full five-minute treasure window even when it ends after the original run
deadline. Cancellation retires them immediately. Surviving monsters are not
converted into deaths or loot.

## Revival and chest interaction

The client resets its actor animation during scene relocation. If the native
HP value is still zero at that moment, it selects death animation 4. Wonderland
revival now publishes restored HP/MP before the scene-reset packet, after the
server has committed the relocation and validated its authority. Nearby
players receive the existing removal/reappearance sequence. Invalid and
repeated revival requests do not produce another life transition. See the
[native revival audit](wonderland-native-death-revival-20260911.md).

A valid island-box click now opens its original native NPC description before
showing the claim result. Locked boxes show their description but grant no
reward. The existing settled island-clear, proximity, admitted-member and
once-per-island rules remain. See the [chest click audit](wonderland-chest-click-20260911.md).

## Validation

The Release build has zero warnings or errors. All 24 selected protocol checks
pass, including four combinations of the Legacy/ECS monster/player engines,
native revive ordering, raw loot requests, independent party sparkle, current
inventory projection, full-bag retry, corpse visibility and terminal cleanup.
Six database checks pass, including four-gem chests and independent boss sacks,
concurrent/restarted replay, account recreation, preserved owned attributes,
stale ownership rejection and fault-injected transaction rollback. An unrelated
historical item-catalog check selected by an overly broad filter was skipped
by its disposable-database naming guard; it is not part of those six passes.

A rehearsal on a copy of the live database applies migration
`20260911_149_wonderland_boss_loot_claims` (150 migrations total), retains the
1,787-item catalog, and preserves the complete owned-inventory fingerprint.
Artifacts are under `artifacts/wonderland-corpse-revive-20260911`.
The installed client's physical mouse selection and revived appearance still
require an in-game playtest; automated checks validate the native packet paths.

Deployed to Tempest at `2026-09-11T03:33:06.6152356Z`, image
`sha256:003c06d2f651180cd440ed65e2b4c4282cfee6e2a2e6073f0e0c27ee1e8dd6de`.
Health checks passed with zero restarts and unchanged ports. The item revision
remains `A45EA650680C8EA4D5D2FCAA831E97EEEF652BAB55351D860BFB95330FA97EB1`.
The stopped-server inventory comparison also remained identical. The prior
image is retained as `reborn-server:before-wonderland-corpse-20260911`, with
database backups in the artifact directory. Dwargon remains stopped.
