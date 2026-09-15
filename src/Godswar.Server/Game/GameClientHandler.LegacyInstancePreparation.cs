using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private async Task<LegacyInstanceEntryPreparation?>
        TryPrepareLegacyInstanceEntryAsync(
        uint npcId,
        int dialogIndex,
        InstanceCallerEntryDestination destination,
        CancellationToken cancellationToken)
    {
        if (_character is null ||
            _character.CurrentHp <= 0 ||
            !TryResolveMapNpc(npcId, out var npc) ||
            !IsWithinInstanceCallerInteractionDistance(npc))
        {
            Console.Error.WriteLine(
                "[instance-caller] rejected stale entry authority " +
                $"character={_character?.Name ?? "<none>"} npc={npcId}");
            return null;
        }

        var schedule = LegacyInstanceAdmissionPolicy.CheckSchedule(
            destination.Kind,
            _realmCalendar,
            DateTimeOffset.UtcNow);
        if (schedule != LegacyInstanceScheduleStatus.Open)
        {
            await SendLegacyInstanceScheduleFailureAsync(
                npcId,
                schedule,
                cancellationToken);
            return null;
        }

        LegacyInstancePartySnapshot party;
        LegacyInstanceEntryStatus partyStatus;
        if (destination.Kind == InstanceCallerEntryKind.Atlantis &&
            destination.PaymentMode ==
                InstanceCallerEntryPaymentMode.OpalRetry)
        {
            partyStatus = _registry.TryRecordLegacyInstanceOpalRetryConsent(
                _session,
                destination,
                npc.X,
                npc.Z,
                InstanceCallerProtocol.MaximumInteractionDistance,
                DateTimeOffset.UtcNow,
                out party,
                out var requesterIsLeader);
            if (partyStatus == LegacyInstanceEntryStatus.Ready &&
                !requesterIsLeader)
            {
                await SendAtlantisOpalConsentRecordedAsync(
                    npcId,
                    cancellationToken);
                return null;
            }
        }
        else
        {
            partyStatus = _registry.TryCaptureLegacyInstanceParty(
                _session,
                destination,
                npc.X,
                npc.Z,
                InstanceCallerProtocol.MaximumInteractionDistance,
                out party);
        }
        if (partyStatus != LegacyInstanceEntryStatus.Ready)
        {
            await SendLegacyInstanceAdmissionFailureAsync(
                npcId,
                dialogIndex,
                destination.Kind,
                partyStatus,
                cancellationToken);
            return null;
        }

        return new(npc, party);
    }

    private sealed record LegacyInstanceEntryPreparation(
        NpcSpawnDefinition Npc,
        LegacyInstancePartySnapshot Party);
}
