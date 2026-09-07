using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private void InstallUpdatedCharacter(GameCharacter updated)
    {
        ArgumentNullException.ThrowIfNull(updated);
        if (updated.RealmId != _processRealmId)
        {
            throw new InvalidOperationException(
                "The refreshed character belongs to another realm.");
        }

        var current = _character;
        if (current is not null && current.Id == updated.Id)
        {
            if (current.RealmId != updated.RealmId)
            {
                throw new InvalidOperationException(
                    "A character refresh cannot change realms.");
            }

            updated.CurrentMap = current.CurrentMap;
            updated.PositionX = current.PositionX;
            updated.PositionZ = current.PositionZ;
            updated.PositionRevision = Math.Max(
                updated.PositionRevision,
                current.PositionRevision);
            InstallUpdatedCharacterVitals(current, updated);
            updated.CheckpointOwnerId =
                current.CheckpointOwnerId;
            updated.CheckpointOwnerGeneration =
                current.CheckpointOwnerGeneration;
            updated.FashionHidden =
                ResolveFashionHiddenAfterEquipmentChange(
                    current,
                    updated);
            updated.EquipmentEffectsVisible =
                current.EquipmentEffectsVisible;
        }

        _character = updated;
    }

    private static void InstallUpdatedCharacterVitals(
        GameCharacter current,
        GameCharacter updated)
    {
        lock (current.VitalsSync)
        {
            var currentHp = current.CurrentHp;
            var currentMp = current.CurrentMp;
            if (current.CalculatedStats is not null &&
                updated.CalculatedStats is null)
            {
                // Legacy bag and wallet writes reload only base character
                // columns. Once a session owns a calculated projection, that
                // base-only result has no authority to replace its maxima or
                // live vitals.
                updated.MaxHp = current.MaxHp;
                updated.MaxMp = current.MaxMp;
                updated.CurrentHp = currentHp;
                updated.CurrentMp = currentMp;
                updated.CalculatedStats = current.CalculatedStats;
                updated.VitalsRevision = current.VitalsRevision;
                return;
            }

            updated.CurrentHp = Math.Clamp(
                currentHp,
                0,
                Math.Max(1, updated.MaxHp));
            updated.CurrentMp = Math.Clamp(
                currentMp,
                0,
                Math.Max(0, updated.MaxMp));
            updated.VitalsRevision = Math.Max(
                updated.VitalsRevision,
                current.VitalsRevision);
            if (updated.CurrentHp != currentHp ||
                updated.CurrentMp != currentMp)
            {
                updated.MarkVitalsChanged();
            }
        }
    }
}
