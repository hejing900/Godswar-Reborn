using Godswar.Server.Domain.World.Content;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Application.Characters;

namespace Godswar.Server.Application.WorldInstances;

internal enum LegacyInstanceDailyEntryClaimStatus : byte
{
    Claimed = 1,
    DailyLimitReached = 2,
    AlreadyUsed = DailyLimitReached
}

internal static class LegacyInstanceDailyEntryPolicy
{
    public const ushort DefaultFreeEntryLimit = 3;

    public static ushort? GetDefaultPaidRetryLimit(
        InstanceCallerEntryKind instanceKind) => instanceKind switch
    {
        InstanceCallerEntryKind.Atlantis => 1,
        InstanceCallerEntryKind.Wonderland => 0,
        _ => throw new ArgumentOutOfRangeException(nameof(instanceKind))
    };

    public static ushort? GetDefaultDailyEntryLimit(
        InstanceCallerEntryKind instanceKind)
    {
        var paidRetryLimit = GetDefaultPaidRetryLimit(instanceKind);
        return paidRetryLimit is ushort paid
            ? checked((ushort)(DefaultFreeEntryLimit + paid))
            : null;
    }
}

internal sealed record LegacyInstanceDailyEntryClaimResult(
    LegacyInstanceDailyEntryClaimStatus Status,
    ushort? DailyEntryLimit,
    ushort FreeEntryLimit,
    IReadOnlySet<int> PaymentRequiredCharacterIds,
    ushort? PaidRetryLimit = 0);

internal sealed record LegacyInstanceDailyEntryClaimRequest(
    Guid ReservationId,
    RealmId RealmId,
    DateOnly RealmDay,
    InstanceCallerEntryKind InstanceKind,
    IReadOnlyCollection<int> CharacterIds,
    DateTimeOffset ClaimedAtUtc)
{
    public void Validate()
    {
        if (ReservationId == Guid.Empty ||
            !RealmId.IsValid ||
            ClaimedAtUtc == default ||
            ClaimedAtUtc.Offset != TimeSpan.Zero ||
            !Enum.IsDefined(InstanceKind))
        {
            throw new ArgumentException(
                "Invalid legacy-instance daily-entry claim identity.");
        }

        if (CharacterIds.Count is < 1 or > 5 ||
            CharacterIds.Any(static id => id <= 0) ||
            CharacterIds.Distinct().Count() != CharacterIds.Count)
        {
            throw new ArgumentException(
                "The legacy-instance claim requires a valid, unique party.");
        }
    }
}

internal interface ILegacyInstanceDailyEntryClaimStore
{
    Task<LegacyInstanceDailyEntryClaimResult> TryClaimAsync(
        LegacyInstanceDailyEntryClaimRequest request,
        CancellationToken cancellationToken = default);

    Task ReleaseAsync(
        Guid reservationId,
        CancellationToken cancellationToken = default);

    Task ReleaseMembersAsync(
        Guid reservationId,
        IReadOnlyCollection<int> characterIds,
        CancellationToken cancellationToken = default);

    Task RecordAdmissionsAsync(
        Guid reservationId,
        IReadOnlyCollection<int> admittedCharacterIds,
        CancellationToken cancellationToken = default);

    Task<int> RecoverPendingAsync(
        RealmId realmId,
        DateTimeOffset staleBeforeUtc,
        CancellationToken cancellationToken = default);

    Task<int> RecoverCharacterAsync(
        RealmId realmId,
        int accountId,
        int characterId,
        PlayerOwnershipFence ownership,
        CancellationToken cancellationToken = default);
}
