# Native status-effect sync (10167)

The bundled client renders its buff/status bar from the complete
`S2C 10167 / 0x27B7` player-status snapshot. This is established by the
working-original captures, including Sacred Zeal casts. No clear opcode
`10120` status packet appears in those captures.

The old `PlayerExtendedStatusTemplate` must not be restored: its literal was
only 324 bytes despite its embedded 340-byte header, and its data region was
nibble-shifted. Always build this packet field-by-field.

## Packet layout

The packet is always 340 bytes:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | `u16` | Packet length (`340`) |
| 2 | `u16` | Opcode (`10167`) |
| 4 | `u32` | World object ID |
| 8 | `u32` | Active status count |
| 12 | `u32[20]` | Status IDs, ascending by ID |
| 92 | `u32[20]` | Remaining seconds paired with the status IDs |
| 172 | 168 bytes | Complete derived player/status data |
| 300 | `f32` | Aggregate fighter-EXP bonus |
| 324 | `f32` | Movement-speed multiplier; baseline is `1.0` |

The data block is an absolute snapshot, not a set of status deltas. The known
prefix is Max HP, Max MP, HP recovery, MP recovery, physical attack, physical
defense, magic attack, magic defense, Hit, Dodge, Critical, Critical Resistance,
physical damage bonus, magic damage bonus, damage absorption, received-healing
bonus, and healing bonus. Runtime Hit/Critical buffs must be added to the
character's derived totals before serialization. Sending a zero-based packet
would overwrite the client's displayed stats.

The original server allows ten beneficial and ten detrimental statuses. A
permanent status uses `4294967295` (`uint32 -1`) as the client-facing timer.
Every producer must compose all active sources into one replacement snapshot;
otherwise one status family will erase another.

The initial self snapshot is sent once after client opcode `10357`
(`EnterUiReady`). Sacred Zeal follows the captured order: cast visual (`10040`),
full status snapshot (`10167`), impact (`10046`), then mana (`10135`).

## Reborn membership and EXP status IDs

The installed English client definitions live in
`Localization/en_us/Settings/Sys/Status.ini`.

| ID | Status | Kind | Fighter EXP | Talent EXP | Pet EXP | Max HP | Physical/magical attack | Client time |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1500 | Kijin Patron | 1008 | +5% | - | - | +2% | +1% | Permanent while active |
| 1501 | Oni Patron | 1008 | +10% | - | - | +4% | +2% | Permanent while active |
| 1502 | Demon Lord Seed | 1008 | +15% | - | - | +6% | +3% | Permanent while active |
| 1503 | True Demon Lord | 1008 | +20% | - | - | +8% | +4% | Permanent while active |
| 1504 | Faction Area EXP Bonus | 1009 | Configured | Configured | Configured | - | - | 43,200 seconds |
| 1506 | Octagram Patron | 1008 | +25% | - | - | +10% | +5% | Permanent while active |
| 1507 | Premium Battle Pass | 1010 | +5% | +5% | +5% | - | - | Entitlement countdown, or permanent |

The five Donator definitions deliberately share kind `1008`, making account
tiers mutually exclusive. Faction control and Premium Battle Pass use distinct
kinds and stack with Donator and stock EXP families. Status `1505` is not
reused: an older Erebus Lion client patch assigned that ID before the installed
client moved the mount to status `1390`.

The Battle Pass client definition uses effects `15,32,34` with values
`0.05,0.05,0.05`, exposing its Fighter, Talent, and pet EXP benefits in one
status. Faction status `1504` uses the same three effect channels; its
authoritative reward rate comes from the active area's configured control row.
Donator and Trick or Treat remain Fighter-only. Donator HP and attack rates are
descriptive client metadata; the authoritative percentage-derived totals are
carried in the absolute `10166` game-data block sent alongside the `10167`
status snapshot. The server reconciliation pass removes membership icons after
their account entitlement expires.

The separate global monster-kill EXP multiplier has no status ID. It is a
startup-pinned database policy from `1x` through `5x`, applies to Fighter,
Talent, and pet EXP after their additive stacks, and is intentionally absent
from the fighter-only aggregate at offset `300`.

The guarded English-client deployment is managed by
`tools/PatchClientDonatorStatusLocalization.ps1`. `Status` recognizes the exact
`Original`, `AppliedV1`, `AppliedV2`, and `AppliedV3` section sets. `Apply`
safely upgrades any predecessor to `AppliedV3`, whose Faction Area and Premium
Battle Pass definitions both expose Fighter, Talent, and pet EXP through
matching three-effect and `Interval=0,0,0` vectors. It preserves unrelated
bytes, refuses the historical `1505` mount state, and requires Origin.exe to be
closed for writes. `Revert` requires the matching hash-pinned backup receipt
and restores the exact predecessor bytes; legacy v1 and v2 receipts remain
accepted. The disposable round trip is
`tools/TestClientDonatorStatusLocalizationPatch.ps1`.
