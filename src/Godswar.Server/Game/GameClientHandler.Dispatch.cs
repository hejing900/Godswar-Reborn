using System.Buffers.Binary;
using System.Text;
using Godswar.Server.Application.Accounts;
using Godswar.Server.Application.Characters;
using Godswar.Server.Application.Inventory;
using Godswar.Server.Application.Pets;
using Godswar.Server.Application.Talents;
using Godswar.Server.Application.World;
using Godswar.Server.Application.Zodiac;
using Godswar.Server.Networking;
using Godswar.Server.Networking.Secure.Udp;
using Godswar.Server.Operations;
using Godswar.Server.Operations.Observability;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// Per-tick traffic that would bury the diagnostic file: the UI heartbeat,
    /// the client's movement stream and the world spawn/vitals updates.
    /// </summary>
    private static bool IsTraceNoise(ushort opcode) =>
        opcode is 10015 or 10016 or 10017 or 10194;

    private async Task HandlePacketAsync(GamePacket packet, CancellationToken cancellationToken)
    {
        if (_session.AllowsPayloadDiagnostics)
        {
            LogReceived(packet);
        }

        // A diagnostic for clicks that produce no answer at all: the file trace
        // survives the container's folded stdout, so the next click can be read
        // back with its opcode and payload even when the handler never runs.
        // Per-tick traffic is filtered out - thousands of 20-byte movement and
        // world-update frames otherwise bury the clicks - and every other frame
        // keeps a bounded preview instead of the old 64-byte cap, which hid the
        // 92-byte bag activation (opcode 10051) that item use travels on.
        if (!IsTraceNoise(packet.Opcode))
        {
            var payload = packet.Payload;
            var shown = Math.Min(payload.Length, 24);
            QuestFrameTrace.Append(
                $"[recv] op={packet.Opcode} len={packet.Length} " +
                $"payload={Convert.ToHexString(payload[..shown])}",
                []);
        }

        if (_session.BoundGamePrincipal is not null &&
            _account is null &&
            packet.Opcode is not (
                Opcodes.LoginGameServer or
                Opcodes.Ping or
                Opcodes.UiHeartbeat))
        {
            _session.Disconnect();
            return;
        }

        if (!AuthorizeAuthenticatedPacket())
        {
            return;
        }

        if (IsMapTransitionPending &&
            !IsAllowedDuringMapTransition(packet.Opcode))
        {
            return;
        }

        if (await TryHandlePartyPacketAsync(packet, cancellationToken)) return;
        if (await TryHandlePetCapturePacketAsync(packet, cancellationToken)) return;

        switch (packet.Opcode)
        {
            case Opcodes.DesignationSelection:
                await HandleTitleSelectionAsync(packet, cancellationToken);
                break;
            case Opcodes.LoginGameServer:
                await HandleGameLoginAsync(packet, cancellationToken);
                break;
            case Opcodes.RoleInfo:
                await SendCharacterPreviewAsync(cancellationToken);
                break;
            case Opcodes.CreateRole:
                await HandleCreateRoleAsync(packet, cancellationToken);
                break;
            case Opcodes.DeleteRole:
                await HandleDeleteRoleAsync(packet, cancellationToken);
                break;
            case Opcodes.EnterGame:
                await HandleEnterGameAsync(cancellationToken);
                break;
            case Opcodes.Ping:
                await _session.SendAsync(packet.Buffer, cancellationToken, "PingEcho");
                break;
            case Opcodes.UiHeartbeat:
                await _session.SendAsync(packet.Buffer, cancellationToken, "UiHeartbeatEcho");
                break;
            case Opcodes.Talk:
                if (!await HandleDeveloperItemCommandAsync(packet, cancellationToken))
                {
                    await BroadcastToCurrentMapAsync(packet, cancellationToken);
                }

                break;
            case Opcodes.WalkBegin:
            case Opcodes.WalkEnd:
            case Opcodes.Walk:
                if (RejectDeadLegacyMovement(packet))
                {
                    break;
                }
                if (IsMapTransitionPending)
                {
                    break;
                }
                if (packet.Opcode != Opcodes.Walk &&
                    RejectBlockedNonWalkMovement())
                {
                    break;
                }
                if (packet.Opcode == Opcodes.WalkBegin)
                {
                    await InterruptPendingSkillCastAsync(
                        SkillCastInterruptionReason.Movement,
                        cancellationToken);
                }
                if (packet.Opcode == Opcodes.Walk)
                {
                    if (!await HandleWalkAsync(packet, cancellationToken))
                    {
                        break;
                    }
                }
                else if (packet.Opcode == Opcodes.WalkEnd)
                {
                    await PersistCharacterPositionAsync(force: true, cancellationToken);
                }

                await BroadcastToCurrentMapAsync(packet, cancellationToken);
                break;
            case Opcodes.SkillCast:
                await HandleSkillCastAsync(packet, cancellationToken);
                break;
            case Opcodes.SkillCastInterrupt:
                await HandleSkillCastInterruptRequestAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.PlayerStateAction:
                await HandlePlayerStateActionAsync(packet, cancellationToken);
                break;
            case Opcodes.BasicAttack:
                await HandleBasicAttackAsync(packet, cancellationToken);
                break;
            case Opcodes.Revive:
            case Opcodes.ReviveLegacy:
                await HandleReviveAsync(packet, cancellationToken);
                break;
            case Opcodes.Kitbag:
            case Opcodes.Storage:
            case Opcodes.MoveItem:
            case Opcodes.Sell:
                // The same opcode carries an inventory move and the corpse
                // click that opens a loot window, so the loot source is claimed
                // before the log-only inventory path.
                if (await TryHandleGroundLootSourceAsync(
                        packet,
                        cancellationToken))
                {
                    break;
                }

                LogInventoryPacket(packet);
                break;
            case Opcodes.PickupDrops:
                await HandleMonsterLootPickupAsync(packet, cancellationToken);
                break;
            case Opcodes.UseOrEquip:
                await HandleUseOrEquipAsync(packet, cancellationToken);
                break;
            case Opcodes.BagItemAction:
                await HandleBagItemActionAsync(packet, cancellationToken);
                break;
            case Opcodes.ItemInfoRequest:
                HandleItemInfoRequest(packet);
                break;
            case Opcodes.ForgeSelection:
                HandleForgeSelection(packet);
                break;
            case Opcodes.ForgeStart:
                await HandleForgeStartAsync(packet, cancellationToken);
                break;
            case Opcodes.ForgeCancel:
                // The stock Gear Mentor emits this ordinary-forge cancel when
                // gear is unequipped into the bag while its dialog is open.
                // Its subsequent 10193 item selections still belong to the
                // active Gear Mentor workflow, so only ordinary forge state is
                // invalidated here.
                ClearForgeSelection();
                break;
            case Opcodes.ForgeReplacementSelection:
            case Opcodes.ForgeReplacementAction:
                ClearForgeSelection();
                Console.WriteLine(
                    $"[forge] ignored unsupported {Opcodes.Name(packet.Opcode)} opcode={packet.Opcode}");
                break;
            case Opcodes.NpcDialogOpen:
                await HandleNpcDialogOpenAsync(packet, cancellationToken);
                break;
            case Opcodes.NpcDialogPageRequest:
                await HandleNpcDialogPageRequestAsync(packet, cancellationToken);
                break;
            case Opcodes.NpcFunctionAction:
                await HandleNpcFunctionActionAsync(packet, cancellationToken);
                break;
            case Opcodes.MallCatalog:
                await HandleMallCatalogRequestAsync(packet, cancellationToken);
                break;
            case Opcodes.MallPurchase:
                await HandleMallPurchaseAsync(packet, cancellationToken);
                break;
            case Opcodes.NpcShopPurchase: await HandleCapitalNpcShopPurchaseAsync(packet, cancellationToken); break;
            case Opcodes.QuestSelection:
                await HandleQuestSelectionAsync(packet, cancellationToken);
                break;
            case Opcodes.QuestAction:
                await HandleQuestActionAsync(packet, cancellationToken);
                break;
            case Opcodes.QuestSceneQuery:
                await HandleQuestSceneQueryAsync(packet, cancellationToken);
                break;
            case Opcodes.QuestAccepted:
                await HandleQuestHandInAsync(packet, cancellationToken);
                break;
            case Opcodes.QuestActionPair:
                await HandleQuestActionPairAsync(packet, cancellationToken);
                break;
            case Opcodes.GearEnhancerItemSelection:
                HandleGearEnhancerItemSelection(packet);
                break;
            case Opcodes.PlayerNameInspectRequest:
                await _session.SendAsync(packet.Buffer, cancellationToken, "PlayerNameInspectAck");
                break;
            case Opcodes.PlayerInspectRequest:
                await HandlePlayerInspectRequestAsync(packet, cancellationToken);
                break;
            case Opcodes.PlayerInspectVisualRequest:
                await HandlePlayerInspectVisualRequestAsync(packet, cancellationToken);
                break;
            case Opcodes.PetTakeRequest:
                await HandlePetPresenceRequestAsync(
                    packet,
                    PetPresenceOperation.Take,
                    cancellationToken);
                break;
            case Opcodes.PetCallOutRequest:
                await HandlePetPresenceRequestAsync(
                    packet,
                    PetPresenceOperation.CallOut,
                    cancellationToken);
                break;
            case Opcodes.PetRecallRequest:
                await HandlePetPresenceRequestAsync(
                    packet,
                    PetPresenceOperation.Recall,
                    cancellationToken);
                break;
            case Opcodes.PetOwnerMergeRequest:
                await HandlePetOwnerMergeRequestAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.PackedPetDetailRequest:
                await HandlePackedPetDetailRequestAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.PetToPetMergeRequest:
                await HandlePetToPetMergeRequestAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.PetSoulContractRequest:
                await HandlePetSoulContractRequestAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.PetRebirthRequest:
                await HandlePetRebirthRequestAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.PetLevelUpgradeRequest:
                await HandlePetLevelUpgradeAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.Zodiac:
                await HandleZodiacAsync(packet, cancellationToken);
                break;
            case Opcodes.BreakItem:
                await HandleBreakItemAsync(packet, cancellationToken);
                break;
            case Opcodes.StorageItem:
                await HandleStorageItemAsync(packet, cancellationToken);
                break;
            case Opcodes.WarehouseTransfer:
                await HandleWarehouseTransferAsync(packet, cancellationToken);
                break;
            case Opcodes.ServerTimeRequest:
                await _session.SendAsync(
                    PacketBuilder.ServerTime(_realmCalendar),
                    cancellationToken,
                    "ServerTime");
                break;
            case Opcodes.ClientReady:
                await HandleClientReadyAsync(cancellationToken);
                break;
            case Opcodes.PlayerDetailRequest:
                await HandlePlayerDetailRequestAsync(packet, cancellationToken);
                break;
            case Opcodes.FashionEffectVisibility:
                await HandleFashionEffectVisibilityAsync(
                    packet,
                    cancellationToken);
                break;
            case Opcodes.EnterUiReady:
                _enterUiReadyReceived = true;
                Console.WriteLine($"[game] EnterUiReady character={_character?.Name ?? "<none>"}");
                await SendPostEnterBootstrapAsync(cancellationToken);
                // A quest whose objectives are already met is published only now:
                // the client crashed dereferencing npc zero while the frame arrived
                // ahead of the world entry, and the reference only ever sends it in
                // the middle of play, right behind the kill that finished the quest.
                await SendLoginQuestProgressAsync(cancellationToken);
                break;
            case Opcodes.GameServerReady:
            case Opcodes.GameServerInfo:
            case Opcodes.PlayerInspectFollowup:
            case 10192:
                Console.WriteLine($"[game] ignored {Opcodes.Name(packet.Opcode)} opcode={packet.Opcode}");
                break;
            // The client sells with 10060, not the known-but-unused 10053.
            case Opcodes.SellItem:
                await HandleSellItemRequestAsync(packet, cancellationToken);
                break;
            default:
                Console.WriteLine(
                    $"[game] unknown {Opcodes.Name(packet.Opcode)} opcode={packet.Opcode} len={packet.Length} {packet.ToHexPreview()}");
                break;
        }
    }

}
