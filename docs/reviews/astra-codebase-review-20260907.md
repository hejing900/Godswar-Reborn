# Godswar Reborn architecture review — 7 September 2026

Reviewed commit: `39c98a6323c68c2eb960b7065e3fec4ec3d1da8d`.

I would retain the C#/.NET modular monolith, PostgreSQL as the authority for player value, explicit ownership fences, bounded world execution, and the native protocol compatibility layer. I would change the boundaries between those parts and repair the validation gates before expanding the feature set. The current implementation is too dependent on large shared objects, duplicated contracts, and synchronous compatibility paths.

This is a repository-wide architecture review with focused source traces across startup, game sessions/worlds, persistence, content publication, the C++ shim, tooling, and CI. The inventory covered 4,323 tracked source/script files; it is not a line-by-line correctness certification of every file. Static findings below are distinguished from locally reproduced failures. No gameplay code, database, client installation, or running container was changed for this review.

**GPT-6 Astra migration applicability.** No OpenAI SDK dependency, API call, active model setting, or project Codex configuration was found. The project does not require an API model migration to be developed with Astra. The [official guide](https://developers.openai.com/api/docs/guides/latest-model) applies to applications invoking the model: use `gpt-6-astra`, use Responses for tools, replace `none`/`minimal` reasoning with `low`, and remove unsupported sampling parameters. There is no corresponding integration here to edit. The useful development change is clearer outcome contracts and evidence-based reviews; introducing a model into the game server would be a separate feature.

| Priority | Finding | Evidence status |
| --- | --- | --- |
| High | A timed-out membership mutation can finish after transfer rollback | Static interleaving traced across caller, mailbox, map, and egress |
| High | Mandatory validation gates are already inconsistent with the committed code | Architecture failures reproduced; stale PostgreSQL gate confirmed in source |
| Medium | A boolean transition result loses whether relocation committed | Static call-path finding |
| Medium | Akou is missing from the native warehouse paging endpoint list | Static C#/C++ contract mismatch; UI not exercised |
| Medium | Test selection and skip reporting can overstate coverage; native CI is absent | Runner problems reproduced; workflow inspected |
| Medium | Reconciliation can delay readiness in proportion to retained history | Static scaling calculation; feature disabled in checked-in defaults |
| Medium | Dialogue release identity omits its spawn dependency | Existing workaround documented in code |
| Medium | Partial files disguise large shared state and I/O coupling | Source inventory and lock/await paths inspected |
| Medium | Permanent schema errors enter an availability retry loop | Static exception classification and terminal logging inspected |

**1. Make accepted world mutations complete before deciding rollback.**

[`GameSessionRegistry.MapTransfers.cs:147`](../../src/Godswar.Server/Game/GameSessionRegistry.MapTransfers.cs#L147) calls `RemoveFromMap(existing)` and records `sourceRemoved = true` only after the call returns. Removal is submitted to the source world owner. [`BoundedSingleOwnerMailbox.cs:120`](../../src/Godswar.Server/Application/WorldInstances/BoundedSingleOwnerMailbox.cs#L120) explicitly permits an accepted command to continue after its caller times out.

Meanwhile, [`MapInstance.cs:69`](../../src/Godswar.Server/Game/MapInstance.cs#L69) waits synchronously for the monster viewer's transition gate. [`GameSessionRegistry.MonsterDelivery.cs:58`](../../src/Godswar.Server/Game/GameSessionRegistry.MonsterDelivery.cs#L58) retains that gate through physical network delivery. The default owner wait is one second; reliable writes can wait five seconds.

A slow monster delivery overlapping a map change can therefore time out the removal call. The transfer catch sees `sourceRemoved == false` and skips restoring source membership. The accepted removal later completes, after rollback, leaving registry and source-world membership inconsistent. The synchronous wait also holds the registry's global lock. This interleaving is supported by the code; its occurrence rate has not been measured or reproduced in a running game.

Use explicit accepted-command completion for membership mutations. The existing [`InvokeWorldOwnerAuthoritativeMutation`](../../src/Godswar.Server/Game/GameSessionRegistry.WorldOwnerAuthoritativeTransactions.cs#L13) is a useful precedent. Move network-dependent waits outside the world owner and global registry lock. The regression should hold a delivery lease beyond the owner deadline, attempt a transfer, release the lease, and assert consistent membership in both worlds after every accepted command completes.

**2. Repair the current validation gates before relying on a release result.**

Both `Data-boundary architecture ratchet` and `B20A legacy persistence retirement ratchet` failed locally against the reviewed tree. There are real dependency violations: [`Application/Warehouse/WarehouseWireProtocol.cs:2`](../../src/Godswar.Server/Application/Warehouse/WarehouseWireProtocol.cs#L2) imports packet/protocol types, and [`Infrastructure/Characters/PostgresCharacterLifecycleCommandExecutor.Create.cs:4`](../../src/Godswar.Server/Infrastructure/Characters/PostgresCharacterLifecycleCommandExecutor.Create.cs#L4) imports `Game`. The legacy store interface also grew from the ratchet's 28 methods to 31.

Some textual debt findings require interpretation: for example, a feature-specific field named `_store` is not automatically a reference to `IGameStore`. Resolve the actual dependency violations and review the analyzer's classification; simply increasing every baseline would obscure the intended boundaries. Move packet decoding to the adapter while retaining the transport-neutral intent in Application, and place shared faction-skill rules below Game/Infrastructure.

There is a separate deterministic CI failure. [`InvokeB03PostgresCiGate.ps1:69`](../../tools/InvokeB03PostgresCiGate.ps1#L69) expects 94 migrations through `20260814_093_monster_combat_authority`; the current catalog has 142 through `20260907_141_duel_arena_services`. [`B03PostgresCiGate.Helpers.ps1:277`](../../tools/B03PostgresCiGate.Helpers.ps1#L277) rejects the current schema after a successful bootstrap because it differs from that stale expectation. The workflow requires this gate.

Expose current catalog metadata through one machine-readable command and consume it from tooling. Keep historical upgrade fixtures explicitly pinned to their historical revisions. Preserve the mandatory migration, replay, and isolation checks.

**3. Represent transition commit state explicitly.**

[`GameClientHandler.MapTransitions.cs:194`](../../src/Godswar.Server/Game/GameClientHandler.MapTransitions.cs#L194) can return `false` after persisting the destination and transferring registry membership, when coordination publication then fails. It disconnects the session, but relocation is already authoritative. [`GameClientHandler.Backhaul.cs:262`](../../src/Godswar.Server/Game/GameClientHandler.Backhaul.cs#L262) treats every `false` as a rejected teleport and attempts a mana refund. Whether that refund reaches storage depends on the ownership failure; the compensation branch is nevertheless selected after a relocation commit.

Return an outcome such as `RejectedBeforeCommit`, `CommittedAwaitingReadiness`, or `CommittedRequiresReconnect`. Charge/refund decisions should use that outcome. Apply the same contract to same-map, ordinary map, and instance transitions while preserving their different admission policies. Test failures before persistence, after persistence, after membership transfer, and during coordination publication independently.

**4. Keep server and native warehouse endpoint contracts synchronized.**

The server supports Akou, NPC 5202, in [`WarehouseNpcProtocol.cs:12`](../../src/Godswar.Server/Domain/World/Content/WarehouseNpcProtocol.cs#L12). The enabled native paging adapter's [`IsWarehouseNpc` at line 134](../../client/network-shim/src/OriginWarehousePageHost.cpp#L134) recognizes only the two capital warehouse IDs. Akou's ordinary eight-byte page request consequently clears native context; [`TryBuildPageRequest` at line 403](../../client/network-shim/src/OriginWarehousePageHost.cpp#L403) cannot emit logical page requests without it. Snapshot tracking and transfer-slot rewriting also depend on that context.

This affects the enabled/deployed warehouse shim; it is not a claim that the current user's client has reproduced the failure. Initial storage may open while extended paging lacks its adapter. Add Akou to the native contract and cover opening, tab switching, and transfer-slot translation. Longer term, generate the shared endpoint/packet contract for both languages or validate it with shared fixtures.

**5. Make test results state what actually ran, and cover the native build.**

[`Program.cs:285`](../../tests/Godswar.Server.ProtocolChecks/Program.cs#L285) accepts substring filters and errors only when none match. A valid filter plus a nonexistent required filter exits successfully while omitting the latter. This was reproduced with `Native faction backhaul skill catalog` plus `__nonexistent_required_check__`.

At [`Program.cs:305`](../../tests/Godswar.Server.ProtocolChecks/Program.cs#L305), any check that returns normally is marked passed. Several database checks print `SKIP` and return when their environment is unavailable. Reproduction with the NPC dialogue upgrade check and no test connection string printed both `SKIP` and `PASS`, followed by `1 passed, 0 failed`, exit 0. The mandatory B03 wrapper separately rejects skips, which is worth preserving; the generic runner remains misleading for manual validation and other scripts.

Use explicit pass/fail/skip outcomes, stable check IDs, and validation of every requested filter. Required checks should fail closed when prerequisites are missing. Export structured results usable by CI instead of requiring wrappers to infer outcomes from console text.

The sole workflow builds the managed `GodswarServer.sln`. The C++ implementation and tests are in a separate solution, and neither native build nor native unit execution is invoked. Add a Windows native gate. Separate hermetic native unit checks from installed-client acceptance: [`TestClientNetworkShim.ps1:58`](../../tools/TestClientNetworkShim.ps1#L58) currently requires the original client DLL before reaching the unit executable.

**6. Separate reconciliation sweep completion from startup readiness.**

[`ServerReadinessMonitor.cs:186`](../../src/Godswar.Server/Operations/ServerReadinessMonitor.cs#L186) requires `FirstPassCompleted` when reconciliation is enabled. The worker sets that only after a full sweep, and waits the entire polling interval after truncated batches. Defaults are 5,000 outbox events per run and five minutes between runs ([options](../../src/Godswar.Server/Application/Reconciliation/ReconciliationContracts.cs#L144)). The [outbox query](../../src/Godswar.Server/Infrastructure/Reconciliation/PostgresReconciliationSnapshot.Outbox.cs#L108) includes delivered history.

At those defaults, scanning 100,000 retained events takes approximately 20 batches and at least about 95 minutes of inter-batch waits before first-pass readiness, with other scanning work potentially adding delay. This is a calculation from the implementation, not a benchmark. Reconciliation is disabled in the checked-in main, Docker, and local Redis worker settings, so this is a conditional operational issue.

Require a validated manifest and a healthy bounded reconciliation pass for readiness. Monitor complete sweep age separately. Capture a high-water mark, retain continuation progress, and process continuation batches promptly within a resource budget. Bound per-character ledger-history work as well as character count; otherwise one large account can repeatedly exhaust the run timeout.

**7. Give content releases an identity that includes dependencies.**

[`HashNpcDialogues`](../../src/Godswar.Server/Application/World/WorldContentRevisionHasher.cs#L53) hashes dialogue payload but not its required spawn revision. That hash is used as the release key, while the [release row](../../src/Godswar.Server/Infrastructure/WorldContent/PostgresNpcDialogueBaselinePublisher.Writes.cs#L18) binds one spawn revision and the loader requires an exact dependency match.

The resulting workaround is already visible: [`NpcDialogueBaselineV18.cs:7`](../../src/Godswar.Server/Infrastructure/WorldContent/NpcDialogueBaselineV18.cs#L7) and V19 document wording-only changes to create distinct releases for new geometry. Moving an NPC should not require rewriting its dialogue.

Separate payload hashes from release identity. Publish an immutable, versioned manifest containing payload hashes, dependency revisions, and protocol/client compatibility requirements. Keep historical content hashes and migration checksums intact through a forward format migration. A coordinated client compatibility manifest would also help catch missing appearance aliases before publishing server NPC content.

**8. Extract components that own state, rather than adding more partial files.**

The inventory found 190 `GameClientHandler` files totaling approximately 1.50 MB and 153 `GameSessionRegistry` files totaling approximately 1.17 MB. They remain shared classes. The handler's [constructor](../../src/Godswar.Server/Game/GameClientHandler.Construction.cs#L26) accepts a long list of optional feature dependencies. The 20 KB file guideline should remain, but file size alone does not measure cohesion.

This coupling has runtime consequences: the [packet loop](../../src/Godswar.Server/Game/GameClientHandler.cs#L95) holds `_characterStateGate` throughout an awaited handler, including a [warehouse database read](../../src/Godswar.Server/Game/GameClientHandler.WarehouseOpen.cs#L34) and response delivery. [Realtime movement](../../src/Godswar.Server/Game/GameClientHandler.RealtimeMovement.cs#L82) needs the same gate. A slow feature read therefore delays that player's movement and other serialized work. This coupling is established; player-visible latency has not been benchmarked.

Extract session lifecycle, scene transitions, combat/casting, and economy/NPC services as components with explicit owners and small interfaces. Preserve serialization of conflicting valuable operations. For slow work, capture or reserve intent, perform asynchronous I/O, then post a completion that revalidates ownership and generation. First extract the scene-transition component while repairing findings 1 and 3; use that as a pattern before moving more features.

**9. Distinguish permanent startup errors from transient unavailability.**

[`PostgresSchemaStartup.cs:53`](../../src/Godswar.Server/Infrastructure/Database/PostgresSchemaStartup.cs#L53) classifies every `NpgsqlException` as transient, including permanent PostgreSQL errors. Invalid SQL or insufficient privileges can produce the same 30-attempt “waiting for PostgreSQL schema” loop as a temporarily unreachable database. The outer [`Program.cs:507`](../../src/Godswar.Server/Program.cs#L507) catch drops the exception and records only `startup_failed`.

Use provider transient classification and explicitly reviewed retry conditions. Log a structured terminal cause with exception type, SQLSTATE, migration ID, and an appropriate stack, excluding sensitive connection/payload data. This would make failures like the original startup complaint substantially easier to diagnose. It does not establish that this classification caused that earlier incident.

**Implementation order I recommend.**

1. Restore trustworthy validation: repair actual boundary violations, update the schema gate contract, fix skip/filter outcomes, and add native unit CI.
2. Repair membership timeout semantics and replace ambiguous transition booleans; add deterministic failure/interleaving regressions.
3. Align the Akou native endpoint and introduce a shared server/client compatibility fixture.
4. Extract scene/session components, then economy and combat, retaining ownership fences and immutable committed results.
5. Introduce dependency-aware content manifests, improve startup diagnostics, and decouple reconciliation sweep age from readiness.

Retain the existing transactional inbox/state/outbox model for valuable commands, bounded checkpoint coalescing, immutable migration checksums, server-owned destinations and costs, hidden scene membership until readiness, transport-independent combat rules, and guarded client-patch backups/rollback. Redis should continue to coordinate disposable presence/routing rather than own player value. There is no evidence here requiring a language change or a split into more deployed services.

**Validation performed for this review.**

- Inventoried tracked code and project manifests; searched tracked text and dependencies for model/API integration; read the linked official Astra guide.
- Reproduced two architecture-check failures against the committed source.
- Reproduced skipped-check reporting and mixed valid/invalid filter acceptance without connecting to a database.
- Traced the remaining findings statically across their callers and implementations. No full regression suite, native UI acceptance, or production load benchmark was run.
- Local transcripts are in `artifacts/astra-review-20260907/`. Runtime behavior and deployments remain unchanged; this report is the only tracked-file addition from the review.
