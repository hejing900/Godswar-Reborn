Bloodfang was installed on 2026-09-14 as species46 in the Tempest development
server and both locales of `C:\Godswar Origin`. It uses the original small
vampiric dragon mesh, rig and animations from
`artifacts/bloodfang-vampiric-dragon-20260914/native`. Both genders and all four
rebirth thresholds resolve those assets. The current UI uses the existing
native dragon portrait and generic egg/jade icons; no existing 3D pet is replaced.

The client content installer adds29 files/edits with exact backups and lossless
text insertion. A guarded binary successor changes four comparison bytes to
admit species46 in appearance and gender refresh packets, preserving all later
title/combat patches. Installed executable SHA256:
`402B2E777AF33A8BE82AF0BB74CF910C58BFA14E155CFAAAC3B8F53CC7DA0F66`.

Server migration151 adds the species identity and the explicit46-to11096 Magic
Jade mapping. Bloodfang Egg10194 hatches with VampiricI6400; jade11096 changes
appearance while retaining existing stats and skills. Item11095 remains
Ambrosia of Rebirth. All45 existing species and their historical content remain
readable. Current publications:

- Pet V11: `38E7F45D43BE3EDF757CC97B63661FE39C417D20371140D80E6D282E59BB2329`
- Items,1795 entries: `9F32B3E3AF965D23FB8156BFB89CEA38CC061E69059885D2610C235D7982D965`
- Runtime image: `sha256:c0620e735b3cfcec553f927d77a2a537d93fc5e623ed752750c3195b605b185c`

At the user's request, AresMage's existing pet199 changed from species12 to46.
Its name AresMageBond, level120, rank30, sex, bound/carried/summoned state,
Basic Savvy total1500 and learned skills2800/800/6405 remain intact. Both species
have merge factor2.6. Final pet revision is143. VampiricVI remains20% of actual
damage per target; the existing merged flat-healing forecast remains2584.

The cloned-database rehearsal exposed an older administrative Strength grant
that changed Added Savvy to650.51 but left growth at3 per level. Exact startup
validation correctly rejected the inconsistent state. The guarded repair sets
growth acceleration2.420917 and derives Added Savvy650.510040 at level120.
Six-decimal growth cannot represent650.510000 exactly at that level. This
nearest representable value changes no displayed centi-unit, leaves Basic Savvy
unchanged, and retains displayed totalStrength750.51 and the same integer
healing projection. No runtime validation was weakened.

Validation passed: build with zero warnings/errors; eight focused pure protocol
and migration checks;434 native patch assertions;14 client compatibility and
transaction tests; and three restored-database checks for additive item
publication, actual hatch/reconnect and historical-dragon jade conversion.
The actual AresMage repair and appearance SQL were also rehearsed on the clone.
Live snapshots verify that startup preserved the repaired pet, appearance change
preserved all pet stats/skills, and unrelated inventory, talents, other pets,
publications, runtime configuration and PostgreSQL/Redis services were unchanged.
Tempest became healthy with zero restarts. Actual in-game rendering and animation
timing still require a client playtest; the native parser and exported poses have
already been verified independently.

Release evidence and exact backups are under
`artifacts/bloodfang-install-20260914`. The deployment's first wrapper stopped
after successful Docker recreation because Windows PowerShell interpreted normal
Docker stderr progress as an error. `deploy.ps1 -Complete` resumed guarded
post-startup verification without repeating the repair or restarting the server.
The wrapper now checks Docker's exit status explicitly.

Client content backups are under `C:\Godswar Origin\backups\bloodfang` and
the executable backup under `backups\bloodfang-species46`. The prior runtime is
preserved as `reborn-server:before-bloodfang-20260914`. Rollback requires stopping
Tempest, reviewing any later player activity, reverting pet199 to its prior
species with a new revision, restoring the prior item/pet publication pointers,
then selecting the preserved image and reverting the client additions. Keep the
valid Strength growth repair and immutable content history. Do not restore the
full database backup over later player progress automatically.

Reapply/readback commands:

```powershell
python tools/PatchClientBloodfang.py --client-root 'C:\Godswar Origin' --repository-root C:\Reborn --apply
& tools/PatchClientPetSpecies46.ps1 -Mode Status
python tools/TestClientBloodfang.py
```
