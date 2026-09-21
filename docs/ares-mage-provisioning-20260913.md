# AresMage isolated development provisioning

Created the separate `aresmage` account and `AresMage` character on Tempest.
Account ID is 7256, character ID is 7009, and pet ID is 199. The committed
transaction verified that every pre-existing row across 186 public tables
remained unchanged, including test25/AresTempest.

The subsequent [Zodiac, mount and MP-recovery completion](ares-mage-completion-20260913.md)
records Zodiac20/all16 grids31, Erebus Lion and full MysticG12 Faithcreed mount
equipment, raising normal passive recovery from634 to994MP every6seconds.
The original creation details below are historical.

The default provisioning command is read-only. Apply refuses any existing
case-insensitive account or character name, so it cannot overwrite this character.

## Level-140 talent correction

The initial creation omitted character talents. The corrected future fixture
now grants all 18 published mage talents, IDs 100 through 117, at rank 60 before
calculating current HP/MP. `TalentProgression.CalculateRequiredPlayerLevel(59)`
is 140; the next upgrade requires 141. The global rank-100 cap is reached at
level 160 and is not the level-140 allocation.

The published mage definitions require zero predecessor/total ranks and have
no equipment prerequisite. The fixture pins the exact 18-ID set and these
conditions, rejects existing talent rows, and preserves the ten unspent talent
points and zero talent EXP. Initial `outbox_revision` is zero: provisioning
does not impersonate 1,080 paid upgrade commands or manufacture their receipts.
The existing all-table comparison now permits only this newly created
character's talent rows, preserving every pre-existing character.

At rank 60 the effective stat rank is 80. The talents contribute 6,400 maximum
HP, 2,560 maximum MP, 1,760 magic attack, 640 physical defense, 960 magic defense,
800 absorption, 560 hit, 320 dodge, 96 critical, 80 critical resistance, 800 HP
recovery, 320 MP recovery and 48% magic damage bonus before other systems.
Base HP/MP are not overwritten with these derived totals.

The existing character was repaired at **2026-09-13 06:34:40 UTC** using
`artifacts/ares-mage-20260913/grant_level140_talents.py`. Its serializable
transaction locked the exact account and character rows, rechecked level 140,
Mage profession, active lifecycle, offline login presence and released checkpoint
ownership, and required all target talent rows to be absent. It inserted only
IDs 100–117 at rank 60 with initial outbox revision zero.

The committed transaction verified the entire character-base row and every
other character's talents remained unchanged. Post-commit readback verified
the exact 18 rows, equipment digest, ten unspent points, zero talent EXP,
current HP 7,396, current MP 316 and map 207. The repair did not heal, relocate,
change base stats or reset equipment. A fresh login loads the talents and
recalculates their derived bonuses. No post-repair native rendering was tested.
Evidence: `talents-before-20260913T063439Z.json` and
`talent-repair-receipt.json` in `artifacts/ares-mage-20260913`.

`python tools/TestProvisionAresMage.py` passed all five hermetic checks:
native password encoding, live/existing-account rejection before I/O, SQL
drift rejection, a single quoted credential within one transaction, and talent
insertion before derived vitals with existing-row preservation. The additional
C# policy assertions passed in **All-class talent rank-100 progression policy**.
The Release build completed with zero warnings/errors; the secondary-combat
projection and ordinary intoned combat lifecycle checks also passed (three
selected checks, no failures or skips). The latter verifies actual lifesteal
healing through both Legacy and ECS mage skill paths. Results are recorded in
`artifacts/ares-mage-20260913/talent-and-life-absorption-checks.json`.
The corrected create-only SQL
has not been run against a database and remains unable to overwrite AresMage.

The lifesteal audit found pet 199 summoned but not merged
(`contributes_to_character=false`), no persisted owner-Merge bonus rows, and no
Life Absorption equipment affix. This saved configuration has no on-hit
lifesteal source; activating Merge supplies the pet contribution. Separately,
the existing PVE lifesteal publisher sends HP/MP updates but no floating healing
number. Neither combat publication nor the pet's active state was changed in
this repair. Aquatic Rejuvenation, the mage's HP-regeneration talent, is now
rank 60 and contributes 800 HP recovery before other modifiers.

The original creation and login evidence below describes the pre-correction
character and retains its historical HP/MP figures.

## Original creation evidence

The reviewed plan is account `aresmage`, character `AresMage`, level140 Mage
(profession3), Sparta (camp0), map0 at165,-97. It uses the normal10000silver,
10gold,0BGold and10unspent talent points, plus ten starter HP potions and ten
starter MP potions. The original creation granted no talents, sockets, elements,
mount, donor tier or titles. Eleven main equipment slots have class-eligible Spell Break gear,
Mystic quality10, grade12 and PlatinumI401. Each gear piece has five permitted
mage-oriented native affixes. The two ring slots use3265. Suitpoints are
recomputed through the current function:11×31=341.

Eleven combat families receive their highest learnable rank at140, plus Sparta
capital/suburb portals and Riding Skills. BaseHP/MP remain the normal1500/177;
current vitals are filled to the calculated equipped maxima. The compatibility
stat view omits runtime's per-item suit multiplier, so this narrow fixture adds
the exact quality-indexed, integer-truncated PlatinumI delta and asserts the
reviewed result:4365HP and990MP. The real login probe should independently confirm
currentHP=maximumHP and currentMP=maximumMP.

The carried, initially unsummoned pet is Smart Blue Crystal Dragon
`AresMageBond`, species12, level120, rank1.00, no rebirths or pet merges and no
unspent EXP. Current Basic Savvy is exactly1500:

| Stat | Basic |
| --- | ---: |
| Agility |600|
| Strength |100|
| Accuracy |200|
| Technique |150|
| Wisdom |150|
| Luck |300|

Agility supports the project's owner-Merge magic attack/MP channels; Luck supports
magic damage. A valid Smart birth baseline180 is preserved as30perstat. Revealed
Growth3perstat totals18 within the published Smart16–23 bracket. With no growth
acceleration, Added Savvy is360perstat at120, separately from the requested
1500Basic total. Natural Smart talentmask26 provides Quest/Healing/Merge; there
are two normal open skill cells containing IceshotI2800 and MysticOracleI800.
No stored owner-Merge bonus is fabricated and Merge is initially off. Mystic
Oracle is a valid native learned skill; this does not claim additional durable
stat support beyond the server's implemented skill-effect projections.

Read-only plan and hermetic checks:

```powershell
python tools/ProvisionAresMage.py
python tools/TestProvisionAresMage.py
```

The operator coordinates a stopped-server window and the live execution. After stopping
the exact reviewed Tempest image and completing the disposable SQL preview:

```powershell
python tools/ProvisionAresMage.py --apply
```

The runner checks isolated-development container identities, the exact image,
target absence and the target's hashed login-name lease. It creates a fresh
ACL-private artifact directory containing a validated full PostgreSQL backup,
`credentials.private.json` and a non-secret `receipt.json`. The password is
24printable ASCII characters. The stock client's lowercaseMD5 wire credential
is protected with PBKDF2-SHA256600000, a fresh16-byte salt and32-byte key; secrets
are passed through stdin and never printed or placed in process arguments.

SQL runs as one serializable transaction with a bounded lock/statement timeout,
current-content pins and no other database client connected. It snapshots every
existing public base table, writes only new identity-owned rows, creates the
normal economy/inventory baseline, and compares all pre-existing rows again
before committing. Any unrelated change, including test25 data, rolls back.
The receipt records created IDs, stats, content/script identity and the backup
hash. Script hashes are rechecked immediately before execution.

If the transaction fails, leave the server stopped while inspecting the cause;
the transaction has no partial character state. PostgreSQL identity sequences
can advance across a rollback. Do not rerun an ambiguous completed operation:
the default read-only command can establish whether the name now exists.
Restore a backup only as a separately reviewed recovery action. The runner does
not stop/start the server or restore data automatically.

Validation: four hermetic checks passed (native credential boundary,
live/existing-identity rejection before I/O, SQL drift rejection, and one quoted
credential within one transaction). Read-only status confirmed the target did
not exist. The full SQL transaction passed against an isolated restored database
with a final rollback. That check also caught and corrected the verification of
absent class/element attributes: their canonical database representation is NULL.
The temporary validation database was removed after successful live creation.

The live transaction committed with 51,955 current/max HP and 5,463 current/max MP.
Its fresh database backup SHA-256 is
`f99e6df93ca5b32885cc2480c3ea7fd1c54d4843c7d45f1df365bd0d959a5935`.
The private backup and credentials are in the ignored, ACL-restricted
`artifacts/ares-mage-20260913` directory. The creation receipt and SQL hashes are
also recorded under `artifacts/wonderland-followup-20260913`.
Tempest restarted healthy with the reviewed image, zero restarts and unchanged ports.

Native login and full world entry passed on the actual local endpoints. The
210-packet bootstrap confirmed AresMage's name, Spartan faction, Mage class and
level 140. Pet 199 was carried, level 120, with skills 2800/800 and the exact
requested Basic vector totaling 1,500; Added Savvy was independently decoded as
360 per stat. The first probe used an NPC outside the spawn's visible area;
the corrected probe opened the visible Teaching Manager (5066).
This probe exercised protocol loading, not manual client rendering.

After disconnect, login presence, checkpoint ownership and the Redis login-name
lease were all released. Current vitals remained 51,955 HP and 5,463 MP. Evidence:
`mage-native-probe-final.json` and `mage-final-readback.json` in the followup
artifact directory. The private `Login.txt` contains only the account, typed
password, character and realm for convenient use in the client.
