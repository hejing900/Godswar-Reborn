using Godswar.Server.State;

namespace Godswar.Server.Game;

internal static class FlameBlastPulsePolicy
{
    // External rank V: seven overlapping fields against a surviving tower
    // produced five hits each, at completion and +4/+8/+12/+16 seconds.
    // Earlier ranks share this family policy; their timing is not captured.
    public const int TotalPulses = 5;
    public static readonly TimeSpan Interval = TimeSpan.FromSeconds(4);

    public static bool AppliesTo(in SkillCombatDefinition combat) =>
        combat.SkillId is >= 570 and <= 574 &&
        SkillCombatResolver.IsHostileMonsterGroundAreaSkill(combat);
}
