using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game;
using Godswar.Server.Game.WorldInstances;

namespace Godswar.Server.ProtocolChecks;

internal static class LegacyInstanceDailyEntryChecks
{
    public const string CheckName =
        "Atomic Atlantis and Wonderland daily entry claims";

    public static async Task RunAsync()
    {
        CheckRequestValidation();
        CheckLocalAtomicClaims();
        await CheckFailedLaunchRuntimeRetirementAsync();
    }

    private static void CheckRequestValidation()
    {
        var valid = new LegacyInstanceDailyEntryClaimRequest(
            Guid.NewGuid(),
            RealmId.Tempest,
            new DateOnly(2026, 9, 1),
            InstanceCallerEntryKind.Atlantis,
            [101, 102, 103],
            DateTimeOffset.UnixEpoch);
        valid.Validate();

        Check.Throws<ArgumentException>(
            () => (valid with { CharacterIds = [101, 102] }).Validate(),
            "Atlantis requires exactly three unique characters");
        Check.Throws<ArgumentException>(
            () => (valid with { CharacterIds = [101, 101, 103] })
                .Validate(),
            "a daily claim rejects duplicate characters");
    }

    private static void CheckLocalAtomicClaims()
    {
        var registry = new GameSessionRegistry();
        var day = new DateOnly(2026, 9, 1);
        var firstReservation = Guid.NewGuid();
        var first = registry.TryReserveLocalLegacyInstanceDailyEntry(
                firstReservation,
                RealmId.Tempest,
                day,
                InstanceCallerEntryKind.Atlantis,
                [101, 102, 103]);
        Check.True(
            first.Status == LegacyInstanceDailyEntryClaimStatus.Claimed &&
            first.DailyEntryLimit == 4 &&
            first.FreeEntryLimit == 3 &&
            first.PaidRetryLimit == 1 &&
            first.PaymentRequiredCharacterIds.Count == 0,
            "the first Atlantis attempt is free and claimed atomically");
        var second = registry.TryReserveLocalLegacyInstanceDailyEntry(
            Guid.NewGuid(),
            RealmId.Tempest,
            day,
            InstanceCallerEntryKind.Atlantis,
            [101, 104, 105]);
        Check.True(
            second.Status == LegacyInstanceDailyEntryClaimStatus.Claimed &&
            second.PaymentRequiredCharacterIds.Count == 0,
            "the second Atlantis attempt remains free");
        var third = registry.TryReserveLocalLegacyInstanceDailyEntry(
                Guid.NewGuid(),
                RealmId.Tempest,
                day,
                InstanceCallerEntryKind.Atlantis,
                [101, 106, 107]);
        Check.True(
            third.Status == LegacyInstanceDailyEntryClaimStatus.Claimed &&
            third.PaymentRequiredCharacterIds.Count == 0,
            "the third Atlantis attempt remains free");
        var fourth = registry.TryReserveLocalLegacyInstanceDailyEntry(
                Guid.NewGuid(),
                RealmId.Tempest,
                day,
                InstanceCallerEntryKind.Atlantis,
                [101, 108, 109]);
        Check.True(
            fourth.Status == LegacyInstanceDailyEntryClaimStatus.Claimed &&
            fourth.PaymentRequiredCharacterIds.SetEquals([101]),
            "only the returning member pays for the fourth Atlantis " +
            "entry");
        Check.True(
            registry.TryReserveLocalLegacyInstanceDailyEntry(
                Guid.NewGuid(),
                RealmId.Tempest,
                day,
                InstanceCallerEntryKind.Atlantis,
                [101, 110, 111]).Status ==
                LegacyInstanceDailyEntryClaimStatus.DailyLimitReached,
            "one exhausted Atlantis member rejects the fifth party");
        Check.True(
            registry.TryReserveLocalLegacyInstanceDailyEntry(
                Guid.NewGuid(),
                RealmId.Tempest,
                day,
                InstanceCallerEntryKind.Atlantis,
                [110, 111, 112]).Status ==
                LegacyInstanceDailyEntryClaimStatus.Claimed,
            "a rejected party consumes no attempt for eligible members");
        var wonderland = registry.TryReserveLocalLegacyInstanceDailyEntry(
                Guid.NewGuid(),
                RealmId.Tempest,
                day,
                InstanceCallerEntryKind.Wonderland,
                [101]);
        Check.True(
            wonderland.Status ==
                LegacyInstanceDailyEntryClaimStatus.Claimed &&
            wonderland.FreeEntryLimit == 3 &&
            wonderland.PaymentRequiredCharacterIds.Count == 0,
            "Wonderland is independent and all three attempts are free");

        registry.ReleaseLocalLegacyInstanceDailyEntryMembers(
            firstReservation,
            [101]);
        var restored = registry.TryReserveLocalLegacyInstanceDailyEntry(
                Guid.NewGuid(),
                RealmId.Tempest,
                day,
                InstanceCallerEntryKind.Atlantis,
                [101, 113, 114]);
        Check.True(
            restored.Status == LegacyInstanceDailyEntryClaimStatus.Claimed &&
            restored.PaymentRequiredCharacterIds.SetEquals([101]),
            "a partial release restores only the failed member's paid " +
            "retry slot");
        Check.True(
            registry.TryReserveLocalLegacyInstanceDailyEntry(
                Guid.NewGuid(),
                RealmId.Tempest,
                day.AddDays(1),
                InstanceCallerEntryKind.Atlantis,
                [101, 102, 103]).Status ==
                LegacyInstanceDailyEntryClaimStatus.Claimed,
            "all attempts reset on the next realm day");
    }

    private static async Task CheckFailedLaunchRuntimeRetirementAsync()
    {
        await using var registry = new GameSessionRegistry();
        var before = registry.GetWorldInstanceDirectorySnapshot();
        var creation = await registry.CreateLocalWorldInstanceAsync(
            RealmId.Tempest,
            new MapId(205),
            InstanceKind.Dungeon,
            playerCapacity: 3);
        Check.True(
            creation.Status == WorldInstanceRuntimeDirectoryStatus.Created &&
            creation.Runtime is not null,
            "the failed-launch fixture creates an exact dungeon runtime");
        Check.Equal(
            before.RuntimeCount + 1,
            registry.GetWorldInstanceDirectorySnapshot().RuntimeCount,
            "a created dungeon consumes one runtime slot");

        Check.True(
            await registry.TryRetireEmptyLocalWorldInstanceAsync(
                creation.Runtime!.Descriptor),
            "an exact empty failed-launch runtime drains, closes, and removes");
        Check.Equal(
            before.RuntimeCount,
            registry.GetWorldInstanceDirectorySnapshot().RuntimeCount,
            "failed launch retirement restores the runtime slot");
    }
}
