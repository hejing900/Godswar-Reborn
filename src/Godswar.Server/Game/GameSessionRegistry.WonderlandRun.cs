using System.Collections.Concurrent;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private const byte WonderlandMapId = 207;
    private const ushort WonderlandClientSceneId = 227;
    private readonly ConcurrentDictionary<WorldInstanceId, WonderlandAdmission> _wonderlandAdmissions = [];
    private readonly ConcurrentDictionary<Guid, WorldInstanceId> _wonderlandReservations = [];

    internal bool TryStartWonderlandEncounter(WorldInstanceId instanceId, ushort dailyLimit,
        IReadOnlyList<LegacyInstancePartyMember> members, DateTimeOffset startedAt, Guid reservationId)
    {
        if (dailyLimit == 0 || reservationId == Guid.Empty || members.Count is < 1 or > 5 ||
            !WorldInstances.TryFind(instanceId, out var runtime) || runtime.MapId != WonderlandMapId)
            return false;
        lock (_gate)
        {
            if (_wonderlandAdmissions.ContainsKey(instanceId)) return false;
            var participants = new List<WonderlandParticipant>();
            foreach (var member in members)
            {
                if (!_sessions.TryGetValue(member.Session, out var current) ||
                    current.CharacterId != member.CharacterId || current.AccountId != member.AccountId ||
                    current.Ownership != member.Ownership || current.RealmId != runtime.RealmId ||
                    current.Session.IsDisconnected || !IsCurrentAccountSession(
                        member.AccountId, member.Session, member.Ownership)) return false;
                participants.Add(new(member.CharacterId, member.Level, current.Character.Camp));
            }
            if (!InvokeWorldOwnerAuthoritativeMutation(runtime, map =>
                map.TryConfigureWonderland(_gameplayCatalogs.Content, participants, startedAt))) return false;
            _wonderlandAdmissions[instanceId] = new(reservationId, dailyLimit, members[0].CharacterId,
                members.ToArray(), startedAt.ToUniversalTime());
            _wonderlandReservations[reservationId] = instanceId;
            return true;
        }
    }

    internal void RecordWonderlandAdmissions(Guid reservationId, IReadOnlyCollection<int> admittedIds)
    {
        lock (_gate)
        {
            if (!_wonderlandReservations.TryGetValue(reservationId, out var instanceId) ||
                !_wonderlandAdmissions.TryGetValue(instanceId, out var admission) || admission.Sealed) return;
            foreach (var id in admittedIds)
                if (admission.OriginalMembers.Any(member => member.CharacterId == id)) admission.Entrants.Add(id);
        }
    }

    internal void CompleteWonderlandAdmissions(Guid reservationId)
    {
        lock (_gate)
        {
            if (!_wonderlandReservations.TryGetValue(reservationId, out var instanceId) ||
                !_wonderlandAdmissions.TryGetValue(instanceId, out var admission) || admission.Sealed) return;
            // Include a committed entry whose transport acknowledgement threw
            // before the handler could publish its normal admission marker.
            foreach (var member in admission.OriginalMembers)
                if (_sessions.TryGetValue(member.Session, out var current) &&
                    current.CharacterId == member.CharacterId && current.AccountId == member.AccountId &&
                    current.Ownership == member.Ownership && current.WorldInstanceId == instanceId)
                    admission.Entrants.Add(member.CharacterId);
            if (WorldInstances.TryFind(instanceId, out var runtime))
                InvokeWorldOwnerAuthoritativeMutation(runtime, map =>
                {
                    if (admission.Entrants.Count == 0 ||
                        !map.TryFinalizeWonderlandAdmissions(admission.Entrants))
                        map.CancelWonderland(DateTimeOffset.UtcNow);
                    return true;
                });
            admission.Sealed = true;
            if (admission.Entrants.Count == 0) _wonderlandDepartures.TryAdd(instanceId, 0);
        }
    }

    private bool MayEnterWonderlandMap(MapInstance map, int characterId)
    {
        if (map.MapId != WonderlandMapId || !map.TryGetWonderlandSnapshot(out var run)) return true;
        if (!_wonderlandAdmissions.TryGetValue(map.WorldInstanceId, out var admission)) return false;
        if (run.State == WonderlandRunState.Active)
            return admission.Sealed ? admission.Entrants.Contains(characterId) :
                admission.OriginalMembers.Any(member => member.CharacterId == characterId);
        // A completed run permits only in-place travel for an existing owner.
        // WorldReady can be false while that same-map scene change is pending.
        return WonderlandCompletionPolicy.IsTreasureWindowOpen(run, DateTimeOffset.UtcNow) &&
            admission.Sealed && admission.Entrants.Contains(characterId) &&
            _sessions.Values.Any(member => member.CharacterId == characterId &&
                member.WorldInstanceId == map.WorldInstanceId && member.MapId == WonderlandMapId &&
                member.Character.CurrentMap == WonderlandMapId && !member.Session.IsDisconnected &&
                member.Ownership.IsValid && IsCurrentAccountSession(member.AccountId, member.Session, member.Ownership));
    }

    internal bool TryGetWonderlandEncounterSnapshot(WorldInstanceId instanceId, out WonderlandSnapshot snapshot)
    {
        snapshot = null!;
        if (!WorldInstances.TryFind(instanceId, out var runtime) || runtime.MapId != WonderlandMapId) return false;
        var captured = InvokeWorldOwner(runtime, map => map.TryGetWonderlandSnapshot(out var run) ? run : null);
        if (captured is null) return false;
        snapshot = captured;
        return true;
    }

    internal void RecordWonderlandMonsterKillCommitted(WorldInstanceRuntime runtime,
        MonsterDamageResult damage, DateTimeOffset now)
    {
        if (runtime.MapId != WonderlandMapId || !damage.Killed || damage.AfterHealth != 0 ||
            damage.Monster.Definition.MapId != WonderlandMapId || damage.HealthMutation is not { } mutation ||
            mutation.AfterHealthRevision != damage.Monster.HealthRevision ||
            mutation.SpawnGeneration != damage.Monster.SpawnGeneration) return;
        lock (_gate)
        {
            if (!_wonderlandAdmissions.TryGetValue(runtime.InstanceId, out var admission) || !admission.Sealed) return;
            var result = InvokeWorldOwnerAuthoritativeMutation(runtime, map =>
            {
                if (!map.TryGetMonsterSnapshot(damage.ObjectId, out var current) || current.IsAlive ||
                    current.CurrentHealth != 0 || current.RuntimeInstanceId != damage.Monster.RuntimeInstanceId ||
                    current.SpawnGeneration != damage.Monster.SpawnGeneration ||
                    current.HealthRevision != mutation.AfterHealthRevision) return null;
                return map.RecordCommittedWonderlandKill(runtime.InstanceId, damage.ObjectId,
                    damage.Monster.SpawnGeneration, now);
            });
            if (result?.ClearedIsland is not { } clear || clear.Island is < 1 or > 8) return;
            var admitted = admission.OriginalMembers.Where(member => admission.Entrants.Contains(member.CharacterId))
                .Select(member => new WonderlandTitleMember(member.AccountId, member.CharacterId, member.Ownership))
                .ToArray();
            var finishers = SnapshotWonderlandMembersLocked(runtime).Where(context =>
                    admission.Entrants.Contains(context.CharacterId)).ToArray();
            var frozen = finishers
                .Select(context => new WonderlandTitleMember(context.AccountId, context.CharacterId, context.Ownership))
                .ToArray();
            if (admitted.Length == 0 || frozen.Length == 0) return;
            var request = new WonderlandTitleRequest(runtime.InstanceId, runtime.RealmId, admission.ReservationId,
                admission.StartedAt, clear.ClearedAt, clear.Island, admitted, frozen);
            if (QueueWonderlandTitleMilestone(request))
                CaptureWonderlandCompletionNoticeLocked(request, admission.LeaderId, finishers);
        }
    }

    private GameSessionContext[] SnapshotWonderlandMembersLocked(WorldInstanceRuntime runtime) =>
        _sessions.Values.Where(context => context.WorldInstanceId == runtime.InstanceId &&
            context.WorldReady && !context.Session.IsDisconnected && context.RealmId == runtime.RealmId &&
            context.MapId == WonderlandMapId && context.Character.CurrentMap == WonderlandMapId &&
            context.Ownership.IsValid && IsCurrentAccountSession(context.AccountId, context.Session, context.Ownership))
            .OrderBy(context => context.CharacterId).ToArray();

    private bool IsCurrentWonderlandMember(GameSessionContext member, WorldInstanceId instanceId) =>
        _sessions.TryGetValue(member.Session, out var current) && current.WorldReady &&
        !current.Session.IsDisconnected && current.AccountId == member.AccountId &&
        current.CharacterId == member.CharacterId && current.Ownership == member.Ownership &&
        current.WorldInstanceId == instanceId && current.MapId == WonderlandMapId &&
        current.Character.CurrentMap == WonderlandMapId &&
        IsCurrentAccountSession(member.AccountId, member.Session, member.Ownership);

    private sealed class WonderlandAdmission(Guid reservationId, ushort dailyLimit, int leaderId,
        LegacyInstancePartyMember[] originalMembers, DateTimeOffset startedAt)
    {
        public Guid ReservationId { get; } = reservationId;
        public ushort DailyLimit { get; } = dailyLimit;
        public int LeaderId { get; } = leaderId;
        public LegacyInstancePartyMember[] OriginalMembers { get; } = originalMembers;
        public DateTimeOffset StartedAt { get; } = startedAt;
        public HashSet<int> Entrants { get; } = [];
        public bool Sealed { get; set; }
    }
}
