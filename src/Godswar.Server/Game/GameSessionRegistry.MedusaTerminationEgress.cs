using System.Collections.Concurrent;
using Godswar.Server.Application.Characters;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private readonly ConcurrentDictionary<WorldInstanceId, DateTimeOffset>
        _medusaTerminationExitRequested = [];
    private readonly ConcurrentDictionary<WorldInstanceId, byte>
        _medusaTerminationEgressInFlight = [];
    private readonly ConcurrentDictionary<WorldInstanceId, byte>
        _medusaTerminationExitSettled = [];

    // MedusaTerminationExitDelay lives beside the panel publisher, which reads
    // the same window to publish the countdown.

    private readonly ConcurrentDictionary<WorldInstanceId, byte>
        _medusaTerminationExitImmediate = [];

    /// <summary>
    /// A member's own "leave the instance" during the end-of-run countdown: the
    /// run is already terminal, so the countdown is cut short and everyone still
    /// inside is carried home now, the way the end control always behaved.
    /// </summary>
    internal bool TryRequestImmediateMedusaTerminationExit(
        ClientSession session)
    {
        ArgumentNullException.ThrowIfNull(session);
        lock (_gate)
        {
            if (!_sessions.TryGetValue(session, out var actor) ||
                !actor.WorldReady || actor.Session.IsDisconnected ||
                actor.MapId is not (200 or 204) ||
                actor.Character.CurrentMap != actor.MapId ||
                !actor.Ownership.IsValid ||
                !IsCurrentAccountSession(
                    actor.AccountId,
                    actor.Session,
                    actor.Ownership) ||
                !WorldInstances.TryFind(actor.WorldInstanceId, out var runtime))
            {
                return false;
            }
            var run = InvokeWorldOwner(
                runtime,
                static map => map.TryGetMedusaOwnershipSnapshot(
                        out var ownership)
                    ? ownership.Run
                    : null);
            if (run is null ||
                run.State is not (
                    MedusaRunState.TimedOut or
                    MedusaRunState.VoluntarilyExited))
            {
                return false;
            }
            RequestMedusaTerminationExit(actor.WorldInstanceId);
            _medusaTerminationExitImmediate.TryAdd(actor.WorldInstanceId, 0);
            return true;
        }
    }

    /// <summary>
    /// Whether this session's run reached completion, so the end control closes
    /// the completion countdown rather than the end-of-run countdown.
    /// </summary>
    internal bool IsMedusaRunCompleted(ClientSession session)
    {
        ArgumentNullException.ThrowIfNull(session);
        if (!_sessions.TryGetValue(session, out var actor) ||
            !WorldInstances.TryFind(actor.WorldInstanceId, out var runtime))
        {
            return false;
        }
        var run = InvokeWorldOwner(
            runtime,
            static map => map.TryGetMedusaOwnershipSnapshot(
                    out var ownership)
                ? ownership.Run
                : null);
        return run is { State: MedusaRunState.Completed };
    }

    private void RequestMedusaTerminationExit(
        WorldInstanceId worldInstanceId) =>
        _medusaTerminationExitRequested.TryAdd(
            worldInstanceId,
            DateTimeOffset.UtcNow);

    private MedusaTerminationEgress? CaptureMedusaTerminationEgress(
        WorldInstanceRuntime runtime,
        DateTimeOffset now)
    {
        if (!_medusaTerminationExitRequested.TryGetValue(
                runtime.InstanceId,
                out var requestedAt) ||
            _medusaTerminationExitSettled.ContainsKey(runtime.InstanceId))
        {
            return null;
        }

        var run = InvokeWorldOwner(
            runtime,
            static map => map.TryGetMedusaOwnershipSnapshot(
                    out var ownership)
                ? ownership.Run
                : null);
        if (run is null ||
            run.State is not (
                MedusaRunState.TimedOut or
                MedusaRunState.VoluntarilyExited))
        {
            return null;
        }

        // The run is terminal, but its members keep the same leave countdown a
        // completed run shows; they are carried out when it expires, or at once
        // when a member asks to leave during it.
        var endStartedAt = run.State == MedusaRunState.TimedOut
            ? run.Deadline
            : requestedAt;
        if (!_medusaTerminationExitImmediate.ContainsKey(runtime.InstanceId) &&
            now - endStartedAt < MedusaTerminationExitDelay)
        {
            return null;
        }

        var members = new List<MedusaTerminationEgressMember>();
        lock (_gate)
        {
            foreach (var context in _sessions.Values)
            {
                if (!context.WorldReady ||
                    context.Session.IsDisconnected ||
                    context.WorldInstanceId != runtime.InstanceId ||
                    context.Character.CurrentMap != context.MapId ||
                    context.MapId is not (200 or 204) ||
                    !context.Ownership.IsValid ||
                    !IsCurrentAccountSession(
                        context.AccountId,
                        context.Session,
                        context.Ownership))
                {
                    continue;
                }

                members.Add(new(
                    context.Session,
                    context.CharacterId,
                    context.CharacterName,
                    context.WorldInstanceId,
                    context.MapId,
                    context.Ownership,
                    context.Character.Camp));
            }
        }

        // A run that ended early still pays the documented score tier it reached,
        // so the reward settles from the run's own final numbers.
        return new(
            runtime.InstanceId,
            runtime.RealmId,
            run.Difficulty,
            endStartedAt.ToUniversalTime(),
            endStartedAt.ToUniversalTime() - run.StartedAt.ToUniversalTime(),
            run.TeamScore,
            run.AdmittedCharacterIds.ToArray(),
            members);
    }

    private async Task PublishMedusaTerminationEgressAsync(
        MedusaTerminationEgress egress,
        CancellationToken cancellationToken)
    {
        if (!_medusaTerminationEgressInFlight.TryAdd(
                egress.SourceWorldInstanceId,
                0))
        {
            return;
        }

        try
        {
            // Pay before carrying anyone home. A failed or pending settlement is
            // retried by later ticks and never holds the egress hostage: being
            // carried home must not depend on a durable write.
            _ = await SettleMedusaTerminationRewardAsync(egress, cancellationToken);

            var allTransferred = true;
            foreach (var member in egress.Members)
            {
                var targetMapId = member.Camp == GameDefaults.SpartaCamp
                    ? GameDefaults.SpartaCapitalMap
                    : GameDefaults.AthensCapitalMap;
                try
                {
                    var target = GetOrCreateDefaultWorldInstance(
                        targetMapId);
                    var command = new MedusaInstanceTransitionCommand(
                        member.CharacterId,
                        member.SourceWorldInstanceId,
                        member.SourceMapId,
                        member.Ownership,
                        target.InstanceId,
                        targetMapId,
                        GameDefaults.StartingPositionX,
                        GameDefaults.StartingPositionZ);
                    if (!await TransitionPartyMemberToInstanceAsync(
                            member.Session,
                            command,
                            cancellationToken))
                    {
                        allTransferred = false;
                        Console.WriteLine(
                            "[instance] Medusa termination egress will " +
                            $"retry character={member.CharacterId} " +
                            $"instance={egress.SourceWorldInstanceId}");
                    }
                }
                catch (Exception error) when (
                    error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    allTransferred = false;
                    Console.WriteLine(
                        "[instance] Medusa termination egress failed " +
                        $"character={member.CharacterId}: " +
                        error.Message);
                }
            }

            if (allTransferred)
            {
                _medusaTerminationExitSettled.TryAdd(
                    egress.SourceWorldInstanceId,
                    0);
                _medusaTerminationExitRequested.TryRemove(
                    egress.SourceWorldInstanceId,
                    out _);
                _medusaTerminationExitImmediate.TryRemove(
                    egress.SourceWorldInstanceId,
                    out _);
            }
        }
        finally
        {
            _medusaTerminationEgressInFlight.TryRemove(
                egress.SourceWorldInstanceId,
                out _);
        }
    }

    /// <summary>
    /// Pays the tier a run that ended early actually reached, through the same
    /// durable settlement and projection the completed path uses.
    /// </summary>
    /// <remarks>
    /// The settlement is keyed by world instance, so a run can never be paid
    /// twice even if it is seen by both the completion and the termination paths.
    /// The synthesized completion marker carries the run's real final score and
    /// elapsed time, and never a selected title, so an incomplete run resolves to
    /// its documented incomplete tier and pays no title.
    /// </remarks>
    private Task<bool> SettleMedusaTerminationRewardAsync(
        MedusaTerminationEgress egress,
        CancellationToken cancellationToken)
    {
        var leaderCharacterId = _medusaLeaderUi.TryGetValue(
            egress.SourceWorldInstanceId,
            out var registration)
            ? registration.LeaderCharacterId
            : egress.AdmittedCharacterIds.FirstOrDefault();
        var rewardEgress = new MedusaCompletionEgress(
            egress.SourceWorldInstanceId,
            egress.RealmId,
            egress.Difficulty,
            leaderCharacterId,
            new MedusaRunCompletionMarker(
                egress.EndedAt,
                egress.Elapsed,
                egress.FinalScore,
                SelectedTitle: null),
            egress.AdmittedCharacterIds,
            egress.Members
                .Select(static member => new MedusaCompletionEgressMember(
                    member.Session,
                    member.CharacterId,
                    member.CharacterName,
                    member.SourceWorldInstanceId,
                    member.SourceMapId,
                    member.Ownership,
                    member.Camp))
                .ToArray(),
            ExitPlayers: false,
            // The bosses never fell: this run keeps the score tier it reached.
            Completed: false);
        return SettleMedusaCompletionRewardAsync(
            rewardEgress,
            cancellationToken);
    }

    private sealed record MedusaTerminationEgress(
        WorldInstanceId SourceWorldInstanceId,
        RealmId RealmId,
        MedusaEncounterDifficulty Difficulty,
        DateTimeOffset EndedAt,
        TimeSpan Elapsed,
        int FinalScore,
        IReadOnlyList<int> AdmittedCharacterIds,
        IReadOnlyList<MedusaTerminationEgressMember> Members);

    private readonly record struct MedusaTerminationEgressMember(
        ClientSession Session,
        int CharacterId,
        string CharacterName,
        WorldInstanceId SourceWorldInstanceId,
        byte SourceMapId,
        PlayerOwnershipFence Ownership,
        byte Camp);
}
