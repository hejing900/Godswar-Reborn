# Ordinary Transporter

The ordinary world Transporter is a finite server-owned dialogue and map
admission path. It is separate from scheduled event transport, battlefields,
duel arenas, and instanced dungeons.

## Evidence boundary

The stock client establishes dialogue index `1`, the menu/result sub-IDs, the
destination labels, and the capital level requirements. Existing external
captures do not contain a completed ordinary Transporter interaction, so the
map bindings below are an explicit server-authored mapping to the reviewed
world topology. Landing positions are safe inward points derived from the
target map's reciprocal walking portal; they are not claimed to be stock
server coordinates.

## Published endpoints

| NPC | Map | Interaction ID | Menu |
| --- | ---: | ---: | --- |
| `Sparta_042` | 0 | 5039 | `1,3,2,8,9,10` |
| `Athens_041` | 1 | 5180 | `4,6,5,7,9,10` |
| `Mycenae_All_013` | 6 | 59721 | `1088,1089,1090` |

Capital routes are ordered by progression level. Sparta routes lead to the
Suburbs of Sparta, Peloponnesus, Nemea, Nemea Forest, Thermopylae, and Thebes.
Athens routes lead to the Suburbs of Athens, Marathon, Parnitha, Parnitha
Port, Thermopylae, and Thebes. Their minimum levels are respectively 1, 30,
40, 70, 100, and 130. A rejected Athens route returns native result page
`2/1000`; Sparta returns `2/1001`.

Mycenae's outbound choices lead to Olympia, Delphi Forest, and Larissa. They
have no additional gate because reaching Mycenae is the admission boundary.
The separate Thebes-to-Mycenae time, level, and Silver workflow is not part of
these outbound choices.

## Authority and safety

Actions must be the canonical 92-byte NPC function frame, repeat dialogue
index `1`, contain the exact 18-value empty argument path, originate from the
published NPC on the character's current map, and select a menu entry owned by
that endpoint. The character must first open that exact Transporter's menu
while alive and within 12 world units. This issues a one-use, two-minute lease
bound to the account, character, NPC, source map, and world instance; distance
and living state are checked again when a destination is selected. Accepted
routes reuse the normal authoritative map-transition pipeline: checkpoint
persistence, map/world ownership transfer, native scene change, client
readiness, destination visibility, status refresh, and EXP boost refresh.

`Nemea_1_022`, `Parnitha_1_022`, and `Thebes_All_027` exist as client/template
definitions but are not present in the reviewed spawn publication. They must
not be assigned guessed interaction IDs. They can be enabled in a later NPC
spawn release after authoritative placement evidence is available.
