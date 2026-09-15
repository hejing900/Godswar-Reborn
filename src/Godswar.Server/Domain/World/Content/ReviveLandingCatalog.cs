namespace Godswar.Server.Domain.World.Content;

/// <summary>
/// Free-revive landing points, keyed by the map the character died on. The
/// reference server relocates a revived character to that map's own revive
/// point instead of one global camp coordinate, so the destination - including
/// the destination map - is a per-map record.
/// <para>
/// Only capture-proven rows belong here. A map without a row keeps the camp
/// capital fallback in <c>GameDefaults.InitializeStartingLocation</c>, and the
/// revive trace logs the fallback so a missing map is visible instead of
/// silently wrong.
/// </para>
/// </summary>
internal static class ReviveLandingCatalog
{
    /// <param name="MapId">Map the character is placed on after reviving.</param>
    /// <param name="X">Landing X.</param>
    /// <param name="Z">Landing Z.</param>
    internal readonly record struct ReviveLanding(byte MapId, float X, float Z);

    /// <summary>
    /// Captured 2026-09-15 on the reference server. A character killed in
    /// Athens city (map 1) received the 28-byte landing frame
    /// <c>1C002227 8F040000 0000A041 00000000 0000C8C2 01000100 01000000</c>:
    /// object 1167 at x = 20, y = 0, z = -100 with the map in the high word of
    /// +20. It revives on the map it died on.
    /// See docs/death-revive-capture-20260915.md.
    /// </summary>
    private static readonly ReviveLanding[] Landings =
    [
        new(MapId: 1, X: 20f, Z: -100f)
    ];

    /// <summary>Every capture-proven landing point, in capture order.</summary>
    public static IReadOnlyList<ReviveLanding> Captured => Landings;

    public static bool TryResolve(byte deathMap, out ReviveLanding landing)
    {
        foreach (var candidate in Landings)
        {
            if (candidate.MapId == deathMap)
            {
                landing = candidate;
                return true;
            }
        }

        landing = default;
        return false;
    }
}
