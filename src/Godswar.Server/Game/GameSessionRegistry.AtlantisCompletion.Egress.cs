using System.Collections.Concurrent;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private readonly ConcurrentDictionary<WorldInstanceId, byte> _atlantisCompletionEgressInFlight = [];
    private readonly ConcurrentDictionary<WorldInstanceId, DateTimeOffset> _atlantisCompletionEgressLastLogAt = [];

    private void ForgetAtlantisCompletion(WorldInstanceId instanceId)
    {
        _atlantisCompletionEgressInFlight.TryRemove(instanceId, out _);
        _atlantisCompletionEgressLastLogAt.TryRemove(instanceId, out _);
    }

    private async Task PublishAtlantisCompletionEgressAsync(
        AtlantisRunDelivery delivery, CancellationToken cancellationToken)
    {
        var instanceId = delivery.Runtime.InstanceId;
        if (delivery.Run.State != AtlantisRunState.Completed || delivery.Run.TerminalAt is not { } completedAt ||
            delivery.ObservedAt - completedAt < AtlantisCompletionExitDelay &&
                !_atlantisTerminationExitRequested.ContainsKey(instanceId) ||
            !_atlantisCompletionEgressInFlight.TryAdd(instanceId, 0))
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
                        LogAtlantisCompletionEgressDeferred(delivery, member.CharacterId, "transfer rejected");
                    }
                    // Committed membership departure already clears native
                    // repetition state. A failed transfer retains membership
                    // and is retried from the next world delivery.
                }
                catch (Exception error) when (error is not OperationCanceledException ||
                    !cancellationToken.IsCancellationRequested)
                {
                    LogAtlantisCompletionEgressDeferred(delivery, member.CharacterId, error.GetType().Name);
                }
            }
        }
        finally
        {
            _atlantisCompletionEgressInFlight.TryRemove(instanceId, out _);
        }
    }

    private void LogAtlantisCompletionEgressDeferred(
        AtlantisRunDelivery delivery, int characterId, string reason)
    {
        var id = delivery.Runtime.InstanceId;
        var now = delivery.ObservedAt;
        if (_atlantisCompletionEgressLastLogAt.TryAdd(id, now) ||
            _atlantisCompletionEgressLastLogAt.TryGetValue(id, out var last) &&
            now - last >= TimeSpan.FromSeconds(30) &&
            _atlantisCompletionEgressLastLogAt.TryUpdate(id, now, last))
        {
            Console.WriteLine($"[atlantis] completion exit deferred instance={id} " +
                $"character={characterId} reason={reason}");
        }
    }
}
