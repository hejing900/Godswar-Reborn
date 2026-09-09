using System.Collections.Concurrent;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private readonly ConcurrentDictionary<WorldInstanceId, int> _atlantisLeaderCharacterIds = [];
    private readonly ConcurrentDictionary<WorldInstanceId, byte> _atlantisTerminationExitRequested = [];
    private readonly ConcurrentDictionary<WorldInstanceId, byte> _atlantisTerminationEgressInFlight = [];

    private void ForgetAtlantisTermination(WorldInstanceId instanceId)
    {
        _atlantisLeaderCharacterIds.TryRemove(instanceId, out _);
        _atlantisTerminationExitRequested.TryRemove(instanceId, out _);
        _atlantisTerminationEgressInFlight.TryRemove(instanceId, out _);
    }

    internal bool TryTerminateAtlantisRunFromLeader(ClientSession session, DateTimeOffset requestedAt) =>
        TryEndAtlantisRunFromLeader(session, AtlantisClientSceneId, 0, requestedAt);

    internal bool TryEndAtlantisRunFromLeader(ClientSession session, int repetitionId,
        int repetitionIndex, DateTimeOffset requestedAt)
    {
        ArgumentNullException.ThrowIfNull(session);
        GameSessionContext actor;
        WorldInstanceRuntime runtime;
        lock (_gate)
        {
            if (repetitionId != AtlantisClientSceneId || repetitionIndex != 0 ||
                !_sessions.TryGetValue(session, out actor!) ||
                !IsCurrentAtlantisTerminationLeader(actor) ||
                GetPartyMembership(session) is { IsLeader: false } ||
                !WorldInstances.TryFind(actor.WorldInstanceId, out runtime!) ||
                !AtlantisEncounterPolicy.IsAtlantisInstance(runtime.Descriptor))
            {
                return false;
            }
            // Match membership transition ordering: registry serialization
            // precedes this owner command, which never acquires the registry
            // gate. Leadership and ownership cannot change during cancellation.
            return InvokeWorldOwnerAuthoritativeMutation(runtime, map =>
            {
                if (!IsCurrentAtlantisTerminationLeader(actor) ||
                    map.WorldInstanceId != actor.WorldInstanceId ||
                    !map.Snapshot().Any(member => ReferenceEquals(member.Session, session) &&
                        member.CharacterId == actor.CharacterId && member.Ownership == actor.Ownership) ||
                    !map.TryCancelAtlantisEncounter(requestedAt, out _))
                {
                    return false;
                }
                _atlantisTerminationExitRequested.TryAdd(actor.WorldInstanceId, 0);
                return true;
            });
        }
    }

    private bool IsCurrentAtlantisTerminationLeader(GameSessionContext actor) =>
        !actor.Session.IsDisconnected && actor.WorldReady &&
        actor.MapId == DynamicDungeonContentMapPolicy.AtlantisPortalMapId &&
        actor.Character.CurrentMap == actor.MapId && actor.Ownership.IsValid &&
        _atlantisLeaderCharacterIds.TryGetValue(actor.WorldInstanceId, out var leaderId) &&
        leaderId == actor.CharacterId &&
        IsCurrentAccountSession(actor.AccountId, actor.Session, actor.Ownership);
}
