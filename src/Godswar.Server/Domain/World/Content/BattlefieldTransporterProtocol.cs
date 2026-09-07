namespace Godswar.Server.Domain.World.Content;

internal enum BattlefieldDestinationKind : byte
{
    Pindus = 1,
    NiMiniLower = 2,
    NiMiniUpper = 3,
    DuelArena = 4
}

internal sealed record BattlefieldTransportDestination(
    BattlefieldDestinationKind Kind,
    string DisplayName,
    int SourceMapId,
    int TargetMapId,
    float TargetX,
    float TargetZ,
    int MinimumLevel,
    int MaximumLevel);

/// <summary>
/// Finite stock NpcFunTranmit surface for the two capital Battlefield
/// Transporters. Ni Mini is a second-page choice; Pindus and Duel Arena are
/// direct root actions. Destination coordinates are reviewed server-owned
/// arrivals and are never accepted from the client.
/// </summary>
internal static class BattlefieldTransporterProtocol
{
    public const uint SpartaNpcId = 5053;
    public const uint AthensNpcId = 5195;
    public const int DialogIndex = 1;
    public const int ActionPacketBytes = 92;
    public const int FunctionArgumentCount = 18;
    public const int InitialRequestSubId = -1;
    public const int PindusSubId = 251;
    public const int AthensPindusSubId = 252;
    public const int NiMiniRootSubId = 274;
    public const int NiMiniLowerSubId = 272;
    public const int NiMiniUpperSubId = 273;
    public const int DuelArenaSubId = 1001;
    public const int PindusResultDialogIndex = 2;
    public const int PindusMinimumLevelResultDialogIndex = 1;
    public const int PindusMinimumLevelResultSubId = 8002;
    public const int PindusClosedResultSubId = 8000;
    public const int PindusLevelResultSubId = 8001;
    public const int NiMiniResultDialogIndex = 3;
    public const int NiMiniUnavailableResultSubId = 7000;
    public const float MaximumInteractionDistance = 12f;

    public static readonly TimeSpan MenuContextLifetime =
        TimeSpan.FromMinutes(2);

    public static IReadOnlyList<int> SpartaInitialMenuSubIds { get; } =
        Array.AsReadOnly(new[]
        {
            PindusSubId,
            NiMiniRootSubId,
            DuelArenaSubId
        });

    public static IReadOnlyList<int> AthensInitialMenuSubIds { get; } =
        Array.AsReadOnly(new[]
        {
            AthensPindusSubId,
            NiMiniRootSubId,
            DuelArenaSubId
        });

    public static IReadOnlyList<int> NiMiniPageSubIds { get; } =
        Array.AsReadOnly(new[]
        {
            NiMiniUpperSubId
        });

    public static bool IsEndpoint(string npcKey, uint interactionId) =>
        (npcKey, interactionId) is
            ("Sparta_056", SpartaNpcId) or
            ("Athens_056", AthensNpcId);

    public static bool TryGetInitialMenu(
        string npcKey,
        uint interactionId,
        out IReadOnlyList<int> menu)
    {
        menu = (npcKey, interactionId) switch
        {
            ("Sparta_056", SpartaNpcId) => SpartaInitialMenuSubIds,
            ("Athens_056", AthensNpcId) => AthensInitialMenuSubIds,
            _ => []
        };
        return menu.Count > 0;
    }

    public static bool TryGetNiMiniPage(
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out int[] responseSubIds)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        responseSubIds = [];
        if (dialogIndex != DialogIndex ||
            subId != NiMiniRootSubId ||
            !HasExactPath(arguments))
        {
            return false;
        }

        responseSubIds = NiMiniPageSubIds.ToArray();
        return true;
    }

    public static bool TryResolveDestination(
        string npcKey,
        uint interactionId,
        byte sourceMapId,
        byte camp,
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out BattlefieldTransportDestination destination)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        destination = null!;
        if (dialogIndex != DialogIndex ||
            !TryResolveFaction(
                npcKey,
                interactionId,
                sourceMapId,
                camp,
                out var sparta))
        {
            return false;
        }

        destination = subId switch
        {
            PindusSubId when sparta && HasExactPath(arguments) =>
                Pindus(sourceMapId, sparta),
            AthensPindusSubId when !sparta && HasExactPath(arguments) =>
                Pindus(sourceMapId, sparta),
            NiMiniRootSubId when HasExactPath(
                arguments,
                NiMiniUpperSubId) =>
                NiMini(sourceMapId, sparta),
            DuelArenaSubId when HasExactPath(arguments) =>
                DuelArena(sourceMapId, sparta),
            _ => null!
        };
        return destination is not null;
    }

    private static BattlefieldTransportDestination Pindus(
        int sourceMapId,
        bool sparta) =>
        new(
            BattlefieldDestinationKind.Pindus,
            "Pindus Mountains Battlefield",
            sourceMapId,
            TargetMapId: 38,
            TargetX: sparta ? 14f : 10f,
            TargetZ: sparta ? 180f : -183f,
            MinimumLevel: 31,
            MaximumLevel: 120);

    private static BattlefieldTransportDestination NiMini(
        int sourceMapId,
        bool sparta) =>
        new(
            BattlefieldDestinationKind.NiMiniUpper,
            "Ni Mini Valley (Level 70-89)",
            sourceMapId,
            TargetMapId: 34,
            TargetX: sparta ? 216f : 136f,
            TargetZ: sparta ? -220f : -4f,
            MinimumLevel: 70,
            MaximumLevel: 89);

    private static BattlefieldTransportDestination DuelArena(
        int sourceMapId,
        bool sparta) =>
        new(
            BattlefieldDestinationKind.DuelArena,
            "Duel Arena",
            sourceMapId,
            TargetMapId: 57,
            TargetX: DuelArenaCapturedLayout.UpperArrivalX,
            TargetZ: DuelArenaCapturedLayout.UpperArrivalZ,
            MinimumLevel: 1,
            MaximumLevel: int.MaxValue);

    private static bool TryResolveFaction(
        string npcKey,
        uint interactionId,
        byte sourceMapId,
        byte camp,
        out bool sparta)
    {
        sparta = false;
        if ((npcKey, interactionId, sourceMapId, camp) is
            ("Sparta_056", SpartaNpcId, 0, 0))
        {
            sparta = true;
            return true;
        }

        return (npcKey, interactionId, sourceMapId, camp) is
            ("Athens_056", AthensNpcId, 1, 1);
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
