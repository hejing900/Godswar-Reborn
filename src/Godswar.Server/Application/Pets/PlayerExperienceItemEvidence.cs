using Godswar.Server.State;

namespace Godswar.Server.Application.Pets;

internal sealed record PlayerExperienceItemEvidence(
    long ItemInstanceId, int KitBagSlot, uint ItemTemplateId, int ExperienceGranted,
    int PreviousLevel, long PreviousExperience, bool FighterLevelSealed,
    int NewLevel, long NewExperience, long PreviousProgressionRevision, long NewProgressionRevision)
{
    public bool IsValid => ItemInstanceId > 0 && KitBagSlot is >= 0 and < 96 &&
        ItemTemplateId == PlayerExperienceItemPolicy.ItemId &&
        ExperienceGranted == PlayerExperienceItemPolicy.ExperiencePerPill &&
        PreviousProgressionRevision is >= 0 and < long.MaxValue &&
        NewProgressionRevision == PreviousProgressionRevision + 1 &&
        PlayerExperienceItemPolicy.TryApply(PreviousLevel, PreviousExperience, FighterLevelSealed, out var result) &&
        result.Level == NewLevel && result.Experience == NewExperience;
}
