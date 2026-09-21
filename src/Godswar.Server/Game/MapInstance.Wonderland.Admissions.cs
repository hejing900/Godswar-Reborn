using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Game.WorldInstances;

namespace Godswar.Server.Game;

internal sealed partial class MapInstance
{
    /// <summary>Fix actual successful entrants before publication, retaining the leader's faction and clock.</summary>
    internal bool TryFinalizeWonderlandAdmissions(IReadOnlyCollection<int> actualEntrants)
    {
        ArgumentNullException.ThrowIfNull(actualEntrants);
        var ids = actualEntrants.Order().ToArray();
        if (ids.Length is < 1 or > 5 || ids.Distinct().Count() != ids.Length) return false;
        lock (_wonderlandGate)
        lock (_monsterRuntimeGate)
        {
            if (_wonderlandFinalizedIds is not null) return _wonderlandFinalizedIds.SequenceEqual(ids);
            if (_wonderlandRun is null || _wonderlandMonsters is null || _wonderlandMonsters.Count != 0) return false;
            var pending = _wonderlandRun.Snapshot();
            if (pending.State != WonderlandRunState.Active || pending.CurrentIsland != 1 || !pending.PublicationPending ||
                ids.Any(id => !pending.Participants.Any(p => p.CharacterId == id))) return false;
            var entrants = pending.Participants.Where(p => ids.Contains(p.CharacterId)).ToArray();
            var run = new WonderlandRunRuntime(Descriptor, entrants, pending.StartedAt, pending.PartyCamp);
            _ = run.Advance(pending.LastObservedAt);
            var policies = Enumerable.Range(1, 8).Select(island =>
                WonderlandMonsterPlan.Create(island, entrants.Length, pending.PartyCamp)).ToArray();
            var definitions = PrepareWonderlandDefinitions(_wonderlandContent!, policies);
            var monsters = new WonderlandMonsterRuntime(Descriptor.InstanceId, pending.Deadline, ids,
                policies.Sum(stage => stage.Length));
            // No actor exists yet. Only HP and the participant whitelist change;
            // fixed combat ratings/ranges and their existing profile pin are identical.
            _wonderlandRun = run;
            _wonderlandDefinitions = definitions;
            _wonderlandPolicies = policies.SelectMany(stage => stage).ToDictionary(p => p.ObjectId);
            _wonderlandMonsters = monsters;
            _monsterRuntime = monsters;
            _wonderlandFinalizedIds = ids;
            return true;
        }
    }
}
