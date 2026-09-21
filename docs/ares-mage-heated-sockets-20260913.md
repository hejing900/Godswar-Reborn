# AresMage Heated Holy Stone sockets

Applied September 13, 2026 at 12:02:44 UTC to AresMage7009/account7256.
Corrected to percentage magic damage at the user's request at 12:19:52 UTC.

The existing helmet2443, gloves2863, rings3265/3265 and staff1834 now each
have two sockets. Socket1 is Grade X Fire Spirit of Blood, effect7 with
explicit value600 (+6% critical damage). Socket2 is Grade X Fire Spirit of
Lightning, effect4 with explicit value600 (+6% magic damage).
The total equipment increase is **30% critical damage and 30 percentage
points of magic damage bonus**. Critical chance is unchanged.

All five items retain Mystic quality10, grade12, Platinum I401, their prior
attributes and identities. The transaction verified every other inventory
field and the entire character row unchanged. Both the original grant and
the correction recorded five named item audit entries with complete prior
item states. Inventory revision remains0,
following this developer fixture's existing administrative grant convention.

Only Tempest was briefly stopped for the grant. A fresh full database backup
was validated before execution. It restarted healthy on the same image
`sha256:57ac4db77e56ce4f90d10962b57a4b7b598c5cb01dd7c64b999406dca53ea953`.
The sockets load when AresMage next logs in; no gameplay or client code changed.

Private backup, exact SQL, before/after records and receipt for the original
flat-damage grant are in `artifacts/ares-mage-heated-sockets-20260913`.
Its executed SQL SHA-256 is:
`332e5ceb10f14ee0c9670114114b4be4e03c198f5482e4bad92d8d66a1270f1d`.
The subsequent correction's separate backup, audited preimages and receipt
are in `artifacts/ares-mage-heated-percent-20260913`. Correction SQL SHA-256:
`562f209a8a1ccb2014d198423361e06a52c5ae0d1427a44cb077b4b9ae88da86`.
The correction changes only socket2's effect and explicit value on each of
the five items, replacing the added 1,500 flat damage with +30% magic damage.

The legacy `character_stat_summary` view uses older grade-based socket values
and overstates these additions. Runtime hydration uses the pinned-content
`PostgresCharacterHolySpiritCombatProjectionSql` CTE, which reads the explicit
600/600 values. Use the runtime projection when comparing these socket stats.
