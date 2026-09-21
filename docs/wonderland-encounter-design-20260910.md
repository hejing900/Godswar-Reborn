# Wonderland encounter implementation

> Historical record: the design, placements, roster and party HP scaling below are superseded where they differ from the [September 13 full external comparison](wonderland-external-comparison-20260913.md). Preserve the recorded evidence and release results as history.


User-approved rules and starting balance, September 10, with daily entry approved September 11. These are authored Reborn values, not original-server numeric captures. Boss HP below already includes the requested x3 increase. Do not multiply it again. Content map 207, client scene 227, Fane. Entry requires level 120+, 1-5 players, with three free entries every day before 23:00 in the realm calendar and a 40-minute deadline.

## Boss balance

Five-player HP; admission roster fixes HP factors for 1/2/3/4/5 players at 25/45/65/85/100 percent. Attack/defense remain fixed; no extra level scaling. P/M means physical/magical. Basic attacks every 2 seconds. Skill multipliers apply to the corresponding attack power through the shared skill-damage calculation before defense and absorption. Normal encounter profiles are separate from max-Cupid development characters.

| Island | Boss | HP | PAtk | MAtk | PDef | MDef |
|---|---|---:|---:|---:|---:|---:|
| 1 | Alpha Demon | 3000000 | 12000 | 6000 | 3000 | 2500 |
| 2 | Capritaur Derskey | 4500000 | 14000 | 4000 | 4000 | 2500 |
| 2 | Depraved Monkeyface | 4500000 | 4000 | 14000 | 2500 | 4000 |
| 3 | Flame Rooster | 30000000 | 5000 | 18000 | 4500 | 4500 |
| 4 | Outrageous Rock Spirit | 9000000 | 20000 | 5000 | 7000 | 5500 |
| 5 | Athenian Marshal Addis | 12000000 | 18000 | 8000 | 10000 | 8000 |
| 5 | Spartan Marshal Knocker | 12000000 | 18000 | 8000 | 10000 | 8000 |
| 6 | Depraved Platinum Dragon | 15000000 | 18000 | 22000 | 8500 | 8500 |
| 7 | Iberian Multi-headed | 24000000 | 24000 | 12000 | 8000 | 7000 |
| 8 | Distraught Minotaur | 9000000 | 24000 | 6000 | 11000 | 8000 |
| 8 | Titan's X'mas Deer | 10500000 | 6000 | 26000 | 7000 | 10000 |
| 8 | Iberian Dragon King | 15000000 | 22000 | 26000 | 9000 | 9000 |
| 8 | Scorpion King | 18000000 | 28000 | 10000 | 10500 | 9500 |

## Boss abilities

- Alpha Demon: passive +25% attack below 30% HP. Demonic Cleave frontal physical x1.6, 8s cooldown.
- Derskey: 80% physical damage reduction after defense; 50% stun chance on landed basic attack, 2s stun, no additional proc cooldown. Trample physical x1.8 around boss, 10s cooldown.
- Monkeyface: 80% magical damage reduction after defense; same stun rule. Mind Blast magical x1.8 area, 10s cooldown.
- Flame Rooster: Fire Blast magical x2.5 area, 4s cooldown, 1.2s visible warning.
- Rock Spirit: returns 10% of actual committed direct damage to attacking player; dedicated nonrecursive boss reflection, never the PvP-only DamageRebound stat. Every hostile island-4 mob attack inflicts 2s silence. Rock Smash physical x2 area, 8s cooldown.
- Marshals: hostile faction boss can be lured into allied marshal range for help; both have the above stats. War Cleave physical x1.8 frontal, 8s cooldown. Spartans fight Addis, with Knocker allied; Athenians reverse. Allied marshal is not a progression kill and cannot be farmed/attacked by players.
- Platinum Dragon: Dragon Fire magical x2 frontal, 6s cooldown. Separate random terrain-fire schedule below.
- Multi-headed: 18000 Dodge and encounter-specific accuracy calculation, designed for roughly 15% hit at ordinary baseline without bird buff and 90-98% with it; do not change global PvE hit rules. Multi-head Strike three physical x0.7 hits, 8s cooldown.
- Minotaur: Armor Rend physical x1.5, -50% player PDef for 10s, 12s cooldown.
- Deer: Magic Burst magical x2 area, 6s cooldown. Focused Bolt magical x1.5 single target, 4s cooldown.
- Dragon King: Dragon Breath magical x2.2 frontal, 6s cooldown.
- Scorpion King: Meteor Blast physical x2.5 area, 10s cooldown. Spear Blast physical x1.8 and -40% PDef for 8s, 6s cooldown. Repeated defense penalties refresh, not exponential stacking.

Unless above explicitly specifies otherwise, implementation tuning defaults: hostile area radius 6 units, frontal reach 10 units with 90-degree cone, visible 1.2s windup. Bosses can start only one active skill cast at a time; cooldown starts with cast. All effects are exact-instance, target-life, generation and combat-event fenced. Terminal/departure cancels future casts. Stun/silence refresh duration, never add durations. Basic attacks and potions remain usable while silenced.

## Supporting mechanics

1. Alpha island: provisionally three stationary Arrow Towers, detection/attack range25, basic interval2s. One Wonderland Chest Guard casts strong Fire Blast each attack, 2s interval, zero extra cooldown. Initial authored support tuning: tower HP300k/PAtk16000/PDef3000/MDef2500; chest HP450k/MAtk18000/PDef3000/MDef3000 and Fire Blast x2.5. Both use party HP factors above. Count3 remains explicitly provisional user recall.
2. Derskey and Monkeyface on opposite ends. Spiders (Demonic Wolfspider), cyclops (Cannibalistic Troll), and spirits support them. Initial support count: four of each, split symmetrically into boss approaches. Base support HP300k, attack8000, defenses2500, 2s attacks. Both bosses required; support mobs not an artificial kill-all gate.
3. Only Disguised Petbirds as regular mobs; initially six distributed around the island. A bird attack grants the targeted player total x5 PAtk/MAtk for15s, refresh-only, not repeated multiplication. Bird support HP250k, attack4000, defenses2000. Grant on a valid committed attack event even if dodged/absorbed, so defensive builds can use the mechanic. Clear on leaving island.
4. Rock Spirit with initially six Stone Guardians and four Mana Def Spoilers, all attacks silence2s. Support HP350k, attack10000, defenses3000. No permanent additive silence durations.
5. Both faction marshals spawn at opposite ends, with clear lure corridor. Four allied and four hostile expedition soldiers/sentinels/mages may support them; baseHP400k, attack10000, defenses4000. Allegiance derives from the admitted party leader's camp and stays fixed. Clear on enemy marshal death. Allied monster-v-monster damage cannot mint player loot/rewards or apply to another instance.
6. Platinum island has three random ground-fire circles every3s, radius5, warning1.5s, based on reachable walkable terrain, keeping safe traversable space. Fire magical attack22000 x2.5. No fire on entry/portal safe zones. No additional ordinary monsters required for first version.
7. Multi-headed with initially six Putrid Birds and three stationary Lost Towers. Bird attack gives +25000 Hit15s, refresh-only, clear on leaving island; HP250k, attack4000, defenses2000. LostTower HP450k, PAtk26000, defenses4000, attackinterval1.5s, range30. Base direct hit chance against Multi-head = clamp(9000 + (Hit-Dodge)/2,500,9800) basis points, preserving explicit current boss scope; normal global PvE is unchanged.
8. Four corners in sequence: Minotaur, Deer, Dragon King, Scorpion King. EACH boss has TWO Followers of Atlas (eight total), latest user correction. Every boss/Atlas group has wide aggro112 and leash128, anchored locally with terrain separation to avoid unintended cross-corner pulls where possible. Followers HP400k, MAtk16000, defenses3000, continuously Fire Blast magical x2 with1.5s cast time and0s cooldown. Each death schedules exactly one final Fire Blast x3 with1.5s warning; cancel at timeout/termination. All four bosses and their eight followers required for final clear. Followers' HP is not boss HP and receives only party-size scaling, not the extra x3.

Player deaths recover at the player's physical island entrance, retaining the run timer even when the party leader has advanced. The seven outer islands follow southeast, south, southwest, west, northwest, northeast, east, then the central eighth island; the user's `(159,-163)` and `(-15,-185)` anchors identify the first two. The first arrival and revive landing is the requested `(169,-216)`. The first transporter now follows captured `(153,-125)`, and the entrance Blackmarket actor is at `(165,-219)`; travel requires a native dialogue action. See the [transporter audit](wonderland-transporters-20260911.md) for captured NPCs and retained protected landings, the [terrain foundation](wonderland-terrain-and-spawn-audit.md) for the original authored geometry, and the [native revival audit](wonderland-native-death-revival-20260911.md) for the installed client's death/revive packet correction. Required deaths unlock later islands without clearing living support monsters, their HP, pending skills, or damage eligibility. Support deaths from an earlier island cannot advance the current island.

Completion displays a five-minute treasure countdown before returning eligible members to their faction capital. The shared `WonderlandCompletionPolicy.TreasureWindow` controls UI, chest claims, unlocked forward portals, physical-island revival, automatic egress, and runtime retention. It starts at the final clear even when completion occurs just before the forty-minute encounter deadline. Terminal combat stays frozen. Completed travel is restricted to currently admitted owners already inside that exact run; departing does not permit re-entry. Players may leave earlier using existing capital travel. Termination and voluntary departure clear UI and transient effects; empty active runs retire. Completion/award persistence must settle before retiring the runtime. Other dungeons retain their existing countdowns.

## Titles

Every completed island awards its own title to eligible admitted members:

| Island | Title ID | Name |
|---|---:|---|
| 1 | 5155 | Gatebreaker |
| 2 | 5114 | Demonbreaker |
| 3 | 5156 | Flamebreaker |
| 4 | 5115 | Stonebreaker |
| 5 | 5157 | Marshal's Bane |
| 6 | 5116 | Dragonbane |
| 7 | 5117 | Hydra's Bane |
| 8 | 5118 | Wonderland Sovereign |

IDs 5155-5157 fill the previously missing islands without changing existing title ownership or receipt hashes. Unlock ownership only, never auto-equip. Preserve existing selected title and strongest-owned Medusa gameplay bonuses. No unrequested Hard Points or title stat bonuses.

Durable title awards are per completed island and eligible original admitted member; current presence and exact ownership/instance are captured at clear. Transport failure after clear must not discard earned ownership. Client display changes require backup and exact intended IDs, preserving UTF-16 format. Normal title selection must recognize Wonderland ownership.

Only a full eight-island clear produces a Medusa-style centered completion announcement. It names the solo player or party and the Wonderland Sovereign title. The audience is online players in the same realm whose faction is represented by the eligible finishers. Subject, factions, and solo/party classification are frozen at the final clear; publication waits for successful final-title settlement. The notice is admitted once per completed run, including repeat clears by players who already own the title, and transport failures cannot replay it to recipients already queued. Earlier island unlocks use private server notes. Cancellation and timeout do not announce completion.

## Validation targets

CheckHPx3/party scaling, all13boss identities, eightAtlas, fixed tower positions, runtime profile overrides in both engines, island2opposing reductions andstuns, nonstackingbirdbuffs andclear,10%reflection/nonrecursion/replay, silence expiry, faction aid fencing, terrain safe zones/cadence, island7accuracy, Atlas exactly-once death blast, progression anddeadline races, title durability/noautoequip, UI/entry/termination/egress. Build/test before local deployment. Capture live health/isolation and back up database before migration.

## Completed validation and deployment

- Debug and Release solution builds passed without warnings or errors. The focused suite passed 57 checks in both configurations; the eight Wonderland checks were rerun in Debug after the final combat clock corrections. Release covers the final production source.
- Three disposable PostgreSQL checks passed: Wonderland milestone settlement/ownership, manual title selection, and existing Atlantis completion rewards. All 145 migrations applied, with head `20260910_144_wonderland_titles`; the disposable container was removed.
- Combat checks exercise all four combinations of Legacy/ECS monster and player engines. They include actual incoming damage, opposed damage reductions, bird buffs, silence/stun expiry, reflection, allied combat and telegraphed cleave, random terrain fire, final-Atlas completion damage, stale observations, and exactly-once effects.
- Tempest was deployed at 2026-09-09 23:11:45 UTC with image `sha256:e0eaaccea1bfcf8652cb28b09e79ce28abd768357c44000551d86bd19f94dd6c`. Startup reached ready, health is healthy, restart count is zero, and live isolation passed. Port bindings are unchanged; Dwargon remains stopped.
- Both client locales were patched and verified. Backup manifest: `C:\Godswar Origin\backups\wonderland-titles\20260909-230006-dd458bd066fc482eb800681f8dceb977\manifest.json`. Restart the client to load the new labels.
- Database backup, rollback-image reference, test reports, and deployment receipt are under `artifacts/wonderland-20260910/`. All changed authored files are below 20 KB; `git diff --check` passed.

The route and placements are authored from the installed Fane terrain, not recovered original-server coordinates. Native rendering over floating platforms and visual effects still require an in-client playthrough; see `wonderland-terrain-and-spawn-audit.md`. Entry uses the existing level-120 minimum, three free entries every day before 23:00 in the realm calendar (Asia/Manila on Tempest), and reopens at midnight. Rejected schedule attempts consume no daily entry.

### Follow-up: title for every island

The per-island title extension was deployed on September 10 at 01:05 UTC. Every island now grants the title in the table above; islands 1, 3, and 5 use newly allocated client IDs. Existing selected titles, earned ownership, and original run/receipt hashes remain valid. Forward migration `20260910_145_wonderland_all_island_titles` brings the schema to 146 migrations without editing the previously deployed migration.

Validation passed: 11 focused checks in Debug and Release, four PostgreSQL checks including upgrade of an existing title receipt, and 16 client-patch checks. Both client locales were patched and verified with a backup manifest under `C:\Godswar Origin\backups\wonderland-titles\20260910-010405-d796548c02734e9d9c2afd65f7548784\`. Tempest reached healthy with zero restarts; isolation and unchanged port bindings were verified. Full receipts and backups are under `artifacts/wonderland-all-island-titles-20260910/`.

### Follow-up: full-clear announcement

The Medusa-style faction announcement was deployed on September 10 at 01:22 UTC. It appears only after all eight islands complete and the final title award saves. Intermediate titles use private notices; repeat full clears still announce, while settlement retries, termination, and timeout do not create additional completion announcements.

Debug and Release builds passed without warnings or errors. The new announcement regression passed in Debug and all 12 focused checks passed in Release, including two complete runs in one registry, reward persistence failure/retry, faction and realm boundaries, termination, and timeout. Tempest is healthy with zero restarts, live isolation passed, port bindings are unchanged, and the schema remains at 146 migrations. Reports and rollback details are under `artifacts/wonderland-completion-announcement-20260910/`. Native client display still requires an in-game clear to verify visually.
