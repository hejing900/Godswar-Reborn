using Godswar.Server.Domain.World.Content;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    // Both native repetition controls share the existing packet-shape checks.
    // The current server-owned instance, never the supplied repetition ID,
    // decides which dungeon receives the action.
    private async Task<bool> TryHandleHarborAttackTerminationAsync(
        int? repetitionId,
        int repetitionIndex,
        CancellationToken cancellationToken)
    {
        if (_character is null ||
            !DynamicDungeonContentMapPolicy.IsHarborAttackMap(
                _character.CurrentMap))
        {
            return false;
        }

        var sceneId = HarborAttackClientSceneId(_character.CurrentMap);
        // The panel's Terminate control arrives with no repetition id; the
        // twelve-byte end request carries the scene it belongs to.
        if (repetitionId is { } requested && requested != sceneId)
        {
            return false;
        }

        if (!_registry.TryTerminateHarborAttackRunFromLeader(
                _session,
                sceneId,
                repetitionIndex))
        {
            // The run may already be terminal - ended by its leader or run out of
            // time - and this same control is then this member's own "leave the
            // instance" during the countdown.
            if (_registry.TryResolveHarborAttackEndLeave(
                    _session,
                    sceneId,
                    repetitionIndex,
                    DateTimeOffset.UtcNow,
                    out var leave))
            {
                var transferred = await TryBeginAuthoritativeInstanceTransitionAsync(
                    leave,
                    cancellationToken);
                Console.WriteLine(
                    "[harbor] end-window leave character=" + _character.Name +
                    $" transferred={transferred}");
                return true;
            }
            Console.WriteLine(
                "[harbor] rejected non-authoritative end control " +
                $"character={_character.Name} scene={sceneId}");
            return true;
        }

        // The run is terminal from here. The world tick publishes the native
        // leave countdown to every member inside, exactly as a completed run
        // does, so no reset is sent: it would wipe the panel the countdown needs.
        return true;
    }

    private static int HarborAttackClientSceneId(byte mapId) =>
        mapId == DynamicDungeonContentMapPolicy.HarborAttackSecondMapId
            ? InstanceCallerProtocol.HarborAttackSecondClientSceneId
            : InstanceCallerProtocol.HarborAttackFirstClientSceneId;
}
