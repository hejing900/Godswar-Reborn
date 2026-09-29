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
            // The run may already be terminal - the leader ended it or it ran out
            // of time - and this same native control is then the member's own
            // "leave the instance" during the countdown.
            if (_registry.TryResolveAtlantisTerminationLeave(_session, repetitionId,
                    repetitionIndex, DateTimeOffset.UtcNow, out var leave))
            {
                var transferred = await TryBeginAuthoritativeInstanceTransitionAsync(
                    leave,
                    cancellationToken);
                Console.WriteLine(
                    "[atlantis] end-window leave character=" +
                    $"{_character?.Name ?? "<none>"} transferred={transferred}");
                return true;
            }
            Console.WriteLine("[atlantis] rejected non-authoritative terminate action");
            return true;
        }
        await _session.SendAsync(PacketBuilder.RepetitionReset(), cancellationToken,
            "AtlantisLeaderInstanceTerminate");
        return true;
    }
}
