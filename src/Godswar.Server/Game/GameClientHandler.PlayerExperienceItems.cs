using Godswar.Server.Application.Pets;
using Godswar.Server.Packets;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private bool IsPlayerExperienceItemProjection(PetDurableReceipt receipt) =>
        receipt.Status is PetDurableReceiptStatus.PlayerExperienceAdded or
            PetDurableReceiptStatus.PlayerExperienceMaximumReached ||
        receipt.Status == PetDurableReceiptStatus.ConsumableCooldownActive &&
            _character is not null && receipt.KitBagSlot >= 0 &&
            KitBagSlots.GetItemId(_character.KitBag, receipt.KitBagSlot) == PlayerExperienceItemPolicy.ItemId;

    private async Task<bool> SendPlayerExperienceItemProjectionAsync(PetDurableReceipt receipt,
        PetDurableExecutionDisposition disposition, CancellationToken token)
    {
        if (_character is null) return false;
        if (receipt.Succeeded && KitBagSlots.GetItem(_character.KitBag, receipt.KitBagSlot).IsEmpty)
            await _session.SendAsync(PacketBuilder.StorageItemKitBagDelete(receipt.KitBagSlot), token,
                "PlayerExperiencePillConsumedSlotClear");
        await SendKitBagRefreshAsync(token);

        if (!receipt.Succeeded)
        {
            var message = receipt.Status == PetDurableReceiptStatus.ConsumableCooldownActive
                ? "The EXP Pill is cooling down. Please wait a moment."
                : "You cannot receive the full EXP reward at your current limit. Your EXP Pill was not consumed.";
            await _session.SendAsync(PacketBuilder.ServerNote(message), token, "PlayerExperiencePillRejected");
            return true;
        }

        var firstCommit = disposition == PetDurableExecutionDisposition.Committed;
        if (receipt.PlayerExperience is not { } evidence) return false;
        // Always project the freshly read character. A replay must never restore historical EXP.
        if (firstCommit && evidence.NewLevel != evidence.PreviousLevel)
        {
            var maximum = PlayerExperienceCatalog.GetClientExperienceMaximum(_character.Level, _character.FighterLevelSealed);
            await _session.SendAsync(PacketBuilder.PlayerLevelUp(LocalPlayerObjectId, _character.Level,
                maximum, _character.Experience, _character.MaxHp, _character.CurrentHp,
                _character.MaxMp, _character.CurrentMp), token, "PlayerExperiencePillLevelUp");
            await _registry.BroadcastToMapAsync(_character.CurrentMap,
                PacketBuilder.PlayerLevelUp(CurrentPlayerObjectId, _character.Level, maximum,
                    _character.Experience, _character.MaxHp, _character.CurrentHp, _character.MaxMp, _character.CurrentMp),
                token, _session, "PlayerExperiencePillLevelUpWorld");
        }
        await _session.SendAsync(PacketBuilder.ExperienceGain(firstCommit ? evidence.ExperienceGranted : 0,
            _character.Experience), token, "PlayerExperiencePillExperience");
        await _session.SendAsync(BuildLocalPlayerStatusUpdate(), token, "PlayerExperiencePillStatus");
        await _session.SendAsync(PacketBuilder.ServerNote(firstCommit
            ? "EXP Pill granted 1,000,000 character EXP."
            : "This EXP Pill was already used. Your current EXP and bag have been refreshed."),
            token, "PlayerExperiencePillResult");
        return true;
    }
}
