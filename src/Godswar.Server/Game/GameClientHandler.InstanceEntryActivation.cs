using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private async Task ActivatePendingInstanceEntryAsync(PendingInstanceEntry pending,
        CancellationToken cancellationToken)
    {
        if (PendingInstanceEntryAuthorityFailure(pending) is { } authorityFailure)
        {
            ClearPendingInstanceEntryConsent(pending);
            await RejectPendingInstanceEntryAsync(pending, authorityFailure,
                EntryAuthorityMessage(authorityFailure), cancellationToken);
            return;
        }

        // These are the original durable admission paths: they re-read the
        // schedule/day, claim limits, settle explicit payment consent and
        // revalidate ownership before transferring any admitted participant.
        if (pending.Destination is { } legacyDestination)
        {
            var result = await HandleLegacyInstanceEntryAsync(pending.NpcId, pending.DialogIndex,
                legacyDestination, pending.Legacy!, cancellationToken);
            if (!_session.IsDisconnected && _registry.TryGetSessionWorldInstanceId(_session, out var current) &&
                current == pending.Legacy!.Party.Members[0].SourceWorldInstanceId)
                await RejectPendingInstanceEntryAsync(pending, result.Outcome.ToString(),
                    LegacyEntryRejectionMessage(pending, result), cancellationToken);
            return;
        }
        var status = await BeginMedusaLeaderEntryAsync(pending.MedusaParty!, pending.Difficulty,
            pending.TargetMapId, cancellationToken);
        if (status != MedusaPartyEntryStatus.Ready)
        {
            await RejectPendingInstanceEntryAsync(pending, $"Medusa:{status}", null, cancellationToken);
            await SendInstanceCallerFailureAsync(pending.NpcId, pending.DialogIndex, status, cancellationToken);
        }
    }
}
