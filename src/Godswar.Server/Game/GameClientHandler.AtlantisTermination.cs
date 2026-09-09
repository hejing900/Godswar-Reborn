using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    // Both native repetition controls share the existing packet-shape checks.
    // The current server-owned instance, never the supplied repetition ID,
    // decides which dungeon receives the action.
    private async Task<bool> TryHandleAtlantisTerminationAsync(
        int? repetitionId, int repetitionIndex, CancellationToken cancellationToken)
    {
        if (_character?.CurrentMap != DynamicDungeonContentMapPolicy.AtlantisPortalMapId)
        {
            return false;
        }
        var terminated = repetitionId is { } id
            ? _registry.TryEndAtlantisRunFromLeader(_session, id, repetitionIndex, DateTimeOffset.UtcNow)
            : _registry.TryTerminateAtlantisRunFromLeader(_session, DateTimeOffset.UtcNow);
        if (!terminated)
        {
            Console.WriteLine("[atlantis] rejected non-authoritative terminate action");
            return true;
        }
        await _session.SendAsync(PacketBuilder.RepetitionReset(), cancellationToken,
            "AtlantisLeaderInstanceTerminate");
        return true;
    }
}
