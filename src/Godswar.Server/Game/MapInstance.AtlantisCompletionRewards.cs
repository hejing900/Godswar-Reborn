using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Game.WorldInstances;

namespace Godswar.Server.Game;

internal sealed partial class MapInstance
{
    private Guid _atlantisRewardReservation;
    private IReadOnlyDictionary<int, AtlantisCompletionMember> _atlantisRewardCandidates =
        new Dictionary<int, AtlantisCompletionMember>();
    private readonly HashSet<int> _atlantisRewardAdmissions = [];
    private AtlantisCompletionEvidence? _atlantisCompletionEvidence;

    internal void ConfigureAtlantisRewardAdmission(Guid reservationId,
        IReadOnlyList<LegacyInstancePartyMember> members)
    {
        lock (_atlantisEncounterGate)
        {
            if (reservationId == Guid.Empty || members.Count is < 1 or > 5 ||
                _atlantisRewardReservation != Guid.Empty && _atlantisRewardReservation != reservationId)
            {
                throw new InvalidOperationException("Invalid Atlantis admission reward identity.");
            }
            if (_atlantisRewardReservation != Guid.Empty) return;
            _atlantisRewardReservation = reservationId;
            _atlantisRewardCandidates = members.ToDictionary(member => member.CharacterId,
                member => new AtlantisCompletionMember(member.AccountId, member.CharacterId));
        }
    }

    internal void RecordAtlantisRewardAdmissions(Guid reservationId, IReadOnlyCollection<int> characterIds)
    {
        lock (_atlantisEncounterGate)
        {
            if (_atlantisRewardReservation != reservationId || _atlantisCompletionEvidence is not null) return;
            foreach (var characterId in characterIds)
            {
                if (_atlantisRewardCandidates.ContainsKey(characterId)) _atlantisRewardAdmissions.Add(characterId);
            }
        }
    }

    // Called by the world owner in the same mutation that commits point850.
    // Membership may change immediately afterwards without changing entitlement.
    private void FreezeAtlantisCompletionMembers(AtlantisRunSnapshot run)
    {
        if (_atlantisCompletionEvidence is not null || _atlantisRewardReservation == Guid.Empty) return;
        var admitted = _atlantisRewardAdmissions.Order().Select(id => _atlantisRewardCandidates[id]).ToArray();
        var eligible = Snapshot().Where(context => context.WorldReady &&
                context.WorldInstanceId == run.WorldInstanceId && context.Ownership.IsValid &&
                _atlantisRewardAdmissions.Contains(context.CharacterId) &&
                _atlantisRewardCandidates[context.CharacterId].AccountId == context.AccountId)
            .OrderBy(context => context.CharacterId)
            .Select(context => new AtlantisCompletionIdentity(context.AccountId, context.CharacterId,
                context.CharacterName, context.Character.Camp)).ToArray();
        if (eligible.Length == 0)
        {
            _atlantisCompletionEvidence = new(null, []);
            return;
        }
        _atlantisCompletionEvidence = new(new AtlantisCompletionRewardRequest(run.WorldInstanceId,
            Descriptor.RealmId, _atlantisRewardReservation, run.StartedAt.ToUniversalTime(),
            run.TerminalAt!.Value.ToUniversalTime(), run.TeamPoints, admitted,
            eligible.Select(member => new AtlantisCompletionMember(member.AccountId, member.CharacterId)).ToArray()),
            Array.AsReadOnly(eligible));
    }

    internal AtlantisCompletionEvidence? GetAtlantisCompletionEvidence()
    {
        lock (_atlantisEncounterGate) return _atlantisCompletionEvidence;
    }

    internal bool HasAdmittedAtlantisPetOwner(int accountId, int characterId)
    {
        lock (_atlantisEncounterGate)
        {
            return _atlantisRewardReservation != Guid.Empty &&
                _atlantisRewardAdmissions.Contains(characterId) &&
                _atlantisRewardCandidates.TryGetValue(characterId, out var member) &&
                member.AccountId == accountId &&
                TryGetAtlantisRunSnapshot(out _);
        }
    }
}

internal sealed record AtlantisCompletionIdentity(int AccountId, int CharacterId, string Name, byte Camp);
internal sealed record AtlantisCompletionEvidence(AtlantisCompletionRewardRequest? Request,
    IReadOnlyList<AtlantisCompletionIdentity> Members);
