using System.Collections.Concurrent;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;
using Godswar.Server.Packets;
using Godswar.Server.State;

namespace Godswar.Server.Game;

/// <summary>
/// 港湾遇袭 runs: one exact instance per admitted party, a thirty-minute window,
/// and a return to the faction capital when that window closes or the run ends.
/// </summary>
/// <remarks>
/// The dungeon's own monsters and drops are published into the map by the
/// content tooling, so a run owns no encounter, roster, loot or progression
/// state of its own. What it owns is admission, the clock, egress, the client's
/// repetition panel and retirement.
/// </remarks>
internal sealed partial class GameSessionRegistry
{
    private readonly ConcurrentDictionary<WorldInstanceId, HarborAttackAdmission>
        _harborAttackAdmissions = [];
    private readonly ConcurrentDictionary<Guid, WorldInstanceId>
        _harborAttackReservations = [];
    // The instant the end control was accepted, or the deadline that expired, so
    // every non-completed end gives its members the same thirty-second leave
    // countdown a completed run shows.
    private readonly ConcurrentDictionary<WorldInstanceId, DateTimeOffset>
        _harborAttackTerminations = [];
    private readonly ConcurrentDictionary<WorldInstanceId, byte>
        _harborAttackRetirements = [];
    private readonly ConcurrentDictionary<WorldInstanceId, DateTimeOffset>
        _harborAttackLastError = [];
    private readonly ConcurrentDictionary<ClientSession, HarborAttackUiStamp>
        _harborAttackUi = [];
    private int _harborAttackWorldInFlight;

    internal bool TryStartHarborAttackEncounter(
        WorldInstanceId instanceId,
        ushort dailyLimit,
        IReadOnlyList<LegacyInstancePartyMember> members,
        DateTimeOffset startedAt,
        Guid reservationId)
    {
        if (dailyLimit == 0 ||
            reservationId == Guid.Empty ||
            members.Count is < 1 ||
            members.Count > Protocol.PartyProtocol.MaximumMembers ||
            !WorldInstances.TryFind(instanceId, out var runtime) ||
            !DynamicDungeonContentMapPolicy.IsHarborAttackMap(runtime.MapId))
        {
            return false;
        }

        lock (_gate)
        {
            if (_harborAttackAdmissions.ContainsKey(instanceId))
            {
                return false;
            }
            foreach (var member in members)
            {
                if (!_sessions.TryGetValue(member.Session, out var current) ||
                    current.CharacterId != member.CharacterId ||
                    current.AccountId != member.AccountId ||
                    current.Ownership != member.Ownership ||
                    current.RealmId != runtime.RealmId ||
                    current.Session.IsDisconnected ||
                    !IsCurrentAccountSession(
                        member.AccountId,
                        member.Session,
                        member.Ownership))
                {
                    return false;
                }
            }

            _harborAttackAdmissions[instanceId] = new(
                reservationId,
                dailyLimit,
                members[0].CharacterId,
                members[0].Session,
                members.ToArray(),
                startedAt.ToUniversalTime());
            _harborAttackReservations[reservationId] = instanceId;
            return true;
        }
    }

    /// <summary>
    /// Whether this session has already been routed into a 港湾遇袭 run.
    /// </summary>
    /// <remarks>
    /// Deliberately weaker than <see cref="TryGetHarborAttackInstance"/>: the
    /// leader's own activation asks this before the destination readiness
    /// handshake, when the member is not yet a live occupant of the map.
    /// </remarks>
    internal bool IsHarborAttackRunForSession(ClientSession session)
    {
        lock (_gate)
        {
            return _sessions.TryGetValue(session, out var context) &&
                _harborAttackAdmissions.ContainsKey(context.WorldInstanceId);
        }
    }

    /// <summary>
    /// Whether this session currently holds a 港湾遇袭 run.
    /// </summary>
    internal bool TryGetHarborAttackInstance(
        ClientSession session,
        out WorldInstanceId instanceId)
    {
        instanceId = default;
        lock (_gate)
        {
            if (!_sessions.TryGetValue(session, out var context) ||
                !_harborAttackAdmissions.ContainsKey(context.WorldInstanceId) ||
                !IsCurrentHarborAttackMember(context, context.WorldInstanceId))
            {
                return false;
            }
            instanceId = context.WorldInstanceId;
            return true;
        }
    }

    /// <summary>
    /// Free revival inside a 港湾遇袭 run: the character returns to the run's own
    /// arrival with a tenth of their health, and the run keeps its clock.
    /// </summary>
    internal bool TryReviveHarborAttackPlayer(
        ClientSession session,
        out WorldInstanceId instanceId,
        out float arrivalX,
        out float arrivalZ,
        out long lifeRevision)
    {
        instanceId = default;
        arrivalX = InstanceCallerProtocol.HarborAttackArrivalX;
        arrivalZ = InstanceCallerProtocol.HarborAttackArrivalZ;
        lifeRevision = -1;
        lock (_gate)
        {
            if (!_sessions.TryGetValue(session, out var context) ||
                !_harborAttackAdmissions.TryGetValue(
                    context.WorldInstanceId,
                    out var admission) ||
                !IsCurrentHarborAttackMember(context, context.WorldInstanceId) ||
                DateTimeOffset.UtcNow >= admission.Deadline ||
                _harborAttackTerminations.ContainsKey(context.WorldInstanceId))
            {
                return false;
            }
            lock (context.Character.VitalsSync)
            {
                if (context.Character.CurrentHp > 0)
                {
                    return false;
                }
                lifeRevision = AdvancePlayerLifeRevision(session);
                if (lifeRevision < 0)
                {
                    return false;
                }
                context.Character.CurrentHp =
                    Math.Max(1, context.Character.MaxHp / 10);
                context.Character.CurrentMp =
                    Math.Max(0, context.Character.MaxMp / 10);
                context.Character.MarkVitalsChanged();
            }
            instanceId = context.WorldInstanceId;
            return true;
        }
    }

    /// <summary>
    /// The admitted leader ends the run through either native repetition control,
    /// exactly as Atlantis, Wonderland and Medusa do.
    /// </summary>
    internal bool TryTerminateHarborAttackRunFromLeader(
        ClientSession session,
        int repetitionId,
        int repetitionIndex)
    {
        if (repetitionIndex != 0)
        {
            return false;
        }
        lock (_gate)
        {
            if (!_sessions.TryGetValue(session, out var actor) ||
                actor.Character.CurrentMap != actor.MapId ||
                !DynamicDungeonContentMapPolicy.IsHarborAttackMap(actor.MapId) ||
                repetitionId != HarborAttackClientSceneId(actor.MapId) ||
                !_harborAttackAdmissions.TryGetValue(
                    actor.WorldInstanceId,
                    out var admission) ||
                actor.CharacterId != admission.LeaderId ||
                // Party leadership is a separate system and must not gate the
                // instance's own end control; only its leader may end it.
                !IsCurrentAccountSession(
                    actor.AccountId,
                    actor.Session,
                    actor.Ownership))
            {
                return false;
            }

            _harborAttackTerminations.TryAdd(
                actor.WorldInstanceId,
                DateTimeOffset.UtcNow);
            Console.WriteLine(
                "[harbor] leader termination instance=" +
                $"{actor.WorldInstanceId} leader={actor.Character.Name}");
            return true;
        }
    }

    private async Task AdvanceHarborAttackWorldAsync(
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        if (Interlocked.Exchange(ref _harborAttackWorldInFlight, 1) != 0)
        {
            return;
        }
        try
        {
            foreach (var entry in _harborAttackAdmissions)
            {
                var instanceId = entry.Key;
                try
                {
                    if (!WorldInstances.TryFind(instanceId, out var runtime))
                    {
                        ForgetHarborAttackRun(instanceId);
                        continue;
                    }

                    var admission = entry.Value;
                    if (runtime.Descriptor.LifecycleState !=
                        WorldInstanceLifecycleState.Active)
                    {
                        await TryRetireHarborAttackRuntimeAsync(
                            instanceId,
                            runtime,
                            cancellationToken);
                        continue;
                    }

                    GameSessionContext[] members;
                    lock (_gate)
                    {
                        members = SnapshotHarborAttackMembersLocked(runtime);
                        foreach (var member in members)
                        {
                            admission.Entrants.Add(member.CharacterId);
                        }
                        // A run whose registered leader has left keeps an ending
                        // authority: the earliest present entrant takes over.
                        var present = OrderInstanceMembers(
                            [.. admission.OriginalMembers.Select(
                                static member => member.CharacterId)],
                            [.. members.Select(static member => member.CharacterId)]);
                        if (TryResolveInstanceLeaderSuccessor(
                                instanceId,
                                "HarborAttack",
                                admission.LeaderId,
                                present,
                                out var successor))
                        {
                            admission.LeaderId = successor;
                        }
                    }

                    var expired = now >= admission.Deadline;
                    var terminated = _harborAttackTerminations.TryGetValue(
                        instanceId,
                        out var terminatedAt);
                    if (expired || terminated)
                    {
                        // A run that was ended or ran out of time behaves like a
                        // completed one: the panel becomes the native leave
                        // countdown, every member may leave immediately, and the
                        // rest are carried home when the thirty seconds expire.
                        var endStartedAt = terminated ? terminatedAt : admission.Deadline;
                        var endRemaining = checked((int)Math.Clamp(
                            Math.Ceiling((endStartedAt + HarborAttackPolicy.EndExitDelay - now)
                                .TotalSeconds),
                            0,
                            (int)HarborAttackPolicy.EndExitDelay.TotalSeconds));
                        if (endRemaining > 0 && members.Length != 0)
                        {
                            await PublishHarborAttackEndUiAsync(
                                runtime,
                                admission,
                                members,
                                endRemaining,
                                cancellationToken);
                        }
                        else
                        {
                            await ExitHarborAttackMembersAsync(
                                runtime,
                                admission,
                                members,
                                terminated ? "terminated" : "deadline",
                                cancellationToken);
                        }
                    }
                    else
                    {
                        await PublishHarborAttackRunUiAsync(
                            runtime,
                            admission,
                            members,
                            now,
                            cancellationToken);
                    }

                    // The run is abandoned once everyone it admitted has left
                    // the map, but never before the first arrival: the runtime
                    // exists from before the leader's transfer commits. An
                    // instance whose whole party vanished before the first tick
                    // observed them is released when its own window closes.
                    if (members.Length == 0 &&
                        (admission.Entrants.Count != 0 || expired || terminated))
                    {
                        _harborAttackRetirements.TryAdd(instanceId, 0);
                    }
                    await TryRetireHarborAttackRuntimeAsync(
                        instanceId,
                        runtime,
                        cancellationToken);
                }
                catch (Exception error) when (
                    error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    LogHarborAttackDeferred(instanceId, now, error);
                }
            }
        }
        finally
        {
            Volatile.Write(ref _harborAttackWorldInFlight, 0);
        }
    }

    /// <summary>
    /// Publishes the native leave countdown to every member still inside a run
    /// that was ended or timed out, exactly as a completed run does: the same
    /// panel-completion state, the same countdown packet, and the same thirty
    /// seconds.
    /// </summary>
    private async Task PublishHarborAttackEndUiAsync(
        WorldInstanceRuntime runtime,
        HarborAttackAdmission admission,
        IReadOnlyList<GameSessionContext> members,
        int remainingSeconds,
        CancellationToken cancellationToken)
    {
        var sceneId = HarborAttackClientSceneId(runtime.MapId);
        var roster = members
            .Select(member => new RepetitionInstanceMember(
                member.CharacterId,
                member.Character.Name,
                member.Character.Level,
                true,
                member.Character.Profession))
            .ToArray();
        var signature = string.Join('|', roster.Select(member =>
            $"{member.CharacterId}:{member.Name}:{member.Level}:{member.Profession}"));
        var stamp = new HarborAttackUiStamp(
            runtime.InstanceId,
            remainingSeconds,
            signature,
            Ending: true);

        foreach (var member in members)
        {
            if (!member.WorldReady)
            {
                continue;
            }
            Task? write = null;
            lock (_gate)
            {
                if (!IsCurrentHarborAttackMember(member, runtime.InstanceId))
                {
                    continue;
                }
                _harborAttackUi.TryGetValue(member.Session, out var previous);
                // The native countdowns locally from the published value, so the
                // batch is sent once per member: resending would restart it.
                if (previous?.InstanceId == stamp.InstanceId && previous.Ending)
                {
                    continue;
                }
                var packets = new List<ReadOnlyMemory<byte>>();
                packets.Add(PacketBuilder.RepetitionSync(
                    checked((ushort)sceneId),
                    0,
                    0,
                    5,
                    admission.DailyLimit));
                if (previous?.InstanceId != stamp.InstanceId ||
                    previous.Roster != signature)
                {
                    packets.Add(PacketBuilder.RepetitionInstanceMembers(roster));
                }
                packets.Add(PacketBuilder.RepetitionFightInfo(remainingSeconds, 0));
                packets.Add(PacketBuilder.RepetitionPanelCompletion());
                packets.Add(PacketBuilder.RepetitionCompletionState(sceneId, true));
                packets.Add(PacketBuilder.RepetitionCountdown(remainingSeconds));
                if (member.Session.TryAdmitExactBatch(packets, out var admitted))
                {
                    _harborAttackUi[member.Session] = stamp;
                }
                write = admitted;
            }

            if (write is not null)
            {
                try
                {
                    await write;
                    Console.WriteLine(
                        "[harbor] end countdown published instance=" +
                        $"{runtime.InstanceId} character={member.CharacterId} " +
                        $"seconds={remainingSeconds}");
                }
                catch (Exception error) when (
                    error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    member.Session.Disconnect();
                }
            }
        }
    }

    private async Task PublishHarborAttackRunUiAsync(
        WorldInstanceRuntime runtime,
        HarborAttackAdmission admission,
        IReadOnlyList<GameSessionContext> members,
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        if (members.Count == 0)
        {
            return;
        }

        var sceneId = HarborAttackClientSceneId(runtime.MapId);
        var remaining = checked((int)Math.Clamp(
            Math.Ceiling((admission.Deadline - now).TotalSeconds),
            0,
            HarborAttackPolicy.TimeLimitSeconds));
        var roster = members
            .Select(member => new RepetitionInstanceMember(
                member.CharacterId,
                member.Character.Name,
                member.Character.Level,
                true,
                member.Character.Profession))
            .ToArray();
        var signature = string.Join('|', roster.Select(member =>
            $"{member.CharacterId}:{member.Name}:{member.Level}:{member.Profession}"));
        var stamp = new HarborAttackUiStamp(
            runtime.InstanceId,
            remaining,
            signature);

        foreach (var member in members)
        {
            // The repetition state must reach the client after its destination
            // scene is ready, exactly as the Wonderland and Medusa panels do: a
            // sync delivered while the scene is still loading leaves the panel
            // without its run state (and without the native end-instance
            // control). A member who is not ready yet is published on a later
            // tick.
            if (!member.WorldReady)
            {
                continue;
            }
            Task? write = null;
            lock (_gate)
            {
                if (!IsCurrentHarborAttackMember(member, runtime.InstanceId))
                {
                    continue;
                }
                _harborAttackUi.TryGetValue(member.Session, out var previous);
                if (previous == stamp)
                {
                    continue;
                }

                var packets = new List<ReadOnlyMemory<byte>>();
                if (previous?.InstanceId != stamp.InstanceId)
                {
                    // Repetition state 5 is the client's active-run state, the
                    // same value the Wonderland panel reasserts.
                    packets.Add(PacketBuilder.RepetitionSync(
                        checked((ushort)sceneId),
                        0,
                        0,
                        5,
                        admission.DailyLimit));
                }
                if (previous?.InstanceId != stamp.InstanceId ||
                    previous.Roster != signature)
                {
                    packets.Add(PacketBuilder.RepetitionInstanceMembers(roster));
                }
                packets.Add(PacketBuilder.RepetitionFightInfo(remaining, 0));
                if (member.Session.TryAdmitExactBatch(packets, out var admitted))
                {
                    _harborAttackUi[member.Session] = stamp;
                }
                write = admitted;
            }

            if (write is not null)
            {
                try
                {
                    await write;
                }
                catch (Exception error) when (
                    error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    member.Session.Disconnect();
                }
            }
        }
    }

    /// <summary>
    /// A member's own leave during the end-of-run countdown: the run is already
    /// terminal, so this returns the transition that carries that member home
    /// immediately instead of waiting for the countdown to expire.
    /// </summary>
    internal bool TryResolveHarborAttackEndLeave(
        ClientSession session,
        int repetitionId,
        int repetitionIndex,
        DateTimeOffset now,
        out AuthoritativeInstanceTransitionCommand command)
    {
        command = default;
        ArgumentNullException.ThrowIfNull(session);
        if (repetitionIndex != 0)
        {
            return false;
        }
        lock (_gate)
        {
            if (!_sessions.TryGetValue(session, out var actor) ||
                !DynamicDungeonContentMapPolicy.IsHarborAttackMap(actor.MapId) ||
                actor.Character.CurrentMap != actor.MapId ||
                repetitionId != HarborAttackClientSceneId(actor.MapId) ||
                !_harborAttackAdmissions.TryGetValue(
                    actor.WorldInstanceId,
                    out var admission) ||
                !IsCurrentHarborAttackMember(actor, actor.WorldInstanceId) ||
                !IsCurrentAccountSession(
                    actor.AccountId,
                    actor.Session,
                    actor.Ownership))
            {
                return false;
            }
            var endStartedAt = _harborAttackTerminations.TryGetValue(
                actor.WorldInstanceId,
                out var terminatedAt)
                    ? terminatedAt
                    : admission.Deadline;
            if (now < endStartedAt ||
                now - endStartedAt >= HarborAttackPolicy.EndExitDelay)
            {
                return false;
            }

            var targetMap = actor.Character.Camp == GameDefaults.SpartaCamp
                ? GameDefaults.SpartaCapitalMap
                : GameDefaults.AthensCapitalMap;
            var target = GetOrCreateDefaultWorldInstance(targetMap);
            command = new AuthoritativeInstanceTransitionCommand(
                actor.CharacterId,
                actor.WorldInstanceId,
                actor.MapId,
                actor.Ownership,
                target.InstanceId,
                targetMap,
                GameDefaults.StartingPositionX,
                GameDefaults.StartingPositionZ);
            return true;
        }
    }

    private async Task ExitHarborAttackMembersAsync(
        WorldInstanceRuntime runtime,
        HarborAttackAdmission admission,
        IReadOnlyList<GameSessionContext> members,
        string reason,
        CancellationToken cancellationToken)
    {
        if (members.Count == 0)
        {
            return;
        }

        foreach (var member in members)
        {
            lock (_gate)
            {
                if (!IsCurrentHarborAttackMember(member, runtime.InstanceId))
                {
                    Console.WriteLine(
                        "[harbor] exit skipped character=" +
                        $"{member.Character.Name} " +
                        $"instance={runtime.InstanceId} reason=stale");
                    continue;
                }
            }

            var targetMap = member.Character.Camp == GameDefaults.SpartaCamp
                ? GameDefaults.SpartaCapitalMap
                : GameDefaults.AthensCapitalMap;
            var target = GetOrCreateDefaultWorldInstance(targetMap);
            var command = new AuthoritativeInstanceTransitionCommand(
                member.CharacterId,
                runtime.InstanceId,
                runtime.MapId,
                member.Ownership,
                target.InstanceId,
                targetMap,
                GameDefaults.StartingPositionX,
                GameDefaults.StartingPositionZ);
            if (!await TransitionPartyMemberToAuthoritativeInstanceAsync(
                    member.Session,
                    command,
                    cancellationToken))
            {
                LogHarborAttackDeferred(
                    runtime.InstanceId,
                    DateTimeOffset.UtcNow,
                    new InvalidOperationException(
                        $"Exit deferred for character {member.CharacterId}."));
                continue;
            }

            Console.WriteLine(
                "[harbor] exit " +
                $"character={member.Character.Name} " +
                $"instance={runtime.InstanceId} reason={reason} " +
                $"leader={admission.LeaderId} target-map={targetMap}");
        }
    }

    private async Task TryRetireHarborAttackRuntimeAsync(
        WorldInstanceId instanceId,
        WorldInstanceRuntime runtime,
        CancellationToken cancellationToken)
    {
        if (!_harborAttackRetirements.ContainsKey(instanceId))
        {
            return;
        }

        for (var phase = 0; phase < 3; phase++)
        {
            if (!WorldInstances.TryFind(instanceId, out runtime))
            {
                ForgetHarborAttackRun(instanceId);
                return;
            }

            var descriptor = runtime.Descriptor;
            bool empty;
            if (descriptor.LifecycleState == WorldInstanceLifecycleState.Closed)
            {
                empty = runtime.Map.Population == 0;
            }
            else
            {
                if (runtime.Owner.GetSnapshot().State !=
                    SingleOwnerMailboxState.Accepting)
                {
                    return;
                }
                empty = InvokeWorldOwner(
                    runtime,
                    map => map.Population == 0);
            }
            if (!empty)
            {
                return;
            }

            var at = Maximum(DateTimeOffset.UtcNow, descriptor.LastTransitionAt);
            var result = descriptor.LifecycleState switch
            {
                WorldInstanceLifecycleState.Active =>
                    await WorldInstances.BeginDrainAsync(
                        instanceId,
                        descriptor.Revision,
                        at,
                        cancellationToken),
                WorldInstanceLifecycleState.Draining =>
                    await WorldInstances.CloseAsync(
                        instanceId,
                        descriptor.Revision,
                        at,
                        cancellationToken),
                WorldInstanceLifecycleState.Closed =>
                    await WorldInstances.RemoveClosedAsync(
                        instanceId,
                        cancellationToken),
                _ => default
            };
            if (result.Status is
                WorldInstanceRuntimeDirectoryStatus.Removed or
                WorldInstanceRuntimeDirectoryStatus.InstanceNotFound)
            {
                ForgetHarborAttackRun(instanceId);
                return;
            }
            if (result.Status is not (
                WorldInstanceRuntimeDirectoryStatus.Draining or
                WorldInstanceRuntimeDirectoryStatus.Closed))
            {
                return;
            }
        }
    }

    /// <summary>
    /// The sessions this run has routed into its instance.
    /// </summary>
    /// <remarks>
    /// Deliberately not gated on the client's destination readiness handshake:
    /// the abort vote and the terminal egress must account for, and carry out,
    /// every member the run admitted even if their client has not finished
    /// loading the scene yet.
    /// </remarks>
    private GameSessionContext[] SnapshotHarborAttackMembersLocked(
        WorldInstanceRuntime runtime) =>
        _sessions.Values
            .Where(context =>
                context.WorldInstanceId == runtime.InstanceId &&
                !context.Session.IsDisconnected &&
                context.RealmId == runtime.RealmId &&
                context.Ownership.IsValid &&
                IsCurrentAccountSession(
                    context.AccountId,
                    context.Session,
                    context.Ownership))
            .OrderBy(context => context.CharacterId)
            .ToArray();

    private bool IsCurrentHarborAttackMember(
        GameSessionContext member,
        WorldInstanceId instanceId) =>
        _sessions.TryGetValue(member.Session, out var current) &&
        !current.Session.IsDisconnected &&
        current.AccountId == member.AccountId &&
        current.CharacterId == member.CharacterId &&
        current.Ownership == member.Ownership &&
        current.WorldInstanceId == instanceId &&
        IsCurrentAccountSession(
            member.AccountId,
            member.Session,
            member.Ownership);

    private void ForgetHarborAttackRun(WorldInstanceId instanceId)
    {
        if (_harborAttackAdmissions.TryRemove(instanceId, out var admission))
        {
            _harborAttackReservations.TryRemove(
                admission.ReservationId,
                out _);
            CloseMemberEntryWindow(admission.LeaderSession);
        }
        _harborAttackTerminations.TryRemove(instanceId, out _);
        _harborAttackRetirements.TryRemove(instanceId, out _);
        _harborAttackLastError.TryRemove(instanceId, out _);
        foreach (var cached in _harborAttackUi
                     .Where(pair => pair.Value.InstanceId == instanceId))
        {
            _harborAttackUi.TryRemove(cached);
        }
    }

    private static int HarborAttackClientSceneId(int mapId) =>
        mapId == DynamicDungeonContentMapPolicy.HarborAttackSecondMapId
            ? InstanceCallerProtocol.HarborAttackSecondClientSceneId
            : InstanceCallerProtocol.HarborAttackFirstClientSceneId;

    private void LogHarborAttackDeferred(
        WorldInstanceId instanceId,
        DateTimeOffset now,
        Exception error)
    {
        if (_harborAttackLastError.TryAdd(instanceId, now) ||
            _harborAttackLastError.TryGetValue(instanceId, out var previous) &&
            now - previous >= TimeSpan.FromSeconds(30) &&
            _harborAttackLastError.TryUpdate(instanceId, now, previous))
        {
            Console.Error.WriteLine(
                $"[harbor] deferred instance={instanceId}: {error.Message}");
        }
    }

    private sealed class HarborAttackAdmission(
        Guid reservationId,
        ushort dailyLimit,
        int leaderId,
        ClientSession leaderSession,
        LegacyInstancePartyMember[] originalMembers,
        DateTimeOffset startedAt)    {
        public Guid ReservationId { get; } = reservationId;
        public ushort DailyLimit { get; } = dailyLimit;
        // Transferable: the run's leader moves to the earliest still-present
        // entrant when the registered leader leaves or drops.
        public int LeaderId { get; set; } = leaderId;
        public ClientSession LeaderSession { get; } = leaderSession;
        public LegacyInstancePartyMember[] OriginalMembers { get; } =
            originalMembers;
        public DateTimeOffset StartedAt { get; } = startedAt;
        public HashSet<int> Entrants { get; } = [];

        public DateTimeOffset Deadline =>
            StartedAt + HarborAttackPolicy.TimeLimit;
    }

    private sealed record HarborAttackUiStamp(
        WorldInstanceId InstanceId,
        int RemainingSeconds,
        string Roster,
        bool Ending = false);
}
