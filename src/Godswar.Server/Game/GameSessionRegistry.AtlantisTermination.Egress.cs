using Godswar.Server.Game.WorldInstances;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private async Task PublishAtlantisTerminationEgressAsync(
        AtlantisRunDelivery delivery, CancellationToken cancellationToken)
    {
        var instanceId = delivery.Runtime.InstanceId;
        // A completion exit must pass durable reward settlement, including a
        // leader's manual Finish/Leave request during the completion countdown.
        if (delivery.Run.State is AtlantisRunState.Active or AtlantisRunState.Completed ||
            !_atlantisTerminationExitRequested.ContainsKey(instanceId) ||
            !_atlantisTerminationEgressInFlight.TryAdd(instanceId, 0))
        {
            return;
        }
        try
        {
            foreach (var member in delivery.Members)
            {
                lock (_gate)
                {
                    if (!IsCurrentAtlantisMember(delivery, member))
                    {
                        continue;
                    }
                }
                var targetMap = member.Camp == GameDefaults.SpartaCamp
                    ? GameDefaults.SpartaCapitalMap : GameDefaults.AthensCapitalMap;
                try
                {
                    var target = GetOrCreateDefaultWorldInstance(targetMap);
                    var command = new AuthoritativeInstanceTransitionCommand(member.CharacterId,
                        instanceId, 205, member.Ownership, target.InstanceId, targetMap,
                        GameDefaults.StartingPositionX, GameDefaults.StartingPositionZ);
                    if (!await TransitionPartyMemberToAuthoritativeInstanceAsync(
                            member.Session, command, cancellationToken))
                    {
                        Console.WriteLine($"[atlantis] termination exit deferred character={member.CharacterId}");
                    }
                }
                catch (Exception error) when (error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    Console.WriteLine($"[atlantis] termination exit failed character={member.CharacterId} " +
                        $"reason={error.GetType().Name}");
                }
            }
            // Keep the request until retirement: a member who is still loading
            // or whose fenced transfer failed must exit on a later world tick.
        }
        finally
        {
            _atlantisTerminationEgressInFlight.TryRemove(instanceId, out _);
        }
    }
}
