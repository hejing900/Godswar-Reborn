using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Instances;

namespace Godswar.Server.ProtocolChecks;

internal static class AtlantisCompletionRewardPolicyChecks
{
    public const string CheckName = "Atlantis completion rewards preserve original admission and eligible finishers";

    public static Task RunAsync()
    {
        var instance = WorldInstanceId.New();
        var reservation = Guid.NewGuid();
        var start = new DateTimeOffset(2026, 9, 8, 0, 0, 0, TimeSpan.Zero);
        AtlantisCompletionMember[] admitted = [new(11, 101), new(12, 102)];
        var party = new AtlantisCompletionRewardRequest(instance, RealmId.Tempest, reservation,
            start, start.AddMinutes(20), 850, admitted, [admitted[0]]);
        Check.True(party.Award == new AtlantisCompletionRewardAward(2800, 5013, "Seabed Explorer") &&
            party.AdmittedMembers.Count == 2 && party.FrozenMembers.Count == 1,
            "one remaining finisher receives a party title while voluntary leavers are excluded");
        var solo = new AtlantisCompletionRewardRequest(WorldInstanceId.New(), RealmId.Tempest, Guid.NewGuid(),
            start, start.AddMinutes(1), 850, [admitted[0]], [admitted[0]]);
        Check.True(solo.Award == new AtlantisCompletionRewardAward(2800, 5014, "Deep Sea Hunter"),
            "actual solo admission grants the stock Deep Sea Hunter title and documented2800 HardPoints");
        var slow = new AtlantisCompletionRewardRequest(WorldInstanceId.New(), RealmId.Tempest, Guid.NewGuid(),
            start, start.AddMinutes(40).AddTicks(-1), 850, [admitted[0]], [admitted[0]]);
        Check.Equal(solo.Award, slow.Award, "completion time does not invent an undocumented HardPoints multiplier");
        var ordered = new AtlantisCompletionRewardRequest(instance, RealmId.Tempest, reservation,
            start, start.AddMinutes(20), 850, admitted.Reverse().ToArray(), [admitted[0]]);
        Check.Equal(party.RequestHash, ordered.RequestHash, "canonical evidence is independent of roster enumeration order");
        var changedFinisher = new AtlantisCompletionRewardRequest(instance, RealmId.Tempest, reservation,
            start, start.AddMinutes(20), 850, admitted, [admitted[1]]);
        Check.True(changedFinisher.RequestHash != party.RequestHash, "eligible finishers are bound into durable identity");
        admitted[0] = new(99, 999);
        Check.True(party.FrozenMembers[0] == new AtlantisCompletionMember(11, 101) && party.AdmittedMembers[0].CharacterId == 101,
            "caller mutations cannot change captured completion or original admission evidence");

        void Invalid(int score, TimeSpan duration, AtlantisCompletionMember[] original, AtlantisCompletionMember[] finishers) =>
            Check.Throws<ArgumentException>(() => new AtlantisCompletionRewardRequest(instance, RealmId.Tempest,
                reservation, start, start.Add(duration), score, original, finishers), "invalid Atlantis entitlement rejects before storage");
        AtlantisCompletionMember[] one = [new(11, 101)];
        Invalid(849, TimeSpan.FromMinutes(1), one, one);
        Invalid(851, TimeSpan.FromMinutes(1), one, one);
        Invalid(850, TimeSpan.FromMinutes(40), one, one);
        Invalid(850, TimeSpan.FromTicks(-1), one, one);
        Invalid(850, TimeSpan.FromMinutes(1), one, []);
        Invalid(850, TimeSpan.FromMinutes(1), one, [new(12, 101)]);
        Invalid(850, TimeSpan.FromMinutes(1), [one[0], one[0]], one);
        Invalid(850, TimeSpan.FromMinutes(1), Enumerable.Range(1, 6).Select(id => new AtlantisCompletionMember(id, id)).ToArray(), one);
        return Task.CompletedTask;
    }
}
