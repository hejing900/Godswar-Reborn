using System.Buffers.Binary;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
<<<<<<< HEAD
    /// <summary>
    /// Answers the client's corpse click (C2S 10050, 16-byte payload) so the
    /// client opens that corpse's loot window and only then requests the drop.
    /// The installed client sends no pickup at all until this reply arrives,
    /// and the reply has to echo the clicked drop index: capture shows
    /// `{corpseObjectId, 0, dropIndex, 0}` answered by
    /// `{playerObjectId, corpseObjectId, dropIndex}`.
    /// </summary>
    private async Task<bool> TryHandleGroundLootSourceAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_character is null || packet.Payload.Length != 16)
        {
            return false;
        }

        var corpseObjectId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload);
        var dropIndex = BinaryPrimitives.ReadInt32LittleEndian(
            packet.Payload.Slice(8));
        if (corpseObjectId == 0 ||
            !_registry.HasPendingMonsterLoot(
                _session,
                corpseObjectId,
                dropIndex))
        {
            return false;
        }

        MonsterLootTrace.Log(
            $"source-open character={_character.Name} corpse={corpseObjectId} dropIndex={dropIndex}");
        await _session.SendAsync(
            PacketBuilder.MonsterLootSourceOpen(
                LocalPlayerObjectId,
                corpseObjectId,
                dropIndex),
            cancellationToken,
            "MonsterLootSourceOpen");
        return true;
    }

    /// <summary>
    /// The installed client picks ground loot up on 10056 with the captured
    /// 40-byte bag/ground descriptor, not on 10048. Captured 2026-09-15: the
    /// request names the destination bag slot at +12/+16, the item at +20 and
    /// echoes the ground identity at +32/+36; the reference server answered by
    /// echoing the same descriptor with the ground identity it matched.
    /// A bag-to-equipment move uses the same opcode, so the pickup path only
    /// claims a request that names a free slot and matches a pending ground item.
    /// </summary>
    private async Task<bool> TryHandleGroundLootPickupAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        const int DescriptorLength = 40;
        if (_account is null || _character is null ||
            packet.Buffer.Length != DescriptorLength ||
            !TryReadGroundLootPickup(
                packet.Payload,
                out var slot,
                out var itemId,
                out var groundKeyHigh,
                out var groundKeyLow))
        {
            return false;
        }

        if (MatchesCurrentKitBagItem(_character, slot, itemId) ||
            !_registry.TryReserveGroundLootPickup(
                _session,
                itemId,
                groundKeyHigh,
                groundKeyLow,
                DateTimeOffset.UtcNow,
                out var reservation))
        {
            MonsterLootTrace.Log(
                $"pickup-unmatched character={_character.Name} slot={slot} item={itemId} key={groundKeyHigh:X8}:{groundKeyLow:X8}");
            return false;
        }

        MonsterLootTrace.Log(
            $"pickup-reserved character={_character.Name} slot={slot} item={itemId} corpse={reservation.MonsterObjectId} quantity={reservation.Quantity}");

        var completed = false;
        try
        {
            var result = await _monsterRewardExtras.PickupMonsterLootAsync(
                _account.Id,
                _character.Id,
                reservation.DeathEventId,
                reservation.RuleLootIndex,
                reservation.ItemId,
                reservation.Quantity,
                cancellationToken);
            if (!result.Succeeded || result.Character is null ||
                !RevalidateCurrentWorldEffectOwnership("ground_loot_pickup"))
            {
                if (result.Status ==
                    MonsterLootPickupStatus.InsufficientCapacity)
                {
                    await SendKitBagRefreshAsync(cancellationToken);
                }
                return true;
            }

            InstallUpdatedCharacter(result.Character);
            _registry.UpdateCharacter(
                _session,
                _character,
                advanceWorldRevision: false);
            await _session.SendAsync(
                BuildGroundLootPickupAck(packet.Buffer, reservation),
                cancellationToken,
                "GroundLootPickupAck");
            await SendKitBagRefreshAsync(cancellationToken);
            _registry.CompleteMonsterLootPickup(reservation);
            completed = true;
            MonsterLootTrace.Log(
                $"picked character={_character.Name} item={reservation.ItemId} quantity={reservation.Quantity} slot={slot} corpse={reservation.MonsterObjectId}");
        }
        finally
        {
            if (!completed)
            {
                _registry.ReleaseMonsterLootPickup(reservation);
            }
        }

        return true;
    }

    private static byte[] BuildGroundLootPickupAck(
        ReadOnlySpan<byte> requestPacket,
        MonsterLootPickupReservation reservation)
    {
        var response = requestPacket.ToArray();
        var groundKey = MonsterLootGroundKey.Resolve(
            reservation.DeathEventId,
            reservation.RuleLootIndex);
        BinaryPrimitives.WriteUInt32LittleEndian(
            response.AsSpan(32, 4),
            groundKey.High);
        BinaryPrimitives.WriteUInt32LittleEndian(
            response.AsSpan(36, 4),
            groundKey.Low);
        return response;
    }

=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
    private async Task HandleMonsterLootPickupAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_account is null || _character is null ||
            packet.Payload.Length != 12)
        {
            return;
        }

        var playerObjectId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload);
        var monsterObjectId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload.Slice(4));
        var pickupIndex = BinaryPrimitives.ReadInt32LittleEndian(
            packet.Payload.Slice(8));
        if (playerObjectId != LocalPlayerObjectId &&
            playerObjectId != CurrentPlayerObjectId ||
            !_registry.TryReserveMonsterLootPickup(
                _session,
                monsterObjectId,
                pickupIndex,
                DateTimeOffset.UtcNow,
                out var reservation))
        {
            return;
        }

        var completed = false;
        try
        {
            var result = await _monsterRewardExtras.PickupMonsterLootAsync(
                _account.Id,
                _character.Id,
                reservation.DeathEventId,
                reservation.RuleLootIndex,
                reservation.ItemId,
                reservation.Quantity,
                cancellationToken);
            if (!result.Succeeded || result.Character is null ||
                !RevalidateCurrentWorldEffectOwnership(
                    "monster_loot_pickup"))
            {
                if (result.Status ==
                    MonsterLootPickupStatus.InsufficientCapacity)
                {
                    await SendKitBagRefreshAsync(cancellationToken);
                }
                return;
            }

            InstallUpdatedCharacter(result.Character);
            _registry.UpdateCharacter(
                _session,
                _character,
                advanceWorldRevision: false);
            await _session.SendAsync(
                PacketBuilder.MonsterLootPickup(
                    LocalPlayerObjectId,
                    monsterObjectId,
                    pickupIndex),
                cancellationToken,
                "MonsterLootPickup");
            await SendKitBagRefreshAsync(cancellationToken);
            _registry.CompleteMonsterLootPickup(reservation);
            completed = true;
            Console.WriteLine(
                $"[loot] picked character={_character.Name} monster={monsterObjectId} item={reservation.ItemId} quantity={reservation.Quantity}");
        }
        finally
        {
            if (!completed)
            {
                _registry.ReleaseMonsterLootPickup(reservation);
            }
        }
    }
}
