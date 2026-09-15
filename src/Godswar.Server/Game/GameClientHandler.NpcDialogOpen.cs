using System.Buffers.Binary;
<<<<<<< HEAD
using Godswar.Server.Application.World;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Networking;
=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private async Task HandleNpcDialogOpenAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (packet.Payload.Length < sizeof(uint))
        {
            _warehouseAccessContext = null;
            Console.WriteLine("[npc] dialog open ignored: payload too short");
            return;
        }

        ClearGearEnhancerSelection();
        ClearInstanceCallerPageContext();
        ClearTransporterDialogueContext();
        ClearBattlefieldTransporterDialogueContext();
        ClearDuelArenaTransporterDialogueContext();
        var npcId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload[..sizeof(uint)]);
        if (!TryResolveMapNpc(npcId, out var npc))
        {
            _warehouseAccessContext = null;
<<<<<<< HEAD
            QuestFrameTrace.Append(
                $"[npc] dialog open ignored: unknown npc={npcId} " +
                $"map={_character?.CurrentMap.ToString() ?? "<none>"} " +
                $"len={packet.Length}",
                []);
=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
            Console.WriteLine(
                $"[npc] dialog open ignored: unknown npc={npcId} " +
                $"map={_character?.CurrentMap.ToString() ?? "<none>"}");
            return;
        }

<<<<<<< HEAD
        QuestFrameTrace.Append(
            $"[npc] dialog open received npc={npcId} key={npc.NpcKey} " +
            $"map={npc.MapId} len={packet.Length} buffer={packet.Buffer.Length} " +
            $"carried={_character?.Quests.Count ?? 0}",
            []);

=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
        // The stock client can leave normal storage open while the related
        // manager dialogue is used. Preserve only an access lease that was
        // already issued by the normal Warehouse NPC; the manager never
        // grants one. Every unrelated NPC click still invalidates the lease.
        if (!WarehouseNpcProtocol.IsManagerEndpoint(
                npc.NpcKey,
                npc.InteractionId))
        {
            _warehouseAccessContext = null;
        }

<<<<<<< HEAD
        // The flags word is a bitmask, so an npc whose normal page is something
        // else keeps it and gains the quest page. Computed once here because every
        // branch below needs the same answer.
        var questFlags = HasQuestFunctionFor(npc.InteractionId)
            ? QuestContentBaseline.QuestOpenFlags
            : 0;

=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
        if (WarehouseNpcProtocol.IsWarehouseEndpoint(
                npc.NpcKey,
                npc.InteractionId))
        {
            if (packet.Length == 48 && packet.Buffer.Length == 48 &&
                CanUseDuelArenaWarehouseNpc(npc))
            {
                await _session.SendAsync(
                    PacketBuilder.WarehouseDialogOpenAck(
                        npc.InteractionId,
                        WarehouseNpcProtocol.ClientScriptKey(
<<<<<<< HEAD
                            npc.NpcKey, npc.InteractionId),
                        questFlags),
=======
                            npc.NpcKey, npc.InteractionId)),
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
                    cancellationToken,
                    "WarehouseDialogOpenAck");
            }
            else
            {
                Console.Error.WriteLine(
                    "[warehouse] rejected non-canonical NPC click " +
                    $"npc={npc.InteractionId} length={packet.Length}");
            }
            return;
        }

<<<<<<< HEAD
        if (QuestContentBaseline.IsNewbieGuide(npc.InteractionId))
        {
            // Replayed from the reference capture: the guide opens with the 10067
            // frame captured at packet 222, the responder (Sparta_106) with the
            // one captured at packet 1307. Both are this frame with the clicked
            // npc's own id and script key - which is what the capture holds - so
            // building it from the npc keeps Sparta byte-identical and stops the
            // Athens guide (5233, also named Acacia) from advertising Sparta_094.
            await _session.SendAsync(
                PacketBuilder.NpcQuestDialogOpenAck(
                    npc.InteractionId,
                    npc.NpcKey),
                cancellationToken,
                "NpcQuestDialogOpenAck");
            Console.WriteLine(
                $"[quest] guide dialog open npc={npc.InteractionId} " +
                $"key={npc.NpcKey} responder=" +
                $"{QuestContentBaseline.IsNewbieGuideResponder(npc.InteractionId)}");
            QuestFrameTrace.Append(
                $"[npc] dialog open branch=guide npc={npc.InteractionId} " +
                $"key={npc.NpcKey}",
                []);
            return;
        }

        // Every other npc that has a quest to give or take opens the same quest
        // page. The captured dialogs advertise it with flags 3; the generic
        // description window advertises 0, which is why the npc that receives the
        // second quest used to open a window with no quest entry in it at all.
        if (questFlags != 0)
        {
            await _session.SendAsync(
                PacketBuilder.NpcQuestDialogOpenAck(
                    npc.InteractionId,
                    npc.NpcKey),
                cancellationToken,
                "NpcQuestDialogOpenAck");
            Console.WriteLine(
                $"[quest] dialog open npc={npc.InteractionId} " +
                $"key={npc.NpcKey}");
            QuestFrameTrace.Append(
                $"[npc] dialog open branch=quest npc={npc.InteractionId} " +
                $"key={npc.NpcKey}",
                []);
            return;
        }

        if (await TryHandleDuelArenaNpcDialogOpenAsync(
                packet, npc, cancellationToken))
        {
            QuestFrameTrace.Append(
                $"[npc] dialog open branch=duel-arena npc={npc.InteractionId} " +
                $"key={npc.NpcKey}",
                []);
=======
        if (await TryHandleDuelArenaNpcDialogOpenAsync(
                packet, npc, cancellationToken))
        {
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
            return;
        }

        if (await TryHandleCapitalNpcDialogOpenAsync(
                npc,
<<<<<<< HEAD
                questFlags,
                cancellationToken))
        {
            QuestFrameTrace.Append(
                $"[npc] dialog open branch=capital npc={npc.InteractionId} " +
                $"key={npc.NpcKey}",
                []);
            return;
        }

        var (routes, text) = await ResolveNpcDialogueRoutesAsync(
=======
                cancellationToken))
        {
            return;
        }

        var routes = await ResolveNpcDialogueRoutesAsync(
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
            npc,
            cancellationToken);
        if (routes.Count == 0)
        {
<<<<<<< HEAD
            // A published NPC may carry dialogue text without any extended
            // function: the Wishing Pool is one, and the captured Duel Arena
            // Vendor and capital Teaching Manager are others. Advertise the
            // description-only window so the stock client opens its own
            // description page, exactly as those captured endpoints do. The
            // client resolves the visible text from the script key in its own
            // NPCDescription.dat, so no text travels in this packet.
            if (text is { } description &&
                !string.IsNullOrWhiteSpace(description.Description))
            {
                await SendNpcDescriptionOpenAsync(npc, cancellationToken);
                return;
            }

            // Nothing matched: no function, no route and no description, so the
            // client is sent nothing at all and the click looks dead. Record it
            // because this is the one branch that leaves no other trace.
            QuestFrameTrace.Append(
                $"[npc] dialog open sent nothing npc={npc.InteractionId} " +
                $"key={npc.NpcKey} map={npc.MapId} questFlags={questFlags} " +
                $"warehouse={WarehouseNpcProtocol.IsWarehouseEndpoint(npc.NpcKey, npc.InteractionId)} " +
                $"text={(text is null ? "none" : "empty")} " +
                $"capital={CapitalNpcServiceProtocol.TryResolve(npc, out _)}",
                []);
=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
            return;
        }

        var clientScriptKey = routes[0].ClientScriptKey;
        if (routes.Count > 3 || routes.Any(route =>
                !string.Equals(
                    route.ClientScriptKey,
                    clientScriptKey,
                    StringComparison.Ordinal)))
        {
            Console.Error.WriteLine(
                "[npc] dialog open rejected: routes cannot be represented " +
                $"npc={npc.InteractionId} routes={routes.Count}");
            return;
        }

        // One native advertisement carries up to three ordered top-level
        // functions in a base-1000 field. For Gear Mentor, [4, 37] becomes
        // 37004, so Gear Enhancement and Class Suit are sibling choices.
        var dialogIndices = routes
            .Select(static route => route.DialogIndex)
            .ToArray();
        if (routes.Any(DuelArenaCapturedTransportProtocol.IsCapturedRoute) &&
            (packet.Length != 48 || packet.Buffer.Length != 48 ||
                !TryIssueDuelArenaTransporterDialogueContext(npc)))
        {
            return;
        }
        if (routes.Any(static route =>
                route.Behavior == NpcDialogueBehavior.DuelArenaServices) &&
            (packet.Length != 48 || packet.Buffer.Length != 48 ||
                !CanUseCapturedArenaNpc(npc)))
        {
            return;
        }
        if (routes.Any(DuelArenaExitProtocol.IsRoute) &&
            !TryIssueDuelArenaTransporterDialogueContext(npc))
        {
            return;
        }
        await _session.SendAsync(
            PacketBuilder.NpcDialogOpenAck(
                npc.InteractionId,
                dialogIndices,
                clientScriptKey),
            cancellationToken,
            "NpcDialogOpenAck");

        foreach (var route in routes)
        {
            Console.WriteLine(
                $"[npc] dialog open npc={npc.InteractionId} " +
                $"script={route.ClientScriptKey} " +
                $"behavior={route.Behavior} dialog={route.DialogIndex} " +
                $"order={route.RouteOrder}");
        }
<<<<<<< HEAD

        QuestFrameTrace.Append(
            $"[npc] dialog open branch=routes npc={npc.InteractionId} " +
            $"key={npc.NpcKey} script={clientScriptKey} routes={routes.Count}",
            []);
=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
    }

    private async Task HandleNpcDialogPageRequestAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (packet.Payload.Length < sizeof(uint))
        {
            Console.WriteLine("[npc] page request ignored: payload too short");
            return;
        }

        var npcId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload[..sizeof(uint)]);
        if (!TryResolveMapNpc(npcId, out var npc))
        {
            Console.WriteLine(
                $"[npc] page request ignored: unknown npc={npcId}");
            return;
        }

        if (WarehouseNpcProtocol.IsWarehouseEndpoint(
                npc.NpcKey,
                npc.InteractionId))
        {
            if (!CanUseDuelArenaWarehouseNpc(npc))
            {
                _warehouseAccessContext = null;
                return;
            }
            if (packet.Length == 8 && packet.Buffer.Length == 8)
            {
                await HandleWarehouseOpenAsync(npc, cancellationToken);
            }
            else if (packet.Length == 12 &&
                     packet.Buffer.Length == 12 &&
                     TryAuthorizeWarehouseTransfer(out var authorizedNpc) &&
                     authorizedNpc.InteractionId == npc.InteractionId)
            {
                var page = BinaryPrimitives.ReadInt32LittleEndian(
                    packet.Payload.Slice(sizeof(uint), sizeof(int)));
                await HandleWarehouseOpenAsync(
                    npc,
                    cancellationToken,
                    page,
                    issueAccess: false);
            }
            else
            {
                Console.Error.WriteLine(
                    "[warehouse] rejected non-canonical page request " +
                    $"npc={npc.InteractionId} length={packet.Length}");
            }
            return;
        }

        if (await TryHandleCapitalNpcPageRequestAsync(
                npc,
                cancellationToken))
        {
            return;
        }

        Console.WriteLine(
            $"[npc] page request npc={npcId} key={npc.NpcKey}");
    }
<<<<<<< HEAD

    /// <summary>
    /// Opens the stock client's plain description window for a published NPC
    /// that owns dialogue text but no extended function.
    /// </summary>
    /// <remarks>
    /// The advertised script key is the NPC key because the client indexes its
    /// own <c>NPCDescription.dat</c> by that key; the captured Duel Arena
    /// Vendor and the capital Teaching Manager both open this way. The packet
    /// is an ordinary 48-byte <see cref="Opcodes.NpcDialogOpen"/>
    /// acknowledgement with <c>flags = 0</c> and an empty function field, so it
    /// advertises no function the client would try to dispatch. It is unrelated
    /// to opcode 10090: no quest page is sent, and the quest refresh routine is
    /// never entered.
    /// </remarks>
    private async ValueTask SendNpcDescriptionOpenAsync(
        NpcSpawnDefinition npc,
        CancellationToken cancellationToken)
    {
        await _session.SendAsync(
            PacketBuilder.NpcDescriptionDialogOpenAck(
                npc.InteractionId,
                npc.NpcKey),
            cancellationToken,
            "NpcDescriptionDialogOpenAck");
        Console.WriteLine(
            $"[npc] description open npc={npc.InteractionId} " +
            $"key={npc.NpcKey}");
    }
=======
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
}
