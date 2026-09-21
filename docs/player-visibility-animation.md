# First-visibility player animation

The stationary-player walking defect came from the position replay accompanying
a remote-player appearance. `PlayerWorldPosition` wrote the movement state `2`
into the high word at offset 4 of opcode `10194` (`0x27D2`). This state means
walking, even when the coordinates have not changed. A stationary character
does not send another stop sample, so the observer could keep that animation.

The builder now sends state `0` for synthetic position snapshots. The same
builder covers initial visibility, the activation catch-up, arrival broadcasts,
and reliable position corrections. Actual movement keeps its original state
through `PlayerWorldMovement`; this includes both walking and stopping.
A player already moving when a viewer joins resumes its walking state on the
next normal movement sample.

Read-only inspection of the installed `Origin.exe` on 2026-09-11 establishes
the native contract:

- The sender writes state `2` at `0x00492669` while moving, then overwrites it
  with `0` at `0x004926F5` when stopping.
- The receiver at `0x004F08BD` reads the high word and passes it to
  `0x00499DB0`. That routine queues the final position and animation state even
  for a zero-distance sample (`0x0049A005` through `0x0049A02D`).
- The queue consumer at `0x00492BF6` reads the queued animation state and calls
  the state setter at `0x00490C80` when it differs. It does not infer idle from
  unchanged coordinates.

`PlayerVisibilityAnimationChecks` exercises the real map-entry publication for
two stationary characters. It checks the newcomer’s initial and activation
position packets and the existing viewer’s arrival packet, including ordering,
identity, coordinates, and native idle state. Separate real movement samples
verify that both walking and stop states remain intact when the object ID is
remapped. Client rendering still requires an in-game confirmation.
