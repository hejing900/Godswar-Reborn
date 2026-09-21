# AresMage pet Strength and Extraction II

Subsequent user request: Extraction II was removed from pet199. Strength750.51,
rank30, the opened third slot and the original two skills remain. The offline
removal advanced pet revision139 to140 and preserved every Savvy row. Evidence
is in `artifacts/aresmage-remove-extraction-20260914/`. Expected Merge-only
healing is now2,584; the225 learned bonus described below is no longer equipped.
The remainder records the earlier completed grant and runtime support change.

Updated AresMageBond (pet199, character7009/account7256) to total Strength
750.51: Basic100 + Added650.51. Other Savvy values and the total1,500 Basic
Savvy are preserved. Added Extraction II (2018, priority2) in a third opened
skill slot, preserving the existing two skills. Pet rank is30, the minimum
for its published225 healing step; birth-rank evidence remains unchanged.
Rank30 was the stated default after the optional rank question had no reply.

Extraction's published family341/effect34 previously had no owner-stat
projection. It now supplies `life_absorption_flat` from the selected carried,
owned pet's active learned skill, using the pinned skill publication and
rank thresholds. It combines once with independent owner-Merge healing and
does not require the pet to be merged or visible. No per-character healing
constant or skill-ID special case was introduced.

The live learned-skill projection gives225 unmerged. The unchanged published
project Merge curve gives:

```text
100 + 60*5 + 90*4.25 + 150*3.5 + 300*3 + 150.51*2.5
= 2583.775
Including Extraction II: 2583.775 + 225 = 2808.775 -> 2809 HP
```

Expected normal full healing while merged is therefore2,809 per damaged
monster, subject to missing HP and existing healing modifiers. The external
pet's2,666 uses a different Merge curve; this task matches Strength and adds
Extraction II without changing global Merge balance. Merge remains inactive
after this offline grant and is activated by the player normally.

Release build passed with zero warnings/errors. All five selected checks
passed with no skips, including an isolated PostgreSQL full character-stat
projection test for180/193/208/225 rank steps, inactive/uncarried exclusion,
unrelated same-effect family exclusion, and independent Merge composition.
Per-monster healing and recurring Flame Blast checks also passed. Disposable
PostgreSQL was removed after testing.

Deployed2026-09-14T05:08:30Z to `godswar-dev-tempest-openworld-01`, image
`sha256:da5fb24731753e86b159fdf52f55f688083d3a7321978939d243f73ef7ef55b4`.
Healthy, zero restarts/OOM. Schema, all11 publications, other pets, inventory,
talents, boss balance, ports and other services were verified unchanged.

Evidence: `artifacts/aresmage-extraction-strength-20260914/`, including the
validated private pre-grant database backup, grant receipt, source hashes,
protocol results, runtime projection and deployment receipt. The first QA
expectation incorrectly totaled the Merge curve as2,621 instead of2,584;
`verification-correction.json` records the arithmetic correction. The grant
was already correct and was not repeated; `complete-deployment.ps1` resumed
verification and deployment. No production formula was changed to fit the
mistaken expectation, and no interactive combat session was simulated.
