# Divinium vendor crash diagnosis

Opening the Holy Suit vendor crashed the native client at `006EBF84` on
2026-09-11 at 12:46:17. The fault dereferenced a null icon-coordinate pointer.
The return address `004E0BDF` follows the call to the NPCTrade catalog renderer
at `005AFFD0`. The client executable was `C:\Godswar Origin\Origin.exe`.

Item 9017 (Divinium Essence) existed in valid XML but was a direct child of
`ItemBaseAttribute`, while its sibling wares were children of `Item`. The
native loader treats top-level elements as containers and loads their child
rows. It never parses a root-level item row. Thus Divinium was unavailable
when the newly stocked item first needed an icon.

Native evidence from this executable:

- `0043EB10` loads the item document; `0043EBB4` selects each top-level
  container's child pointer. `0043EC93` through `0043ECB5` skips a container
  with no children. `0043ECBA` calls the item parser `0043ACC0` only for child
  rows. Weapons has one additional group level.
- `0048C159` accepts up to 32 records per catalog frame. NPCTrade initializes
  45 cells per category at `005AFF77` and indexes categories with a stride of
  45 at `005B0268`. The 19-item Holy Suit tab uses frames of 16 and 3; this
  stays within both bounds. Other vendor tabs already use continuation frames.
- A new single Divinium record matches the captured Seraphite record except
  for its item ID, approved price and caption field before catalog assembly.
  The assembled caption remains the same for every Holy Suit item. Bulk
  listings intentionally differ in quantity preset byte 27 (25 versus 1).

The fix belongs in the client metadata and installer: move the unchanged
9017 row into the same `Item` container as 9016. Catalog ordering, prices,
item IDs, inventory, content revision and server vendor behavior need no
change. A complete client restart is required because item definitions load
at startup.

The server protocol regression now checks every ID in the generated vendor
catalog against repository XML using the native traversal depth. It reproduced
the original failure with exactly one missing item: 9017. Its negative case
moves Divinium back to the root in memory, proving that well-formed XML alone
cannot pass the check. The client installer has its own placement regression.
Tests do not depend on a locally installed client or modify source fixtures.

After the repository item row was placed under `Item`, the full captured
capital NPC protocol check passed (one passed, zero failures or skips).
The Release build passed with zero warnings or errors. The failing pre-fix
result is retained alongside the passing result. No server production code
changed for this fix, so the previously verified purchase and publication
transactions remain unchanged.

Crash reports, native disassembly and verification receipts are under
`artifacts/divinium-vendor-crash-20260911/`.
# Installed repair and daily Wonderland admission

Both installed client locales now place Divinium 9017 inside the same `Item`
group as Seraphite 9016. The Holy Suit installer repairs the historical orphan
and inserts fresh definitions in that container. Repository XML and Divinium
text now carry the corrected definition as well. Real installed-file checks
confirm all eight wares are uniquely reachable by native loader traversal.
No artwork, prices, or quantity presets were changed by this repair.

Client repair changed exactly two item XML files, followed by two Wonderland
dialogue files. Three native-container tests and all 38 Holy Suit installer
tests passed. The vendor/client definition regression fails on the original
orphan and passes on the repair. Ascension Core and Socket Spell releases
still verify. This is native-code, dump, and data validation; an interactive
in-game retry remains necessary after completely restarting the client.

Wonderland now permits every weekday, retaining three free daily entries,
level 120+, one to five players, 40-minute runs, and a 23:00 Asia/Manila entry
cutoff. Four focused runtime/protocol checks passed, including actual Friday
admission, Sunday admission, Manila midnight rollover and cutoff rejection
without consuming a claim.

Deployed server image:
`sha256:9af2e936772d91f321829631d7ad94593c46e6a50290d62de4c23ae4ee71296c`.
Tempest is healthy with zero restarts; development isolation passes. Database
publication, policies, and owned inventory match the stopped backup. All
installation, backup and verification evidence is under
`artifacts/divinium-vendor-crash-20260911/`.
