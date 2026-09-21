# Wonderland monster control behavior

Wonderland bosses and ordinary monsters now use the existing native single-target Stun, Frozen, Silence and Shackle definitions. Previously only Warrior Stun reached a monster-control handler; the other three families could enter ordinary damage handling. The change neither equips titles nor changes player movement correction behavior.

The installed `Status.ini` definitions are recorded with their source hash in `artifacts/wonderland-full-external-20260913/native-monster-controls.json`.

| Family | Native statuses | Movement | Basic attacks | New skills | Current intonation |
| --- | --- | --- | --- | --- | --- |
| Stun | 331 | Blocked | Blocked | Blocked | Interrupted |
| Frozen | 301–305 | Blocked | Allowed in range | Allowed | Interrupted |
| Silence | 360, 363, 364 | Allowed | Allowed | Blocked | Interrupted |
| Shackle / Caged | 400, 407, 408 | Blocked | Blocked | Blocked | Interrupted |

Shackle also retains the native 75% incoming physical and magical damage reduction. It combines multiplicatively with the opposing island-two bosses' 80% encounter reductions, producing 95% for the protected channel. It is not treated as a movement-only root. Frozen retains its distinct native behavior even though its name can suggest a full stun.

Controls are immutable and belong to the exact monster runtime and spawn generation. Different native kinds coexist; a weaker same-kind effect cannot replace a stronger one. Expiry removes restrictions without restoring old queued attacks or casts. Death, return and respawn retire the old control state. New controls stop an already-moving monster once; held ticks do not repeatedly send movement-end packets.

The final attack commit checks interruption revisions, so an attack emitted before a later stun cannot deal delayed damage after the stun expires. Wonderland's scheduled-cast path separately checks the cast interruption revision. Native skill-bearing basic attacks use the captured generic physical fallback while Silence is active; they do not become forbidden ordinary basic attacks.

Control packets resolve the current complete status list after acquiring the viewer lease. Packet admission shares the registry gate with control commits and does not wait for network I/O while holding it. The same projection hydrates newly visible actors and health reconciliations, so an older pending publication cannot overwrite a newer Silence or omit it from a new viewer's appearance. Native countdowns expire naturally; a later refresh also projects the complete current list, including an empty list after expiry.

The new route deliberately excludes bound Medusa instances, which retain their existing Warrior Stun owner path. Direct elemental Shock gains the Wonderland-boss exception while other boss immunity policy remains unchanged. No client asset changes are required for these stock statuses.

Focused checks are `Monster native controls preserve movement attack and cast distinctions` and `Wonderland boss control skills and queued attack interruption`. They exercise both monster and player engines, real class-skill handlers, mana persistence, no control-as-damage fallthrough, overlap/priority/expiry, generation rejection, queued basic interruption and a real viewer-lease publication race. Existing encounter overlay tests now explicitly seed a synthetic test stun; they no longer claim the captured island-two bosses have the removed invented stun proc.

Validation is coordinated by the root release run; this note does not claim an independent build or deployment.
