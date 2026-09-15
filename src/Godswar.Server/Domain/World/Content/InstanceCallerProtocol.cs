namespace Godswar.Server.Domain.World.Content;

internal enum InstanceCallerDifficulty
{
    Advanced = 204,
    Normal = 205,
    Mythic = 207
}

internal enum InstanceCallerEntryKind : byte
{
    Atlantis = 1,
    Wonderland = 2
}

internal enum InstanceCallerEntryPaymentMode : byte
{
    FreeOnly = 1,
    OpalRetry = 2
}

internal sealed record InstanceCallerEntryDestination(
    InstanceCallerEntryKind Kind,
    string DisplayName,
    byte TargetMapId,
    float TargetX,
    float TargetZ,
    int MinimumLevel,
    int MaximumLevel,
    int? RequiredPartySize)
{
    public InstanceCallerEntryPaymentMode PaymentMode { get; init; } =
        InstanceCallerEntryPaymentMode.FreeOnly;
}

/// <summary>
/// Finite stock NpcFunRepetition surface for Medusa Island. The stock client
/// keeps the root choice in the request sub-id and appends the difficulty to
/// the fixed 18-value argument path.
/// </summary>
internal static class InstanceCallerProtocol
{
    public const uint AthensNpcId = 5199;
    public const uint SpartaNpcId = 5057;
    public const int DialogIndex = 9;
    public const int WonderlandResultDialogIndex = 3;
    public const int ActionPacketBytes = 92;
    public const int FunctionArgumentCount = 18;
    public const float MaximumInteractionDistance = 12f;
    public const int InitialRequestSubId = -1;
    public const int MedusaRootSubId = 11;
    public const int AtlantisRootSubId = 14;
    public const int WonderlandRootSubId = 15;
    public const int DescriptionSubId = 206;
    public const int AdvancedDifficultySubId =
        (int)InstanceCallerDifficulty.Advanced;
    public const int NormalDifficultySubId =
        (int)InstanceCallerDifficulty.Normal;
    public const int MythicDifficultySubId =
        (int)InstanceCallerDifficulty.Mythic;
    public const int QueueUnavailableResultSubId = 1000;
    public const int AtlantisDescriptionSubId = 208;
    public const int AtlantisOpalSubId = 209;
    public const int AtlantisEnterSubId = 210;
    public const int WonderlandEnterSubId = 211;
    public const int AtlantisMaximumEntriesResultSubId = 1500;
    public const int AtlantisInvalidOpalResultSubId = 1501;
    public const int AtlantisInsufficientOpalResultSubId = 1502;
    public const int AtlantisEntryPolicyResultSubId = 1600;
    public const int AtlantisOpalConsentRecordedResultSubId = 1601;
    public const int AtlantisOpalConsentMissingResultSubId = 1602;
    public const int AtlantisLevelResultSubId = 1510;
    public const int AtlantisLeaderResultSubId = 1511;
    public const int AtlantisPartyTooSmallResultSubId = 1521;
    public const int AtlantisPartyTooLargeResultSubId = 1800;
    public const int WonderlandWeekendResultSubId = 300;
    public const int WonderlandCutoffResultSubId = 301;

    public static readonly TimeSpan PageContextLifetime =
        TimeSpan.FromMinutes(2);

    public static IReadOnlyList<int> InitialMenuSubIds { get; } =
        Array.AsReadOnly(new[]
        {
            MedusaRootSubId,
            AtlantisRootSubId,
            WonderlandRootSubId
        });

    public static IReadOnlyList<int> MedusaPageSubIds { get; } =
        Array.AsReadOnly(new[]
        {
            DescriptionSubId,
            AdvancedDifficultySubId,
            NormalDifficultySubId,
            MythicDifficultySubId
        });

    public static IReadOnlyList<int> AtlantisPageSubIds { get; } =
        Array.AsReadOnly(new[]
        {
            AtlantisDescriptionSubId,
            AtlantisOpalSubId,
            AtlantisEnterSubId
        });

    public static IReadOnlyList<int> WonderlandPageSubIds { get; } =
        Array.AsReadOnly(new[] { WonderlandEnterSubId });

    public static bool IsEndpoint(string npcKey, uint interactionId) =>
        (npcKey, interactionId) is
            ("Athens_060", AthensNpcId) or
            ("Sparta_060", SpartaNpcId);

    public static bool TryGetMedusaPage(
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out int[] responseSubIds)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        responseSubIds = [];
        if (dialogIndex != DialogIndex ||
            subId != MedusaRootSubId ||
            !HasExactPath(arguments))
        {
            return false;
        }

        responseSubIds = MedusaPageSubIds.ToArray();
        return true;
    }

    public static bool TryGetPage(
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out int rootSubId,
        out int[] responseSubIds)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        rootSubId = 0;
        responseSubIds = [];
        if (dialogIndex != DialogIndex || !HasExactPath(arguments))
        {
            return false;
        }

        (rootSubId, IReadOnlyList<int>? page) = subId switch
        {
            MedusaRootSubId => (MedusaRootSubId, MedusaPageSubIds),
            AtlantisRootSubId => (AtlantisRootSubId, AtlantisPageSubIds),
            WonderlandRootSubId =>
                (WonderlandRootSubId, WonderlandPageSubIds),
            _ => default
        };
        if (page is null)
        {
            return false;
        }

        responseSubIds = page.ToArray();
        return true;
    }

    public static bool TryResolveEntry(
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out InstanceCallerEntryDestination destination)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        destination = null!;
        if (dialogIndex != DialogIndex)
        {
            return false;
        }

        destination = subId switch
        {
            AtlantisRootSubId when HasExactPath(
                arguments,
                AtlantisOpalSubId) =>
                AtlantisDestination with
                {
                    PaymentMode =
                        InstanceCallerEntryPaymentMode.OpalRetry
                },
            AtlantisRootSubId when HasExactPath(
                arguments,
                AtlantisEnterSubId) =>
                AtlantisDestination,
            WonderlandRootSubId when HasExactPath(
                arguments,
                WonderlandEnterSubId) =>
                new InstanceCallerEntryDestination(
                    InstanceCallerEntryKind.Wonderland,
                    "Wonderland",
                    TargetMapId: 207,
                    TargetX: 120f,
                    TargetZ: 209f,
                    MinimumLevel: 120,
                    MaximumLevel: int.MaxValue,
                    RequiredPartySize: null),
            _ => null!
        };
        return destination is not null;
    }

    private static InstanceCallerEntryDestination AtlantisDestination =>
        new(
            InstanceCallerEntryKind.Atlantis,
            "Atlantis",
            TargetMapId: 205,
            TargetX: 171f,
            TargetZ: 24f,
            MinimumLevel: 90,
            MaximumLevel: int.MaxValue,
            RequiredPartySize: null);

    public static bool TryResolveDifficulty(
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out InstanceCallerDifficulty difficulty)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        difficulty = default;
        if (dialogIndex != DialogIndex ||
            subId != MedusaRootSubId ||
            arguments.Count != FunctionArgumentCount)
        {
            return false;
        }

        difficulty = arguments[0] switch
        {
            AdvancedDifficultySubId => InstanceCallerDifficulty.Advanced,
            NormalDifficultySubId => InstanceCallerDifficulty.Normal,
            MythicDifficultySubId => InstanceCallerDifficulty.Mythic,
            _ => default
        };
        return difficulty != default &&
            HasExactPath(arguments, (int)difficulty);
    }

    private static bool HasExactPath(
        IReadOnlyList<int> arguments,
        params int[] path)
    {
        if (arguments.Count != FunctionArgumentCount ||
            path.Length > arguments.Count)
        {
            return false;
        }

        for (var index = 0; index < arguments.Count; index++)
        {
            var expected = index < path.Length ? path[index] : -1;
            if (arguments[index] != expected)
            {
                return false;
            }
        }

        return true;
    }
}
