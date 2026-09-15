namespace Godswar.Server.ProtocolChecks;

internal static class LegacyInstanceCheckCatalog
{
    public static readonly (string Name, Func<Task> Run)[] All =
    [
        (
            LegacyInstanceDailyEntryChecks.CheckName,
            LegacyInstanceDailyEntryChecks.RunAsync),
        (
            PostgresLegacyInstanceDailyEntryChecks.CheckName,
            PostgresLegacyInstanceDailyEntryChecks.RunAsync),
        (
            PostgresLegacyInstanceOpalPaymentIntegrationChecks.CheckName,
            PostgresLegacyInstanceOpalPaymentIntegrationChecks.RunAsync)
    ];
}
