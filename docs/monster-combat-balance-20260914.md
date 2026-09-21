# Database boss Critical Resistance

Boss Critical Resistance is now editable in PostgreSQL at
`public.monster_combat_balance.critical_resistance`. The primary key is
`(map_id, template_key)`. `display_name` makes the rows readable to operators.
The column is a nonnegative rating, not a percentage; zero is supported.

Migration `20260914_150_monster_combat_balance` initializes every listed
Wonderland, Medusa and Atlantis boss to **100**. There are 22 distinct bosses
and 26 rows: Medusa has four Normal-map identities and four Enhanced/Mythic
identities. Wonderland has 13 and Atlantis has five. The migration preserves
existing operator values if its seed SQL is replayed.

## Editing resistance

Inspect the authoritative rows:

```sql
SELECT map_id, display_name, template_key, critical_resistance
FROM public.monster_combat_balance
ORDER BY map_id, display_name;
```

Example for Alpha Demon; replace the assigned number for future tuning:

```sql
UPDATE public.monster_combat_balance
SET critical_resistance = 100
WHERE map_id = 207 AND template_key = 'B_boss_xerxer_001'
RETURNING display_name, critical_resistance;
```

Restart the affected server workers after editing. No rebuild or gameplay
publication is needed. Values are loaded into an immutable startup snapshot;
an existing process retains its loaded values until restart. Restarting a
worker interrupts its active instance sessions, so schedule changes accordingly.

This table currently controls Critical Resistance. A missing row uses the
existing generated rating. New rows must identify an exact published boss
template and map; malformed, duplicate, unknown or non-boss identities are
rejected instead of silently ignored.

## Runtime behavior

The database loader reads balances in the same read-only repeatable-read
transaction as world content, after verifying the immutable gameplay revision.
The separate balance revision participates in worker coordination, so workers
using different tuning cannot be treated as compatible. Combat itself uses
in-memory values and performs no database queries.

The catalog applies database resistance after generated and per-instance
profiles, retaining it through Wonderland's custom stats. Player basic attacks,
single-target skills, AoE and repeated Flame Blast pulses consume that rating.
Wonderland's allied boss assistance also reads the configured boss resistance.

With AresMage Critical 206 against a level-200 boss at resistance 100, the
existing PvE chance calculation gives **5.88%**, instead of zero at resistance
2,632. This changes the chance of a critical hit, not normal-hit damage.

## Verification

The Release build completed without warnings or errors. Ten selected checks
passed, including an isolated PostgreSQL test that changed Alpha resistance
from 100 to 317, reloaded it into combat, preserved the original loaded snapshot,
and confirmed seed replay did not reset the edit. The other checks cover exact
identity isolation, zero ratings, authored overrides, coordination fingerprints,
Wonderland, Medusa, Atlantis, player ECS and Flame Blast pulses.

Release evidence, migration checksum, source hashes, test reports, backup and
deployment receipt are in `artifacts/monster-combat-balance-20260914/`.

Deployed at 2026-09-14T02:25:02.3928838+00:00. Tempest is healthy with zero restarts,
and its startup balance revision matches the26 database rows. Existing schema,
all11 content publications, inventory, talents, ports and peer services were
verified unchanged apart from the new balance migration/table.

Runtime image: `sha256:132b7b9361595a6c2333dffb187cc1fa116e4d0c59990299fdf8359b51acace0`.
