# Monster target projection and elemental commit lock order

The reported Wonderland server failure was logged at 06:11:04 UTC on 11 September 2026, shortly after a Meteor Blast cast. The original fatal exception was not retained. This change fixes a separately proven concurrency failure on the same monster-world path; it does not establish the original exception's identity.

Previously, the monster tick entered its world-owner mailbox and then projected player targets under each character's `VitalsSync` monitor. A concurrent elemental secondary-effect transaction retained `VitalsSync` while submitting a monster lookup, derived damage, or Shock control to that same owner. Those two operations could wait on one another until the bounded owner invocation timed out.

The deterministic regression uses the real elemental Shock transaction. It pauses after acquiring the source's vitals monitor, starts a monster-world tick, and permits Shock when target projection begins. Before the fix, this produced `TimeoutException` from `BoundedSingleOwnerMailbox.Invoke`, propagated through `AdvanceMonsterWorldOnceAsync`; the report is `artifacts/wonderland-crash-fireblast-20260911/protocol-lock-red.json`. This is an actual mailbox timeout, not a test barrier timeout.

The registry now snapshots membership through the owner, projects immutable scalar targets outside it, and submits those targets for advancement. The owner checks current ready membership, character/object identity, ownership, instance, world revision, membership epoch, and life revision without acquiring character vitals. Existing final damage-commit authority checks remain in place. The convenience projection API explicitly rejects calls made inside any owner mailbox, and the older owner-based test helpers now use prepared projections.

The focused checks are:

- `Monster world target projection and elemental Shock do not invert owner and vitals locks`
- `Prepared monster targets preserve exact membership and life authority outside the owner`

They exercise both monster engines, a real successful Shock and retained primary damage, owner usability after the race, exact emitted target identity, and rejection of stale prepared identities, revived lives, unready members, and departed members. Test hooks are null by default. No exception is swallowed to recover from the lock inversion.

Release validation after the change passed both focused checks, the full Elemental Class Suit runtime suite, the live monster-to-player ECS adapter, the owner-routing/mailbox checks, and the adapted Medusa ownership suite. The solution built with zero warnings and errors. Evidence is in `artifacts/wonderland-crash-fireblast-20260911/protocol-release.json` and `build-release.log`; that initial combined report also contains a separate startup SQLSTATE diagnostic assertion failure, outside this change.
