# Wonderland buff bird range

The September 15 follow-up reduces Isle 3 Petbirds from 25-unit attack and
acquisition range to 12 units. Isle 7 Putrid Birds now use the same 12-unit range
and single-target native Fireball (2015). Their 1.92-second attack cadence,
mobility, 64-unit leash, HP, and attack ratings are retained. The 24 Petbirds
still grant fivefold attack; the five Putrid Birds still grant 25,000 Hit.

The original external attack IDs remain capture evidence. Live spell selection,
damage channel, silence fallback, and interruption checks use the requested
Fireball behavior. Arrow Towers and Lost Towers keep their existing ranges.

The behavior checks cover both monster engines: acquisition at 12 units,
no acquisition at the former 25-unit range, cooldown, chasing, and stopping at
ranged reach. Native combat checks exercise both bird variants on Isle 3 and
the Isle 7 birds across all monster/player engine combinations, checking target
and observer packets, single-target damage, retained buffs, and interrupted casts.

Deployment evidence and the separately authorized AresMage currency grant are
saved under `artifacts/wonderland-birds-marshals-20260915`. Allied marshal changes
are documented in `wonderland-allied-general-20260915.md`.

Four focused groups passed with no failures or skips across the bird and allied
marshal reports. Installed image
`sha256:4100eb16cb46f42be49affc744484a5fcba31ee4c1cc359342477cacaf5bb6fc`
is healthy on `godswar-dev-tempest-openworld-01`. The previous image is retained
as `reborn-server:before-birds-marshals-20260915`.

AresMage received 100,000,000 of each currency while the server was stopped.
Verified balances are 100,002,000 Silver, 100,000,010 Gold, and 100,000,000 B-Gold.
Wallet revision 2 reconciles with three grant ledger rows and no chain mismatches.
