using System.Buffers.Binary;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private async Task HandleMedusaLeaderPanelActionAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        const byte terminateAction = 0;
        if (packet.Length != 6 ||
            packet.Buffer.Length != 6 ||
            packet.Payload[0] != terminateAction)
        {
            Console.WriteLine(
                "[instance] ignored unsupported Medusa panel action " +
                $"len={packet.Length} hex={packet.ToHexPreview()}");
            return;
        }

        if (await TryHandleAtlantisTerminationAsync(null, 0, cancellationToken))
        {
            return;
        }

        if (await TryHandleWonderlandTerminationAsync(null, 0, cancellationToken))
        {
            return;
        }

        if (await TryHandleHarborAttackTerminationAsync(null, 0, cancellationToken))
        {
            return;
        }

        // A completed run's leader closes its completion countdown with the same
        // reset the completed-run leave publishes; a run that was ended early
        // keeps the leave countdown panel the tick published instead.
        var closingCompletionCountdown =
            _registry.IsMedusaRunCompleted(_session);
        if (!_registry.TryTerminateMedusaRunFromLeader(
                _session,
                DateTimeOffset.UtcNow))
        {
            // The run may already be terminal, and this same control is then the
            // member's own "leave the instance" during the countdown.
            if (_registry.TryRequestImmediateMedusaTerminationExit(_session))
            {
                Console.WriteLine(
                    "[instance] Medusa end-window leave character=" +
                    $"{_character?.Name ?? "<none>"}");
                return;
            }
            Console.WriteLine(
                "[instance] rejected non-authoritative Medusa " +
                "terminate action");
            return;
        }
        if (closingCompletionCountdown)
        {
            await _session.SendAsync(
                PacketBuilder.RepetitionReset(),
                cancellationToken,
                "MedusaLeaderInstanceTerminate");
        }
    }

    private async Task HandleMedusaLeaderEndAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (packet.Length != 12 || packet.Buffer.Length != 12)
        {
            Console.Error.WriteLine(
                "[instance] rejected malformed Medusa end request");
            return;
        }

        var repetitionId = BinaryPrimitives.ReadInt32LittleEndian(
            packet.Payload);
        var repetitionIndex = BinaryPrimitives.ReadInt32LittleEndian(
            packet.Payload.Slice(sizeof(int)));
        if (await TryHandleAtlantisTerminationAsync(repetitionId, repetitionIndex, cancellationToken))
        {
            return;
        }
        if (await TryHandleWonderlandTerminationAsync(repetitionId, repetitionIndex, cancellationToken))
        {
            return;
        }
        if (await TryHandleHarborAttackTerminationAsync(repetitionId, repetitionIndex, cancellationToken))
        {
            return;
        }
        var closingCompletionCountdown =
            _registry.IsMedusaRunCompleted(_session);
        if (!_registry.TryEndMedusaRunFromLeader(
                _session,
                repetitionId,
                repetitionIndex,
                DateTimeOffset.UtcNow))
        {
            if (_registry.TryRequestImmediateMedusaTerminationExit(_session))
            {
                Console.WriteLine(
                    "[instance] Medusa end-window leave character=" +
                    $"{_character?.Name ?? "<none>"}");
                return;
            }
            Console.WriteLine(
                "[instance] rejected non-authoritative Medusa end request " +
                $"repetition={repetitionId} index={repetitionIndex}");
            return;
        }

        // A completed run's leader closes its completion countdown; a run that
        // was ended early keeps the leave countdown panel instead.
        if (closingCompletionCountdown)
        {
            await _session.SendAsync(
                PacketBuilder.RepetitionReset(),
                cancellationToken,
                "MedusaLeaderInstanceEnd");
        }
    }
}
