Vampiric is a new shared pet skill. Tiers I–VI heal 6%, 8%, 11%, 14%, 17% and 20% of the HP actually removed from a target. The selected carried pet supplies the passive, whether summoned or recalled; Merge is not required. Existing flat owner-Merge healing remains a separate contribution. Extraction II remains removed from AresMage's pet.

Each damaged target contributes separately, including area attacks and Flame Blast pulses. Misses, zero damage and reflected damage grant no healing. Overkill uses actual HP removed, and healing is capped by the owner's missing HP. The existing combat settlement prevents duplicate healing when an attack is replayed. These rules apply through the existing percentage-life-absorption stat, without a second damage formula.

| Tier | Heal | Runtime skill | Book | Required Accuracy |
|---|---:|---:|---:|---:|
| I | 6% | 6400 | 16400 | 0 |
| II | 8% | 6401 | 16401 | 64 |
| III | 11% | 6402 | 16402 | 192 |
| IV | 14% | 6403 | 16403 | 235 |
| V | 17% | 6404 | 16404 | 270 |
| VI | 20% | 6405 | 16405 | 305 |

Family 428 has one rank-zero step per tier, so pet rank does not change the percentage. Books use the normal durable learning path and require the preceding tier. Upgrading replaces the same slot; active lower tiers do not stack. Existing species-exclusive books retain their restrictions. Books have no new vendor listing or sale price.

The immutable learned-skill publication advances from `64748AC27B0D815B9C30CFF78A7CE8AD519AE83DF528CB5CDFF4374503ABB473` to `4B57F8562B679692E2C1517D26290FE9D05D1CF079492CB3E785284F56E7260A`. All 384 original curves and 1,655 steps are preserved; six curves and six steps are appended. The current 1,787-item publication gains six books, producing `A9987EF33AC288A99A86CC18043C3E91005A816B3003CB34AE7B1B5CAC20931E` with 1,793 items. No schema migration is required.

The release grants Vampiric VI in pet 199's free third slot for AresMage. Its existing Iceshot and Mystic Oracle, rank 30, Strength 750.51 and total Basic Savvy 1,500 are preserved. While unmerged, its pet healing contribution is 20%; merging adds the existing 2,584 flat healing. For 40,000 actual damage, that is 8,000 from Vampiric, plus 2,584 when merged, before the missing-HP cap.

Release evidence is under `artifacts/vampiric-pet-skills-20260914`: content and projection SQL readbacks, a rehearsal on a restored database copy, guarded grant, backups, test reports and deployment receipts. The rehearsal preserves existing item definitions, 69 historical item revisions and all owned inventory. Client details and reproduction steps are in [the client patch notes](vampiric-pet-client-20260914.md).

Rollback requires stopping Tempest, removing only the added 6405 skill with guarded state checks, restoring the two predecessor publication pointers, and recreating Tempest from the preserved image. Leave immutable new content history in place. A full backup is available, but must not overwrite later player progress blindly.

Deployed and verified: Tempest image e751df12a83d2278905724f0f46f8baa0776693b44fd82f77a27736160534e16 is healthy with zero restarts. Pet 199 is revision 141 with Vampiric VI; live content and percentage projection match the rehearsal. Non-target pets, inventory, talents, boss balance, other publications, ports and other Docker services are unchanged. Validation passed: 13 initial server checks, two final checks (real book learning and updated area healing), two cloned-database publication checks, and 12 client patch tests. The final build has zero warnings/errors. A prior concurrent build encountered a Windows test-DLL lock; the sequential retry passed. Native visual rendering still needs an in-game check.
