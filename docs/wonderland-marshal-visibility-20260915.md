# Wonderland marshal damage delivery

The allied Isle 5 marshal and soldiers committed their target's HP loss and sent native damage packets directly. Those raw sends bypassed the viewer's monster health revision ledger. The next player attack therefore appeared to have missed an earlier HP change, triggering the normal remove-and-respawn repair. Repeated `AreaSkillSelf` and `BasicAttackSelf` health reconciliation for hostile marshal object `46500` in the September 15 session logs matched the reported disappearing general.

Allied hits now capture their committed health mutation, native skill, source incarnation and ready recipients under the authoritative registry gate. `AdvanceWonderlandCombatAsync` publishes those records after releasing that gate, using the same health delivery lease as player attacks. Native skill impacts `2004` / `2000` and the applied HP loss are admitted together, and the viewer health revision advances only after egress owns that batch. The actual combat, NPC targeting and HP settings are unchanged.

A viewer who can see the damaged enemy but cannot yet see the allied attacker receives the source appearance in the same batch. Source hydration shares the existing viewer lease, avoiding both an untracked HP delta and nested visibility gates. The final admission rechecks viewer membership and life plus source/target runtime and spawn identity. Genuine missed health revisions retain the existing reconciliation behavior.

The authoritative registry lock is not held while waiting for visibility. Accepted direct damage releases the visibility lease before transport completion observation. Failed exact admissions disconnect the affected recipient rather than advancing its health revision without an owned packet.

Validation and deployment receipts are recorded in `artifacts/wonderland-marshal-visibility-20260915` by the coordinating task.

Timestamped server evidence records 26 refreshes of object 46500 in 86.17 seconds.
Its HP continued decreasing, confirming presentation repair rather than gameplay
respawning. No recent local wire capture was available; the remove/appearance
opcode mapping is verified from the exact logged server path.

The two focused protocol groups passed with no failures or skips. The regression
alternates player basic and AOE delivery after allied hits for both factions and
all four monster/player engine combinations, rejects duplicate HP delivery,
holds a visibility transition while verifying the registry gate remains usable,
and checks an intentionally missing source appearance is sent before its damage.
The shared health ordering checks still repair a real missing delta.
