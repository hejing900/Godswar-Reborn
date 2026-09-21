# Wonderland final-island aggro and collision

Isle 8 actors now acquire nearby players within 24 units and leash at 64 units, matching the normal mobile Wonderland boundaries. The former 112-unit detection radius pulled separate chambers into the same fight. Boss HP, attack reach, skills and captured spawn coordinates are unchanged by this correction.

The previous server AI used straight movement segments for chasing, patrols and returning home. The central island has a winding corridor and walls, so a straight segment could cross blocked terrain even when both endpoints were walkable. Isle 8 now uses the actual native collision grid for each of these movement modes. Basic attacks also require a clear segment to the target; being within attack radius across a wall is insufficient.

## Native source

Source: `C:\Godswar Origin\Map\Fane.hmp`, 9,175,332 bytes.

SHA-256: `375b51547593b82924c6a6c809316e070b44536a853a8e75080ce5dad49cf292`.

The native header contains two 16-bit dimensions (128×128) and two 32-bit floating point scales (4×4). The block table begins at 262,432 and contains 2048×2048 one-byte cells; zero is walkable. A native cell is a quarter world unit. Columns are `floor((X+256)*4)` and rows are `floor((256-Z)*4)`.

`tools/ExtractWonderlandNavigation.py` validates the exact source hash and header, then extracts X[-36,72), Z[-124,104). This produces 393,984 exact native cells, compressed to 1,652 bytes in `Game/Navigation/WonderlandFinalIsland.grid.gz`. The server embeds the resource and does not depend on a client installation or a Windows path at runtime. Regenerate it with:

```powershell
python tools/ExtractWonderlandNavigation.py 'C:/Godswar Origin/Map/Fane.hmp'
```

## Routing and scope

An A* graph uses one-unit squares whose 16 constituent native cells are all clear. Diagonal edges require both adjacent squares to be clear. Start and goal attach only through collision-checked native segments. Each actor owns a route cache; visible waypoints can be skipped only after checking every crossed quarter-unit cell, including both sides of a crossed corner. Physical motion and the complete segment advertised to the client follow the same route.

Invalid or unreachable destinations never receive a straight-line fallback. Chase gives up and returns along a valid route; return preserves exact home coordinates. Patrol proposals crossing a wall are rejected. Only Isle 8 runtimes receive this navigation grid. Other maps retain their existing movement rules.

The grid covers native planar blocking. It does not create new collision for decorative meshes absent from the client's block table. Damage areas continue to use their existing authored/captured geometry.

## Verification

`Wonderland final island collision navigation` checks the embedded grid against captured spawns, a known wall and void, traverses the entry-to-boss/guard routes in both directions, and exercises actual Legacy and ECS runtimes. The Minotaur must ignore a player 43 units down the entry corridor, route around a blocked corner after taking a hit, attack only with a clear segment, return through the corridor, and patrol safely. Every emitted movement segment is checked against native collision cells. The existing Wonderland behavior and policy checks cover the reduced aggro and retained combat profiles.

The focused group passed in Release with no skips on September 15. The local result receipt is `artifacts/wonderland-final-navigation-20260915/checks.json`. The tests also cover diagonal traversal ending exactly on a native cell boundary in both directions; this caught and corrected an endpoint overshoot during implementation.
