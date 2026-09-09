using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private async Task PublishAtlantisRunDeliveryAsync(
        AtlantisRunDelivery delivery,
        CancellationToken cancellationToken)
    {
        if (delivery.Run.State == AtlantisRunState.Completed)
        {
            var settled = await SettleAtlantisCompletionRewardsAsync(delivery, cancellationToken);
            await PublishAtlantisCompletionAsync(delivery, settled, cancellationToken);
            if (settled)
            {
                await RetireFinishedEmptyAtlantisRunAsync(delivery, cancellationToken);
            }
            return;
        }
        if (delivery.Run.State == AtlantisRunState.Cancelled)
        {
            await PublishAtlantisTerminationEgressAsync(delivery, cancellationToken);
            await RetireFinishedEmptyAtlantisRunAsync(delivery, cancellationToken);
            return;
        }
        var remaining = checked((int)Math.Clamp(Math.Ceiling(
            (delivery.Run.Deadline - delivery.Run.LastObservedAt).TotalSeconds),
            0, AtlantisEncounterPolicy.TimeLimit.TotalSeconds));
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
                if (_atlantisTerminationExitRequested.ContainsKey(delivery.Runtime.InstanceId) ||
                    !IsCurrentAtlantisMember(delivery, member))
                {
                    continue;
                }
                _atlantisUi.TryGetValue(member.Session, out var previous);
                if (previous == stamp || previous is not null &&
                    previous.InstanceId == stamp.InstanceId &&
                    (previous.Points > stamp.Points ||
                     previous.RemainingSeconds < stamp.RemainingSeconds ||
                     previous.State != AtlantisRunState.Active && stamp.State == AtlantisRunState.Active))
                {
                    continue;
                }
                var packets = new List<ReadOnlyMemory<byte>>();
                if (previous?.InstanceId != stamp.InstanceId)
                {
                    packets.Add(PacketBuilder.RepetitionSync(
                        AtlantisClientSceneId, 0, 0, 5, delivery.DailyEntryLimit));
                }
                if (previous?.Roster != signature || previous?.InstanceId != stamp.InstanceId)
                {
                    packets.Add(PacketBuilder.RepetitionInstanceMembers(roster));
                }
                packets.Add(PacketBuilder.RepetitionFightInfo(remaining, stamp.Points));
                if (stamp.State != AtlantisRunState.Active)
                {
                    if (stamp.State == AtlantisRunState.Completed)
                    {
                        packets.Add(PacketBuilder.RepetitionPanelCompletion());
                    }
                    packets.Add(PacketBuilder.RepetitionCompletionState(
                        AtlantisClientSceneId, stamp.State == AtlantisRunState.Completed));
                }
                // Admission and exact membership validation share the registry
                // fence. Physical writes complete after that fence is released.
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
        await PublishAtlantisTerminationEgressAsync(delivery, cancellationToken);
        await RetireFinishedEmptyAtlantisRunAsync(delivery, cancellationToken);
    }

    private bool IsCurrentAtlantisMember(AtlantisRunDelivery delivery, AtlantisRunMember member) =>
        _sessions.TryGetValue(member.Session, out var current) && current.WorldReady &&
        !member.Session.IsDisconnected && current.AccountId == member.AccountId &&
        current.CharacterId == member.CharacterId && current.Ownership == member.Ownership &&
        current.WorldInstanceId == delivery.Runtime.InstanceId &&
        current.MapId == DynamicDungeonContentMapPolicy.AtlantisPortalMapId &&
        current.Character.CurrentMap == current.MapId &&
        IsCurrentAccountSession(member.AccountId, member.Session, member.Ownership);
}
