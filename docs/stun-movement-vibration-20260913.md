# Stun movement vibration

The September 12 server patch sent native position packet 10194 for every
movement attempt rejected by stun. The user reported screen vibration when
trying to move. This packet does more than acknowledge rejection: the local
receiver writes X/Z before setting idle. Sending it repeatedly while a key
is held was a presentation regression. Earlier Medusa behavior deliberately
rejected these inputs without repeated position corrections.

The fix restores silent rejection for native Begin 10013, End 10014 and Walk
10194 while a movement control is active. The installed native NonMoving
status continues to govern local controls. The server still rejects movement,
skills remain blocked by stun, and the final check after an awaited cast
interruption still prevents queued movement from committing after stun.
Silence continues to permit movement.

Realtime input still receives sequenced authoritative rejection/acknowledgement
snapshots, including rebased coordinates and generation after a rejected late
commit. These snapshots are metadata: `SecureUdpClientWorker::ConsumePositionSnapshot`
calls `SecureRealtimeMovementRouter::AcceptAuthenticatedSnapshot`, which only
updates the authenticated baseline, acknowledgement and pending input state.
`PublishMovement` copies that metadata into the worker's published state;
it does not inject a native movement packet. The separate reliable 10194
correction is suppressed while movement is blocked by a control. Death and
unrelated movement validation/transport corrections remain intact.

An untagged legacy Walk received after realtime cutover also checks movement
control before the normal cutover correction path, preventing the same shake
through a different ingress route. No status, client asset, timer, damage,
ownership, skill interruption, or authority locking behavior was changed.

The focused regressions now assert the intended absence of positional egress:

- Ordinary stun/freeze statuses: eight repeated Begin/Walk/End cycles through
  the actual handler in both player engines, no movement or persistence, no
  native correction packets, and movement resuming after real expiry.
- Medusa: the same repeated input behavior under a real boss stun, with no
  self or viewer movement packets and unchanged attack/skill restrictions.
- Wonderland: a real Derskey stun in both monster/player engines, native
  status 1512 remaining present, 24 actual input packets, unchanged position
  and revision, and no native movement packets.
- Realtime: repeated and stale queued input, native legacy input after
  cutover, and stun arriving during actual cast-interruption publication.
  Rejection acknowledgements and the late-commit rebase remain asserted.

The parent release workflow records build/test receipts in
`artifacts/wonderland-followup-20260913`. Native inspection proves packet
semantics; in-game confirmation of the visual result remains separate.
