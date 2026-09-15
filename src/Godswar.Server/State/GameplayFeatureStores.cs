namespace Godswar.Server.State;

/// <summary>Compatibility projection contract; SQL belongs to the feature adapter.</summary>
internal interface ICapitalShopPurchaseStore
{
    Task<CapitalShopPurchaseResult> PurchaseCapitalShopItemAsync(
        int accountId,
        int characterId,
        Guid purchaseId,
        CapitalShopOffer offer,
        int quantity,
        CancellationToken cancellationToken = default) =>
        Task.FromResult(new CapitalShopPurchaseResult(
            CapitalShopPurchaseStatus.UnsupportedItem,
            Character: null,
            CurrencyBalance: 0));

<<<<<<< HEAD
    Task<CapitalShopSaleResult> SellCapitalShopItemAsync(
        int accountId,
        int characterId,
        Guid saleId,
        int sourceSlot,
        CancellationToken cancellationToken = default) =>
        Task.FromResult(CapitalShopSaleResult.Rejected(
            CapitalShopSaleStatus.UnsupportedItem));

=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
}

/// <summary>Idempotent loot and summoned-pet reward supplements.</summary>
internal interface IMonsterRewardExtrasStore
{
    Task<PetMonsterExperienceResult> ApplyPetMonsterKillExperienceAsync(
        int accountId,
        int characterId,
        Guid deathEventId,
        int experience,
        CancellationToken cancellationToken = default) =>
        Task.FromResult(new PetMonsterExperienceResult(
            PetMonsterExperienceStatus.NoSummonedPet,
            deathEventId,
            0,
            PetId: null,
            TotalExperience: null,
            PetRevision: null));

    Task<MonsterLootPickupResult> PickupMonsterLootAsync(
        int accountId,
        int characterId,
        Guid deathEventId,
        int lootIndex,
        uint itemId,
        int quantity,
        CancellationToken cancellationToken = default) =>
        Task.FromResult(new MonsterLootPickupResult(
            MonsterLootPickupStatus.Unsupported,
            Character: null));

}

internal sealed class UnsupportedGameplayFeatures : ICapitalShopPurchaseStore, IMonsterRewardExtrasStore
{
    public static readonly UnsupportedGameplayFeatures Instance = new();
    private UnsupportedGameplayFeatures() { }
}
