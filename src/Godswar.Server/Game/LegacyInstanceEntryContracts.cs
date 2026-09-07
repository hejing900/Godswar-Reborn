using Godswar.Server.Application.Characters;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Networking;

namespace Godswar.Server.Game;

internal enum LegacyInstanceEntryStatus : byte
{
    Ready = 1,
    LeaderRequired = 2,
    PartyUnavailable = 3,
    PartyTooSmall = 4,
    PartyTooLarge = 5,
    LevelRequirementNotMet = 6,
    RuntimeUnavailable = 7,
    TransferFailed = 8,
    ScheduleClosed = 9
}

internal sealed record LegacyInstancePartySnapshot(
    long? PartyId,
    RealmId RealmId,
    int LeaderCharacterId,
    IReadOnlyList<LegacyInstancePartyMember> Members);

internal sealed record LegacyInstancePartyMember(
    ClientSession Session,
    int AccountId,
    int CharacterId,
    string CharacterName,
    int Level,
    RealmId RealmId,
    WorldInstanceId SourceWorldInstanceId,
    byte SourceMapId,
    PlayerOwnershipFence Ownership);
