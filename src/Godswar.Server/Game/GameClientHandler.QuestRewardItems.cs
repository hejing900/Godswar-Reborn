using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// How long the client may take to announce the reward item it paid itself.
    /// </summary>
    /// <remarks>
    /// The installed client pays the slot and announces it on opcode 10056 in the
    /// same breath as it handles the hand-in acknowledgement - the captured pair
    /// is 0 ms apart - so a short window is all the match needs. Keeping it short
    /// is also what makes the match safe: a relog's bag synchronisation replays
    /// every owned item on the same opcode, and a stale promise would let such a
    /// replay pay an item the character already owns.
    /// </remarks>
    private const int QuestRewardAnnouncementSeconds = 120;

    /// <summary>
    /// The reward items the last hand-in promised, while the client's own
    /// announcement of the item it paid is still expected.
    /// </summary>
    private QuestRewardOffer? _pendingQuestRewardOffer;

    private sealed record QuestRewardOffer(
        uint QuestId,
        IReadOnlyList<QuestRewardItem> Items,
        DateTimeOffset ExpiresAt);

    /// <summary>
    /// Remembers what the hand-in answer just offered, so the item the client
    /// announces next can be matched against this server's own promise instead of
    /// against whatever the client claims.
    /// </summary>
    /// <remarks>
    /// The built-in menu is accepted as well as the current one, because the client
    /// keeps the reward menu it was shown when it accepted the quest: a quest
    /// accepted before the GM tool changed its reward is handed in with the old
    /// item, and refusing that would silently drop the reward the client already
    /// paid into its own bag. A quest accepted after the change still announces the
    /// replaced item, which matches the current menu.
    /// </remarks>
    private void OfferQuestRewardItems(uint questId)
    {
        var items = new List<QuestRewardItem>(
            QuestRewardItemCatalog.Resolve(questId));
        foreach (var builtIn in QuestRewardItemCatalog.ResolveBuiltIn(questId))
        {
            if (!items.Any(item => item.ItemId == builtIn.ItemId))
            {
                items.Add(builtIn);
            }
        }

        _pendingQuestRewardOffer = items.Count == 0
            ? null
            : new QuestRewardOffer(
                questId,
                items,
                DateTimeOffset.UtcNow.AddSeconds(
                    QuestRewardAnnouncementSeconds));
    }

    /// <summary>
    /// Pays a quest reward item the client announced on opcode 10056.
    /// </summary>
    /// <remarks>
    /// The client grants the reward into its own bag, so without this write the
    /// item exists only there and the next relog replaces the bag with this
    /// server's copy - the item disappears. The claim is checked against the slot
    /// the answer offered, and the durable claim row makes the slot payable once
    /// however often the announcement arrives.
    /// </remarks>
    private async Task<bool> TryHandleQuestRewardItemGrantAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (packet.Payload.Length != GameClientHandler.GroundLootPickupPayloadBytes ||
            !TryReadGroundLootPickup(
                packet.Payload,
                out var bagSlot,
                out var itemId,
                out _,
                out _))
        {
            return false;
        }

        return await TryHandleQuestRewardItemGrantAsync(
            packet,
            bagSlot,
            itemId,
            cancellationToken);
    }

    /// <summary>
    /// Pays the reward item a hand-in promised, named either by the 40-byte 10056
    /// descriptor or by the 52-byte 10114 announcement.
    /// </summary>
    private async Task<bool> TryHandleQuestRewardItemGrantAsync(
        GamePacket packet,
        int bagSlot,
        uint itemId,
        CancellationToken cancellationToken)
    {
        if (_account is null || _character is null ||
            _pendingQuestRewardOffer is not { } offer)
        {
            return false;
        }

        if (DateTimeOffset.UtcNow >= offer.ExpiresAt)
        {
            _pendingQuestRewardOffer = null;
            return false;
        }

        var slotIndex = -1;
        var attributes = ItemGrantAttributes.None;
        foreach (var item in offer.Items)
        {
            if (item.ItemId == itemId)
            {
                slotIndex = item.SlotIndex;
                attributes = item.Attributes;
                break;
            }
        }

        // A menu the client cached before the GM tool changed this quest's reward
        // can name an item that is in neither the current menu nor the one the quest
        // shipped with - it paid that item into its own bag, and refusing it would
        // lose the reward silently. Anything the pinned content recognises is
        // therefore paid once per quest under the last slot, which is what makes the
        // reward the player actually received survive a relog. The store still
        // refuses an item outside that content, so the net is bounded.
        var staleMenu = slotIndex < 0;
        if (staleMenu)
        {
            slotIndex = QuestRewardItemCatalog.MaximumSlots - 1;
        }

        var result = await _monsterRewardExtras.GrantQuestRewardItemAsync(
            _account.Id,
            _character.Id,
            offer.QuestId,
            slotIndex,
            itemId,
            quantity: 1,
            attributes,
            cancellationToken);
        if (result.Character is not null)
        {
            InstallUpdatedCharacter(result.Character);
            _registry.UpdateCharacter(
                _session,
                _character,
                advanceWorldRevision: false);
        }

        switch (result.Status)
        {
            case QuestRewardItemGrantStatus.Added:
            case QuestRewardItemGrantStatus.Duplicate:
                _pendingQuestRewardOffer = null;
                Console.WriteLine(
                    $"[quest-reward] item paid character={_character.Name} " +
                    $"quest={offer.QuestId} slot={slotIndex} item={itemId} " +
                    $"announced-slot={bagSlot} stale-menu={staleMenu} " +
                    $"status={result.Status}");
                // A 40-byte 10056 announcement is answered with its own
                // descriptor; the 52-byte 10114 one has nothing to echo, so the
                // authoritative bag is the whole answer.
                if (packet.Buffer.Length ==
                    GameClientHandler.GroundLootPickupPayloadBytes + 4)
                {
                    await _session.SendAsync(
                        PacketBuilder.BagItemActionAck(packet.Buffer),
                        cancellationToken,
                        "QuestRewardItemAck");
                }

                await SendKitBagRefreshAsync(cancellationToken);
                return true;
            case QuestRewardItemGrantStatus.InsufficientCapacity:
                // The bag is full: the reward stays unclaimed, so the slot can
                // still be paid once the character has room. The refresh is what
                // tells the client its own copy is not the authoritative one.
                Console.Error.WriteLine(
                    $"[quest-reward] bag full character={_character.Name} " +
                    $"quest={offer.QuestId} slot={slotIndex} item={itemId}");
                await SendKitBagRefreshAsync(cancellationToken);
                return true;
            default:
                Console.Error.WriteLine(
                    $"[quest-reward] item refused character={_character.Name} " +
                    $"quest={offer.QuestId} slot={slotIndex} item={itemId} " +
                    $"status={result.Status}");
                _pendingQuestRewardOffer = null;
                return false;
        }
    }
}
