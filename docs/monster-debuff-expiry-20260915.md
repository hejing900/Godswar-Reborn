# Automatic monster debuff icon expiry

Timed controls already stopped affecting monster behavior at their deadlines,
but the client received a status list only on application or appearance refresh.
An expired Silence, Freeze, Stun, or Shackle could therefore leave its icon behind.

The world tick now processes a deadline index for affected monster generations
and publishes the complete current status list, including an empty list when
the final debuff expires. The index stores one next deadline per actor rather
than scanning every monster or creating a task per status. Refreshes replace
their deadline, overlapping controls expire independently, and publication
re-reads current state after waiting for the viewer's visibility lease.

Control entries and the separate native `StunnedUntil` timer both register
deadlines. The legacy Warrior stun path now uses the same complete composer,
preserving other active controls. Direct elemental stuns register their timer
too. Existing elemental effects without monster icons are not given new icons.

Cleanup is independent of the caster's connection and targets the exact world,
runtime, object ID, and spawn generation. Retained boss corpses receive empty
status lists. A later application advances the status clock, so a delayed old
expiry cannot restore an expired icon or clear a newer control. Viewer waits
occur outside the registry gate.

Validation covers all 20 supported control skill IDs across both monster and
player engines, exact deadline boundaries, overlapping Freeze/Silence, refreshed
Silence, caster departure, corpse expiry, and a new control applied while an old
expiry waits on visibility. A separate Medusa test covers native stun expiry
through `StunnedUntil` for both player engines. Evidence and deployment receipts
are under `artifacts/monster-debuff-expiry-20260915`.

All three focused groups passed with no failures or skips. Installed image
`sha256:efb62380429127de2dbd200c40818f1d9ca378706a764e1c8b520778b8f183c7`
is healthy on the Tempest development server, with login and game listeners up.
The previous image is tagged `reborn-server:before-monster-debuff-expiry-20260915`.
