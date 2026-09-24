using System.Buffers.Binary;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Networking;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>The quest the server last offered, used when the client answers
    /// an accept without repeating the id (C2S 10081).</summary>
    private uint _offeredQuestId;

    // Quest ids are the client's own (Quest.xml / Text/Quest), so the client
    // renders real text. A character may carry several quests at once, each with
    // its own objective progress, and acceptance is always driven by the id the
    // client sends: the chain supplies the giver and responder for whatever id
    // comes in, so a new quest only needs a new chain row.

    /// <summary>How many quests the login snapshot has room for.</summary>
    /// <remarks>
    /// The frame is 2048 bytes and carries a 96-byte descriptor plus a 72-byte
    /// record per quest, so the arithmetic allows twelve. A character holding more
    /// than this keeps them all in storage; only the published list is bounded.
    /// </remarks>
    private const int MaximumPublishedQuests = 12;

    /// <summary>
    /// Publishes the accepted-quest snapshot: the client's list of the quests it
    /// is working on, each with its giver, responder and the objective it is
    /// counting right now.
    /// </summary>
    /// <remarks>
    /// The snapshot is the client's own state of the quest log, so it goes out on
    /// world entry and again whenever the objective a carried quest is counting
    /// changes. A quest with several targets - 528 asks for one Addiya the
    /// Destroyer and eight Fake Treasures - is published one target at a time, so
    /// finishing the first has to republish the quest or the window keeps waiting
    /// for a monster that is already dead and never shows the rest.
    /// <para>
    /// A character with no quests gets an empty snapshot; quests are only ever
    /// accepted by hand at the npc, so nothing appears here on its own.
    /// </para>
    /// </remarks>
    private async Task SendQuestSnapshotAsync(
        string reason,
        CancellationToken cancellationToken)
    {
        if (_character is null)
        {
            return;
        }

        var entries = new List<PacketBuilder.QuestSnapshotEntry>();
        foreach (var quest in _character.Quests)
        {
            if (StarterQuestChain.Find(quest.QuestId) is not { } step)
            {
                continue;
            }

            var objectives = StarterQuestObjectives.For(quest.QuestId);
            // Every target the quest names is published, not just the one still
            // open: the client draws one line per filled slot, so sending only the
            // active objective is what made a multi-target quest show a single
            // line. The reference server's own answer for the two-target quest
            // 1533 carries both targets, and the same parallel slots are used
            // here. Progress travels per slot, so finishing the first target
            // updates its line instead of hiding the rest.
            var targets = new PacketBuilder.QuestSnapshotObjective[
                objectives.Count];
            for (var slot = 0; slot < objectives.Count; slot++)
            {
                targets[slot] = new PacketBuilder.QuestSnapshotObjective(
                    objectives[slot].MonsterId,
                    objectives[slot].Required,
                    StarterQuestObjectives.Counter(quest.Progress, slot));
            }

            entries.Add(new PacketBuilder.QuestSnapshotEntry(
                step.QuestId,
                await ResolveQuestNpcIdForSnapshotAsync(
                    step.GiverKey,
                    cancellationToken),
                await ResolveQuestNpcIdForSnapshotAsync(
                    step.ResponderKey,
                    cancellationToken),
                Objectives: targets));
            if (entries.Count == MaximumPublishedQuests)
            {
                break;
            }
        }

        await _session.SendAsync(
            PacketBuilder.QuestSnapshot(entries),
            cancellationToken,
            "LoginQuestSnapshot",
            framed: false);
        Console.WriteLine(
            $"[quest] snapshot character={_character.Name} reason={reason} " +
            $"carried={entries.Count} of={_character.Quests.Count}");
    }

    /// <summary>
    /// Re-sends the npc quest tables so the quest mark matches the character again.
    /// </summary>
    /// <remarks>
    /// The tables are per npc and carry the "available here" flag, so they have to
    /// follow every change to what the character may take - which is why the hand-in
    /// path already sends them. A deleted quest now does the same, otherwise the
    /// npc that offers it keeps showing nothing.
    /// </remarks>
    private async Task SendQuestRefreshAsync(
        uint changedQuestId,
        CancellationToken cancellationToken)
    {
        var acceptable = NextAcceptableQuest();
        var npcId = acceptable is { } step
            ? ResolveQuestNpcId(step.GiverKey)
            : StarterQuestChain.Find(changedQuestId) is { } changed
                ? ResolveQuestNpcId(changed.GiverKey)
                : 0u;
        if (npcId == 0)
        {
            return;
        }

        await _session.SendAsync(
            PacketBuilder.QuestMarkerList(npcId, QuestMarkerEntries(npcId)),
            cancellationToken,
            "QuestMarkerList",
            framed: false);
        await _session.SendAsync(
            PacketBuilder.QuestHandInMenu(npcId, QuestHandInEntries(npcId)),
            cancellationToken,
            "QuestHandInList",
            framed: false);
        QuestFrameTrace.Append(
            $"[quest] refreshed npc={npcId} acceptable=" +
            $"{acceptable?.QuestId ?? 0} character={_character?.Name}",
            []);
    }

    /// <summary>
    /// Tells the client which carried quests are ready to hand in.
    /// </summary>
    /// <remarks>
    /// It is published from the client's EnterUiReady, not with the login snapshot,
    /// because that is where the client can take it: sending it ahead of the world
    /// entry made the client dereference npc zero and crash, and the reference
    /// capture only ever shows it in the middle of play, immediately behind the
    /// kill that finished the quest.
    /// <para>
    /// How far along a quest is now travels in the snapshot descriptor itself, so
    /// nothing replays the per-kill progress frames on login - doing that would add
    /// the same kills a second time. What the snapshot does not say is whether the
    /// quest may be handed in, and that is what this frame carries.
    /// </para>
    /// <para>
    /// It deliberately does not re-send the accept answer either: that made the
    /// client call acceptQuest for a quest it already held, which errored and then
    /// crashed.
    /// </para>
    /// </remarks>
    private async Task SendLoginQuestProgressAsync(
        CancellationToken cancellationToken)
    {
        if (_character is null)
        {
            return;
        }

        foreach (var quest in _character.Quests)
        {
            var objectives = StarterQuestObjectives.For(quest.QuestId);
            if (objectives.Count == 0 ||
                StarterQuestChain.Find(quest.QuestId) is not { } step ||
                !StarterQuestObjectives.IsSatisfied(objectives, quest.Progress))
            {
                continue;
            }

            // The in-memory npc catalog is installed after this runs, so the
            // synchronous resolver reads zero here; the snapshot resolver reads the
            // published map content instead. A frame naming responder zero is what
            // crashed the client the moment a quest's objectives were met while the
            // character was offline, so an unresolvable responder is skipped
            // outright rather than published.
            var responderNpcId = await ResolveQuestNpcIdForSnapshotAsync(
                step.ResponderKey,
                cancellationToken);
            if (responderNpcId == 0)
            {
                Console.Error.WriteLine(
                    $"[quest] skipped objectives-met without a responder " +
                    $"character={_character.Name} quest={step.QuestId} " +
                    $"responder={step.ResponderKey} map={_character.CurrentMap}");
                continue;
            }

            await _session.SendAsync(
                PacketBuilder.QuestConfirm(
                    responderNpcId,
                    step.QuestId),
                cancellationToken,
                "LoginQuestObjectivesMet",
                framed: false);
            Console.Error.WriteLine(
                $"[quest] login objectives met character={_character.Name} " +
                $"quest={step.QuestId} progress={quest.Progress} " +
                $"responder={responderNpcId} " +
                $"objectives={DescribeObjectives(objectives)}");
        }
    }

    /// <summary>Handles C2S 10083, the per-quest state query.</summary>
    /// <remarks>
    /// The client names a quest at <c>+8</c> (the scene key at <c>+4</c> is not
    /// echoed) and the answer carries that quest with its responder npc.
    /// <para>
    /// This is the quest window's delete button. Every click of it produced one of
    /// these and nothing else - three clicks, three packets - and the reference
    /// capture shows the same thing: it asks about the quest it is holding
    /// seconds before going back to the giver. So the answer confirms the removal
    /// and the row has to go with it: while only the client dropped the quest, the
    /// next login published it again and the player saw a quest they had deleted
    /// come back as if it had been accepted for them.
    /// </para>
    /// A quest the character is not carrying is simply answered, which is what the
    /// duplicate clicks produce once the first one has removed it.
    /// </remarks>
    private async Task HandleQuestSceneQueryAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_character is null || packet.Payload.Length < 12)
        {
            return;
        }

        var sceneKey = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload.Slice(4, sizeof(uint)));
        var requestedQuestId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload.Slice(8, sizeof(uint)));

        var removed = FindCarriedQuest(requestedQuestId);
        if (removed is not null)
        {
            _character.Quests.Remove(removed);
            await SaveQuestStateAsync(cancellationToken);
            QuestFrameTrace.Append(
                $"[quest] dropped character={_character.Name} " +
                $"quest={removed.QuestId} carried={_character.Quests.Count}",
                []);
            Console.Error.WriteLine(
                $"[quest] dropped character={_character.Name} " +
                $"quest={removed.QuestId} carried={_character.Quests.Count}");

            // The npc tables say which quests an npc offers and takes, and the
            // client only redraws the quest mark from them. Without this refresh a
            // deleted quest could not be picked up again until the next login,
            // because the npc still advertised nothing.
            await SendQuestRefreshAsync(removed.QuestId, cancellationToken);
        }

        // Answer about the quest the client named, unless the character may accept
        // a new one - the client uses this exchange to learn a quest is available.
        var acceptable = NextAcceptableQuest();
        var step = acceptable ?? StarterQuestChain.Find(requestedQuestId);
        if (step is not { } answered)
        {
            return;
        }

        _offeredQuestId = acceptable?.QuestId ?? 0;
        var responderNpcId = ResolveQuestNpcId(answered.ResponderKey);
        await _session.SendAsync(
            PacketBuilder.QuestSceneOfferAck(answered.QuestId, responderNpcId),
            cancellationToken,
            "QuestSceneOffer",
            framed: false);
        // stderr: stdout diagnostics are folded into counters by the legacy log
        // suppressor, so this is the channel that survives.
        Console.Error.WriteLine(
            $"[quest] scene query scene=0x{sceneKey:x8} " +
            $"asked={requestedQuestId} answered={answered.QuestId} " +
            $"npc={responderNpcId} character={_character.Name}");
    }

    /// <summary>Handles C2S 10081, the quest picked in a giver's window.</summary>
    /// <remarks>
    /// Captured shape (12 bytes): <c>+4</c> is zero and <c>+8</c> is the quest the
    /// player clicked - the packet's payload is only 8 bytes, so the quest sits at
    /// payload <c>+4</c>. The id is taken from the packet when it names a chain
    /// quest and from the last offer otherwise.
    /// <para>
    /// The accept answer is what fills the window in: with the objective written
    /// into it the client shows "0 of 10" while the player is still deciding.
    /// Sending the reference's 360-byte detail frame instead - which is what one
    /// reference session did before its client confirmed - made the window lose
    /// that line entirely, so this stays a single step.
    /// </para>
    /// </remarks>
    private async Task HandleQuestSelectionAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_character is null || packet.Payload.Length < 8)
        {
            return;
        }

        var selectedQuestId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload.Slice(4, sizeof(uint)));
        if (StarterQuestChain.Find(selectedQuestId) is null)
        {
            selectedQuestId = _offeredQuestId;
        }

        await AcceptQuestAsync(selectedQuestId, cancellationToken);
    }

    /// <summary>Handles C2S 10082, the captured accept action.</summary>
    /// <remarks>
    /// Captured shape: <c>+12</c> is the quest being accepted (518, then 519 in
    /// the second cycle). The two leading words are client pointers, not ids.
    /// </remarks>
    private async Task HandleQuestActionAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_character is null || packet.Payload.Length < 12)
        {
            return;
        }

        var questId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload.Slice(8, sizeof(uint)));
        await AcceptQuestAsync(questId, cancellationToken);
    }

    /// <summary>
    /// Answers a quest acceptance for <paramref name="questId"/>.
    /// </summary>
    /// <remarks>
    /// The chain row supplies the giver and responder, so the whole exchange is
    /// the same three captured frames for every quest. A character may hold
    /// several quests, so the only refusals are a quest it has already finished or
    /// is already carrying; a quest is never accepted twice.
    /// </remarks>
    private async Task AcceptQuestAsync(
        uint questId,
        CancellationToken cancellationToken)
    {
        if (_character is null || StarterQuestChain.Find(questId) is not { } step)
        {
            return;
        }

        if (FindCarriedQuest(questId) is not null)
        {
            Console.Error.WriteLine(
                $"[quest-accept] already carried character={_character.Name} " +
                $"quest={questId}");
            return;
        }

        if (!IsChainUnlocked(step))
        {
            Console.Error.WriteLine(
                $"[quest-accept] locked character={_character.Name} " +
                $"quest={questId}");
            return;
        }

        var giverNpcId = ResolveQuestNpcId(step.GiverKey);
        var responderNpcId = ResolveQuestNpcId(step.ResponderKey);

        await _session.SendAsync(
            PacketBuilder.QuestAnswer(giverNpcId, responderNpcId, step.QuestId),
            cancellationToken,
            "QuestAcceptAnswer",
            framed: false);
        await _session.SendAsync(
            PacketBuilder.AcceptPairAckFrame(),
            cancellationToken,
            "QuestAcceptPairAck",
            framed: false);

        // 10084 means "the objectives are met, go and hand it in". A quest with
        // nothing to kill is met the moment it is taken - that is why the capture
        // has it for the talk quest 518 - but sending it for a kill quest told the
        // client the work was already done, so the window came up full (10 of 10
        // for a quest asking for ten) and every kill pushed it past that.
        var objectives = StarterQuestObjectives.For(step.QuestId);
        if (objectives.Count == 0)
        {
            await _session.SendAsync(
                PacketBuilder.QuestConfirm(responderNpcId, step.QuestId),
                cancellationToken,
                "QuestAcceptConfirm",
                framed: false);
        }

        _offeredQuestId = 0;
        _character.Quests.Add(new CharacterQuest { QuestId = step.QuestId });
        _character.Quests.Sort(
            static (left, right) => left.QuestId.CompareTo(right.QuestId));
        await SaveQuestStateAsync(cancellationToken);
        Console.WriteLine(
            $"[quest] accepted character={_character.Name} " +
            $"quest={step.QuestId} giver={giverNpcId} responder={responderNpcId} " +
            $"carried={_character.Quests.Count}");
    }

    /// <summary>Handles C2S 10091, the paired confirmation.</summary>
    private async Task HandleQuestActionPairAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_character is null || packet.Payload.Length < 4)
        {
            return;
        }

        await _session.SendAsync(
            PacketBuilder.AcceptPairAckFrame(),
            cancellationToken,
            "QuestPairAck",
            framed: false);
    }

    /// <summary>Handles C2S 10084, the hand-in request.</summary>
    /// <remarks>
    /// Captured shape: <c>+4</c> is the quest being handed in. The reward comes
    /// from that quest's chain row, so no quest carries its own reward code, and
    /// the hand-in is refused while the quest still has unsatisfied kill
    /// objectives. Handing in clears that one quest - and only that one, since a
    /// character may be carrying others - and offers the next one without
    /// accepting it.
    /// </remarks>
    private async Task HandleQuestHandInAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_character is null || packet.Payload.Length < 8)
        {
            return;
        }

        var requestedQuestId = BinaryPrimitives.ReadUInt32LittleEndian(
            packet.Payload.Slice(4, sizeof(uint)));
        // The client names the reward slot it wants paid in the same request: 0
        // for a quest that pays one item, the chosen slot for the class-weapon
        // choice, -1 for a quest that pays nothing. The acknowledgement repeats
        // it and the client pays out that slot, so sending a slot the quest does
        // not have is the 004AC835 fault (Athens 1522, whose slots are all free,
        // was being answered with the template's 0).
        var rewardIndex = packet.Payload.Length >= 12
            ? BinaryPrimitives.ReadUInt32LittleEndian(
                packet.Payload.Slice(8, sizeof(uint)))
            : 0u;
        var step = StarterQuestChain.Find(requestedQuestId);
        if (step is not { } rewarded)
        {
            return;
        }

        var carried = FindCarriedQuest(rewarded.QuestId);
        var objectives = StarterQuestObjectives.For(rewarded.QuestId);
        if (objectives.Count > 0 &&
            !StarterQuestObjectives.IsSatisfied(
                objectives,
                carried?.Progress ?? 0))
        {
            // The client offers the quest as handable, but the objectives are the
            // server's own: until every target has been killed the required number
            // of times there is nothing to hand in.
            Console.Error.WriteLine(
                $"[quest-handin] objectives incomplete character=" +
                $"{_character.Name} quest={rewarded.QuestId} " +
                $"progress={carried?.Progress ?? 0} " +
                $"required={DescribeObjectives(objectives)}");
            return;
        }

        Console.WriteLine(
            $"[quest] hand-in character={_character.Name} quest={rewarded.QuestId}");

        // The durable quest experience appraisal scales this hand-in's
        // experience. Monster rewards keep their own multiplier path: the
        // appraisal is quest-only, which is what the client's own SM_L0_06 text
        // promises ("完成任务时可额外获得10%的经验").
        var rewardExperience = await ScaleQuestRewardExperienceAsync(
            rewarded.Experience,
            cancellationToken);
        var progression = await _store.ApplyMonsterKillRewardAsync(
            _account?.Id ?? 0,
            _character.Id,
            rewardExperience,
            rewarded.TalentPoints,
            cancellationToken);
        var levelUps = progression?.LevelUps ?? [];
        if (progression is not null)
        {
            _character.Level = progression.CurrentLevel;
            _character.Experience = progression.CurrentExperience;
            _character.TalentExperience = progression.CurrentTalentExperience;
            _character.TalentPoints = progression.CurrentTalentPoints;
        }

        // The money half of the reward is written to the character row before
        // anything is sent, so a relog cannot lose it. The status frame this
        // hand-in ends with carries the wallet, so the client shows it at once.
        try
        {
            var wallet = await _store.GrantQuestCurrencyAsync(
                _account?.Id ?? 0,
                _character.Id,
                rewarded.Silver,
                rewarded.Gold,
                cancellationToken);
            if (wallet is not null)
            {
                _character.Silver = wallet.Silver;
                _character.Gold = wallet.Gold;
                Console.Error.WriteLine(
                    $"[quest] reward paid character={_character.Name} " +
                    $"quest={rewarded.QuestId} silver=+{rewarded.Silver} " +
                    $"gold=+{rewarded.Gold} wallet={wallet.Silver}/" +
                    $"{wallet.Gold}");
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            Console.Error.WriteLine(
                $"[quest] reward payment failed character={_character.Name} " +
                $"quest={rewarded.QuestId} {ex.GetType().Name}: {ex.Message}");
        }

        if (carried is not null)
        {
            _character.Quests.Remove(carried);
        }

        var completed = new List<uint>(_character.QuestCompletedIds);
        if (!completed.Contains(rewarded.QuestId))
        {
            completed.Add(rewarded.QuestId);
        }

        _character.QuestCompletedIds = [.. completed];
        _offeredQuestId = 0;
        await SaveQuestStateAsync(cancellationToken);

        if (levelUps.Count > 0)
        {
            await RefreshLevelUpStatsAsync(_character, cancellationToken);
        }

        _registry.UpdateCharacter(
            _session,
            _character,
            advanceWorldRevision: false);

        var giverNpcId = ResolveQuestNpcId(rewarded.GiverKey);
        var responderNpcId = ResolveQuestNpcId(rewarded.ResponderKey);

        // Captured hand-in order (reference capture 2026-09-14 09:08:15, ids
        // 142589..142595): the status refresh first, then one opcode-10030
        // level-up notice per level the reward carried, then the hand-in ack,
        // the follow-up detail, the npc marker list and the hand-in menu.
        // Applying the reward experience without that 10030 notice leaves the
        // client rendering a level its panels never received, which is the
        // 004AC835 fault right after a hand-in - and is why only the quests
        // whose reward crosses a level threshold crashed.
        await _session.SendAsync(
            BuildLocalPlayerStatusUpdate(),
            cancellationToken,
            "QuestHandInStatus");

        foreach (var levelUp in levelUps)
        {
            var clientExperienceMaximum =
                PlayerExperienceCatalog.GetClientExperienceMaximum(
                    levelUp.Level,
                    _character.FighterLevelSealed);
            await _session.SendAsync(
                PacketBuilder.PlayerLevelUp(
                    LocalPlayerObjectId,
                    levelUp.Level,
                    clientExperienceMaximum,
                    levelUp.CurrentExperience,
                    _character.MaxHp,
                    _character.CurrentHp,
                    _character.MaxMp,
                    _character.CurrentMp),
                cancellationToken,
                "QuestHandInLevelUp");
            await _registry.BroadcastToMapAsync(
                _character.CurrentMap,
                PacketBuilder.PlayerLevelUp(
                    CurrentPlayerObjectId,
                    levelUp.Level,
                    clientExperienceMaximum,
                    levelUp.CurrentExperience,
                    _character.MaxHp,
                    _character.CurrentHp,
                    _character.MaxMp,
                    _character.CurrentMp),
                cancellationToken,
                _session,
                "QuestHandInLevelUpWorld");
        }

        await _session.SendAsync(
            PacketBuilder.QuestHandInAck(
                giverNpcId,
                responderNpcId,
                rewarded.QuestId,
                rewardIndex,
                (int)Math.Clamp(_character.Experience, 0, int.MaxValue),
                _character.TalentPoints),
            cancellationToken,
            "QuestHandInAck",
            framed: false);

        // The client expects the follow-up quest's record after the ack, so the
        // detail is always sent: a captured answer is replayed verbatim, and a
        // quest the capture never answered is built from this server's own chain
        // and objective data with its own reward slots (or free ones). Omitting
        // the frame - which is what happened while the next quest had no captured
        // answer, e.g. Athens 1523 after handing in 1522 - faulted the client at
        // 004AC835. Opcodes 10077 and 10080 stay built from the chain.
        if (StarterQuestChain.Next(rewarded.QuestId) is { } next)
        {
            var nextGiverNpcId = ResolveQuestNpcId(next.GiverKey);
            await _session.SendAsync(
                PacketBuilder.QuestNextDetail(nextGiverNpcId, next.QuestId),
                cancellationToken,
                "QuestNextDetail",
                framed: false);

            await _session.SendAsync(
                PacketBuilder.QuestMarkerList(
                    nextGiverNpcId,
                    QuestMarkerEntries(nextGiverNpcId)),
                cancellationToken,
                "QuestMarkerList",
                framed: false);
            await _session.SendAsync(
                PacketBuilder.QuestHandInMenu(
                    nextGiverNpcId,
                    QuestHandInEntries(nextGiverNpcId)),
                cancellationToken,
                "QuestHandInList",
                framed: false);
        }

        await _session.SendAsync(
            PacketBuilder.QuestHandInTailFrame(),
            cancellationToken,
            "QuestHandInTail",
            framed: false);
        Console.WriteLine(
            $"[quest] handed in character={_character.Name} " +
            $"quest={rewarded.QuestId} rewardExp={rewarded.Experience} " +
            $"rewardTp={rewarded.TalentPoints} " +
            $"levelUps={levelUps.Count} " +
            $"next={StarterQuestChain.Next(rewarded.QuestId)?.QuestId ?? 0} " +
            $"carried={_character.Quests.Count}");
    }

    /// <summary>
    /// The quest the character may accept next, or null when there is none.
    /// </summary>
    /// <remarks>
    /// The chain order is the progression order, so the first row that is not
    /// finished is the one the character is on. If that row is already being
    /// carried, nothing new is available until it is handed in. Returning the row
    /// after it would advertise a quest the chain has not unlocked, and - because
    /// the client asks about the quest it is carrying - it would answer with a
    /// different quest, which is what broke the delete button and the hand-in
    /// window at the same time.
    /// </remarks>
    private StarterQuestChain.Step? NextAcceptableQuest()
    {
        if (_character is null)
        {
            return null;
        }

        var camp = ChainCamp();
        foreach (var step in StarterQuestChain.Steps)
        {
            if (step.Camp != camp)
            {
                // The other camp's chain is a separate progression: a Sparta
                // character is never offered an Athens npc's quest.
                continue;
            }

            if (_character.QuestCompletedIds.Contains(step.QuestId))
            {
                continue;
            }

            return FindCarriedQuest(step.QuestId) is null ? step : null;
        }

        return null;
    }

    /// <summary>The chain this character walks: its own camp's.</summary>
    private string ChainCamp() =>
        ChainCampFor(_character?.Camp ?? GameDefaults.SpartaCamp);

    /// <summary>The chain name the given camp value walks.</summary>
    internal static string ChainCampFor(byte camp) =>
        camp == GameDefaults.SpartaCamp
            ? StarterQuestChain.SpartaCamp
            : StarterQuestChain.AthensCamp;

    /// <summary>True when every chain row before <paramref name="step"/> is done.</summary>
    private bool IsChainUnlocked(StarterQuestChain.Step step)
    {
        if (_character is null)
        {
            return false;
        }

        // A quest that has already been handed in is never accepted again, and one
        // the character is carrying is not restarted. The chain's first row
        // otherwise passes the ordering test below, which is how a finished quest
        // used to be re-offered after a relog.
        if (_character.QuestCompletedIds.Contains(step.QuestId) ||
            FindCarriedQuest(step.QuestId) is not null)
        {
            return false;
        }

        foreach (var candidate in StarterQuestChain.Steps)
        {
            if (candidate.Camp != step.Camp)
            {
                // Only this camp's own rows gate its quests; the other camp's
                // chain runs in parallel and neither blocks nor unlocks it.
                continue;
            }

            if (candidate.QuestId == step.QuestId)
            {
                return true;
            }

            if (!_character.QuestCompletedIds.Contains(candidate.QuestId))
            {
                return false;
            }
        }

        return true;
    }

    private CharacterQuest? FindCarriedQuest(uint questId)
    {
        foreach (var quest in _character?.Quests ?? [])
        {
            if (quest.QuestId == questId)
            {
                return quest;
            }
        }

        return null;
    }

    /// <summary>Describes a quest's objectives for the diagnostics.</summary>
    private static string DescribeObjectives(
        IReadOnlyList<QuestObjective> objectives)
    {
        var parts = new List<string>(objectives.Count);
        foreach (var objective in objectives)
        {
            var name = StarterQuestObjectives.NameOf(objective);
            parts.Add(name == objective.Target
                ? $"{objective.Required}x {objective.Target}"
                : $"{objective.Required}x {objective.Target} [= {name}]");
        }

        return string.Join(", ", parts);
    }

    private Task SaveQuestStateAsync(CancellationToken cancellationToken) =>
        _character is null || _account is null
            ? Task.CompletedTask
            : _store.SaveCharacterQuestStateAsync(
                _account.Id,
                _character.Id,
                _character.Quests,
                _character.QuestCompletedIds,
                cancellationToken);

    private uint ResolveQuestNpcId(string? npcKey) =>
        npcKey is not null &&
        _mapNpcsByInteractionId.Values.FirstOrDefault(
            npc => string.Equals(npc.NpcKey, npcKey, StringComparison.Ordinal))
            is { } match
            ? match.InteractionId
            : 0u;

    /// <summary>
    /// Resolves a chain npc key for the login snapshot.
    /// </summary>
    /// <remarks>
    /// The snapshot goes out before the npc catalog is installed - that ordering is
    /// what the client expects, and moving it broke the map-transition frame
    /// sequence - so the in-memory catalog is still empty at this point and the
    /// lookup fell back to zero. The published map content is read instead, which
    /// is where the catalog comes from anyway. A descriptor naming npc zero is what
    /// left the client's quest entry unusable and crashed it on the first hand-in.
    /// </remarks>
    private async Task<uint> ResolveQuestNpcIdForSnapshotAsync(
        string? npcKey,
        CancellationToken cancellationToken)
    {
        if (npcKey is null || _character is null)
        {
            return 0u;
        }

        if (ResolveQuestNpcId(npcKey) is var resolved && resolved != 0)
        {
            return resolved;
        }

        try
        {
            var mapContent = await _worldContent.ReadMapAsync(
                _character.CurrentMap,
                cancellationToken);
            // The ids have to be the ones the client was actually sent, so the
            // lookup runs the same placement pipeline world entry runs: the
            // captured Athens ids move a few published npcs, and naming the
            // published id would point the client at an object that is not there.
            var effectiveNpcs = CapturedNpcPlacementPolicy.ApplyToMap(
                [.. mapContent.Npcs
                    .Select(CapitalNpcServiceProtocol.ApplyCapturedSpawnCompatibility)
                    .Where(static npc =>
                        !CapitalNpcServiceProtocol.IsSuppressedSpawn(npc))]);
            foreach (var npc in effectiveNpcs)
            {
                if (string.Equals(npc.NpcKey, npcKey, StringComparison.Ordinal))
                {
                    return npc.InteractionId;
                }
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            Console.Error.WriteLine(
                $"[quest] npc lookup failed character={_character.Name} " +
                $"key={npcKey} {ex.GetType().Name}: {ex.Message}");
        }

        return 0u;
    }

    /// <summary>
    /// True when the npc gives or receives a quest on the chain at all.
    /// </summary>
    private bool IsQuestChainNpc(uint interactionId)
    {
        foreach (var step in StarterQuestChain.Steps)
        {
            if (ResolveQuestNpcId(step.GiverKey) == interactionId ||
                ResolveQuestNpcId(step.ResponderKey) == interactionId)
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>
    /// True when the npc has a quest to offer or to take from this character.
    /// </summary>
    /// <remarks>
    /// This is what decides whether a click opens the quest page. An npc that is
    /// on the chain but has nothing for this character yet keeps the ordinary
    /// description window, and one that gives the quest the character may accept
    /// next - or receives any quest the character is carrying - opens the quest
    /// page. The captured dialogs advertise exactly this through their flags: 3
    /// for the guide and the responder, 0 for an npc with no quest function.
    /// </remarks>
    private bool HasQuestFunctionFor(uint interactionId)
    {
        if (_character is null)
        {
            return false;
        }

        foreach (var quest in _character.Quests)
        {
            if (StarterQuestChain.Find(quest.QuestId) is { } carried &&
                ResolveQuestNpcId(carried.ResponderKey) == interactionId)
            {
                return true;
            }
        }

        return NextAcceptableQuest() is { } acceptable &&
            ResolveQuestNpcId(acceptable.GiverKey) == interactionId;
    }

    /// <summary>
    /// Rewrites the quest tables that travel with an npc spawn so they reflect
    /// this character's progress.
    /// </summary>
    /// <remarks>
    /// The tables are world content, identical for every player, so the captured
    /// ones still advertise a quest the character has already finished. The
    /// availability flag is per character, so the chain npcs' tables are rebuilt
    /// here before they are sent. Everything the content table already listed is
    /// kept - these tables also carry quests outside the newbie chain, which the
    /// client still needs - and only the flags change.
    /// </remarks>
    private IReadOnlyList<NpcSpawnDefinition> ProjectQuestMarkerTables(
        IReadOnlyList<NpcSpawnDefinition> spawns)
    {
        if (_character is null || spawns.Count == 0)
        {
            return spawns;
        }

        var acceptable = NextAcceptableQuest()?.QuestId ?? 0;
        List<NpcSpawnDefinition>? projected = null;
        for (var index = 0; index < spawns.Count; index++)
        {
            var spawn = spawns[index];
            if (!IsQuestChainNpc(spawn.InteractionId))
            {
                continue;
            }

            var given = new List<uint>();
            var received = new List<uint>();
            foreach (var step in StarterQuestChain.Steps)
            {
                if (ResolveQuestNpcId(step.GiverKey) == spawn.InteractionId)
                {
                    given.Add(step.QuestId);
                }

                if (ResolveQuestNpcId(step.ResponderKey) == spawn.InteractionId)
                {
                    received.Add(step.QuestId);
                }
            }

            projected ??= [.. spawns];
            projected[index] = spawn with
            {
                Detail10077 = PacketBuilder.QuestMarkerList(
                    spawn.InteractionId,
                    MergeMarkerEntries(
                        ReadMarkerEntries(spawn),
                        acceptable,
                        given)),
                Detail10080 = PacketBuilder.QuestHandInMenu(
                    spawn.InteractionId,
                    MergeHandInEntries(ReadHandInEntries(spawn), received))
            };
        }

        return projected ?? spawns;
    }

    /// <summary>
    /// Keeps a content table's quests and re-flags them for one character.
    /// </summary>
    /// <remarks>
    /// A quest is available only when it is the one the character may accept next,
    /// so a finished quest loses its flag and stops being offered even though the
    /// captured content table has it switched on.
    /// </remarks>
    internal static List<(uint QuestId, uint Available)> MergeMarkerEntries(
        IReadOnlyList<(uint QuestId, uint Available)> existing,
        uint acceptableQuestId,
        IReadOnlyList<uint> chainQuestIds)
    {
        var merged = new List<(uint, uint)>(existing.Count + chainQuestIds.Count);
        var seen = new HashSet<uint>();
        foreach (var entry in existing)
        {
            if (seen.Add(entry.QuestId))
            {
                merged.Add((
                    entry.QuestId,
                    entry.QuestId == acceptableQuestId ? 1u : 0u));
            }
        }

        foreach (var questId in chainQuestIds)
        {
            if (seen.Add(questId))
            {
                merged.Add((
                    questId,
                    questId == acceptableQuestId ? 1u : 0u));
            }
        }

        return merged;
    }

    /// <summary>Keeps a content table's hand-ins and adds missing chain rows.</summary>
    internal static List<uint> MergeHandInEntries(
        IReadOnlyList<uint> existing,
        IReadOnlyList<uint> chainQuestIds)
    {
        var merged = new List<uint>(existing.Count + chainQuestIds.Count);
        var seen = new HashSet<uint>();
        foreach (var questId in existing.Concat(chainQuestIds))
        {
            if (seen.Add(questId))
            {
                merged.Add(questId);
            }
        }

        return merged;
    }

    /// <summary>The 10077 entries for one npc: every quest it gives.</summary>
    private List<(uint QuestId, uint Available)> QuestMarkerEntries(uint npcId)
    {
        var acceptable = NextAcceptableQuest()?.QuestId ?? 0;
        var entries = new List<(uint, uint)>();
        foreach (var step in StarterQuestChain.Steps)
        {
            if (ResolveQuestNpcId(step.GiverKey) != npcId)
            {
                continue;
            }

            entries.Add((
                step.QuestId,
                step.QuestId == acceptable ? 1u : 0u));
        }

        return entries;
    }

    /// <summary>The 10080 entries for one npc: every quest it receives.</summary>
    private List<uint> QuestHandInEntries(uint npcId)
    {
        var entries = new List<uint>();
        foreach (var step in StarterQuestChain.Steps)
        {
            if (ResolveQuestNpcId(step.ResponderKey) == npcId)
            {
                entries.Add(step.QuestId);
            }
        }

        return entries;
    }

    /// <summary>Reads the 10077 entries a content table carries, if any.</summary>
    private static List<(uint QuestId, uint Available)> ReadMarkerEntries(
        NpcSpawnDefinition spawn)
    {
        var entries = new List<(uint, uint)>();
        var table = spawn.Detail10077;
        if (!IsQuestTable(
                table,
                Opcodes.QuestMarkerList,
                spawn.InteractionId))
        {
            return entries;
        }

        var count = (table.Length - 12) / 8;
        for (var index = 0; index < count; index++)
        {
            entries.Add((
                BinaryPrimitives.ReadUInt32LittleEndian(
                    table.AsSpan(12 + (index * 8), 4)),
                BinaryPrimitives.ReadUInt32LittleEndian(
                    table.AsSpan(16 + (index * 8), 4))));
        }

        return entries;
    }

    /// <summary>Reads the 10080 entries a content table carries, if any.</summary>
    private static List<uint> ReadHandInEntries(NpcSpawnDefinition spawn)
    {
        var entries = new List<uint>();
        var table = spawn.Detail10080;
        if (!IsQuestTable(
                table,
                Opcodes.QuestHandInList,
                spawn.InteractionId))
        {
            return entries;
        }

        var count = (table.Length - 12) / 4;
        for (var index = 0; index < count; index++)
        {
            entries.Add(BinaryPrimitives.ReadUInt32LittleEndian(
                table.AsSpan(12 + (index * 4), 4)));
        }

        return entries;
    }

    private static bool IsQuestTable(
        byte[] table,
        ushort opcode,
        uint interactionId) =>
        table.Length >= 12 &&
        BinaryPrimitives.ReadUInt16LittleEndian(table.AsSpan(0, 2)) ==
            table.Length &&
        BinaryPrimitives.ReadUInt16LittleEndian(table.AsSpan(2, 2)) == opcode &&
        BinaryPrimitives.ReadUInt32LittleEndian(table.AsSpan(4, 4)) ==
            interactionId;
}
