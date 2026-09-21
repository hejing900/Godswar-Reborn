namespace Godswar.Server.Application.WorldInstances;

internal static class WonderlandCompletionPolicy
{
    // Includes walking between final-island boss groups and collecting unlocked
    // treasure. Earlier island portals stay usable until the same deadline.
    public static readonly TimeSpan TreasureWindow = TimeSpan.FromMinutes(5);

    public static bool IsTreasureWindowOpen(WonderlandSnapshot run, DateTimeOffset now) =>
        run.State == WonderlandRunState.Completed && run.TerminalAt is { } completed &&
        now >= completed && now - completed < TreasureWindow;

    public static bool AllowsIslandTravel(WonderlandSnapshot run, DateTimeOffset now) =>
        run.State == WonderlandRunState.Active && now < run.Deadline || IsTreasureWindowOpen(run, now);

    public static bool IsCombatWindowOpen(WonderlandSnapshot run, DateTimeOffset now) =>
        run.State == WonderlandRunState.Active && now >= run.StartedAt && now < run.Deadline ||
        IsTreasureWindowOpen(run, now);
}
