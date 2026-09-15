# Holy Suit realm-calendar day boundary

Holy Suit daily EXP storage uses the server-wide calendar persisted on its
realm row. Tempest and Dwargon currently use `Asia/Manila`, so a new quota day
begins at **00:00 Philippine time (UTC+08:00)**. Audit timestamps remain UTC
`timestamptz` values; only the quota bucket key is realm-local.

The PostgreSQL executor resolves the day from that startup-pinned IANA zone.
It locks that exact `usage_day` and carries the key through the transaction.
The final quota update does not recalculate the date, so an operation that
starts immediately before midnight cannot debit a different day's row after
midnight.

Migration `20260802_049_holy_suit_singapore_day_boundary` introduced the first
local-day behavior. Migration `20260821_103_realm_calendar_authority` moves
active authority to the shared per-realm setting. Existing keys remain exact
historical records; aggregate rows cannot be moved safely without guessing.

After the global-calendar cutover, the executor creates and reads only the
current realm-day key. Historical command audits keep their original UTC timestamps.
For the live cutover, test2's 89,000,000 EXP operation occurred at 14:07 UTC
on 2026-08-01 (22:07 Singapore time), so it correctly remains on the prior
Singapore day and is not charged to 2026-08-02.
