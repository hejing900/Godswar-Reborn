namespace Godswar.Server.Game;

/// <summary>Immutable movement boundaries scoped to one monster runtime.</summary>
internal sealed class MonsterBehaviorPolicy
{
    public static MonsterBehaviorPolicy Default { get; } = new(
        MonsterAggroPolicy.DetectionRadius,
        MonsterMapRuntime.CombatLeashRadius,
        MonsterMapRuntime.MaximumRoamRadius);

    public MonsterBehaviorPolicy(
        float aggroDetectionRadius,
        float combatLeashRadius,
        float maximumRoamRadius)
    {
        ValidateRadius(aggroDetectionRadius, nameof(aggroDetectionRadius));
        ValidateRadius(combatLeashRadius, nameof(combatLeashRadius));
        ValidateRadius(maximumRoamRadius, nameof(maximumRoamRadius));
        if (maximumRoamRadius < MonsterMapRuntime.MovementStep)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumRoamRadius));
        }
        if (combatLeashRadius < aggroDetectionRadius + maximumRoamRadius)
        {
            throw new ArgumentOutOfRangeException(nameof(combatLeashRadius),
                "The leash must contain targets acquired at the idle roam boundary.");
        }
        AggroDetectionRadius = aggroDetectionRadius;
        CombatLeashRadius = combatLeashRadius;
        MaximumRoamRadius = maximumRoamRadius;
    }

    public float AggroDetectionRadius { get; }
    public float CombatLeashRadius { get; }
    public float MaximumRoamRadius { get; }

    private static void ValidateRadius(float radius, string parameter)
    {
        if (radius <= 0f || !float.IsFinite(radius * radius))
        {
            throw new ArgumentOutOfRangeException(parameter);
        }
    }
}
