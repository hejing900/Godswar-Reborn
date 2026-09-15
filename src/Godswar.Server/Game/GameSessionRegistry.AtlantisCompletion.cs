using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private static readonly TimeSpan AtlantisCompletionExitDelay = TimeSpan.FromSeconds(30);

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
