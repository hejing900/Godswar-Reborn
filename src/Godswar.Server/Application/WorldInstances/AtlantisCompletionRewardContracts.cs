using System.Security.Cryptography;
using System.Text;
using Godswar.Server.Domain.World.Instances;

namespace Godswar.Server.Application.WorldInstances;

internal readonly record struct AtlantisCompletionMember(int AccountId, int CharacterId);

internal readonly record struct AtlantisCompletionRewardAward(int HardPoints, uint TitleId, string TitleName);

internal static class AtlantisCompletionRewardPolicy
{
    public const string Revision = "atlantis-completion-v1";
    public const int CompletedHardPoints = 2800;
    public const uint SeabedExplorerTitleId = 5013;
    public const uint DeepSeaHunterTitleId = 5014;

    public static AtlantisCompletionRewardAward Resolve(int admittedMemberCount) => admittedMemberCount switch
    {
        1 => new(CompletedHardPoints, DeepSeaHunterTitleId, "Deep Sea Hunter"),
        >= 2 and <= 5 => new(CompletedHardPoints, SeabedExplorerTitleId, "Seabed Explorer"),
        _ => throw new ArgumentOutOfRangeException(nameof(admittedMemberCount))
    };
}

/// <summary>
/// Evidence captured from the completed original instance. The durable entry
/// reservation fences the admitted roster; current connection ownership only
/// controls projection, never entitlement to an already earned reward.
/// </summary>
internal sealed class AtlantisCompletionRewardRequest
{
    public AtlantisCompletionRewardRequest(WorldInstanceId worldInstanceId, RealmId realmId,
        Guid admissionReservationId, DateTimeOffset startedAtUtc, DateTimeOffset completedAtUtc,
        int finalScore, IReadOnlyCollection<AtlantisCompletionMember> admittedMembers,
        IReadOnlyCollection<AtlantisCompletionMember> frozenMembers)
    {
        ArgumentNullException.ThrowIfNull(admittedMembers);
        ArgumentNullException.ThrowIfNull(frozenMembers);
        var admitted = admittedMembers.OrderBy(member => member.CharacterId).ToArray();
        var members = frozenMembers.OrderBy(member => member.CharacterId).ToArray();
        if (!worldInstanceId.IsValid || !realmId.IsValid || admissionReservationId == Guid.Empty ||
            startedAtUtc == default || startedAtUtc.Offset != TimeSpan.Zero || completedAtUtc.Offset != TimeSpan.Zero ||
            completedAtUtc < startedAtUtc || completedAtUtc - startedAtUtc >= TimeSpan.FromMinutes(40) ||
            finalScore != 850 || !IsValidRoster(admitted) || !IsValidRoster(members) ||
            members.Any(member => !admitted.Contains(member)))
        {
            throw new ArgumentException("Invalid authoritative Atlantis completion evidence.");
        }
        WorldInstanceId = worldInstanceId;
        RealmId = realmId;
        AdmissionReservationId = admissionReservationId;
        StartedAtUtc = startedAtUtc;
        CompletedAtUtc = completedAtUtc;
        FinalScore = finalScore;
        AdmittedMembers = Array.AsReadOnly(admitted);
        AdmittedCharacterIds = Array.AsReadOnly(admitted.Select(member => member.CharacterId).ToArray());
        FrozenMembers = Array.AsReadOnly(members);
        CharacterIds = Array.AsReadOnly(members.Select(member => member.CharacterId).ToArray());
        Award = AtlantisCompletionRewardPolicy.Resolve(admitted.Length);
        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, Encoding.UTF8, leaveOpen: true))
        {
            writer.Write(AtlantisCompletionRewardPolicy.Revision);
            writer.Write(worldInstanceId.Value.ToByteArray());
            writer.Write(realmId.Value);
            writer.Write(admissionReservationId.ToByteArray());
            writer.Write(startedAtUtc.UtcTicks);
            writer.Write(completedAtUtc.UtcTicks);
            writer.Write(finalScore);
            writer.Write(Award.HardPoints);
            writer.Write(Award.TitleId);
            writer.Write(admitted.Length);
            foreach (var member in admitted)
            {
                writer.Write(member.AccountId);
                writer.Write(member.CharacterId);
            }
            writer.Write(members.Length);
            foreach (var member in members)
            {
                writer.Write(member.AccountId);
                writer.Write(member.CharacterId);
            }
        }
        RequestHash = Convert.ToHexString(SHA256.HashData(stream.ToArray()));
    }

    public WorldInstanceId WorldInstanceId { get; }
    public RealmId RealmId { get; }
    public Guid AdmissionReservationId { get; }
    public DateTimeOffset StartedAtUtc { get; }
    public DateTimeOffset CompletedAtUtc { get; }
    public TimeSpan Elapsed => CompletedAtUtc - StartedAtUtc;
    public int FinalScore { get; }
    public IReadOnlyList<AtlantisCompletionMember> AdmittedMembers { get; }
    public IReadOnlyList<int> AdmittedCharacterIds { get; }
    public IReadOnlyList<AtlantisCompletionMember> FrozenMembers { get; }
    public IReadOnlyList<int> CharacterIds { get; }
    public AtlantisCompletionRewardAward Award { get; }
    public string RequestHash { get; }

    private static bool IsValidRoster(AtlantisCompletionMember[] members) =>
        members.Length is >= 1 and <= 5 &&
        members.All(member => member.AccountId > 0 && member.CharacterId > 0) &&
        members.Select(member => member.AccountId).Distinct().Count() == members.Length &&
        members.Select(member => member.CharacterId).Distinct().Count() == members.Length;
}

internal enum AtlantisCompletionRewardStatus : byte
{
    Applied = 1,
    Duplicate = 2,
    RequestConflict = 3,
    AdmissionConflict = 4,
    CharacterUnavailable = 5
}

internal readonly record struct AtlantisCompletionRewardMember(int AccountId, int CharacterId,
    byte Camp, int HonorBefore, int HonorAfter, long RewardRevision, uint AwardedTitleId);

internal sealed record AtlantisCompletionRewardReceipt(AtlantisCompletionRewardStatus Status,
    WorldInstanceId WorldInstanceId, AtlantisCompletionRewardAward Award,
    IReadOnlyList<AtlantisCompletionRewardMember> Members)
{
    public bool Succeeded => Status is AtlantisCompletionRewardStatus.Applied or AtlantisCompletionRewardStatus.Duplicate;
}

internal interface IAtlantisCompletionRewardStore
{
    Task<AtlantisCompletionRewardReceipt> SettleAsync(AtlantisCompletionRewardRequest request,
        CancellationToken cancellationToken = default);
}
