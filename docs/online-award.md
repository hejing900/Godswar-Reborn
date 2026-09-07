# Online Award Admin

Online Award Admin uses the stock `NpcFunStayReward` endpoint at Athens
`Athens_132`/5271 and Sparta `Sparta_132`/5129. The exact claim request is
opcode 10069, 92 bytes, dialog 49 in both dialog fields, sub-ID `-1`, and all
18 arguments set to `-1`. Results are 102 (success), 103 (already claimed),
104 (bag full), and 105 (unavailable or request conflict).

One character may claim once per realm day. The day comes from the global
[realm calendar](realm-calendar.md), so all game systems use the same server
timezone. PostgreSQL enforces uniqueness by realm, character, and calendar
date; it does not rely on a client clock or process memory.

## Seeded award

Migration `20260821_105_online_award_foundation` publishes this immutable
revision-1 balance:

| Order | Item | Quality | Quantity | Bound | Stack cap |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | Rock Elf Egg (Godly), 10150 | 14 | 1 | 0 | 1 |
| 1 | Rock Elf Egg (Smart), 10150 | 10 | 4 | 0 | 1 |
| 2 | Mdew5, 10134 | 1 | 5 | 0 | 99 |
| 3 | Phoenix Feather, 11005 | 1 | 5 | 0 | 99 |

The chosen policy grants unbound items. An empty bag needs seven slots: five
individual eggs, one Dew stack, and one Feather stack. A claim may also fill
compatible existing stacks. Capacity validation and every item mutation are
part of the same transaction, so a bag-full result grants nothing.

## Management and activation

`online_award_balance_revisions` stores immutable headers and content hashes;
`online_award_balance_entries` stores the ordered reward rows; and the
singleton `online_award_balance_publication` row selects the active revision.
`online_award_publication_audit` records every publication transition.
Published revisions are sealed, and sealed headers or child rows cannot be
changed or truncated.

A management update must publish a complete successor with compare-and-swap:
read and lock the singleton pointer, insert revision `expectedRevision + 1`
and all entries, then advance the pointer only if it still names the expected
revision. A stale update rolls back. Item IDs, egg aptitude, stack caps, total
quantity, duplicate identities, ordered rows, native pet hatch profiles, and
the 96-slot upper bound are validated against the pinned item-content release
before publication.

Workers pin the published balance and its SHA-256 fingerprint at startup. A
successful management publication becomes active only after a coordinated
restart of every worker for that realm; it is not hot-reloaded mid-command.

## Durable claim evidence

A successful claim is one PostgreSQL transaction that locks ownership, the
character, and bag state; grants all items; advances inventory and Online
Award revisions; and writes command inbox/audit, exact inventory-ledger
deltas, strict outbox event, and `online_award_claim_settlements`. The
settlement retains the realm day, balance revision/hash, item-content
revision, exact item deltas, revisions, and command/audit/event identities.
Those rows are append-only. Same-operation retries replay the stored receipt;
Athens and Sparta normalize to the same command identity after their concrete
NPC endpoint is validated.

Committed claims emit seven left-side acquisition notices, clean their
temporary scratch slot, refresh the authoritative bag, and then send result
102. Duplicate, already-claimed, and bag-full paths do not replay acquisition
notices.

## Client content and deployment

Migration `20260821_106_online_award_dialogue_v7` enables the finite server
dialogue behavior. Client result text is a separate, reversible localization
patch managed by `tools/PatchClientOnlineAwardLocalization.ps1` in `Status`,
`Apply`, or `Revert` mode. Apply it only to the intended client installation,
keep its receipt/backup, and coordinate it with the server migration and
worker restart. Repository implementation and tests do not themselves deploy
the migration or alter a live client.
