using System.Collections.Concurrent;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Networking;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private readonly ConcurrentDictionary<WorldInstanceId, byte> _atlantisDepartures = [];

    // Called at the end of the membership fence, after commit or rollback.
    // A transiently empty source during transfer is never an abandoned run.
    private Task? RecordCommittedAtlantisDepartureLocked(GameSessionContext? previous)
    {
        if (previous is null || previous.MapId != DynamicDungeonContentMapPolicy.AtlantisPortalMapId)
        {
            return null;
        }
        _sessions.TryGetValue(previous.Session, out var current);
        if (current?.WorldInstanceId == previous.WorldInstanceId)
        {
            return null;
        }

        _atlantisDepartures.TryAdd(previous.WorldInstanceId, 0);
        if (_atlantisUi.TryGetValue(previous.Session, out var stamp) &&
            stamp.InstanceId == previous.WorldInstanceId)
        {
            _atlantisUi.TryRemove(new KeyValuePair<ClientSession, AtlantisUiStamp>(previous.Session, stamp));
        }
        // A player may leave before the first UI tick, or after retirement
        // has dropped the cache. Teardown must not depend on that cache.
        if (current is null || previous.Session.IsDisconnected)
        {
            return null;
        }

        // Enqueue under the same fence as membership publication, so stale
        // world deliveries cannot reopen this panel after its clear packet.
        previous.Session.TryAdmitExactBatch(AtlantisDeparturePackets(), out var completion);
        return completion;
    }

    private static IReadOnlyList<ReadOnlyMemory<byte>> AtlantisDeparturePackets() =>
        // Native 10231 with zero hides RepQueUI and clears repetition state.
        // A state-zero 10232 sync instead creates another pending icon.
        [PacketBuilder.RepetitionReset()];

    private static async Task ObserveAtlantisDepartureWriteAsync(ClientSession session, Task completion)
    {
        try
        {
            await completion;
        }
        catch
        {
            session.Disconnect();
        }
    }

    private void CancelAbandonedAtlantisRuns(DateTimeOffset now)
    {
        foreach (var instanceId in _atlantisDepartures.Keys)
        {
            lock (_gate)
            {
                if (!_atlantisDepartures.ContainsKey(instanceId))
                {
                    continue;
                }
                if (!WorldInstances.TryFind(instanceId, out var runtime) ||
                    runtime.Descriptor.LifecycleState != WorldInstanceLifecycleState.Active ||
                    _sessions.Values.Any(context => context.WorldInstanceId == instanceId))
                {
                    _atlantisDepartures.TryRemove(instanceId, out _);
                    continue;
                }
                // Transfer admission and membership mutation use this same
                // registry -> owner ordering. Hidden admitted players count.
                if (InvokeWorldOwnerAuthoritativeMutation(runtime, map =>
                    map.Population == 0 && map.TryCancelAtlantisEncounter(now, out _)))
                {
                    _pendingAtlantisRetirements.TryAdd(instanceId, 0);
                    Console.WriteLine($"[atlantis] closing empty run after last departure instance={instanceId}");
                }
                _atlantisDepartures.TryRemove(instanceId, out _);
            }
        }
    }
}
