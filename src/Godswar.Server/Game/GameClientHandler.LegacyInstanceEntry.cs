using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Domain.World.Instances;
using Godswar.Server.Game.WorldInstances;
using Godswar.Server.Packets;
using WorldMapId = Godswar.Server.Domain.World.Instances.MapId;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private const string LegacyInstanceUnavailableMessage =
        "The instance is temporarily unavailable.";

    private async Task HandleLegacyInstanceEntryAsync(
        uint npcId,
        int dialogIndex,
        InstanceCallerEntryDestination destination,
        CancellationToken cancellationToken)
    {
        var preparation = await TryPrepareLegacyInstanceEntryAsync(
            npcId,
            dialogIndex,
            destination,
            cancellationToken);
        if (preparation is null)
        {
            return;
        }
        var npc = preparation.Npc;
        var party = preparation.Party;
        var paidIntent = destination.PaymentMode ==
            InstanceCallerEntryPaymentMode.OpalRetry;

        var startedAt = DateTimeOffset.UtcNow;
        var reservationId = Guid.NewGuid();
        LegacyInstanceDailyEntryClaimResult? claimResult;
        try
        {
            claimResult = await TryClaimLegacyInstanceDailyEntryAsync(
                reservationId,
                party.RealmId,
                _realmCalendar.GetDay(startedAt),
                destination.Kind,
                party.Members
                    .Select(static member => member.CharacterId)
                    .ToArray(),
                startedAt,
                cancellationToken);
        }
        catch (OperationCanceledException)
            when (cancellationToken.IsCancellationRequested)
        {
            if (paidIntent)
            {
                _registry.ClearLegacyInstanceOpalRetryConsents(party);
            }
            await ReleaseLegacyInstanceDailyEntryAsync(reservationId);
            throw;
        }
        if (claimResult is null)
        {
            if (paidIntent)
            {
                _registry.ClearLegacyInstanceOpalRetryConsents(party);
            }
            await SendLegacyInstanceUnavailableAsync(cancellationToken);
            return;
        }
        if (claimResult.Status ==
            LegacyInstanceDailyEntryClaimStatus.AlreadyUsed)
        {
            if (paidIntent)
            {
                _registry.ClearLegacyInstanceOpalRetryConsents(party);
            }
            await SendLegacyInstanceDailyEntryUsedAsync(
                npcId,
                destination.Kind,
                cancellationToken);
            return;
        }

        var paymentRequired = RequiresOpalPayment(claimResult);
        if (paymentRequired != paidIntent)
        {
            if (paidIntent)
            {
                _registry.ClearLegacyInstanceOpalRetryConsents(party);
            }
            await ReleaseLegacyInstanceDailyEntryAsync(reservationId);
            await SendAtlantisEntryPolicyAsync(
                npcId,
                cancellationToken);
            return;
        }
        if (paymentRequired &&
            (_legacyInstanceDailyEntries is null ||
             _legacyInstanceOpalPayments is null))
        {
            _registry.ClearLegacyInstanceOpalRetryConsents(party);
            await ReleaseLegacyInstanceDailyEntryAsync(reservationId);
            await SendLegacyInstanceUnavailableAsync(cancellationToken);
            return;
        }
        if (paymentRequired)
        {
            var consentStatus = _registry
                .TryConsumeLegacyInstanceOpalRetryConsents(
                    party,
                    destination,
                    npc.X,
                    npc.Z,
                    InstanceCallerProtocol.MaximumInteractionDistance,
                    claimResult.PaymentRequiredCharacterIds,
                    DateTimeOffset.UtcNow,
                    out _);
            if (consentStatus !=
                LegacyInstanceOpalConsentValidationStatus.Ready)
            {
                await ReleaseLegacyInstanceDailyEntryAsync(reservationId);
                if (consentStatus ==
                    LegacyInstanceOpalConsentValidationStatus
                        .MissingConsent)
                {
                    await SendAtlantisOpalConsentMissingAsync(
                        npcId,
                        cancellationToken);
                }
                else
                {
                    _registry.ClearLegacyInstanceOpalRetryConsents(party);
                    await SendLegacyInstanceUnavailableAsync(
                        cancellationToken);
                }
                return;
            }
        }

        WorldInstanceRuntimeDirectoryResult creation;
        try
        {
            creation = await _registry.CreateLocalWorldInstanceAsync(
                party.RealmId,
                new WorldMapId(checked((short)destination.TargetMapId)),
                InstanceKind.Dungeon,
                party.Members.Count,
                cancellationToken);
        }
        catch (OperationCanceledException)
            when (cancellationToken.IsCancellationRequested)
        {
            await ReleaseLegacyInstanceDailyEntryAsync(reservationId);
            throw;
        }
        catch (Exception error)
        {
            await ReleaseLegacyInstanceDailyEntryAsync(reservationId);
            Console.Error.WriteLine(
                "[instance-caller] runtime creation failed " +
                $"destination={destination.DisplayName}: {error.Message}");
            await SendLegacyInstanceUnavailableAsync(
                cancellationToken);
            return;
        }

        var target = creation.Runtime?.Descriptor;
        if (creation.Status != WorldInstanceRuntimeDirectoryStatus.Created ||
            target is null)
        {
            await ReleaseLegacyInstanceDailyEntryAsync(reservationId);
            Console.Error.WriteLine(
                "[instance-caller] runtime creation rejected " +
                $"destination={destination.DisplayName} " +
                $"status={creation.Status}/{creation.PlacementStatus}");
            await SendLegacyInstanceUnavailableAsync(
                cancellationToken);
            return;
        }

        if (!_registry.IsLegacyInstancePartySnapshotCurrent(
                party,
                destination,
                npc.X,
                npc.Z,
                InstanceCallerProtocol.MaximumInteractionDistance))
        {
            await CleanupFailedLegacyInstanceLaunchAsync(
                target,
                reservationId);
            await SendLegacyInstanceUnavailableAsync(
                CancellationToken.None);
            return;
        }

        var opalsCharged = false;
        if (paymentRequired)
        {
            LegacyInstanceOpalChargeResult? charge;
            try
            {
                charge = await TryChargeLegacyInstanceOpalsAsync(
                    reservationId,
                    party,
                    claimResult,
                    DateTimeOffset.UtcNow,
                    cancellationToken);
            }
            catch (OperationCanceledException)
                when (cancellationToken.IsCancellationRequested)
            {
                _ = await SettleLegacyInstanceOpalsAsync(
                    reservationId,
                    party,
                    Array.Empty<int>());
                await RetireFailedLegacyInstanceRuntimeAsync(target);
                throw;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine(
                    "[instance-caller] Atlantis Opal charge failed " +
                    $"reservation={reservationId}: {error.Message}");
                _ = await SettleLegacyInstanceOpalsAsync(
                    reservationId,
                    party,
                    Array.Empty<int>());
                await RetireFailedLegacyInstanceRuntimeAsync(target);
                await SendLegacyInstanceUnavailableAsync(
                    CancellationToken.None);
                return;
            }

            if (charge is null ||
                charge.Status != LegacyInstanceOpalChargeStatus.Charged)
            {
                await CleanupFailedLegacyInstanceLaunchAsync(
                    target,
                    reservationId);
                if (charge?.Status ==
                    LegacyInstanceOpalChargeStatus.InsufficientOpal)
                {
                    await SendAtlantisInsufficientOpalAsync(
                        npcId,
                        CancellationToken.None);
                }
                else
                {
                    await SendLegacyInstanceUnavailableAsync(
                        CancellationToken.None);
                }
                return;
            }

            opalsCharged = true;
            var chargeProjected = false;
            try
            {
                chargeProjected =
                    await ProjectLegacyInstanceOpalMutationsAsync(
                        party,
                        charge.Mutations);
            }
            catch (Exception error)
            {
                Console.Error.WriteLine(
                    "[instance-caller] Atlantis Opal charge projection " +
                    $"failed reservation={reservationId}: {error.Message}");
            }
            if (!chargeProjected)
            {
                _ = await SettleLegacyInstanceOpalsAsync(
                    reservationId,
                    party,
                    Array.Empty<int>());
                await RetireFailedLegacyInstanceRuntimeAsync(target);
                await SendLegacyInstanceUnavailableAsync(
                    CancellationToken.None);
                return;
            }
        }

        if (!_registry.IsLegacyInstancePartySnapshotCurrent(
                party,
                destination,
                npc.X,
                npc.Z,
                InstanceCallerProtocol.MaximumInteractionDistance))
        {
            if (opalsCharged)
            {
                _ = await SettleLegacyInstanceOpalsAsync(
                    reservationId,
                    party,
                    Array.Empty<int>());
                await RetireFailedLegacyInstanceRuntimeAsync(target);
            }
            else
            {
                await CleanupFailedLegacyInstanceLaunchAsync(
                    target,
                    reservationId);
            }
            await SendLegacyInstanceUnavailableAsync(
                CancellationToken.None);
            return;
        }

        var leader = party.Members[0];
        var leaderCommand = BuildLegacyInstanceTransitionCommand(
            leader,
            target.InstanceId,
            destination);
        bool leaderMoved;
        try
        {
            leaderMoved = (destination.Kind != InstanceCallerEntryKind.Atlantis ||
                _registry.TryStartAtlantisEncounter(target.InstanceId,
                    claimResult.DailyEntryLimit ?? 1,
                    party.Members.Select(static member => (member.CharacterId, member.Level)).ToArray(),
                    DateTimeOffset.UtcNow, reservationId, party.Members)) &&
                await TryBeginAuthoritativeInstanceTransitionAsync(
                    leaderCommand,
                    cancellationToken);
        }
        catch (OperationCanceledException)
            when (cancellationToken.IsCancellationRequested)
        {
            var leaderEntered = _registry.IsSessionInWorldInstance(
                _session,
                target.InstanceId);
            if (leaderEntered)
            {
                _ = await RecordLegacyInstanceAdmissionsAsync(
                    reservationId,
                    new[] { leader.CharacterId });
            }
            if (opalsCharged)
            {
                _ = await SettleLegacyInstanceOpalsAsync(
                    reservationId,
                    party,
                    leaderEntered
                        ? new[] { leader.CharacterId }
                        : Array.Empty<int>());
                if (!leaderEntered)
                {
                    await RetireFailedLegacyInstanceRuntimeAsync(target);
                }
            }
            else if (!leaderEntered)
            {
                await CleanupFailedLegacyInstanceLaunchAsync(
                    target,
                    reservationId);
            }
            else
            {
                await ReleaseLegacyInstanceDailyEntryMembersAsync(
                    reservationId,
                    party.Members
                        .Skip(1)
                        .Select(static member => member.CharacterId)
                        .ToArray());
            }
            throw;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(
                "[instance-caller] leader transfer fault " +
                $"destination={destination.DisplayName}: {error.Message}");
            leaderMoved = false;
        }

        if (!leaderMoved)
        {
            var leaderEntered = _registry.IsSessionInWorldInstance(
                _session,
                target.InstanceId);
            if (leaderEntered)
            {
                _ = await RecordLegacyInstanceAdmissionsAsync(
                    reservationId,
                    new[] { leader.CharacterId });
            }
            if (opalsCharged)
            {
                _ = await SettleLegacyInstanceOpalsAsync(
                    reservationId,
                    party,
                    leaderEntered
                        ? new[] { leader.CharacterId }
                        : Array.Empty<int>());
                if (!leaderEntered)
                {
                    await RetireFailedLegacyInstanceRuntimeAsync(target);
                }
            }
            else if (!leaderEntered)
            {
                await CleanupFailedLegacyInstanceLaunchAsync(
                    target,
                    reservationId);
            }
            else
            {
                await ReleaseLegacyInstanceDailyEntryMembersAsync(
                    reservationId,
                    party.Members
                        .Skip(1)
                        .Select(static member => member.CharacterId)
                        .ToArray());
                Console.Error.WriteLine(
                    "[instance-caller] leader entered before transfer " +
                    $"publication failed instance={target.InstanceId}; " +
                    "leader claim retained and member claims released");
            }
            await SendLegacyInstanceUnavailableAsync(
                CancellationToken.None);
            return;
        }

        _ = await RecordLegacyInstanceAdmissionsAsync(
            reservationId,
            new[] { leader.CharacterId });

        var failedMembers = new List<LegacyInstancePartyMember>();
        foreach (var member in party.Members.Skip(1))
        {
            if (!_registry.IsLegacyInstancePartyMemberSnapshotCurrent(
                    party,
                    member,
                    npc.X,
                    npc.Z,
                    InstanceCallerProtocol.MaximumInteractionDistance))
            {
                failedMembers.Add(member);
                Console.Error.WriteLine(
                    "[instance-caller] member changed party or source " +
                    $"before transfer character={member.CharacterName}");
                continue;
            }

            var command = BuildLegacyInstanceTransitionCommand(
                member,
                target.InstanceId,
                destination);
            bool moved;
            try
            {
                moved = await _registry
                    .TransitionPartyMemberToAuthoritativeInstanceAsync(
                        member.Session,
                        command,
                        CancellationToken.None);
            }
            catch (Exception error)
            {
                Console.Error.WriteLine(
                    "[instance-caller] member transfer fault " +
                    $"character={member.CharacterName}: {error.Message}");
                moved = false;
            }

            if (!moved && _registry.IsSessionInWorldInstance(
                    member.Session,
                    target.InstanceId))
            {
                moved = true;
                Console.Error.WriteLine(
                    "[instance-caller] member entered before transfer " +
                    "publication failed; claim and Opal retained " +
                    $"character={member.CharacterName}");
            }

            if (!moved)
            {
                failedMembers.Add(member);
            }
            else
            {
                _ = await RecordLegacyInstanceAdmissionsAsync(
                    reservationId,
                    new[] { member.CharacterId });
            }
        }

        if (failedMembers.Count != 0)
        {
            if (!opalsCharged)
            {
                await ReleaseLegacyInstanceDailyEntryMembersAsync(
                    reservationId,
                    failedMembers
                        .Select(static member => member.CharacterId)
                        .ToArray());
            }
            await SendLegacyInstanceUnavailableAsync(
                CancellationToken.None);
        }

        if (opalsCharged)
        {
            var failedCharacterIds = failedMembers
                .Select(static member => member.CharacterId)
                .ToHashSet();
            _ = await SettleLegacyInstanceOpalsAsync(
                reservationId,
                party,
                party.Members
                    .Where(member =>
                        !failedCharacterIds.Contains(member.CharacterId))
                    .Select(static member => member.CharacterId)
                    .ToArray());
        }

        Console.WriteLine(
            "[instance-caller] instance admitted " +
            $"leader={leader.CharacterName} " +
            $"destination={destination.DisplayName} " +
            $"instance={target.InstanceId} party={party.Members.Count} " +
            $"member-transfer-failures={failedMembers.Count}");
    }

}
