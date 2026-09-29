using System.Collections.Concurrent;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;
using Godswar.Server.State;

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
                // Party leadership is a separate system and must not gate the
                // instance's own end control; only its leader may end it.
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

    /// <summary>
    /// Moves Atlantis's leader to the earliest still-present member when the
    /// registered leader has left the run. Atlantis keeps its leader in this
    /// registry rather than in an admission record, so the transfer writes the
    /// dictionary directly; the run's end control reads the same entry.
    /// </summary>
    private void MaintainAtlantisLeader(AtlantisRunDelivery delivery)
    {
        var instanceId = delivery.Runtime.InstanceId;
        if (!_atlantisLeaderCharacterIds.TryGetValue(instanceId, out var leaderId))
        {
            return;
        }
        // The delivery's member order is the run's own capture order; the
        // character id breaks ties for members it does not order.
        var present = OrderInstanceMembers(
            [.. delivery.Members.Select(static member => member.CharacterId)],
            [.. delivery.Members.Select(static member => member.CharacterId)]);
        if (TryResolveInstanceLeaderSuccessor(
                instanceId,
                "Atlantis",
                leaderId,
                present,
                out var successor))
        {
            _atlantisLeaderCharacterIds[instanceId] = successor;
        }
    }

    private bool IsCurrentAtlantisTerminationLeader(GameSessionContext actor) =>
        !actor.Session.IsDisconnected && actor.WorldReady &&
        actor.MapId == DynamicDungeonContentMapPolicy.AtlantisPortalMapId &&
        actor.Character.CurrentMap == actor.MapId && actor.Ownership.IsValid &&
        _atlantisLeaderCharacterIds.TryGetValue(actor.WorldInstanceId, out var leaderId) &&
        leaderId == actor.CharacterId &&
        IsCurrentAccountSession(actor.AccountId, actor.Session, actor.Ownership);

    /// <summary>
    /// A member's own leave during the end-of-run countdown. The run is already
    /// terminal, so this returns the transition that carries that member home
    /// immediately instead of waiting for the countdown to expire.
    /// </summary>
    internal bool TryResolveAtlantisTerminationLeave(ClientSession session, int? repetitionId,
        int repetitionIndex, DateTimeOffset now,
        out AuthoritativeInstanceTransitionCommand command)
    {
        command = default;
        ArgumentNullException.ThrowIfNull(session);
        if (repetitionId is not null and not AtlantisClientSceneId || repetitionIndex != 0)
        {
            return false;
        }
        lock (_gate)
        {
            if (!_sessions.TryGetValue(session, out var actor) ||
                actor.MapId != DynamicDungeonContentMapPolicy.AtlantisPortalMapId ||
                actor.Character.CurrentMap != actor.MapId ||
                !actor.Ownership.IsValid ||
                !IsCurrentAccountSession(actor.AccountId, actor.Session, actor.Ownership) ||
                !WorldInstances.TryFind(actor.WorldInstanceId, out var runtime) ||
                !AtlantisEncounterPolicy.IsAtlantisInstance(runtime.Descriptor) ||
                !TryGetAtlantisEncounterSnapshot(actor.WorldInstanceId, out var run) ||
                !IsAtlantisTerminationExitWindowOpen(run, now))
            {
                return false;
            }
            var targetMap = actor.Character.Camp == GameDefaults.SpartaCamp
                ? GameDefaults.SpartaCapitalMap : GameDefaults.AthensCapitalMap;
            var target = GetOrCreateDefaultWorldInstance(targetMap);
            command = new(actor.CharacterId, actor.WorldInstanceId,
                DynamicDungeonContentMapPolicy.AtlantisPortalMapId, actor.Ownership,
                target.InstanceId, targetMap,
                GameDefaults.StartingPositionX, GameDefaults.StartingPositionZ);
            return true;
        }
    }
}
