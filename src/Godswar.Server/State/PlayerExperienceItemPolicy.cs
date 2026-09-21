namespace Godswar.Server.State;

internal static class PlayerExperienceItemPolicy
{
    internal const uint ItemId = 4174;
    internal const int ExperiencePerPill = 1_000_000;

    internal static bool TryApply(int level, long experience, bool sealedLevel,
        out PlayerExperienceProgression progression)
    {
        progression = default!;
        if (level is < 1 or > PlayerExperienceCatalog.MaximumLevel ||
            experience < 0 || experience > PlayerExperienceCatalog.MaximumStoredExperience ||
            (!sealedLevel && level == PlayerExperienceCatalog.MaximumLevel) ||
            (sealedLevel && experience > PlayerExperienceCatalog.MaximumStoredExperience - ExperiencePerPill))
            return false;

        progression = PlayerExperienceCatalog.Apply(level, experience, ExperiencePerPill, sealedLevel);
        return progression.ExperienceGained == ExperiencePerPill;
    }
}
