# Architecture review corrections — 7 September 2026

This follows [the repository review](astra-codebase-review-20260907.md) of
`39c98a6323c68c2eb960b7065e3fec4ec3d1da8d`.

## Runtime and startup

- Membership mutations retain their accepted world-owner operation until it
  completes. Removal leases are acquired before registry serialization and
  revalidated afterward, so blocked delivery does not hold the global registry
  gate or the world owner while a transfer waits.
- Removal keeps the original viewer entry until session and ECS membership are
  gone. Terminal egress completes pending sends, tracks asynchronous registry
  cleanup, and waits for it at disposal. A disconnected session loses gameplay
  readiness and active authority immediately.
- Scene transitions distinguish rejection without relocation, committed
  relocation awaiting client readiness, and committed relocation requiring a
  reconnect. Backhaul refunds only the rejection case. Pending scene state is
  a separate component.
- PostgreSQL startup retries provider-classified transient failures. Permanent
  SQL/authentication failures and cancellation fail promptly. Terminal logs
  retain bounded exception type, SQLSTATE, migration identity, and method stack
  without raw exception messages, SQL, connection strings, or file paths.
- Listener readiness waiting is extracted from Program.cs. Touched source files
  are kept below the repository's file-size limit.
- ECS rebound rewards are prepared before ordinary attack output is admitted.
  A regression measures admitted egress bytes, avoiding a race in the former
  socket-buffer assertion. The synchronous committed-Bleed prefix remains intact.

## Persistence and content

- Nine new legacy SQL partials now live in four focused Infrastructure adapters.
  The broad IGameStore interface returns to 28 methods. Shared compact-item
  readers and writers are Infrastructure helpers. Architecture allowances were
  reduced where code moved, rather than expanded to hide new dependencies.
- Warehouse wire decoding lives in Protocol; neutral transfer intent remains
  in Application. Faction portal policy lives in Domain.Characters.
- Online Award decisions receive the process-pinned pet catalog. Instance Opal
  payment reads authoritative item columns directly instead of a view connected
  to mutable content. Hosted snapshot reloads explicitly enforce the process realm.
- Lifecycle receipt replay verifies canonical JSON for the receipt's original
  v1/v2 contract, so PostgreSQL JSONB formatting cannot invalidate a committed
  receipt. Historical hashes remain valid; altered content and identity are
  still rejected. Concurrent duplicate creation passes against PostgreSQL.
- Item-publication provenance uses a bounded source label that also fits the
  earlier schema's 96-character column during upgrades. The complete manifest
  hash remains the content identity; historical releases are preserved.
- Relational item-attribute bootstrap loads seed data without reinstalling old
  view definitions after migrations. Forward migration 142 restores the two
  affected views to immutable item and attribute publications, preserving their
  signatures and expressions. Schema-release checks preserve the public view
  set and column signatures, plus the two item views' exact definitions and
  authoritative dependencies. A restored NPC view can express the same literal
  array using element casts instead of an array cast; the regression permits
  that verified equivalent representation. The other four baseline resources retain their
  existing behavior, including legacy skill grants.
- Historical pets-v2/v3 item fixtures exclude 90 identities introduced later by
  Medusa and capital-vendor migrations. Their original hashes and row counts
  reproduce exactly; upgrade and sealed-predecessor checks pass unchanged.
- Reconciliation readiness depends on valid authority metadata and a healthy
  bounded batch. Full-sweep completion and age remain separate. Healthy truncated
  scans continue after one second, and timeouts retain completed-page progress
  without double-counting findings. See the
  [readiness notes](../operations/b19-reconciliation-readiness.md).
- Dialogue release identity now includes the unchanged payload hash, its spawn
  dependency, entry count, and loader contract version. Historical payload-only
  releases still load. The V21 payload remains
  `0286976617060763C4B6491739D1724C0104E6E078B4F61D9D8FE59E6E910610`;
  its dependency-bound release is
  `0413340B6531086E307459E5931557A05392424857A26AF368F271BA01205D24`.
  No historical migration, sealed payload, or captured dialogue is rewritten.
  Restarting an already published release stays independent of mutable seed text.

## Client and validation

- Native warehouse paging includes Akou (5202), with a shared finite endpoint
  list and a server/native parity check covering warehouse and manager endpoints.
  The actual page host is tested through an injectable UI boundary.
- Native CI runs on Windows. The `-UnitOnly` gate supports clean builds and
  binary/unit contracts without an installed Origin client. The oversized
  fighter-seal test file was split.
- Protocol checks report passed, failed, and skipped separately. Every requested
  filter must match; `--require-no-skips` rejects incomplete required checks.
  `--results-json` writes machine-readable outcomes. Database gates obtain their
  current migration count/head from `--schema-metadata`.
- Current-schema fixtures follow realm-scoped indexes and lifecycle authority.
  Historical migration fixtures retain their original migration pins. Pet and
  combat fixtures establish admitted, ready sessions and assert exact protocol
  packets instead of stopping before the intended response.

## Verification

Evidence is under `artifacts/astra-fixes-20260907/` (local, ignored by Git).

- Final Release solution build and subsequent test-only rebuild: zero warnings
  or errors (`final-view-release-build.log`, `b03-final-view-build.log`).
- General managed run: 428 passed, two Windows TLS failures described below,
  and 96 environment-dependent skips (93 PostgreSQL and three Redis checks).
  Results are in `verified-managed-results.json`. The final ten focused
  architecture/startup checks passed with zero skips
  (`final-view-focused-results.json`).
- Mandatory PostgreSQL 17 gate: **56 required checks, six migration scenarios,
  zero failures or skips**, including fresh install, historical upgrades,
  backup/restore, startup view authority, and idempotence. All 143 migrations
  are covered through `20260907_142_restore_item_view_authority`
  (`b03-final-view-result.json`). Owned gate databases were cleaned successfully.
- Additional PostgreSQL proofs cover legacy dialogue release preservation,
  lifecycle receipt replay, focused gameplay adapters, Online Award, Opal
  payment, and all item publication upgrade branches. Historical item hashes
  and counts remain unchanged (`item-publication-repaired.json`).
- Debug runtime regressions include held delivery leases, terminal cleanup,
  Medusa fault injection, committed-Bleed ordering, and reward admission
  (`runtime-focused-results.json`, `pet-combat-final.json`,
  `medusa-terminal-final.json`). The reward-ordering regression was observed
  failing before its correction.
- Native clean builds, complete unit checks, binary/export contracts,
  server/client endpoint parity, and installed NetLegacy delegation checks
  passed (`native-tests.log`, `native-origin-tests.log`).
- `git diff --check` passes. Every touched or new file is at most 20,000 bytes.

Two Windows backhaul TLS checks encounter a substituted certificate issued by
`Norton Web/Mail Shield Self-signed Root`; exact certificate pinning correctly
rejects it. The same checks pass inside Linux Docker. Certificate validation has
not been weakened and host antivirus settings have not been changed.
`verified-backhaul-linux.log` records both passing with zero skips. The general
Windows run is therefore not described as an entirely green run.

## Applied development deployment

Tempest was recreated on 7 September 2026 at 08:45:31 UTC using image
`sha256:8e2d8290b329e7fef9b398b3c5d683c83395a6cd4d4e2f3ff56b96dd2c88f8d8`.
The container is healthy with zero restarts; login/game listeners and PostgreSQL
readiness succeeded. The development database now has 143 migrations and both
item views retain their official publication dependencies. Live isolation
checks passed (`deployment-status.json`, `deployment-isolation.log`). A sampled
idle reading was 2.67% CPU and 153.7 MiB for Tempest.

The pre-deployment custom-format database backup is
`artifacts/astra-fixes-20260907/development-before-final.dump` (76,346,287 bytes).
PostgreSQL remains on `127.0.0.1:15432`; Tempest keeps its existing endpoints.
Dwargon remains stopped. The disposable `godswar-astra-verification` container
and its anonymous volume were removed after verification.

The Akou-capable client shim is installed in `C:\Godswar Origin`. Its SHA-256 is
`5AE845091056C3C60B95BF15EBDC4A3BDEE3D6DE354C16F73040053FFDE87950`.
The applied receipt, pinned previous binary, and rollback script are under
`backups/client-network-shim-akou-20260907T075700675Z-4e330fce/`.
Origin.exe, NetLegacy.dll, and the existing UI assets were preserved and
verified against the receipt. Live in-game UI acceptance was not performed.

Deployment provenance above records the verified working tree before commit.
