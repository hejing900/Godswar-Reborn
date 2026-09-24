using System.Buffers.Binary;
using Godswar.Server.Domain.World.Content;
using Godswar.Server.Protocol;

namespace Godswar.Server.Packets;

internal static partial class PacketBuilder
{
    /// <summary>
    /// Where the 10082 accept answer carries its eight 72-byte reward slots.
    /// </summary>
    /// <remarks>
    /// Payload offset 60, so frame offset 64 once the 4-byte length+opcode header
    /// is counted. Confirmed against the capture: the newbie gift bag 240f0000
    /// sits at frame 72 of packet 247, and that is slot 0 plus its eight-byte
    /// record prefix.
    /// </remarks>
    private const int QuestAnswerRecordOffset = 64;

    /// <summary>
    /// Where the 10076 follow-up detail carries the same reward slots.
    /// </summary>
    /// <remarks>
    /// The same records, four bytes earlier than in 10082 and only four slots
    /// deep: packet 1341 has the first slot's reward item at payload 64, which is
    /// slot 0 plus eight, so its records start at payload 56.
    /// </remarks>
    private const int QuestNextDetailRecordOffset = 60;

    /// <summary>How many of a quest's slots the 10076 detail carries.</summary>
    private const int QuestNextDetailRecordBytes = 4 * 72;

    /// <summary>
    /// Where the 10082 kill-quest frame carries the target monster id.
    /// </summary>
    /// <remarks>
    /// Payload +28, so frame +32. Taken from the reference server's own answer for
    /// quest 520, which asked for the ten Dumb Wood Men whose id is 1027.
    /// </remarks>
    private const int ObjectiveAnswerMonsterOffset = 32;

    /// <summary>Where the 10082 kill-quest frame carries the required count.</summary>
    private const int ObjectiveAnswerRequiredOffset = 48;

    /// <summary>
    /// Where the 10082 kill-quest frame carries its kill-quest marker.
    /// </summary>
    /// <remarks>
    /// The reference server's answer for quest 1533 - two targets, 1414 and 1415 -
    /// reads 8 here, the same marker the 10076 detail and the login snapshot
    /// carry.
    /// </remarks>
    private const int ObjectiveAnswerKindOffset = 20;

    /// <summary>
    /// How many targets the parallel objective arrays can hold.
    /// </summary>
    /// <remarks>
    /// The monster array starts at 10082 <c>+32</c> and the count array at
    /// <c>+48</c>, sixteen bytes apart; the login snapshot's descriptor gives each
    /// of its two arrays twelve bytes before the next field. Six is therefore what
    /// every frame can carry, and no quest in the content names more than three
    /// targets.
    /// </remarks>
    private const int QuestObjectiveMaximumSlots = 6;

    /// <summary>
    /// The 10076 equivalents of those two fields, four bytes earlier.
    /// </summary>
    /// <remarks>
    /// The same parallel objective arrays as 10082, four bytes earlier, and the
    /// builder fills them for every quest that names a target - one slot per
    /// target.
    /// <para>
    /// History worth keeping: the 2026-09-13 capture had every one of its 79 10076
    /// frames carrying <c>kind = 4</c>, <c>monster = 0</c> and <c>required = 0</c>,
    /// and filling a single objective into one of them (quest 532) made the client
    /// fault with a null dereference - because the frame then disagreed with the
    /// reference in exactly four bytes, with a kill-quest marker that did not match
    /// the half-filled area. The 2026-09-24 capture settled it: the reference's own
    /// 10076 for the two-target quest 1533 carries <c>kind = 8</c> with both of its
    /// targets in the first two slots. Kind and area are therefore written
    /// together, never one without the other.
    /// </para>
    /// </remarks>
    private const int QuestNextDetailMonsterOffset = 28;
    private const int QuestNextDetailRequiredOffset = 44;

    /// <summary>
    /// The field that reads 4 for a quest with nothing to kill and 8 for one with
    /// a kill objective, at its 10076 offset.
    /// </summary>
    private const int QuestNextDetailKindOffset = 16;

    /// <summary>Bytes of one quest descriptor in the login snapshot.</summary>
    private const int QuestSnapshotDescriptorBytes = 96;

    /// <summary>
    /// Where a descriptor carries the target monster, how many are wanted, the
    /// kill-quest marker and how many are done, measured from the quest id.
    /// </summary>
    private const int QuestSnapshotMonsterOffset = 40;
    private const int QuestSnapshotRequiredOffset = 56;
    private const int QuestSnapshotKindOffset = 68;
    private const int QuestSnapshotProgressOffset = 80;

    /// <summary>The marker a quest with something to kill carries.</summary>
    private const int QuestWithObjectivesKind = 8;

    /// <summary>
    /// Where the first descriptor starts: the count is one 4-byte word, and the
    /// captured frame's quest id sits at payload 4, which is frame 8.
    /// </summary>
    private const int QuestSnapshotFirstDescriptor = 8;

    /// <summary>Bytes of one record slot, in both the login snapshot and 10082.</summary>
    private const int QuestRecordBytes = 72;

    /// <summary>The fill flag an unused record slot carries in the capture.</summary>
    private const uint QuestRecordEmptyFlag = 0x01000101;

    // Verified field layouts, read off the reference capture. Offsets count from
    // the start of the frame, so "+4" is the first payload word after the 4-byte
    // length+opcode header:
    //
    //   10090 S2C  +4 count | 96-byte descriptors | 72-byte records
    //   10083 S2C  +4 quest | +8 responder | +12 quest | +16 = 1
    //   10082 S2C  +4 giver | +8 responder | +12 quest | +16 slot count
    //              then 72-byte slots from +60: +8 reward item, +12..+28 -1 x5,
    //              +32 fill flag
    //   10084 S2C  +4 responder | +8 quest
    //   10086 S2C  +4 giver | +8 responder | +12 quest
    //   10076 S2C  +4 giver | +8 quest
    //   10077 S2C  +4 npc | +8 count | (quest, available) x count
    //   10080 S2C  +4 npc | +8 count | quest x count
    //
    // Every field that varies from quest to quest is a parameter, and the two
    // lists are assembled from the chain, so adding a quest never adds packet
    // code - it only adds a chain row.

    /// <summary>One target a carried quest is still counting.</summary>
    /// <remarks>
    /// A quest can name several targets, and the snapshot carries every one of
    /// them: the objective areas are parallel arrays, so slot <c>i</c> of the
    /// monster array belongs with slot <c>i</c> of the count and progress arrays.
    /// </remarks>
    internal readonly record struct QuestSnapshotObjective(
        uint MonsterId,
        int Required,
        int Current);

    /// <summary>One quest as the login snapshot describes it.</summary>
    /// <remarks>
    /// The descriptor carries the target monster, how many are wanted and how many
    /// are done, so a quest picked up again after a relog still shows what it is
    /// waiting for. The offsets are the reference server's own: its snapshot for a
    /// character carrying quest 520 at three of ten had the monster at +40, the
    /// count at +56, the kill-quest marker at +68 and <c>3 &lt;&lt; 16</c> - the
    /// progress - at +80.
    /// <para>
    /// <paramref name="Objectives"/> is the multi-target form: when it is given,
    /// every entry fills one slot of the parallel arrays and the single
    /// <paramref name="MonsterId"/>/<paramref name="Required"/>/<paramref name="Current"/>
    /// triple is ignored. The single form is kept because captured frames and
    /// existing callers pass exactly one target, and it must stay byte for byte
    /// what it was.
    /// </para>
    /// </remarks>
    internal readonly record struct QuestSnapshotEntry(
        uint QuestId,
        uint GiverNpcId,
        uint ResponderNpcId,
        uint MonsterId = 0,
        int Required = 0,
        int Current = 0,
        IReadOnlyList<QuestSnapshotObjective>? Objectives = null);

    /// <summary>
    /// Builds the opcode-10090 accepted-quest snapshot from the captured frame.
    /// </summary>
    /// <remarks>
    /// Captured layout, all offsets from the frame start:
    /// <list type="bullet">
    /// <item><c>+4</c> the quest count.</item>
    /// <item>one 96-byte descriptor per quest, starting at <c>+8</c>: quest id,
    /// giver npc, responder npc.</item>
    /// <item>one 72-byte record per quest after the descriptors: <c>+8</c> reward
    /// item, <c>+12..+28</c> five <c>-1</c>, <c>+32</c> the fill flag.</item>
    /// </list>
    /// The capture holds one quest, and for one quest this reproduces it byte for
    /// byte - descriptor at payload 4 and record at payload 100, which is what
    /// <c>4 + 96</c> works out to. A character carrying several quests is the same
    /// structure with the count raised, so the records follow the descriptors;
    /// that part has no reference sample yet.
    /// <para>
    /// An empty snapshot (count zero) leaves the frame's own slots alone: it
    /// advertises no quest, which is how a character holding none is represented.
    /// </para>
    /// </remarks>
    public static byte[] QuestSnapshot(IReadOnlyList<QuestSnapshotEntry> quests)
    {
        var packet = (byte[])LoginSnapshotFrame().Clone();
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(4, sizeof(uint)), (uint)quests.Count);
        if (quests.Count == 0)
        {
            return packet;
        }

        var descriptor = QuestSnapshotFirstDescriptor;
        foreach (var quest in quests)
        {
            BinaryPrimitives.WriteUInt32LittleEndian(
                packet.AsSpan(descriptor, 4), quest.QuestId);
            BinaryPrimitives.WriteUInt32LittleEndian(
                packet.AsSpan(descriptor + 4, 4), quest.GiverNpcId);
            BinaryPrimitives.WriteUInt32LittleEndian(
                packet.AsSpan(descriptor + 8, 4), quest.ResponderNpcId);
            var descriptorObjectives = quest.Objectives;
            if (descriptorObjectives is { Count: > 0 })
            {
                WriteSnapshotObjectives(
                    packet.AsSpan(descriptor),
                    descriptorObjectives);
            }
            else if (quest.Required > 0)
            {
                BinaryPrimitives.WriteUInt32LittleEndian(
                    packet.AsSpan(
                        descriptor + QuestSnapshotMonsterOffset,
                        4),
                    quest.MonsterId);
                BinaryPrimitives.WriteInt32LittleEndian(
                    packet.AsSpan(
                        descriptor + QuestSnapshotRequiredOffset,
                        4),
                    quest.Required);
                BinaryPrimitives.WriteInt32LittleEndian(
                    packet.AsSpan(descriptor + QuestSnapshotKindOffset, 4),
                    QuestWithObjectivesKind);
                BinaryPrimitives.WriteInt32LittleEndian(
                    packet.AsSpan(descriptor + QuestSnapshotProgressOffset, 4),
                    Math.Clamp(quest.Current, 0, ushort.MaxValue) << 16);
            }

            descriptor += QuestSnapshotDescriptorBytes;
        }

        var record = QuestSnapshotFirstDescriptor +
            (quests.Count * QuestSnapshotDescriptorBytes);
        foreach (var quest in quests)
        {
            WriteQuestRecord(packet, record, quest.QuestId);
            record += QuestRecordBytes;
        }

        return packet;
    }

    /// <summary>
    /// Writes one quest's 72-byte record slot over whatever the frame held.
    /// </summary>
    /// <remarks>
    /// The slot is the first of the quest's captured 10082 reward slots - the two
    /// frames use the same 72-byte record, which is why quest 518's slot carries
    /// the same newbie gift bag at the same offset inside the slot. A quest with
    /// no captured record keeps the frame's own empty-slot pattern rather than an
    /// invented one.
    /// </remarks>
    private static void WriteQuestRecord(byte[] packet, int offset, uint questId)
    {
        packet.AsSpan(offset, QuestRecordBytes).Clear();
        for (var index = 0; index < 5; index++)
        {
            BinaryPrimitives.WriteUInt32LittleEndian(
                packet.AsSpan(offset + 12 + (index * 4), 4),
                uint.MaxValue);
        }

        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(offset + 32, 4), QuestRecordEmptyFlag);

        if (StarterQuestRewardRecords.Find(questId) is
            { Length: >= QuestRecordBytes } records)
        {
            records.AsSpan(0, QuestRecordBytes).CopyTo(
                packet.AsSpan(offset, QuestRecordBytes));
        }
    }

    /// <summary>
    /// Builds the opcode-10083 scene answer from the captured frame.
    /// </summary>
    /// <remarks>
    /// Captured shape: <c>+4</c> the offered quest, <c>+8</c> the responder npc,
    /// <c>+12</c> the offered quest again and <c>+16</c> the constant 1. The
    /// client's scene key (its request carries 0x1AF720 at <c>+4</c>) does not
    /// come back in the answer, so there is nothing to echo.
    /// </remarks>
    public static byte[] QuestSceneOfferAck(uint questId, uint responderNpcId)
    {
        var packet = (byte[])SceneOfferFrame().Clone();
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(4, sizeof(uint)), questId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(8, sizeof(uint)), responderNpcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(12, sizeof(uint)), questId);
        return packet;
    }

    /// <summary>
    /// Builds the opcode-10082 accept answer from the captured frame.
    /// </summary>
    /// <remarks>
    /// <c>+4</c> giver, <c>+8</c> responder and <c>+12</c> quest are the only
    /// header fields the two captured cycles differ in, and every other difference
    /// lies inside the four reward slots. The slots are therefore the per-quest
    /// part and come from <see cref="StarterQuestRewardRecords"/>; a quest with no
    /// captured records keeps the frame's own slots, because there is no reference
    /// sample to copy for it.
    /// <para>
    /// A quest with no kill objective the capture answered keeps its own frame
    /// instead: <see cref="CapturedQuestAnswers"/> holds the reference's 648 bytes
    /// for it, and only the giver and responder are patched. Quest 1519 answers
    /// with the four class-weapon slots (1000/1400/1700/1800) while the template
    /// carries quest 518's single gift bag; serving the template there handed the
    /// client a one-slot answer for a four-slot quest, and its quest window faulted
    /// at <c>004AC835</c> when the hand-in refreshed that record.
    /// </para>
    /// <para>
    /// The objective area holds exactly one target, so only a quest with exactly
    /// one objective uses it: the capture filled it for the single-target quests
    /// (520 <c>kind=8</c> required 10, 1520 required 10, 1521 required 12) and left
    /// it empty for every multi-target one (528, 533, 537 and 539 - two targets
    /// each - all <c>kind=4</c> with a zero objective). Writing the first target
    /// into a multi-target quest replaced the client's own objective list with one
    /// line, which is why such a quest showed a single counter and hid the rest.
    /// </para>
    /// </remarks>
    public static byte[] QuestAnswer(
        uint giverNpcId,
        uint responderNpcId,
        uint questId)
    {
        var objectives = StarterQuestObjectives.For(questId);
        if (objectives.Count == 0 &&
            CapturedQuestAnswers.TryGetValue(questId, out var capturedHex))
        {
            var captured = Convert.FromHexString(capturedHex);
            BinaryPrimitives.WriteUInt32LittleEndian(
                captured.AsSpan(4, sizeof(uint)), giverNpcId);
            BinaryPrimitives.WriteUInt32LittleEndian(
                captured.AsSpan(8, sizeof(uint)), responderNpcId);
            return captured;
        }

        var hasObjectives = objectives.Count > 0;
        var packet = hasObjectives
            ? (byte[])Objective10082Bytes.Clone()
            : (byte[])AcceptAnswerFrame().Clone();
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(4, sizeof(uint)), giverNpcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(8, sizeof(uint)), responderNpcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(12, sizeof(uint)), questId);
        if (hasObjectives)
        {
            // Every target the quest names goes into its own slot: the reference
            // server's own answer for quest 1533, which asks for fifteen Plumed
            // and fifteen Frenzied Harpies, carries monster 1414/1415 and count
            // 20/20 in the first two slots of the two arrays. Writing only the
            // first target is what left a multi-target quest showing one line.
            WriteObjectiveSlots(
                packet,
                ObjectiveAnswerMonsterOffset,
                ObjectiveAnswerRequiredOffset,
                objectives);
            BinaryPrimitives.WriteInt32LittleEndian(
                packet.AsSpan(ObjectiveAnswerKindOffset, sizeof(int)),
                QuestWithObjectivesKind);
        }

        ApplyQuestRewardRecords(
            packet,
            QuestAnswerRecordOffset,
            questId,
            StarterQuestRewardRecords.AreaBytes,
            hasObjectives ? 8u : 4u);
        return packet;
    }

    /// <summary>
    /// Builds the opcode-10084 accept confirmation from the captured frame.
    /// </summary>
    /// <remarks>Captured shape: <c>+4</c> responder npc, <c>+8</c> quest.</remarks>
    public static byte[] QuestConfirm(uint responderNpcId, uint questId)
    {
        var packet = (byte[])AcceptConfirmFrame().Clone();
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(4, sizeof(uint)), responderNpcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(8, sizeof(uint)), questId);
        return packet;
    }

    /// <summary>
    /// Builds the opcode-10086 hand-in acknowledgement.
    /// </summary>
    /// <remarks>
    /// Captured shape: <c>+4</c> giver, <c>+8</c> responder, <c>+12</c> the quest
    /// the hand-in completed, <c>+16</c> the reward slot the client asked to be
    /// paid, <c>+28</c> the player's experience and <c>+36</c> the player's talent
    /// points after the reward.
    /// <para>
    /// The three value fields are the frame's own, not the template's. The client
    /// reads <c>+16</c> as the index of the reward slot it must pay out of the
    /// quest record's own slot area, and the reference echoes the index the client
    /// put in its hand-in request: 0 for a quest that pays one item, the chosen
    /// slot for the class-weapon choice (1519 carries 3), and <c>-1</c> for a quest
    /// that pays nothing (1521, 1522). A quest without a captured acknowledgement
    /// used to keep the template's 0, so the client was told to pay slot 0 of a
    /// quest whose slots are all free - that is the 004AC835 null dereference, and
    /// it is what broke every quest the capture never answered (Athens 1522).
    /// </para>
    /// <para>
    /// Experience and talent points are the player's post-hand-in values, exactly
    /// as the reference's own acknowledgements carry them (1518 exp 40 tp 2, 1519
    /// exp 88 tp 5, 1520 exp 183 tp 9, 1521 exp 333 tp 11 - each equal to wire 96
    /// and wire 228 of the status frame sent with it).
    /// </para>
    /// </remarks>
    public static byte[] QuestHandInAck(
        uint giverNpcId,
        uint responderNpcId,
        uint questId,
        uint rewardIndex,
        int experience,
        int talentPoints)
    {
        var packet = CapturedHandInAcks.TryGetValue(questId, out var captured)
            ? Convert.FromHexString(captured)
            : (byte[])HandInAckBytes.Clone();
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(4, sizeof(uint)), giverNpcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(8, sizeof(uint)), responderNpcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(12, sizeof(uint)), questId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(QuestHandInRewardIndexOffset, sizeof(uint)),
            rewardIndex);
        BinaryPrimitives.WriteInt32LittleEndian(
            packet.AsSpan(QuestHandInExperienceOffset, sizeof(int)),
            experience);
        BinaryPrimitives.WriteInt32LittleEndian(
            packet.AsSpan(QuestHandInTalentPointsOffset, sizeof(int)),
            talentPoints);
        return packet;
    }

    /// <summary>
    /// Where the 10086 acknowledgement carries the reward slot the client asked
    /// for, the player's experience and the player's talent points.
    /// </summary>
    /// <remarks>
    /// Verified against every captured acknowledgement, e.g. quest 1519's on
    /// 2026-09-14 01:08:15 (index 3, exp 88, tp 5) and quest 1521's on
    /// 2026-09-14 01:12:57 (index -1, exp 333, tp 11).
    /// </remarks>
    private const int QuestHandInRewardIndexOffset = 16;
    private const int QuestHandInExperienceOffset = 28;
    private const int QuestHandInTalentPointsOffset = 36;

    /// <summary>
    /// Builds the opcode-10076 follow-up detail from the captured frame.
    /// </summary>
    /// <remarks>
    /// Captured shape: <c>+4</c> the next giver, <c>+8</c> the next quest. This is
    /// what makes the client pop the follow-up quest after a hand-in.
    /// <para>
    /// The reference sends one detail per next quest and they are not uniform:
    /// quest 1521's carries <c>kind = 8</c> with its kill objective (monster 1011,
    /// 12 required) and empty reward slots, while the Sparta chain's carry
    /// <c>kind = 4</c>, no objective and their own reward slots. The captured frame
    /// for the quest is therefore replayed as it is, and only the giver is patched;
    /// filling the objective into a frame that came from a different quest, or
    /// copying another quest's reward slots over it, is what made the client fault
    /// on the hand-in. A quest the capture never answered keeps the template.
    /// </para>
    /// </remarks>
    /// <summary>
    /// True when the reference capture answered this quest's follow-up detail.
    /// </summary>
    /// <remarks>
    /// The fallback below is another quest's frame: its objective area and its
    /// four reward slots belong to that quest. Replaying them for a quest the
    /// capture never answered is what faults the installed client at
    /// <c>004AC835</c> right after a hand-in, so a caller that has no captured
    /// answer for the next quest must not ask for the frame at all.
    /// </remarks>
    public static bool HasCapturedQuestNextDetail(uint questId) =>
        CapturedNextQuestDetails.ContainsKey(questId);

    public static byte[] QuestNextDetail(uint giverNpcId, uint questId)
    {
        if (CapturedNextQuestDetails.TryGetValue(questId, out var captured))
        {
            var capturedPacket = Convert.FromHexString(captured);
            BinaryPrimitives.WriteUInt32LittleEndian(
                capturedPacket.AsSpan(4, sizeof(uint)), giverNpcId);
            return capturedPacket;
        }

        var detailObjectives = StarterQuestObjectives.For(questId);
        var detailHasObjectives = detailObjectives.Count > 0;
        var packet = (byte[])HandInDetailBytes.Clone();
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(4, sizeof(uint)), giverNpcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(8, sizeof(uint)), questId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(QuestNextDetailKindOffset, sizeof(uint)),
            detailHasObjectives ? 8u : 4u);
        if (detailHasObjectives)
        {
            // The same parallel arrays as 10082, four bytes earlier. The reference
            // server's own 10076 for quest 1533 carries both of its targets, so a
            // multi-target follow-up detail is written the same way as the accept
            // answer rather than left empty.
            WriteObjectiveSlots(
                packet,
                QuestNextDetailMonsterOffset,
                QuestNextDetailRequiredOffset,
                detailObjectives);
        }

        ApplyQuestRewardRecords(
            packet,
            QuestNextDetailRecordOffset,
            questId,
            QuestNextDetailRecordBytes,
            detailHasObjectives ? 8u : 4u);
        return packet;
    }

    /// <summary>
    /// Copies a quest's captured reward slots over the frame's own.
    /// </summary>
    /// <remarks>
    /// The slots belong to the quest, not to the frame, and their number differs
    /// even between siblings: 519 offers the four class weapons, 520 one light
    /// armour, 1521 and 1522 nothing. So the area comes from that quest's own
    /// captured answer - the sample whose objective kind matches the shape being
    /// sent - then from the quest's captured records, and otherwise stays free.
    /// Leaving the template's slots in place was shipping another quest's rewards,
    /// which is what faulted the client at <c>004AC835</c> (one slot for the
    /// four-slot choice of 1519, one bag for the empty 1522).
    /// </remarks>
    private static void ApplyQuestRewardRecords(
        byte[] packet,
        int offset,
        uint questId,
        int bytes,
        uint objectiveKind)
    {
        if (CapturedQuestRewardAreas.TryGetValue(
                (questId, objectiveKind),
                out var areaHex) ||
            CapturedQuestRewardAreas.TryGetValue(
                (questId, objectiveKind == 8u ? 4u : 8u),
                out areaHex))
        {
            var area = Convert.FromHexString(areaHex);
            var capturedLength = Math.Min(bytes, area.Length);
            area.AsSpan(0, capturedLength)
                .CopyTo(packet.AsSpan(offset, capturedLength));
            return;
        }

        if (StarterQuestRewardRecords.Find(questId) is { } records)
        {
            var length = Math.Min(bytes, records.Length);
            records.AsSpan(0, length).CopyTo(packet.AsSpan(offset, length));
            return;
        }

        var emptyLength = Math.Min(bytes, EmptyQuestRewardArea.Length);
        EmptyQuestRewardArea.AsSpan(0, emptyLength)
            .CopyTo(packet.AsSpan(offset, emptyLength));
    }

    /// <summary>
    /// Writes every target a quest names into the frame's parallel objective
    /// arrays: slot <c>i</c> holds one monster id and one required count.
    /// </summary>
    /// <remarks>
    /// Verified against the reference server's own answer for quest 1533, whose
    /// objective area carries monster 1414 at <c>+32</c> and 1415 at <c>+34</c>,
    /// with 20 at <c>+48</c> and 20 at <c>+50</c>. The area is cleared first so a
    /// template's own single target cannot bleed into a later slot.
    /// </remarks>
    private static void WriteObjectiveSlots(
        byte[] packet,
        int monsterOffset,
        int requiredOffset,
        IReadOnlyList<QuestObjective> objectives)
    {
        packet.AsSpan(monsterOffset, QuestObjectiveMaximumSlots * 2).Clear();
        packet.AsSpan(requiredOffset, QuestObjectiveMaximumSlots * 2).Clear();
        var count = Math.Min(objectives.Count, QuestObjectiveMaximumSlots);
        for (var slot = 0; slot < count; slot++)
        {
            BinaryPrimitives.WriteUInt16LittleEndian(
                packet.AsSpan(monsterOffset + (slot * 2), 2),
                checked((ushort)Math.Clamp(
                    objectives[slot].MonsterId,
                    0u,
                    ushort.MaxValue)));
            BinaryPrimitives.WriteUInt16LittleEndian(
                packet.AsSpan(requiredOffset + (slot * 2), 2),
                checked((ushort)Math.Clamp(
                    objectives[slot].Required,
                    0,
                    ushort.MaxValue)));
        }
    }

    /// <summary>
    /// Writes a carried quest's targets into one login-snapshot descriptor, plus
    /// the progress of each slot.
    /// </summary>
    /// <remarks>
    /// The monster and count arrays are the same parallel u16 arrays as 10082, at
    /// the descriptor's own offsets. Progress is the one field with no
    /// multi-target sample: the captured single-target descriptor puts the count
    /// done in the high half of the word at <c>+80</c> (<c>3 &lt;&lt; 16</c> for
    /// three of ten), so slot <c>i</c> keeps that shape at <c>+80 + 4i</c>. That
    /// per-slot stride is inferred, not captured.
    /// </remarks>
    private static void WriteSnapshotObjectives(
        Span<byte> descriptor,
        IReadOnlyList<QuestSnapshotObjective> objectives)
    {
        descriptor.Slice(
            QuestSnapshotMonsterOffset,
            QuestObjectiveMaximumSlots * 2).Clear();
        descriptor.Slice(
            QuestSnapshotRequiredOffset,
            QuestObjectiveMaximumSlots * 2).Clear();
        var count = Math.Min(objectives.Count, QuestObjectiveMaximumSlots);
        for (var slot = 0; slot < count; slot++)
        {
            BinaryPrimitives.WriteUInt16LittleEndian(
                descriptor.Slice(QuestSnapshotMonsterOffset + (slot * 2), 2),
                checked((ushort)Math.Clamp(
                    objectives[slot].MonsterId,
                    0u,
                    ushort.MaxValue)));
            BinaryPrimitives.WriteUInt16LittleEndian(
                descriptor.Slice(QuestSnapshotRequiredOffset + (slot * 2), 2),
                checked((ushort)Math.Clamp(
                    objectives[slot].Required,
                    0,
                    ushort.MaxValue)));
            BinaryPrimitives.WriteInt32LittleEndian(
                descriptor.Slice(QuestSnapshotProgressOffset + (slot * 4), 4),
                Math.Clamp(objectives[slot].Current, 0, ushort.MaxValue) << 16);
        }

        BinaryPrimitives.WriteInt32LittleEndian(
            descriptor.Slice(QuestSnapshotKindOffset, 4),
            QuestWithObjectivesKind);
    }

    /// <summary>
    /// Builds the opcode-10077 npc quest list, the table behind the quest mark
    /// over an npc.
    /// </summary>
    /// <remarks>
    /// Captured shape: <c>+4</c> npc, <c>+8</c> entry count, then one
    /// (quest, available) pair per entry, 8 bytes each. The captured frame for
    /// npc 5103 lists 519/522/524 - exactly the chain rows whose giver is that
    /// npc - so the list is derived from the chain instead of replayed, which is
    /// what keeps new quests data-only. <paramref name="available"/> is 1 for the
    /// quest the character can accept right now and 0 for the rest.
    /// </remarks>
    public static byte[] QuestMarkerList(
        uint npcId,
        IReadOnlyList<(uint QuestId, uint Available)> entries)
    {
        var packet = new byte[12 + (entries.Count * 8)];
        BinaryPrimitives.WriteUInt16LittleEndian(
            packet.AsSpan(0, 2), checked((ushort)packet.Length));
        BinaryPrimitives.WriteUInt16LittleEndian(
            packet.AsSpan(2, 2), Opcodes.QuestMarkerList);
        BinaryPrimitives.WriteUInt32LittleEndian(packet.AsSpan(4, 4), npcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(8, 4), (uint)entries.Count);

        var offset = 12;
        foreach (var entry in entries)
        {
            BinaryPrimitives.WriteUInt32LittleEndian(
                packet.AsSpan(offset, 4), entry.QuestId);
            BinaryPrimitives.WriteUInt32LittleEndian(
                packet.AsSpan(offset + 4, 4), entry.Available);
            offset += 8;
        }

        return packet;
    }

    /// <summary>
    /// Builds the opcode-10080 npc hand-in list.
    /// </summary>
    /// <remarks>
    /// Captured shape: <c>+4</c> npc, <c>+8</c> entry count, then one quest id per
    /// entry. The captured frame for npc 5103 lists 518/521/523 - exactly the
    /// chain rows whose responder is that npc - so this list is derived from the
    /// chain too.
    /// </remarks>
    public static byte[] QuestHandInMenu(uint npcId, IReadOnlyList<uint> questIds)
    {
        var packet = new byte[12 + (questIds.Count * 4)];
        BinaryPrimitives.WriteUInt16LittleEndian(
            packet.AsSpan(0, 2), checked((ushort)packet.Length));
        BinaryPrimitives.WriteUInt16LittleEndian(
            packet.AsSpan(2, 2), Opcodes.QuestHandInList);
        BinaryPrimitives.WriteUInt32LittleEndian(packet.AsSpan(4, 4), npcId);
        BinaryPrimitives.WriteUInt32LittleEndian(
            packet.AsSpan(8, 4), (uint)questIds.Count);

        var offset = 12;
        foreach (var questId in questIds)
        {
            BinaryPrimitives.WriteUInt32LittleEndian(
                packet.AsSpan(offset, 4), questId);
            offset += 4;
        }

        return packet;
    }
}
