# Wonderland city revival and pet Merge energy

The September 11 report exposed a native Revive routing error after a dead player left Wonderland. Pet owner-Merge energy also still drained inside Wonderland and Atlantis. Both changes are server-side; the installed client needs no patch.

## Confirmed live failure

In test25's run `7da50a3c923e4394975abbbecdf1653b`, AresTempest died at 09:57:31 UTC. The 10:11:33 timeout transferred the character from Wonderland 207 to Sparta 0 at zero HP. City scene readiness completed. At 10:13:07 the client sent its standard twelve-byte free Revive request, `0C002C274814000002000000` (opcode 10028, local object 5192, type 2), and the server logged it as unknown.

Dispatch accepted this opcode only on map 207. It now routes it to the existing strict free-revival handler on other maps too. Exact packet length, local object, supported free type, dead-state and life authority checks remain active. The city path persists restored position and 10% HP/MP, advances the life once and sends the normal full entry bootstrap. Timeout itself continues to preserve zero HP until the player chooses Revive.

The native receiver writes restored EnterMain HP/MP before entry processing. Its Revive window closes itself when the request is sent; no invented server ACK is required. Wonderland's separate in-place revival retains its existing vitals-before-SceneChange ordering. See `artifacts/wonderland-city-revive-20260911/README.md` for the bounded native audit. Final installed-client animation remains a playtest check.

## Merge energy policy

The timer previously skipped energy drain only for bound Medusa encounters. It now skips the durable drain for current admitted members of Wonderland and Atlantis too. Admission and current account/session ownership are checked against the exact runtime; a matching map ID alone grants no exemption.

Protection continues while an admitted player waits for terminal egress. After departure, the next ordinary three-second tick drains one point, without charging for skipped intervals. The existing timer generation, cancellation, character gate, store ownership fence, depletion handling and companion restoration remain in place. The tick body was extracted for deterministic tests without changing its cadence.

The new query follows registry-to-world-owner order and acquires no vitals, elemental or status lock. Registry/owner locks are released before the awaited durable energy operation. Bounded peer review found no additional lock inversion; the two earlier deadlock regressions also passed. This does not prove that every possible concurrency bug is eliminated.

## Verification

Release build: zero warnings and zero errors. Fifteen focused protocol checks and one isolated PostgreSQL checkpoint check passed, with no skips.

- Real Wonderland timeout and leader termination while dead, both faction capitals, exact native free Revive, restored EnterMain HP/MP before readiness, and living replay rejection.
- Both supported revive opcodes retain malformed, foreign-object, paid-type and living-player rejection checks.
- Real Wonderland, Atlantis and Medusa admission, skipped energy ticks, terminal waiting, one-point drain after departure, unbound and unadmitted runtime rejection, stale ownership and stale timer generation.
- Existing map readiness, instance completion/retirement, pet Merge projection/lifecycle, checkpoint lifecycle and combat lock-order checks.
- PostgreSQL versioned checkpoint persistence and ownership assertions against a disposable database at migration 150.

New protocol fixtures use a recording persistence store for revival; the separate PostgreSQL check exercises the actual checkpoint store. Test setup corrections supplied the pinned pet catalog for full entry, used exact dynamic-instance identities and initialized the current schema before seeding. Production routing and authority checks were not relaxed to accommodate tests.

All production files touched by this task are below 20 KB. Unrelated working-tree changes were preserved. No commit or push was requested.

## Release evidence

`artifacts/wonderland-timeout-revive-20260911/` holds build/test results, the captured failure, release scripts, the stopped database backup with matched SHA-256 hashes, and runtime/publication verification. The rollback tag is `reborn-server:before-wonderland-timeout-revive-20260911`.

The release restores only test25's recorded 09:31 test-entry reservation `6f243a1e-c5ca-4189-9d04-82545e508e65`, following the backup. Other entries, earned inventory and reward receipts are preserved. The normal daily limit remains three. Only Tempest is recreated; Dwargon remains stopped.

Deployed at 10:29:21 UTC as image `sha256:416740b496a3598ca27a8dcb0c2f4d71bbbd62315206287ca997bc6977580513`. Tempest is healthy with zero restarts and no OOM; both login/game listeners are ready and the inspected startup log contains no failure. Ports remain 127.1.1.111:5998 and :7000. Item publication, policy fingerprints, inventory fingerprint and migration head 150 are unchanged. Daily-entry readback retains the two earlier reservations, leaving test25 one free entry. The stopped backup SHA-256 is `609728f5de164399f6773cd46f9697d9cd9af56d99decfb6fabc187e6f599af0`, verified against the PostgreSQL container before the scoped reset.
