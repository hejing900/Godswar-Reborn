# AresMage third Holy slot and Alpha defense restoration

Later September 14 update: boss Critical Resistance now comes from
`monster_combat_balance` and is set to 100. The zero-critical-chance audit below
describes the earlier generated resistance of 2,632; AresMage's unchanged
Critical 206 now gives 5.88% against Alpha. See `monster-combat-balance-20260914.md`.

Applied September 14, 2026 at 01:31:15 UTC. Alpha Demon's magic defense is
restored from zero to 2,500 in `WonderlandMonsterPlan`; its physical defense
remains 3,000. The defense field remains available for future tuning.

The user requested Ignore Magic Defense in AresMage's third slot. The five
existing Heated hosts now each have three sockets:

| Equipment | Item instance | Third socket |
|---|---:|---|
| Helmet 2443 | 41571 | Grade X Fire Spirit of Penetration, +8% |
| Gloves 2863 | 41573 | Grade X Fire Spirit of Penetration, +8% |
| Ring 3265 | 41579 | Grade X Fire Spirit of Penetration, +8% |
| Ring 3265 | 41580 | Grade X Fire Spirit of Penetration, +8% |
| Staff 1834 | 41581 | Grade X Fire Spirit of Penetration, +8% |

Socket three stores effect 2, level 10, explicit value 800. Socket one retains
effect 7/value 600 and socket two retains effect 4/value 600. The audited
transaction changes only socket count and the third socket's three fields.
Every other AresMage inventory field and the full character row were verified
unchanged; five item audit entries retain the complete prior item states.

This is an explicit development-character grant. The normal drilling gate
still requires a template level of 140 for a third socket; no global drilling
rule or equipment level was changed. Runtime hydration and the native item
record already support these third slots without a client patch.

The exact runtime Holy Spirit SQL projection accepts all 15 sockets and reports
4,000 basis points of magic penetration, 3,000 magic damage bonus and 3,000
critical damage from these sockets. Added penetration takes the previously
audited total from 32% to 72%, below the 80% combat cap.

Using the prior merged stats, Alpha's effective magic defense is now
`2500 * (1 - 0.72) = 700`. Flame Blast V is predicted at 37,934 normal or
71,087 critical against Alpha, before any other encounter/status changes.

The subsequent live run at 01:36 UTC confirms 37,934 on the initial hits and
single-target continuations. This is +3,531 over the former 34,403 normal hit.
The runtime socket projection was checked again and still accepts all five
effect-2/value-800 additions.

The critical forecast above is conditional and not attainable against Alpha
with AresMage's current Critical rating. Live Critical is 206; the level-200
boss inherits 2,632 Critical Resistance. V4 retains the PvE V1 chance rule:
`clamp(500 + trunc(4500 * (206 - 2632) / (5100 + 206 + 2632)), 0, 5000) = 0`
basis points. The recorded post-entry, map-transition and skill-594 status
updates add zero Critical. The +30% critical-damage sockets therefore do not
increase damage against this boss in that stat state. This audit made no
combat, boss-stat or character-stat changes.

The Release build and two relevant protocol checks passed. The grant passed
a rolled-back dry run, then ran while Tempest was stopped after a verified
full database backup. Runtime projection was checked before restart.
Tempest restarted healthy with zero restarts; schema, all 11 publications,
talents, ports and peer services were preserved. Inventory stayed identical
to the authorized post-grant snapshot across startup.

Image: `sha256:6bbcfaaf7aa4374c64b307e478ec845d792ad6c40c1f611d7165827558a30d09`.
Its server assembly SHA-256 matches the earlier shared-formula release with
Alpha defense 2,500: `f4782ad93b0bf064203306595e10b631d50396b5b8cee03a2c57c9f80beff6e7`.
Exact SQL, backup, audit receipt, runtime readback and deployment evidence are
in `artifacts/aresmage-third-socket-20260914/`.
