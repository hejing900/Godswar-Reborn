using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Networking;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    internal bool TryResolveCompletedWonderlandLeave(ClientSession session, int? repetitionId,
        int repetitionIndex, out AuthoritativeInstanceTransitionCommand command)
    {
        command = default;
        if (repetitionId is not null and not WonderlandClientSceneId || repetitionIndex != 0) return false;
        lock (_gate)
        {
            if (!_sessions.TryGetValue(session, out var actor) ||
                !IsCurrentWonderlandMember(actor, actor.WorldInstanceId) ||
                !_wonderlandAdmissions.TryGetValue(actor.WorldInstanceId, out var admission) ||
                !admission.Sealed || !admission.Entrants.Contains(actor.CharacterId) ||
                !TryGetWonderlandEncounterSnapshot(actor.WorldInstanceId, out var run) ||
                run.State != WonderlandRunState.Completed || run.CompletedIslands != 8 ||
                !_wonderlandTitleSettled.ContainsKey((actor.WorldInstanceId, 8)) ||
                HasPendingWonderlandTitles(actor.WorldInstanceId)) return false;

            var targetMap = actor.Character.Camp == GameDefaults.SpartaCamp
                ? GameDefaults.SpartaCapitalMap : GameDefaults.AthensCapitalMap;
            var target = GetOrCreateDefaultWorldInstance(targetMap);
            // Completed Leave affects only the clicking participant. The run,
            // its treasure deadline and other members' rewards stay intact.
            // Like automatic egress, the panel can return a dead finisher.
            command = new(actor.CharacterId, actor.WorldInstanceId, WonderlandMapId, actor.Ownership,
                target.InstanceId, targetMap, GameDefaults.StartingPositionX, GameDefaults.StartingPositionZ);
            return true;
        }
    }
}
