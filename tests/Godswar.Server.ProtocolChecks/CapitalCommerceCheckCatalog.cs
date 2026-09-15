namespace Godswar.Server.ProtocolChecks;

internal static class CapitalCommerceCheckCatalog
{
    public static (string Name, Func<Task> Run)[] All { get; } =
    [
        (FactionCrierProtocolChecks.CheckName,
            FactionCrierProtocolChecks.RunAsync),
        (WarehouseContractChecks.CheckName,
            WarehouseContractChecks.RunAsync),
        (CapitalNpcServiceProtocolChecks.CheckName,
            CapitalNpcServiceProtocolChecks.RunAsync),
        (CapitalShopInventoryPlannerChecks.CheckName,
            CapitalShopInventoryPlannerChecks.RunAsync),
        (PostgresCapitalShopPurchaseIntegrationChecks.CheckName,
            PostgresCapitalShopPurchaseIntegrationChecks.RunAsync),
        (PostgresGameplayFeatureAdapterChecks.CheckName,
            PostgresGameplayFeatureAdapterChecks.RunAsync),
        (QuestProtocolChecks.CheckName,
            QuestProtocolChecks.RunAsync)
    ];
}
