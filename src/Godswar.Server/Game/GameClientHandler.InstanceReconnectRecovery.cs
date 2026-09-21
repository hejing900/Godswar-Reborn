using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private byte? _unavailableInstanceReconnectMap;

    private void PrepareUnavailableInstanceReconnectRecovery()
    {
        if (_character is null ||
            _session.GatewayWorldAdmission is not null)
        {
            return;
        }

        var savedMap = _character.CurrentMap;
        ReviveTrace.Log($"PREPARE-RECONNECT savedMap={savedMap}");
        if (!GameDefaults.TryRecoverUnavailableInstanceLocation(
                _character))
        {
            ReviveTrace.Log("PREPARE-RECONNECT no-recovery");
            return;
        }

        ReviveTrace.Log($"PREPARE-RECONNECT recovered map={_character.CurrentMap} pos={_character.PositionX:F2},{_character.PositionZ:F2}");
        _unavailableInstanceReconnectMap = savedMap;
        _positionDirty = true;
    }

    private async Task<bool>
        PersistUnavailableInstanceReconnectRecoveryAsync(
            CancellationToken cancellationToken)
    {
        if (!_unavailableInstanceReconnectMap.HasValue)
        {
            return true;
        }
        if (_character is null)
        {
            _session.Disconnect();
            return false;
        }

        _character.MarkPositionChanged();
        if (!await PersistPositionCheckpointAsync(
                _character,
                force: true,
                cancellationToken))
        {
            _session.Disconnect();
            return false;
        }

        var recoveredMap = _unavailableInstanceReconnectMap.Value;
        _unavailableInstanceReconnectMap = null;
        _positionDirty = false;
        _lastPositionPersistUtc = DateTime.UtcNow;
        Console.WriteLine(
            "[instance] recovered unavailable saved instance " +
            $"character={_character.Name} map={recoveredMap}->" +
            $"{_character.CurrentMap}");
        return true;
    }
}
