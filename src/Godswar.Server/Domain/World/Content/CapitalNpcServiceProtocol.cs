using System.Buffers.Binary;
using System.Collections.Immutable;

namespace Godswar.Server.Domain.World.Content;

internal enum CapitalNpcServiceKind
{
    ExchangeMentor,
    TeachingManager,
    BoundGoldVendor,
    BindingGoldShop,
    FestivalEnvoy,
    SacredSealer,
    HolyStoneRedeemer,
    HalloweenEnvoy,
    PetMerchant,
    SkillVendor,
    PropsVendor,
    PrizeChest,
    LevelSealer
}

internal enum CapitalNpcShopCurrency
{
    Gold,
    BindingGold,
    Silver
}

internal readonly record struct CapitalNpcShopBalances(
    int Silver,
    int Gold,
    int BindingGold)
{
    public int Get(CapitalNpcShopCurrency currency) =>
        currency switch
        {
            CapitalNpcShopCurrency.Silver => Silver,
            CapitalNpcShopCurrency.Gold => Gold,
            CapitalNpcShopCurrency.BindingGold => BindingGold,
            _ => throw new ArgumentOutOfRangeException(
                nameof(currency),
                currency,
                "Unknown capital shop currency.")
        };
}

internal static class CapitalNpcServiceProtocol
{
    public const int PurchasePayloadBytes = 20;
    public const int ExchangeDialogIndex = 2;
    public const int DescriptionOpenFlags = 0;
    public const int ShopOpenFlags = 4;
    public const int PrizeChestOpenFlags = 0x40;
    public const int LevelSealerDialogIndex = 116;
    public const int LevelSealerDescriptionSubId = 101;
    public const int LevelSealerSealSubId = 102;
    public const int LevelSealerUnsealSubId = 103;
    public const int LevelSealerInsufficientFundsSubId = 104;
    public const int LevelSealerUnavailableSubId = 105;
    public const int LevelSealerSealedSubId = 106;
    public const int LevelSealerUnsealedSubId = 107;
    public const int LevelSealerAlreadyUnsealedSubId = 108;
    public const int LevelSealerAlreadySealedSubId = 109;

    public static ImmutableArray<int> ExchangeInitialMenu { get; } =
        [49, 50, 51];

    public static bool TryResolve(
        NpcSpawnDefinition npc,
        out CapitalNpcServiceKind service) =>
        TryResolve(npc.NpcKey, npc.InteractionId, out service);

    public static bool TryResolve(
        string npcKey,
        uint interactionId,
        out CapitalNpcServiceKind service)
    {
        var resolved = (npcKey, interactionId) switch
        {
            ("Sparta_052", 5049u) or ("Athens_052", 5191u) =>
                (CapitalNpcServiceKind?)CapitalNpcServiceKind.ExchangeMentor,
            ("Sparta_069", 5066u) or ("Athens_069", 5208u) =>
                CapitalNpcServiceKind.TeachingManager,
            ("Sparta_087", 5084u) or ("Athens_087", 5226u) =>
                CapitalNpcServiceKind.BoundGoldVendor,
            ("Sparta_068", 5065u) or ("Athens_068", 5207u) =>
                CapitalNpcServiceKind.BindingGoldShop,
            ("Sparta_084", 5081u) or ("Athens_084", 5223u) =>
                CapitalNpcServiceKind.FestivalEnvoy,
            ("Sparta_130", 5127u) or ("Athens_130", 5269u) =>
                CapitalNpcServiceKind.SacredSealer,
            ("Sparta_131", 5128u) or ("Athens_131", 5270u) =>
                CapitalNpcServiceKind.HolyStoneRedeemer,
            ("Sparta_053", 5050u) or ("Athens_053", 5192u) =>
                CapitalNpcServiceKind.HalloweenEnvoy,
            ("Sparta_089", 5086u) or ("Athens_089", 5228u) =>
                CapitalNpcServiceKind.PetMerchant,
            ("Sparta_034", 44345u) or ("Athens_036", 5175u) or
            ("Sparta_Newbie_004", 46565u) or
            ("Athens_Newbie_004", 54453u) =>
                CapitalNpcServiceKind.SkillVendor,
            ("Sparta_036", 5033u) or ("Athens_021", 5160u) =>
                CapitalNpcServiceKind.PropsVendor,
            ("Sparta_123", 5120u) or ("Athens_123", 5262u) =>
                CapitalNpcServiceKind.PrizeChest,
            ("Sparta_142", 5139u) or ("Athens_142", 5281u) =>
                CapitalNpcServiceKind.LevelSealer,
            _ => null
        };

        service = resolved.GetValueOrDefault();
        return resolved.HasValue;
    }

    public static bool IsShop(CapitalNpcServiceKind service) =>
        service is
            CapitalNpcServiceKind.BoundGoldVendor or
            CapitalNpcServiceKind.BindingGoldShop or
            CapitalNpcServiceKind.PetMerchant or
            CapitalNpcServiceKind.SkillVendor or
            CapitalNpcServiceKind.PropsVendor;

    public static bool IsSuppressedSpawn(NpcSpawnDefinition npc) =>
        (npc.NpcKey, npc.InteractionId) is
            ("Sparta_028", 42888u) or
            ("Sparta_029", 5026u) or
            ("Sparta_037", 5034u) or
            ("Sparta_038", 5035u);

    public static NpcSpawnDefinition ApplyCapturedSpawnCompatibility(
        NpcSpawnDefinition npc) =>
        (npc.MapId, npc.NpcKey, npc.InteractionId) switch
        {
            (0, "Sparta_142", 5139u) => npc with
            {
                TemplateKey = "Sparta_142_Hallo",
                X = 120.007515f,
                Z = -138.16507f,
                AppearanceType = 17u,
                Facing = 3.071875f
            },
            (1, "Athens_142", 5281u) => npc with
            {
                TemplateKey = "Athens_142_Hallo",
                X = 120.007515f,
                Z = -138.16507f,
                AppearanceType = 65_809u,
                Facing = 3.071875f
            },
            _ => npc
        };

    public static bool TryGetDialogueRoutes(
        NpcSpawnDefinition npc,
        out IReadOnlyList<NpcDialogueRouteDefinition> routes)
    {
        routes = [];
        if (!TryResolve(npc, out var service))
        {
            return false;
        }

        routes = service switch
        {
            CapitalNpcServiceKind.FestivalEnvoy =>
                [Route(npc, 28, [2, 3, 4, 5])],
            CapitalNpcServiceKind.SacredSealer =>
                [Route(npc, 95, [1])],
            CapitalNpcServiceKind.HolyStoneRedeemer =>
                [Route(npc, 38, [0, 101])],
            CapitalNpcServiceKind.HalloweenEnvoy =>
                [
                    Route(npc, 95, [0, 1, 2, 3, 4, 5]),
                    Route(npc, 113, [0, 5, 6, 7, 8, 8001], routeOrder: 1)
                ],
            CapitalNpcServiceKind.LevelSealer =>
                [Route(
                    npc,
                    LevelSealerDialogIndex,
                    [
                        LevelSealerDescriptionSubId,
                        LevelSealerSealSubId,
                        LevelSealerUnsealSubId
                    ])],
            _ => []
        };
        return routes.Count != 0;
    }

    public static bool TryGetInitialDialogueReply(
        CapitalNpcServiceKind service,
        out int responseDialogIndex,
        out int[] responseSubIds)
    {
        (responseDialogIndex, responseSubIds) = service switch
        {
            CapitalNpcServiceKind.FestivalEnvoy =>
                (28, new[] { 2, 3, 4, 5 }),
            CapitalNpcServiceKind.HolyStoneRedeemer =>
                (38, new[] { 0, 101 }),
            CapitalNpcServiceKind.HalloweenEnvoy =>
                (113, new[] { 0, 1, 2, 3, 4, 5 }),
            CapitalNpcServiceKind.LevelSealer =>
                (
                    LevelSealerDialogIndex,
                    new[]
                    {
                        LevelSealerDescriptionSubId,
                        LevelSealerSealSubId,
                        LevelSealerUnsealSubId
                    }),
            _ => (0, Array.Empty<int>())
        };
        return responseSubIds.Length != 0;
    }

    public static bool TryGetDialogueReply(
        CapitalNpcServiceKind service,
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out int responseDialogIndex,
        out int[] responseSubIds)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        (responseDialogIndex, responseSubIds) =
            (service, dialogIndex, subId, ReadPath(arguments)) switch
            {
                (CapitalNpcServiceKind.FestivalEnvoy, 28, 5, "") =>
                    (28, new[] { 501, 502, 4, 5 }),
                (CapitalNpcServiceKind.FestivalEnvoy, 28, 5, "501") =>
                    (28, new[] { 511, 3, 4, 5 }),
                (CapitalNpcServiceKind.HalloweenEnvoy, 113, 4, "") =>
                    (113, new[] { 0, 5, 6, 7, 8, 8001 }),
                _ => (0, Array.Empty<int>())
            };
        return responseSubIds.Length != 0;
    }

    public static bool IsWeekendExperienceClaim(
        CapitalNpcServiceKind service,
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        return service == CapitalNpcServiceKind.FestivalEnvoy &&
            dialogIndex == 28 &&
            subId == 5 &&
            ReadPath(arguments) == "501";
    }

    public static bool TryGetLevelSealerChange(
        CapitalNpcServiceKind service,
        int dialogIndex,
        int subId,
        IReadOnlyList<int> arguments,
        out bool desiredSealed)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        desiredSealed = subId == LevelSealerSealSubId;
        return service == CapitalNpcServiceKind.LevelSealer &&
            dialogIndex == LevelSealerDialogIndex &&
            subId is LevelSealerSealSubId or LevelSealerUnsealSubId &&
            ReadPath(arguments) == string.Empty;
    }

    private static NpcDialogueRouteDefinition Route(
        NpcSpawnDefinition npc,
        int dialogIndex,
        int[] menu,
        int routeOrder = 0) =>
        new(
            npc.NpcKey,
            npc.NpcKey,
            dialogIndex,
            NpcDialogueBehavior.CapturedCapital,
            menu.ToImmutableArray())
        {
            RouteOrder = routeOrder
        };

    private static string? ReadPath(IReadOnlyList<int> arguments)
    {
        var path = new List<int>();
        var padding = false;
        foreach (var argument in arguments)
        {
            if (argument == -1)
            {
                padding = true;
                continue;
            }
            if (padding)
            {
                return null;
            }
            path.Add(argument);
        }
        return string.Join('/', path);
    }

    public static bool TryGetShopCurrency(
        CapitalNpcServiceKind service,
        out CapitalNpcShopCurrency currency)
    {
        currency = service switch
        {
            CapitalNpcServiceKind.BoundGoldVendor =>
                CapitalNpcShopCurrency.Gold,
            CapitalNpcServiceKind.BindingGoldShop or
            CapitalNpcServiceKind.SkillVendor =>
                CapitalNpcShopCurrency.BindingGold,
            CapitalNpcServiceKind.PetMerchant =>
                CapitalNpcShopCurrency.Silver,
            _ => default
        };
        return service is
            CapitalNpcServiceKind.BoundGoldVendor or
            CapitalNpcServiceKind.BindingGoldShop or
            CapitalNpcServiceKind.PetMerchant or
            CapitalNpcServiceKind.SkillVendor;
    }

    public static bool TryGetShopCurrency(
        byte shopType,
        out CapitalNpcShopCurrency currency)
    {
        currency = shopType switch
        {
            2 => CapitalNpcShopCurrency.Gold,
            3 => CapitalNpcShopCurrency.Silver,
            4 => CapitalNpcShopCurrency.BindingGold,
            _ => default
        };
        return shopType is 2 or 3 or 4;
    }

    public static NpcDialogueRouteDefinition ExchangeRoute(
        NpcSpawnDefinition npc)
    {
        if (!TryResolve(npc, out var service) ||
            service != CapitalNpcServiceKind.ExchangeMentor)
        {
            throw new ArgumentException(
                "NPC is not an exact capital Exchange Mentor endpoint.",
                nameof(npc));
        }

        return new NpcDialogueRouteDefinition(
            npc.NpcKey,
            npc.NpcKey,
            ExchangeDialogIndex,
            NpcDialogueBehavior.CreditExchange,
            ExchangeInitialMenu);
    }

    public static bool TryGetExchangePage(
        int subId,
        out int[] pageSubIds)
    {
        pageSubIds = subId switch
        {
            50 => [311, 312, 313],
            51 => [314, 315, 316],
            _ => []
        };
        return pageSubIds.Length != 0;
    }

    public static bool TryParsePurchase(
        ReadOnlySpan<byte> payload,
        out CapitalNpcShopPurchaseIntent intent)
    {
        intent = default;
        if (payload.Length != PurchasePayloadBytes)
        {
            return false;
        }

        var candidate = new CapitalNpcShopPurchaseIntent(
            BinaryPrimitives.ReadUInt32LittleEndian(payload),
            BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(4)),
            BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(8)),
            BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(12)),
            BinaryPrimitives.ReadUInt32LittleEndian(payload.Slice(16)));
        if (candidate.NpcId == 0 ||
            candidate.Category is < 0 or > byte.MaxValue ||
            candidate.ListingIndex < 0 ||
            candidate.Quantity is < 1 or > byte.MaxValue ||
            candidate.ItemId == 0)
        {
            return false;
        }

        intent = candidate;
        return true;
    }
}

internal readonly record struct CapitalNpcShopPurchaseIntent(
    uint NpcId,
    int Category,
    int ListingIndex,
    int Quantity,
    uint ItemId);
