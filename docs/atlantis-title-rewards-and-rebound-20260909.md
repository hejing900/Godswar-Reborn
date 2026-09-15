# Atlantis title selection and passive deaths

Receiving an Atlantis completion title grants ownership without selecting it. A player with no displayed title keeps selection 0; a player wearing another title keeps that choice. The completion still awards 2,800 HardPoints, publishes the solo/party announcement and starts the 30-second return countdown. Durable duplicate receipts preserve the selection as well as the exactly-once award.

The reward writer no longer changes `character_base.selected_title_id`. Its live projection adds the earned title to the native 10196 ownership list while retaining the selected-title header. Acquisition sends no 10199 title-change packet to the recipient or scene observers.

Explicit title selection persists the current player's choice only after checking authenticated account, realm, active character, current ownership lease and earned title ownership. Both Medusa and Atlantis titles use this path; zero hides the displayed title. Changing selection advances the existing shared reward revision, preserving HardPoints and owned titles. Identical choices are idempotent. Selection is cosmetic: existing Medusa bonuses use the strongest owned title, so hiding a title does not remove those bonuses.

Delayed reward and selection receipts merge earned ownership while retaining a newer selection and wallet revision. Invalid selections restore the current title list and display; failed reliable packet admission disconnects rather than silently dropping a durable title change.

## Native manual-selection request

The installed client's ChangeDesBtn and HideDesBtn callbacks use opcode 10198 (`0x27D6`). The frame is exactly 8 bytes: a 16-bit length of 8, the 16-bit opcode, then the 32-bit title ID. Title 0 means hide/unequip. There is no character or object ID supplied by the client; server authorization must come from the current authenticated session and durable ownership.

Native evidence: ChangeDesBtn at `0x555340` constructs the header at `0x55537E` / `0x555385`, copies the owned-list title ID at `0x55539E`, and sends 8 bytes at `0x5553AD` through `0x5553B4`. HideDesBtn at `0x5544C5` sends the same frame with a zero title ID at `0x5544F1` through `0x554503`. The XML button identifiers are 430001 and 430002. Opcode 10199 is the separate server-to-client display update.

## Why the Atlantis monsters died without a player attack

The September 9 live server log identified incorrectly applied rebound damage. For example, monster 42229 hit AresTempest for 1 damage and received 60,879 requested rebound damage, capped to its remaining 56,888 HP, killing it. Other normal monsters died through the same erroneous path and received ordinary durable kill settlement.

AresTempestBond is the fixture's max Cupid (species 45). Its 20,000 effective Luck yields 60,879 **fixed** Owner-Merge rebound damage. The combat policy adds this fixed component after calculating any percentage rebound from committed incoming damage. The corrected rule is **player-versus-player only**: monster attacks never receive this stat-based rebound. Zero-damage hits and rebound damage itself cannot recursively trigger it. Unmerged pets contribute no Owner-Merge bonus.

The value matches the existing 20,000-Savvy golden vector. On September 10, the user clarified that rebound affects players only. The former Legacy/ECS tests had encoded the incorrect PvE behavior; they were replaced with no-rebound-to-mobs checks. The fixed and percentage rebound values remain available in PvP. See [the correction](rebound-pvp-only-20260910.md).

Evidence and verification reports are under `artifacts/atlantis-title-deaths-20260909/`.

## Verification and deployment

All 44 focused checks pass in Debug and Release with no skips; both solution builds finish with zero warnings and errors. The two PostgreSQL checks pass for completion ownership without automatic selection, manual equip/hide, reconnect hydration, duplicate/concurrent requests, authorization boundaries, and delayed reward ordering. The existing fixed-rebound golden vector and Legacy/ECS live damage checks also pass. All 161 changed authored files remain below 20KB.

Deployed on 2026-09-09 at 23:42 New Zealand time as image `sha256:a0cfc5f05cf190c67dc583d325e071eeb5a099858f9f878ada6fa47f77f35d1f`. The server is healthy with zero restarts and the live isolation check passes. Schema head remains144; no migration or direct character-data repair was needed. The prior image is retained as `reborn-server:before-atlantis-title-selection-20260909`. The temporary PostgreSQL container, volume and credential were removed and verified. Native visual acceptance remains for the next in-game title-window playtest.
