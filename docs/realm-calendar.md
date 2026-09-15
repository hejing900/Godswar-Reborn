# Per-realm game calendar

`public.server.time_zone_id` is the single calendar authority for each realm.
Migration `20260821_103_realm_calendar_authority` sets Tempest and Dwargon to
`Asia/Manila` and starts both at calendar revision 1.

The complete, sorted realm-calendar catalog is loaded before readiness and is
included in the coordination fingerprint. Each worker selects the entry for
its process realm. A missing, invalid, unavailable, or realm-mismatched entry
fails startup. Workers do not hot-reload the value.

The coordination fingerprint also includes the platform's complete serialized
rule set for each configured zone, not only its IANA identifier or the public
transition fields. This includes offset semantics that some target packs do
not expose as public adjustment-rule properties. Workers with mismatched host
tzdata therefore produce different revisions and must not share daily quota or
admission authority until their time-zone databases agree.

The selected calendar controls:

- Faction Crier daily claims and weekly reclaim periods;
- Online Award Admin daily claims;
- Zodiac daily online windows, rollover, and compensation;
- Holy Suit daily EXP quota buckets;
- the native ServerTime clock bias (serialized as UTC minus the selected
  realm offset, as required by Origin's subtractive wire contract).

Audit timestamps, command receipts, leases, ticket expiry, status expiry,
cooldowns, and elapsed durations remain UTC. Those are instants or durations,
not game calendar dates.

## Management contract

`PostgresRealmCalendarSettingsStore` updates one realm with compare-and-swap:
the caller supplies the realm, canonical IANA ID, expected revision, and audit
actor. A successful change advances `time_zone_revision` by one and appends an
immutable `server_time_zone_audit` row. Stale revisions, unavailable zones,
unfenced writes, and forged audit rows are rejected.

A calendar change becomes active only after a coordinated restart of every
realm worker. All workers fingerprint the complete catalog, so different
realms may intentionally use different zones while workers still reject a
partially rolled-out catalog.

The older Faction Crier `server_utc_offset_minutes` and Holy Suit
`realm_day_time_zone` fields are retained only for immutable migration/content
compatibility. Runtime calendar decisions do not read them.
