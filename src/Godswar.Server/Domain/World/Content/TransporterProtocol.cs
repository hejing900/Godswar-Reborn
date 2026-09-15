namespace Godswar.Server.Domain.World.Content;

internal sealed record TransporterDestination(
    string NpcKey,
    uint InteractionId,
    short SourceMapId,
    int SubId,
    short TargetMapId,
    short ArrivalAnchorSourceMapId,
    int MinimumLevel,
    int LevelRequirementResultSubId,
    string DisplayName);

/// <summary>
/// Finite server-authored contract for the ordinary world Transporters that
/// are present in the reviewed NPC publication. Menu identifiers and level
/// failure identifiers are native NpcFunTranmit values; destination maps use
/// the reviewed world topology.
/// </summary>
internal static class TransporterProtocol
{
    public const uint SpartaNpcId = 5039;
    public const uint AthensNpcId = 5180;
    public const uint MycenaeNpcId = 59721;
    public const int DialogIndex = 1;
    public const int ResultDialogIndex = 2;
    public const int InitialRequestSubId = -1;
    public const int ActionPacketBytes = 92;
    public const int FunctionArgumentCount = 18;
    public const int AthensLevelRequirementResultSubId = 1000;
    public const int SpartaLevelRequirementResultSubId = 1001;
    public const int GenericLevelRequirementResultSubId = 2001;
    public const float MaximumInteractionDistance = 12f;

    public static readonly TimeSpan MenuContextLifetime =
        TimeSpan.FromMinutes(2);

    private static readonly int[] SpartaMenuValues =
        [1, 3, 2, 8, 9, 10];
    private static readonly int[] AthensMenuValues =
        [4, 6, 5, 7, 9, 10];
    private static readonly int[] MycenaeMenuValues =
        [1088, 1089, 1090];

    private static readonly TransporterDestination[] DestinationValues =
    [
        // Sparta progression chain.
        new("Sparta_042", SpartaNpcId, 0, 1, 4, 0, 1,
            SpartaLevelRequirementResultSubId, "Suburbs of Sparta"),
        new("Sparta_042", SpartaNpcId, 0, 2, 5, 13, 40,
            SpartaLevelRequirementResultSubId, "Nemea"),
        new("Sparta_042", SpartaNpcId, 0, 3, 13, 4, 30,
            SpartaLevelRequirementResultSubId, "Peloponnesus"),
        new("Sparta_042", SpartaNpcId, 0, 8, 14, 5, 70,
            SpartaLevelRequirementResultSubId, "Nemea Forest"),
        new("Sparta_042", SpartaNpcId, 0, 9, 8, 14, 100,
            SpartaLevelRequirementResultSubId, "Thermopylae"),
        new("Sparta_042", SpartaNpcId, 0, 10, 9, 19, 130,
            SpartaLevelRequirementResultSubId, "Thebes"),

        // Athens progression chain.
        new("Athens_041", AthensNpcId, 1, 4, 2, 1, 1,
            AthensLevelRequirementResultSubId, "Suburbs of Athens"),
        new("Athens_041", AthensNpcId, 1, 5, 3, 11, 40,
            AthensLevelRequirementResultSubId, "Parnitha"),
        new("Athens_041", AthensNpcId, 1, 6, 11, 2, 30,
            AthensLevelRequirementResultSubId, "Marathon"),
        new("Athens_041", AthensNpcId, 1, 7, 12, 3, 70,
            AthensLevelRequirementResultSubId, "Parnitha Port"),
        new("Athens_041", AthensNpcId, 1, 9, 8, 12, 100,
            AthensLevelRequirementResultSubId, "Thermopylae"),
        new("Athens_041", AthensNpcId, 1, 10, 9, 19, 130,
            AthensLevelRequirementResultSubId, "Thebes"),

        // Mycenae's three outbound world destinations.
        new("Mycenae_All_013", MycenaeNpcId, 6, 1088, 7, 6, 1,
            GenericLevelRequirementResultSubId, "Olympia"),
        new("Mycenae_All_013", MycenaeNpcId, 6, 1089, 20, 7, 1,
            GenericLevelRequirementResultSubId, "Delphi Forest"),
        new("Mycenae_All_013", MycenaeNpcId, 6, 1090, 10, 20, 1,
            GenericLevelRequirementResultSubId, "Larissa")
    ];

    public static IReadOnlyList<int> SpartaInitialMenuSubIds { get; } =
        Array.AsReadOnly(SpartaMenuValues);

    public static IReadOnlyList<int> AthensInitialMenuSubIds { get; } =
        Array.AsReadOnly(AthensMenuValues);

    public static IReadOnlyList<int> MycenaeInitialMenuSubIds { get; } =
        Array.AsReadOnly(MycenaeMenuValues);

    public static IReadOnlyList<TransporterDestination> Destinations { get; } =
        Array.AsReadOnly(DestinationValues);

    public static bool IsEndpoint(string npcKey, uint interactionId) =>
        (npcKey, interactionId) is
            ("Sparta_042", SpartaNpcId) or
            ("Athens_041", AthensNpcId) or
            ("Mycenae_All_013", MycenaeNpcId);

    public static bool TryGetInitialMenu(
        string npcKey,
        uint interactionId,
        out IReadOnlyList<int> subIds)
    {
        subIds = (npcKey, interactionId) switch
        {
            ("Sparta_042", SpartaNpcId) => SpartaInitialMenuSubIds,
            ("Athens_041", AthensNpcId) => AthensInitialMenuSubIds,
            ("Mycenae_All_013", MycenaeNpcId) => MycenaeInitialMenuSubIds,
            _ => []
        };
        return subIds.Count != 0;
    }

    public static bool TryResolveDestination(
        string npcKey,
        uint interactionId,
        short sourceMapId,
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out TransporterDestination destination)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        destination = null!;
        if (dialogIndex != DialogIndex || !HasEmptyPath(arguments))
        {
            return false;
        }

        destination = DestinationValues.FirstOrDefault(candidate =>
            string.Equals(candidate.NpcKey, npcKey, StringComparison.Ordinal) &&
            candidate.InteractionId == interactionId &&
            candidate.SourceMapId == sourceMapId &&
            candidate.SubId == subId)!;
        return destination is not null;
    }

    private static bool HasEmptyPath(IReadOnlyList<int> arguments)
    {
        if (arguments.Count != FunctionArgumentCount)
        {
            return false;
        }

        for (var index = 0; index < arguments.Count; index++)
        {
            if (arguments[index] != -1)
            {
                return false;
            }
        }

        return true;
    }
}
