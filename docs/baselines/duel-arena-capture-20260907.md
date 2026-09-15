# Duel Arena NPC capture, 2026-09-07

The Arena release follows `external-20260907-143201-403.log`. Its initial
roster and travel observations were recorded on 2026-09-07 between 15:40:24
and 15:41:02 (+12:00). That inspected snapshot was
3,221,782 bytes with SHA-256
`E8906579F473232CE5A16295BFE82889B2AF0B49E503A444D8D329A5E4B098A9`.
The local extracted evidence is
`artifacts/duel-arena-capture-20260907/arena-npc-evidence.json`. This reference
records NPC and travel evidence only; account data and raw login traffic are
not needed to reproduce the release.

The later dialogue capture records five additional NPC visits between
16:33:12 and 16:33:30 (+12:00). Its sanitized event sequences and server
dialogue packets are under `artifacts/duel-arena-dialogues-20260907/`.
The finalized event snapshot was 4,732,995 bytes, ending at 16:38:34, with
SHA-256 `3359E42015C59E6527BCA56E643E8EE791E446F3E950622F27C9C5A4CC8604E4`.
A read through 16:47:14 still contained no additional travel actions.
The later **17:29** capture adds the Doorkeeper's actual exit to Sparta;
that evidence and its different destination map are documented below.

## Published roster

All seven actors belong to map **57**, scene **Arena**. The capture prefixes
each template with `gwprivate_`; the server uses the normalized template keys
below for Origin. Object IDs and interaction IDs are equal.

| NPC | NPC key | ID | Normalized template | X | Z |
| --- | --- | ---: | --- | ---: | ---: |
| Arena Vendor | `Arena_001` | 5198 | `Arena_001_FemMale14` | -108 | 81 |
| Arena Doorkeeper | `Arena_002` | 5197 | `Arena_002_Male18` | -110 | 102 |
| Arena Gatekeeper | `Arena_003` | 5199 | `Arena_003_Male18` | -99 | 68 |
| Arena Ward | `Arena_004` | 5201 | `Arena_004_Male18` | -48 | 40 |
| Physician | `Arena_005` | 5200 | `Arena_005_yishi` | -93 | 100 |
| Airdrop Merchant | `Arena_006` | 5203 | `Arena_006_AirDrop` | -118.98906707763672 | 98.9961166381836 |
| [Warehouse] Akou | `DuelArena_001` | 5202 | `DuelArena_001_Male3` | -103.50323486328125 | 103.38972473144531 |

Each captured opcode-10020 appearance has Y = **0**, facing =
**2.3218750953674316** (single-precision bits `0x4014999A`), and appearance
flags `0x0211`. With map 57 in the high word, the object-type field is
`0x00390211`. The five existing NPC appearances match the stock client
templates after removing the prefix.

The external appearance frames are **104 bytes**. Origin retains the existing
server **108-byte** appearance format and its normal initialized fields; this
release copies the captured identity, template, placement, facing, and type.
It does not replay raw external appearance frames or unrelated packet fields.

At the captured upper arrival, the observed group contains the six actors
other than the Ward. The Ward appears on the lower arena floor. The current
roster replaces the earlier authored lobby cluster.

## Captured travel

| Actor clicked | NPC ID | ACK client script key | Native function | Direct action | Destination X, Z |
| --- | ---: | --- | ---: | --- | --- |
| Gatekeeper `Arena_003` | 5199 | `Arena_002` | 87 | 10069, sub-ID -1 | -5, 32 |
| Ward `Arena_004` | 5201 | `Arena_004` | 88 | 10069, sub-ID -1 | -104, 96 |

The Gatekeeper's ACK alias is intentional: the captured actor is
`Arena_003`, while its advertised client script is `Arena_002`. The nearby
Doorkeeper is a separate actor and is not the observed lower-arena return
endpoint.

Both sequences begin with a **48-byte** opcode-10067 click and a **48-byte**
10067 ACK. ACK flags are **512** (`0x200`). The client then sends an **8-byte**
10068 page request and a **92-byte** 10069 function request. Travel happens on
that initial sub-ID **-1**, without an additional server-generated menu.
Origin already contains these native menu labels in `NPCDescription.dat`:

- `SYS_NPC_87`: "I want to go inside."
- `SYS_NPC_88`: "I want to leave."

The 92-byte function request carries eighteen argument words. Its first six
meaningful arguments are all **-1**. The remaining twelve words contain
native padding or stack residue in the capture. Their values are ignored;
they do not choose a destination or authorize an operation. The server still
checks the complete packet length, actor, map, both dialog fields, sub-ID,
and the six meaningful arguments. A nearby living character must first
receive click context for the matching actor and world instance; successful
travel consumes that context.

The observed scene changes remain on map 57:

| Entry | X | Captured Y | Z |
| --- | ---: | ---: | ---: |
| Initial arrival from the capital | -104 | 0 | 96 |
| Gatekeeper admission to the lower arena | -5 | 2.6832761764526367 | 32 |
| Ward return to the upper lobby | -104 | 5.814235210418701 | 96 |

Capital-to-Arena arrival and Ward return use the captured fixed point
`(-104, 96)`. The Y values above document the captured scene packets; NPC
appearance Y remains zero.

### Random lower-arena entry

The user confirmed that entry through the Gatekeeper selects random positions
inside the arena. Only **one** lower destination, `(-5, 32)`, was externally
observed in the available capture. The implementation therefore uses an
explicitly **authored** pool of **77** lower-floor landing points; it does not
claim that the complete pool or its distribution came from external packets.

Every point is within 20 world units of `(-5, 32)` and lies in that point's
walkable component of the stock `Arena.hmp` collision map. A conservative
clearance check requires at least 2 units; the selected pool's measured
minimum clearance from blocked cell rectangles is **3 units**. The Ward at
`(-48, 40)` belongs to the same lower component. The upper arrival and
Gatekeeper occupy a separate component. Terrain evidence and per-point
clearances are recorded in
`artifacts/duel-arena-terrain-20260907/arena-terrain-analysis.json`.

The server selects uniformly from these 77 positions for each admitted
Gatekeeper journey. Repeated selections are possible. This changes only
lower-arena admission; the Ward's return remains fixed at `(-104, 96)`.

## Later NPC dialogues, 16:33 capture

Each visit begins with a 48-byte opcode-10067 click and a 48-byte server ACK,
followed by an 8-byte opcode-10068 page request. The client also emits a
4-byte header-only opcode-10117 cancellation alongside the page request.
ACK function indices and script keys, rather than packet text, select the
labels already present in the client.

| NPC | Click time (+12:00) | ACK flags | Function index | Client script | Additional captured behavior |
| --- | --- | ---: | ---: | --- | --- |
| Physician `Arena_005` | 16:33:12.1527935 | 512 (`0x200`) | 32 | `Arena_005` | Initial action returns menu `[1, 100, 101, 102]` |
| [Warehouse] Akou `DuelArena_001` | 16:33:16.0540904 | 32 (`0x20`) | 0 | `Sparta_023` | Fourteen warehouse snapshot frames follow the ACK |
| Doorkeeper `Arena_002` | 16:33:20.2396274 | 512 (`0x200`) | 88 | `Arena_002` | Leave function advertised; this earlier visit contains no invocation |
| Airdrop Merchant `Arena_006` | 16:33:22.4182881 | 512 (`0x200`) | 95 | `Arena_006` | Initial function request has no menu response |
| Vendor `Arena_001` | 16:33:30.0733953 | 0 | 0 | `Arena_001` | Description only; no shop catalog captured |

Physician and Airdrop each receive a 92-byte opcode-10069 request with their
advertised function index, sub-ID **-1**, and six initialized arguments all
**-1**. The twelve remaining argument words are excluded from evidence and
ignored by the implementation. Physician responds with a **96-byte**
opcode-10070 packet, function 32, menu IDs **1, 100, 101, 102**, and sixteen
zero menu slots. Its final word at offset 92 is **6,496,257**
(`01 20 63 00`). The golden response and all seven NPC ACKs are preserved in
`artifacts/duel-arena-dialogues-20260907/npc-dialogue-golden-packets.json`.
No Physician treatment selection or healing transaction was captured.

Airdrop has no captured opcode-10070 menu response or opcode-10071 shop
catalog. A later opcode-10065 exchange is retained only as unclassified
timing/size metadata; it does not establish an Airdrop reward or purchase
operation. The Vendor likewise supplies only its description. Neither actor
is assigned invented shop stock or reward behavior.

Akou's ACK is immediately followed by **fourteen opcode-10034 frames of 888
bytes each**. Warehouse contents are excluded from the evidence. The server
routes Akou through the existing warehouse provider and normal authoritative
warehouse snapshot/access checks. No separate Arena storage or replay of
captured player inventory is introduced. No warehouse transfer was captured
in this visit.

The 16:33 Doorkeeper visit establishes only its function-88 advertisement;
the completed 17:29 exit below supplies the missing operation evidence.
The Physician menu does not establish treatment actions: treatment remains
unavailable pending operation evidence. Gatekeeper admission and Ward return
remain the travel pair between the two parts of the Arena.

## Doorkeeper capital exit, 17:29 capture

The user invoked the external Doorkeeper at **17:29:12**. Unlike the earlier
click-only visit, this sequence contains an initial function action followed
by a scene change to **map 0 / Sparta**:

| Time (+12:00) | Direction | Opcode / bytes | Captured fields |
| --- | --- | --- | --- |
| 17:29:12.0714610 | Client to server | 10067 / 48 | Doorkeeper `Arena_002`, NPC 5197 |
| 17:29:12.2948443 | Server to client | 10067 / 48 | Flags 512, function 88, script `Arena_002` |
| 17:29:12.2965897 | Client to server | 10068 / 8 | NPC page request |
| 17:29:12.8887771 | Client to server | 10069 / 92 | Both function words 88, sub-ID -1, six initialized arguments all -1 |
| 17:29:13.1125160 | Server to client | 10018 / 24 | Map 0, X 20.031299591064453, Z -100.11289978027344 |

The captured scene packet's Y is **5.554476737976074**. The scene change
arrives 0.223739 seconds after the action, and 42 subsequent Sparta NPC
appearance frames confirm the capital arrival. The sanitized evidence in
`artifacts/duel-arena-doorkeeper-20260907/doorkeeper-exit-evidence.json`
retains both complete 30-second observation windows. Its snapshot is
6,224,397 bytes, ends at 17:30:58, and has SHA-256
`4B111AB8BF3FB72FFA4F5C2E99AA0B089A2DA9925E9732031074021622D053E2`.

The earlier map-57-only scene filter would exclude this new map-0 exit.
It did not hide an exit from the 16:33 snapshot: that earlier visit had no
function invocation. Doorkeeper evidence must retain destination maps
outside the Arena.

The implemented leave action returns a character to its **faction capital**:
Sparta characters go to map 0, Athens characters to map 1, using the same
X/Z point above. The Sparta destination is externally observed. The Athens
destination is an explicit local counterpart policy, supported by the
byte-identical installed `Athena.hmp` and `Sparta.hmp` terrain files; an
external Athens exit has not been captured.

The server validates the existing function-88 initial action, consumes a
one-use click context tied to the current actor and world instance, and
uses the existing durable transition between maps. This is a capital exit,
separate from the Ward's fixed return to the upper Arena lobby. The captured
Y remains packet evidence; the runtime destination uses X/Z through the
normal transition pipeline.

## Origin asset compatibility

The required appearance aliases were installed for the V7 roster, and the
user confirmed that the NPCs now work. These dialogue changes use the same
existing client assets; **no additional client asset patch is required**.
The procedure below remains available for another installation that has not
received those aliases. For such an installation, close Origin before
applying them and restart it afterward so the updated catalogs are loaded.

No additional models, textures, or effects are required. The two additional
normalized template keys are aliases of existing appearances, with their
captured display names:

| Added template | Stock appearance copied | Display name |
| --- | --- | --- |
| `Arena_006_AirDrop` | `Arena_002_Male18` | Airdrop Merchant |
| `DuelArena_001_Male3` | `Athens_025_Male6` | [Warehouse] Akou |

All appearance fields, including Akou's body effect 3, match the respective
stock sources. The installer adds these sections to `NPC.INI` and adds their
names/descriptions to `NpcName.dat` and `NPCDescription.dat`. It preserves
UTF-16LE encoding and every existing byte by appending missing entries.
Conflicting entries are rejected. It does not modify the external capture
client.

From the repository root, inspect the target first:

```powershell
powershell -NoProfile -File tools/PatchClientDuelArenaNpcAliases.ps1 -Mode Status
```

Close the Origin client that uses the target installation, then install:

```powershell
powershell -NoProfile -File tools/PatchClientDuelArenaNpcAliases.ps1 -Mode Apply
```

The default target is `C:\Godswar Origin`; use `-ClientRoot` for another
installation. The process guard compares executable paths under that root,
so the separate external capture client can remain open. Repeated Apply is
a no-op after installation. Apply creates backups and reports a receipt
path. With the target client closed, restore that exact installation using:

```powershell
powershell -NoProfile -File tools/PatchClientDuelArenaNpcAliases.ps1 -Mode Revert -ReceiptPath '<receipt path from Apply>'
```

Revert requires current-file and backup checksums to match the receipt; it
does not overwrite intervening edits. Run Status again to inspect the result.

## Database publication

NPC **V7** publishes the captured seven-actor roster as a new immutable
release, preserving V1-V6. It has 390 total NPC definitions and revision
`AAA9812754984363A92891077212C30EE5D44EC321C746083EBBF84D3F7063B6`.

Dialogue **V20** targeted that exact V7 spawn revision. It supplied the two
additional NPC texts, restores the five stock Arena descriptions, and
replaces the previous Arena transport pair with the captured Gatekeeper/Ward
routes. Its revision is
`DAA3796DB22B08A419EBB95017FD0587ECEF66FEB92086EB9C741C2817E7291E`.
Dialogue **V21** preserves V20's **390 texts** and the V7 spawn revision while
adding three routes for the Physician, Doorkeeper, and Airdrop, bringing the
total to **32 routes**. Its canonical revision is recorded in
`NpcDialogueBaselineV21.ExpectedRevision`. The strict loader continues to
reject mismatched spawn/dialogue publications. V1-V20 remain historical
immutable releases.

Completing the Doorkeeper exit requires **no additional content publication
or schema migration**. V21 already publishes its exact function **88** and
initial sub-ID **-1**. The runtime now executes that existing leave action
using the subsequent 17:29 capture.

Migration **`20260907_140_duel_arena_initial_actions`** permits sub-ID -1 in
dialogue profile entries and admits the specific `Arena_003` → `Arena_002`
client-script alias. Runtime validation restricts these captured initial
actions to their implemented endpoints. Existing immutable publications and
unrelated NPC identities remain unchanged.

Migration **`20260907_141_duel_arena_services`** adds the finite
`DuelArenaServices` behavior **17** and permits its three service profiles.
The singleton profile index retains its restrictions for unrelated behaviors;
the existing travel exceptions are extended from `(14, 15, 16)` to
`(14, 15, 16, 17)`. The publication adds captured dialogue surfaces without
claiming that uncaptured treatment, rewards, or purchases are implemented.

Implementation references:

- `src/Godswar.Server/Domain/World/Content/DuelArenaCapturedLayout.cs`
- `src/Godswar.Server/Domain/World/Content/DuelArenaCapturedTransportProtocol.cs`
- `src/Godswar.Server/Domain/World/Content/DuelArenaEntryDestinations.cs`
- `src/Godswar.Server/Domain/World/Content/DuelArenaServiceProtocol.cs`
- `src/Godswar.Server/Domain/World/Content/DuelArenaExitProtocol.cs`
- `src/Godswar.Server/Game/GameClientHandler.DuelArenaExit.cs`
- `src/Godswar.Server/Infrastructure/WorldContent/NpcContentBaselineV7.cs`
- `src/Godswar.Server/Infrastructure/WorldContent/NpcDialogueBaselineV20.cs`
- `src/Godswar.Server/Infrastructure/WorldContent/NpcDialogueBaselineV21.cs`
- `src/Godswar.Server/State/DatabaseMigrations/PostgresSchemaMigrationCatalog.DuelArenaInitialActions.cs`
- `src/Godswar.Server/State/DatabaseMigrations/PostgresSchemaMigrationCatalog.DuelArenaServices.cs`
- `tools/PatchClientDuelArenaNpcAliases.ps1`
