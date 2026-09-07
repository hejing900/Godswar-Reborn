using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Networking;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    // All work within this scope is synchronous. Acquire delivery ordering
    // first, then registry serialization, and revalidate the captured route.
    private MembershipMutation AcquireMembershipMutation(
        ClientSession session,
        WorldInstanceId? targetInstance = null,
        byte? targetMap = null)
    {
        while (true)
        {
            _sessions.TryGetValue(session, out var expected);
            MapInstance.PlayerRemovalLease? removal = null;
            var removesSource = expected is not null &&
                (targetInstance is { } instance
                    ? expected.WorldInstanceId != instance
                    : targetMap is { } map ? expected.MapId != map : true);
            if (removesSource && TryGetWorldInstance(expected!, out var runtime))
            {
                if (Monitor.IsEntered(_gate))
                {
                    throw new InvalidOperationException(
                        "Prepare membership removal before entering registry serialization.");
                }
                removal = runtime.Map.AcquirePlayerRemoval(session);
            }

            Monitor.Enter(_gate);
            _sessions.TryGetValue(session, out var current);
            if (ReferenceEquals(current, expected))
            {
                return new MembershipMutation(_gate, removal);
            }
            Monitor.Exit(_gate);
            removal?.Dispose();
        }
    }

    private sealed class MembershipMutation(
        object registryGate,
        MapInstance.PlayerRemovalLease? removal) : IDisposable
    {
        public MapInstance.PlayerRemovalLease? Removal { get; } = removal;

        public void Dispose()
        {
            Monitor.Exit(registryGate);
            Removal?.Dispose();
        }
    }
}
