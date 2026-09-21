using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Game.WorldInstances;

namespace Godswar.Server.Game;

internal sealed partial class GameSessionRegistry
{
    // Handler timestamps precede admission to this gate. A world tick may
    // already have advanced the same run while that handler waited.
    private bool TryResolveWonderlandDamageTimeLocked(WorldInstanceRuntime runtime, uint objectId,
        ref DateTimeOffset committedAt)
    {
        if (runtime.MapId != 207) return true;
        if (!runtime.Map.TryGetWonderlandSnapshot(out var run) ||
            committedAt < run.StartedAt || !runtime.Map.TryGetWonderlandSpawnPolicy(objectId, out var policy) ||
            !IsWonderlandPublishedStage(run, policy.Stage)) return false;
        if (committedAt < run.LastObservedAt) committedAt = run.LastObservedAt;
        if (_wonderlandCombat.TryGetValue(runtime.InstanceId, out var state) && committedAt < state.LastAdvancedAt)
            committedAt = state.LastAdvancedAt;
        return WonderlandCompletionPolicy.IsCombatWindowOpen(run, committedAt);
    }

    private bool TryApplyWonderlandMonsterDamage(WorldInstanceRuntime runtime, uint objectId, uint damage,
        int? attackerCharacterId, uint? expectedGeneration, ulong? expectedHealthRevision,
        DateTimeOffset now, out MonsterDamageResult result)
    {
        lock (_gate)
        {
            if (!TryResolveWonderlandDamageTimeLocked(runtime, objectId, ref now) ||
                attackerCharacterId.HasValue && !IsWonderlandPlayerDamageAllowed(runtime, objectId))
            {
                result = null!;
                return false;
            }
            var attempt = InvokeWorldOwnerAuthoritativeMutation(runtime, map =>
            {
                MonsterDamageResult value = null!;
                var applied = map.TryGetMonsterSnapshot(objectId, out var current) &&
                    (!expectedGeneration.HasValue || current.SpawnGeneration == expectedGeneration) &&
                    (!expectedHealthRevision.HasValue || current.HealthRevision == expectedHealthRevision) &&
                    map.TryApplyMonsterDamage(objectId, damage, attackerCharacterId, expectedGeneration, now, out value);
                return (Applied: applied, Value: value);
            });
            result = attempt.Value;
            if (attempt.Applied) ObserveWonderlandMonsterDamageCommitted(runtime, result, now);
            return attempt.Applied;
        }
    }

    private bool IsWonderlandPlayerDamageAllowed(WorldInstanceRuntime runtime, uint objectId)
    {
        return runtime.MapId != 207 || !runtime.Map.TryGetWonderlandSpawnPolicy(objectId, out var policy) ||
            !policy.IsAllied;
    }

    private void ObserveWonderlandMonsterDamageCommitted(WorldInstanceRuntime runtime,
        MonsterDamageResult damage, DateTimeOffset now, GameSessionContext? directAttacker = null)
    {
        if (runtime.MapId != 207 || damage.HealthMutation is not { } mutation) return;
        lock (_gate)
        {
            if (!TryResolveWonderlandDamageTimeLocked(runtime, damage.ObjectId, ref now) ||
                !TryGetWonderlandCombatLocked(runtime, now, out var run, out var state, allowCompleted: true) ||
                !runtime.Map.TryGetWonderlandSpawnPolicy(damage.ObjectId, out var policy) ||
                !IsWonderlandPublishedStage(run, policy.Stage) ||
                !runtime.Map.TryGetMonsterSnapshot(damage.ObjectId, out var current) ||
                current.RuntimeInstanceId != damage.Monster.RuntimeInstanceId ||
                current.SpawnGeneration != damage.Monster.SpawnGeneration ||
                current.HealthRevision != mutation.AfterHealthRevision || current.CurrentHealth != damage.AfterHealth)
                return;
            var identity = (current.RuntimeInstanceId, current.ObjectId, current.SpawnGeneration);
            if (state.DamageRevisions.TryGetValue(identity, out var last) && last >= mutation.AfterHealthRevision) return;
            state.DamageRevisions[identity] = mutation.AfterHealthRevision;
            if (directAttacker is not null && policy.MechanicKey == "rock" &&
                WonderlandBossAbilityPolicy.ReflectionDamage(damage.BeforeHealth, damage.AfterHealth) is > 0 and var reflected &&
                _playerLifeRevisions.TryGetValue(directAttacker.Session, out var life) &&
                IsCurrentWonderlandPlayerLocked(directAttacker, life))
            {
                CommitWonderlandReflectionLocked(runtime, state, directAttacker, life, current, reflected, now);
            }
            if (damage.Killed && policy.MechanicKey == "atlas")
            {
                state.DeathBlasts.Enqueue(new(current, policy, WonderlandBossAbilityPolicy.AtlasDeathBlast,
                    current.X, current.Z, current.X, current.Z, null, now.AddSeconds(1.5), DeathBlast: true));
                // Warning admission precedes any completion transition or reward I/O.
                foreach (var viewer in _sessions.Values.Where(viewer => viewer.WorldReady &&
                             viewer.WorldInstanceId == runtime.InstanceId))
                    AdmitWonderlandWarningLocked(runtime, state, viewer, current, WonderlandBossAbilityPolicy.AtlasDeathBlast,
                        current.X, current.Z, announceBossCast: false);
            }
            if (damage.Killed) RecordWonderlandMonsterKillCommitted(runtime, damage, now);
        }
    }
}
