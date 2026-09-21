using Godswar.Server.Application.Commands;
using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Networking;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    private IWonderlandChestClaimStore? _wonderlandChests;

    internal void ConfigureWonderlandChests(IWonderlandChestClaimStore? store)
    {
        if (store is null) return;
        var previous = Interlocked.CompareExchange(ref _wonderlandChests, store, null);
        if (previous is not null && !ReferenceEquals(previous, store))
            throw new InvalidOperationException("Wonderland chest persistence is already configured.");
    }

    internal IReadOnlyList<NpcSpawnDefinition> AddWonderlandTreasureChests(ClientSession session,
        IReadOnlyList<NpcSpawnDefinition> existing)
    {
        lock (_gate)
            return _sessions.TryGetValue(session, out var actor) &&
                TryGetWonderlandEncounterSnapshot(actor.WorldInstanceId, out var run)
                ? WonderlandTreasureChestPolicy.AddChests(existing, run.PartyCamp) : existing;
    }

    internal async Task<WonderlandChestClaimReceipt> ClaimWonderlandChestAsync(ClientSession session,
        NpcSpawnDefinition npc, DateTimeOffset now, CancellationToken cancellationToken)
    {
        var store = _wonderlandChests;
        if (store is null) return new(WonderlandChestClaimStatus.Unavailable, 0, []);
        WonderlandChestClaimRequest request;
        lock (_gate)
        {
            if (!WonderlandTreasureChestPolicy.TryGetIsland(npc, out var island) ||
                !_sessions.TryGetValue(session, out var actor) || actor.Character.CurrentHp <= 0 ||
                !IsCurrentWonderlandMember(actor, actor.WorldInstanceId) ||
                !_wonderlandAdmissions.TryGetValue(actor.WorldInstanceId, out var admission) ||
                !admission.Sealed || !admission.Entrants.Contains(actor.CharacterId) ||
                !TryGetWonderlandEncounterSnapshot(actor.WorldInstanceId, out var run) ||
                !WonderlandTreasureChestPolicy.IsUnlocked(run, island, now))
                return new(WonderlandChestClaimStatus.NotEligible, 0, []);
            var dx = (double)actor.Character.PositionX - npc.X;
            var dz = (double)actor.Character.PositionZ - npc.Z;
            if (!double.IsFinite(dx) || !double.IsFinite(dz) ||
                dx * dx + dz * dz > WonderlandTreasureChestPolicy.InteractionRadius * WonderlandTreasureChestPolicy.InteractionRadius)
                return new(WonderlandChestClaimStatus.NotEligible, 0, []);
            if (!_wonderlandTitleSettled.TryGetValue((actor.WorldInstanceId, island), out var hash))
                return new(WonderlandChestClaimStatus.Unavailable, 0, []);
            request = new(actor.WorldInstanceId, actor.RealmId, island, run.PartyCamp, hash,
                new CommandSubject(actor.AccountId, actor.CharacterId), actor.Ownership);
        }
        return await store.ClaimAsync(request, cancellationToken);
    }
}
