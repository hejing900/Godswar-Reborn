using System.Collections.Frozen;

namespace Godswar.Server.Game;

internal static class MonsterAggroPolicy
{
    public const uint MinimumAggressiveTier = 30;
    public const float DetectionRadius = 14f;

    /// <summary>
    /// Monsters the reference leaves alone until they are hit.
    /// </summary>
    /// <remarks>
    /// Athens city spawns the Spartan spy family (level 141: "Spartan Spy Master",
    /// "Spartan Spy", "Spartan Spy Captain") inside a level 1..20 city. The
    /// reference never lets them engage on their own - a passer-by is not chased -
    /// and what they hit back with is trivial, so the level check alone cannot
    /// describe them. They stay listed here until a capture shows a spy engaging
    /// first.
    /// </remarks>
    private static readonly FrozenSet<string> PassiveTemplates =
        new[]
        {
            "A_normals_greecewarrior_001",
            "A_normalsA_greecewarrior_001",
            "A_normals_greecewarrior_003",
            "A_normals_greecewarrior_008"
        }.ToFrozenSet(StringComparer.Ordinal);

    public static bool IsPassiveTemplate(string? templateKey) =>
        templateKey is not null && PassiveTemplates.Contains(templateKey);

    public static bool IsAggressive(uint tier, string? templateKey) =>
        !IsPassiveTemplate(templateKey) &&
        tier >= MinimumAggressiveTier;

    public static bool IsAggressive(uint tier) =>
        tier >= MinimumAggressiveTier;

    public static Dictionary<int, ulong> RecordDamage(
        IReadOnlyDictionary<int, ulong>? currentThreat,
        int attackerCharacterId,
        uint actualDamage,
        int? currentTargetCharacterId,
        out int leaderCharacterId)
    {
        if (attackerCharacterId <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(attackerCharacterId));
        }
        if (actualDamage == 0)
        {
            throw new ArgumentOutOfRangeException(nameof(actualDamage));
        }

        var nextThreat = currentThreat is null
            ? new Dictionary<int, ulong>()
            : new Dictionary<int, ulong>(currentThreat);
        nextThreat.TryGetValue(attackerCharacterId, out var priorDamage);
        nextThreat[attackerCharacterId] =
            ulong.MaxValue - priorDamage < actualDamage
                ? ulong.MaxValue
                : priorDamage + actualDamage;
        leaderCharacterId = SelectLeader(
                nextThreat,
                currentTargetCharacterId) ??
            throw new InvalidOperationException(
                "Recorded monster damage has no threat leader.");
        return nextThreat;
    }

    public static int? SelectLeader(
        IReadOnlyDictionary<int, ulong>? threat,
        int? currentTargetCharacterId)
    {
        if (threat is null || threat.Count == 0)
        {
            return null;
        }

        var maximum = 0UL;
        foreach (var pair in threat)
        {
            if (pair.Key > 0 && pair.Value > maximum)
            {
                maximum = pair.Value;
            }
        }
        if (maximum == 0)
        {
            return null;
        }

        if (currentTargetCharacterId is > 0 &&
            threat.TryGetValue(
                currentTargetCharacterId.Value,
                out var currentDamage) &&
            currentDamage == maximum)
        {
            return currentTargetCharacterId;
        }

        int? leader = null;
        foreach (var pair in threat)
        {
            if (pair.Key > 0 &&
                pair.Value == maximum &&
                (!leader.HasValue || pair.Key < leader.Value))
            {
                leader = pair.Key;
            }
        }
        return leader;
    }

    public static bool TrySelectNearestAggressiveTarget(
        IReadOnlyDictionary<int, MonsterCombatTarget> targets,
        float monsterX,
        float monsterZ,
        out MonsterCombatTarget selected,
        float detectionRadius = DetectionRadius)
    {
        ArgumentNullException.ThrowIfNull(targets);
        selected = default;
        var maximumDistanceSquared = detectionRadius * detectionRadius;
        var selectedDistanceSquared = double.MaxValue;
        var found = false;
        foreach (var target in targets.Values)
        {
            if (target.CharacterId <= 0 || !target.IsAlive)
            {
                continue;
            }

            var distanceSquared = DistanceSquared(
                monsterX,
                monsterZ,
                target.X,
                target.Z);
            if (distanceSquared > maximumDistanceSquared ||
                found &&
                (distanceSquared > selectedDistanceSquared ||
                 distanceSquared == selectedDistanceSquared &&
                 target.CharacterId >= selected.CharacterId))
            {
                continue;
            }

            selected = target;
            selectedDistanceSquared = distanceSquared;
            found = true;
        }
        return found;
    }

    private static double DistanceSquared(
        float x1,
        float z1,
        float x2,
        float z2)
    {
        var deltaX = (double)x2 - x1;
        var deltaZ = (double)z2 - z1;
        return (deltaX * deltaX) + (deltaZ * deltaZ);
    }
}
