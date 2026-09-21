# Universal movement controls

The movement handler now reads the same ordinary stun authority as skill
casting, in addition to the existing encounter and training-dummy controls.
Previously ordinary runtime statuses such as 330 could stop skills while the
legacy and realtime movement gates omitted them. Native Frozen 299–305 also
stops movement, but its HaltIntonate-only behavior still permits a later
skill. MagicLocked and other silence statuses continue to permit movement.
When Wonderland silence overlaps an ordinary stun or elemental Shock, the
stronger stun wins instead of an early silence return hiding it.

Realtime movement previously accepted a tentative movement snapshot, awaited
pending-cast interruption, and then committed position without rechecking
control. A stun arriving during that await could therefore be bypassed. The
final commit now rechecks life and movement control. Rejection rebases the
movement authority to the committed character position, consumes the accepted
input, advances its world generation, and sends authoritative acknowledgement
metadata rather than a position save or viewer movement.

The original September 12 patch also sent an idle position correction for
every blocked Begin, End and Walk. The user subsequently reported screen
vibration when trying to move while stunned. That presentation change is
superseded by [the September 13 correction](stun-movement-vibration-20260913.md):
blocked input is silent again, matching the prior Medusa behavior. The
authoritative gates and final queued-commit check remain intact. The reason
the old packet was inappropriate for a held movement input is visible in
native 10194's local branch: at 0x4F08E9 it writes X/Z through 0x490A10 before
calling SetState(0) at 0x4F0906. Repeating it repeatedly resets actor position.
The read-only disassembly and executable hash are under
`artifacts/wonderland-ui-controls-20260912/native-local-movement-correction.txt`.
Installed Wonderland 1512 already contains native effects 0,2,3,4,5,6; 1513
contains 3,4. This change does not modify those client definitions.

No new registry/status/vitals lock nesting was introduced. The ordinary
movement query reads the immutable control snapshot with Volatile.Read; it
does not wait for the status publication semaphore. Existing encounter and
elemental authority readers remain responsible for their own fences.

The live excerpt around 06:32:29 UTC shows a two-second Wonderland
stun and blocked skill requests. The next saved movement at 06:32:31.480 UTC
is after the observed stun deadline, so that excerpt alone does not prove
movement committed during that particular stun. The fixes address the
independently demonstrated source gaps above; visual behavior still needs
the user's in-game confirmation.

Focused checks, each running both Legacy and ECS player modes:

- `Universal native stun and silence movement authority` exercises repeated
  real handler input for all three movement opcodes, stun/freeze/silence
  distinctions, no positional packet spam or blocked persistence, and expiry.
- `Queued movement rejects stun at final commit` covers authenticated queued
  ingress, real cast interruption held at the transport write, concurrent
  status application, rejected final commit, authority rebase, and stale
  queued-generation rejection.
- Existing Wonderland combat controls now include simultaneous encounter
  silence and ordinary stun, proving strongest-control precedence.

The September 12 scoped Release build completed with zero warnings or errors. Both new
checks, existing Medusa controlled movement, and the complete Secure Phase 4
game-handler movement integration passed (four selected checks, zero failures
or skips). Receipts are `build-movement-targeted.log` and
`protocol-movement-targeted.{log,json}` in the artifact directory. The broader
parent release run records its results separately; no native rendering
execution is claimed by these server-side regressions.
