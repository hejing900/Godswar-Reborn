using Godswar.Server.State;

namespace Godswar.Server.Game;

internal static class FactionPortalSkillPolicy
{
    public const uint AthensCapitalPortalSkillId = 3060;

    public const uint AthensSuburbPortalSkillId = 3061;

    public const uint SpartaCapitalPortalSkillId = 3062;

    public const uint SpartaSuburbPortalSkillId = 3063;

    public static uint ResolveCapitalPortalSkillId(byte camp) =>
        camp switch
        {
            GameDefaults.SpartaCamp => SpartaCapitalPortalSkillId,
            GameDefaults.AthensCamp => AthensCapitalPortalSkillId,
            _ => throw new ArgumentOutOfRangeException(
                nameof(camp),
                camp,
                "Faction portal skills require a recognized camp.")
        };

    public static uint ResolveSuburbPortalSkillId(byte camp) =>
        camp switch
        {
            GameDefaults.SpartaCamp => SpartaSuburbPortalSkillId,
            GameDefaults.AthensCamp => AthensSuburbPortalSkillId,
            _ => throw new ArgumentOutOfRangeException(
                nameof(camp),
                camp,
                "Faction portal skills require a recognized camp.")
        };
}
