using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private static readonly TimeSpan AtlantisCompletionExitDelay = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan AtlantisTerminationExitDelay = TimeSpan.FromSeconds(30);

    // The caller owns durable completion rewards. A failed or pending settlement
    // may publish the result UI, but cannot authorize a completion transfer.
    private async Task PublishAtlantisCompletionAsync(
        AtlantisRunDelivery delivery, bool rewardsSettled, CancellationToken cancellationToken)
    {
        if (delivery.Run.State != AtlantisRunState.Completed || delivery.Run.TerminalAt is null)
        {
            return;
        }
        await PublishAtlantisCompletionUiAsync(delivery, cancellationToken);
        if (rewardsSettled)
        {
            await PublishAtlantisCompletionEgressAsync(delivery, cancellationToken);
        }
    }

    private static int AtlantisCompletionRemainingSeconds(AtlantisRunDelivery delivery) =>
        checked((int)Math.Clamp(Math.Ceiling((AtlantisCompletionExitDelay -
            (delivery.ObservedAt - delivery.Run.TerminalAt!.Value)).TotalSeconds),
            0d, AtlantisCompletionExitDelay.TotalSeconds));

    /// <summary>
    /// The same thirty-second leave countdown a completed run shows, for a run
    /// the leader ended early or that ran out of time.
    /// </summary>
    /// <remarks>
    /// An ended run is terminal exactly like a completed one: every member inside
    /// gets the native completion panel with the leave countdown, may leave
    /// immediately, and is carried out when the countdown expires.
    /// </remarks>
    private static bool IsAtlantisTerminationExitWindowOpen(
        AtlantisRunSnapshot run,
        DateTimeOffset now) =>
        run.State is AtlantisRunState.Cancelled or AtlantisRunState.TimedOut &&
        run.TerminalAt is { } terminal && now - terminal < AtlantisTerminationExitDelay;

    private static int AtlantisTerminationRemainingSeconds(
        AtlantisRunDelivery delivery) =>
        checked((int)Math.Clamp(Math.Ceiling((AtlantisTerminationExitDelay -
            (delivery.ObservedAt - delivery.Run.TerminalAt!.Value)).TotalSeconds),
            0d, AtlantisTerminationExitDelay.TotalSeconds));

    private async Task PublishAtlantisTerminationUiAsync(
        AtlantisRunDelivery delivery, CancellationToken cancellationToken)
    {
        if (delivery.Run.TerminalAt is null)
        {
            return;
        }
        var remaining = AtlantisTerminationRemainingSeconds(delivery);
        var roster = delivery.Members.Select(static member => new RepetitionInstanceMember(
            member.CharacterId, member.Name, member.Level, true, member.Profession)).ToArray();
        var signature = string.Join('|', roster.Select(static member =>
            $"{member.CharacterId}:{member.Name}:{member.Level}:{member.Profession}"));
        var stamp = new AtlantisUiStamp(delivery.Runtime.InstanceId, delivery.Run.State,
            remaining, delivery.Run.TeamPoints, signature);

        foreach (var member in delivery.Members)
        {
            Task? completion = null;
            lock (_gate)
            {
                if (!IsCurrentAtlantisMember(delivery, member))
                {
                    continue;
                }
                _atlantisUi.TryGetValue(member.Session, out var previous);
                if (previous?.InstanceId == stamp.InstanceId &&
                    previous.State == stamp.State)
                {
                    // Native 10231 countdowns locally from the published value.
                    // Resending the batch would restart it.
                    continue;
                }
                var packets = new List<ReadOnlyMemory<byte>>();
                if (previous?.InstanceId != stamp.InstanceId)
                {
                    packets.Add(PacketBuilder.RepetitionSync(
                        AtlantisClientSceneId, 0, 0, 5, delivery.DailyEntryLimit));
                }
                if (previous?.InstanceId != stamp.InstanceId || previous.Roster != signature)
                {
                    packets.Add(PacketBuilder.RepetitionInstanceMembers(roster));
                }
                packets.Add(PacketBuilder.RepetitionFightInfo(remaining, stamp.Points));
                packets.Add(PacketBuilder.RepetitionPanelCompletion());
                packets.Add(PacketBuilder.RepetitionCompletionState(
                    AtlantisClientSceneId, true));
                packets.Add(PacketBuilder.RepetitionCountdown(remaining));
                if (member.Session.TryAdmitExactBatch(packets, out var admitted))
                {
                    _atlantisUi[member.Session] = stamp;
                }
                completion = admitted;
            }
            if (completion is not null)
            {
                try
                {
                    await completion;
                    Console.WriteLine(
                        "[atlantis] end countdown published instance=" +
                        $"{delivery.Runtime.InstanceId} " +
                        $"character={member.CharacterId} seconds={remaining} " +
                        $"state={delivery.Run.State}");
                }
                catch (Exception error) when (error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    member.Session.Disconnect();
                }
            }
        }
    }

    private async Task PublishAtlantisCompletionUiAsync(
        AtlantisRunDelivery delivery, CancellationToken cancellationToken)
    {
        var remaining = AtlantisCompletionRemainingSeconds(delivery);
        var roster = delivery.Members.Select(static member => new RepetitionInstanceMember(
            member.CharacterId, member.Name, member.Level, true, member.Profession)).ToArray();
        var signature = string.Join('|', roster.Select(static member =>
            $"{member.CharacterId}:{member.Name}:{member.Level}:{member.Profession}"));
        var stamp = new AtlantisUiStamp(delivery.Runtime.InstanceId, AtlantisRunState.Completed,
            remaining, delivery.Run.TeamPoints, signature);

        foreach (var member in delivery.Members)
        {
            Task? completion = null;
            lock (_gate)
            {
                if (_atlantisTerminationExitRequested.ContainsKey(delivery.Runtime.InstanceId) ||
                    !IsCurrentAtlantisMember(delivery, member))
                {
                    continue;
                }
                _atlantisUi.TryGetValue(member.Session, out var previous);
                if (previous?.InstanceId == stamp.InstanceId &&
                    previous.State == AtlantisRunState.Completed)
                {
                    // Native 10231 drives its own countdown. Resending fight
                    // or reset packets would restart it or revive the old panel.
                    continue;
                }
                var packets = new List<ReadOnlyMemory<byte>>();
                if (previous?.InstanceId != stamp.InstanceId)
                {
                    packets.Add(PacketBuilder.RepetitionSync(
                        AtlantisClientSceneId, 0, 0, 5, delivery.DailyEntryLimit));
                }
                if (previous?.InstanceId != stamp.InstanceId || previous.Roster != signature)
                {
                    packets.Add(PacketBuilder.RepetitionInstanceMembers(roster));
                }
                // Same native sequence as Medusa's CaptureCompletion. A late
                // observer receives the remaining authoritative delay.
                packets.Add(PacketBuilder.RepetitionFightInfo(remaining, stamp.Points));
                packets.Add(PacketBuilder.RepetitionPanelCompletion());
                packets.Add(PacketBuilder.RepetitionCompletionState(AtlantisClientSceneId, true));
                packets.Add(PacketBuilder.RepetitionCountdown(remaining));
                if (member.Session.TryAdmitExactBatch(packets, out var admitted))
                {
                    _atlantisUi[member.Session] = stamp;
                }
                completion = admitted;
            }
            if (completion is not null)
            {
                try
                {
                    await completion;
                }
                catch (Exception error) when (error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    member.Session.Disconnect();
                }
            }
        }
    }
}
