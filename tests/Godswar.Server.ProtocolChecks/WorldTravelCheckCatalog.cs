namespace Godswar.Server.ProtocolChecks;

internal static class WorldTravelCheckCatalog
{
    public static readonly (string Name, Func<Task> Run)[] All =
    [
        ("Authoritative hidden live-map transfer", MapLiveTransferChecks.RunAsync),
        ("Native handler map-transition readiness", MapTransitionHandlerChecks.RunAsync),
        ("Native faction backhaul skill catalog", BackhaulSkillCatalogChecks.RunAsync),
        (FactionPortalSkillPolicyChecks.CheckName, FactionPortalSkillPolicyChecks.RunAsync),
        (
            FactionPortalSkillCreationArchitectureChecks.CheckName,
            FactionPortalSkillCreationArchitectureChecks.RunAsync),
        (
            BackhaulSkillHandlerChecks.NativeSuccessCheckName,
            BackhaulSkillHandlerChecks.RunNativeSuccessAsync),
        (
            BackhaulSkillHandlerChecks.SameMapCheckName,
            BackhaulSkillHandlerChecks.RunSameMapAsync),
        (
            BackhaulSkillHandlerChecks.FactionBoundaryCheckName,
            BackhaulSkillHandlerChecks.RunFactionBoundaryAsync),
        ("Authoritative faction backhaul casting", BackhaulSkillHandlerChecks.RunAsync),
        ("Authoritative map traversal catalog", MapTraversalCatalogChecks.RunAsync),
        (TransporterProtocolChecks.CheckName, TransporterProtocolChecks.RunAsync),
        (TransporterHandlerChecks.CheckName, TransporterHandlerChecks.RunAsync),
        (
            BattlefieldTransporterProtocolChecks.CheckName,
            BattlefieldTransporterProtocolChecks.RunAsync),
        (
            DuelArenaTransporterProtocolChecks.CheckName,
            DuelArenaTransporterProtocolChecks.RunAsync),
        (
            DuelArenaSpawnStreamChecks.CheckName,
            DuelArenaSpawnStreamChecks.RunAsync),
        (
            DuelArenaCapturedProtocolChecks.CheckName,
            DuelArenaCapturedProtocolChecks.RunAsync),
        (
            DuelArenaTransporterHandlerChecks.CheckName,
            DuelArenaTransporterHandlerChecks.RunAsync),
        (
            WarehouseHandlerChecks.ArenaSupportCheckName,
            WarehouseHandlerChecks.RunArenaSupportAsync),
        (
            BattlefieldSchedulePolicyChecks.CheckName,
            BattlefieldSchedulePolicyChecks.RunAsync)
    ];
}
