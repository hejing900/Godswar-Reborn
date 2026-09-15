using System.Buffers.Binary;
using Godswar.Server.Application.World.Content;
using Godswar.Server.Game;
using Godswar.Server.State;

namespace Godswar.Server.ProtocolChecks;

/// <summary>
/// Locks the capture-proven drop channel: the database-owned tables and their
/// migration seed, the deterministic roll, the ground-item identity written
/// into opcode 10029, and the 10056 pickup descriptor the installed client
/// actually sends.
/// </summary>
internal static class MonsterLootChannelChecks
{
    public const string CheckName = "Monster drop channel";

    public static Task RunAsync()
    {
        CheckMigrationOwnsTheTables();
        CheckCaptureProvenTables();
        CheckRollIsDeterministicAndCapped();
        CheckGroundKeys();
        CheckCapturedPickupDescriptor();
        CheckCapturedCorpseClickReply();
        return Task.CompletedTask;
    }

    /// <summary>
    /// The corpse click that opens the client's loot window and tells it which
    /// drop to move. Without this reply the installed client never sends a
    /// pickup at all, so the captured bytes are pinned exactly - including the
    /// echoed drop index, which is what the two captured clicks differ in.
    /// </summary>
    private static void CheckCapturedCorpseClickReply()
    {
        // Captured S2C 10050 at 01:37:27.113 answering the 01:37:26.770 click on
        // corpse 10492 with drop index 1: player 981, corpse 10492, index 1.
        // The 10056 at 01:37:27.118 then named record 1's item (Raw Gem 12040)
        // and its ground key E36F1A70:00065B74.
        var secondDrop = Godswar.Server.Packets.PacketBuilder.MonsterLootSourceOpen(
            981u,
            10492u,
            1);
        Check.True(
            Convert.ToHexString(secondDrop) ==
                "10004227D5030000FC28000001000000",
            "the corpse-click reply matches the captured opcode-10050 frame");

        // Captured S2C 10050 at 01:37:27.883 answering the 01:37:27.540 click
        // with drop index 0: the same corpse answered with the index echoed.
        // The 10056 at 01:37:27.888 then named record 0's item (4224) and its
        // ground key E36F18E2:00065B74.
        var firstDrop = Godswar.Server.Packets.PacketBuilder.MonsterLootSourceOpen(
            981u,
            10492u,
            0);
        Check.True(
            Convert.ToHexString(firstDrop) ==
                "10004227D5030000FC28000000000000",
            "the corpse-click reply echoes the clicked drop index");

        // Every drop source in the server - the database loot tables and the
        // Medusa instance rules - numbers its 10029 records from zero in list
        // order, so the reply has to echo any index of a corpse window, not
        // just the two captured ones.
        for (var index = 0; index < 32; index++)
        {
            var reply = Godswar.Server.Packets.PacketBuilder.MonsterLootSourceOpen(
                981u,
                10492u,
                index);
            Check.True(
                reply.Length == 16 &&
                BinaryPrimitives.ReadUInt16LittleEndian(reply) == 16 &&
                BinaryPrimitives.ReadUInt16LittleEndian(reply.AsSpan(2)) ==
                    Godswar.Server.Protocol.Opcodes.MoveItem &&
                BinaryPrimitives.ReadUInt32LittleEndian(reply.AsSpan(4)) == 981u &&
                BinaryPrimitives.ReadUInt32LittleEndian(reply.AsSpan(8)) == 10492u &&
                BinaryPrimitives.ReadUInt32LittleEndian(reply.AsSpan(12)) ==
                    (uint)index,
                $"the corpse-click reply echoes drop index {index}");
        }

        Check.True(
            Throws(() =>
                Godswar.Server.Packets.PacketBuilder.MonsterLootSourceOpen(
                    981u,
                    10492u,
                    32)),
            "a drop index outside the 10029 record cap is rejected");
    }

    private static bool Throws(Action action)
    {
        try
        {
            action();
            return false;
        }
        catch (ArgumentOutOfRangeException)
        {
            return true;
        }
    }

    /// <summary>
    /// The loot tables are database-owned, exactly like the Medusa ones: one
    /// migration owns the schema and the captured seed.
    /// </summary>
    private static void CheckMigrationOwnsTheTables()
    {
        var migration = PostgresSchemaMigrationCatalog.All.Single(
            static migration => migration.Id ==
                "20260915_147_monster_loot_policy");
        foreach (var fragment in new[]
                 {
                     "CREATE TABLE IF NOT EXISTS public.monster_loot_tables",
                     "CREATE TABLE IF NOT EXISTS public.monster_loot_rules",
                     "REFERENCES public.item_templates(id)",
                     "REFERENCES public.monster_loot_tables(template_key)",
                     "ON DELETE CASCADE",
                     "chance_basis_points BETWEEN 1 AND 10000",
                     "('A_normal_stub_001', 0, 4529, 2500, 1, 1)",
                     "('A_normal_stub_002', 5, 12040, 2500, 1, 1)",
                     "('A_normal_deer_001', 0, 4001, 2500, 1, 1)"
                 })
        {
            Check.True(
                migration.Sql.Contains(fragment, StringComparison.Ordinal),
                $"monster loot migration contains {fragment}");
        }
    }

    private static void CheckCaptureProvenTables()
    {
        var content = MonsterLootContentCatalog.Current;
        Check.Equal(
            3,
            content.Tables.Count,
            "three capture-proven monsters own a loot table");

        Check.True(
            content.TryGetTable("A_normal_stub_002", out var stub) &&
            stub.MaximumDrops == 2,
            "the Athens stub caps one kill at the captured two items");

        Check.True(
            content.Loot
                .Where(static rule => rule.TemplateKey == "A_normal_stub_002")
                .Select(static rule => rule.ItemId)
                .Order()
                .SequenceEqual([4003u, 4150u, 4224u, 4529u, 12030u, 12040u]),
            "the Athens stub keeps its four-kill item set");

        Check.True(
            content.Loot
                .Where(static rule => rule.TemplateKey == "A_normal_stub_001")
                .Select(static rule => rule.ItemId)
                .SequenceEqual([4529u]) &&
            content.Loot
                .Where(static rule => rule.TemplateKey == "A_normal_deer_001")
                .Select(static rule => rule.ItemId)
                .SequenceEqual([4001u]),
            "the Sparta stub and the Athens deer keep their single capture-proven drop");

        Check.True(
            !content.TryGetTable("A_normal_unknown_001", out _) &&
            !content.TryGetTable(null, out _) &&
            content.Loot.All(static rule => rule.ChanceBasisPoints == 2_500),
            "uncaptured monsters drop nothing and seeded chances stay placeholders");
    }

    private static void CheckRollIsDeterministicAndCapped()
    {
        var content = MonsterLootContentCatalog.Current;
        var deathEventId = new Guid("6f0f1c2a-5d3b-4a1e-9c44-70b2c9a31f5d");
        var first = content.RollLoot("A_normal_stub_002", deathEventId);
        var replay = content.RollLoot("A_normal_stub_002", deathEventId);
        Check.True(
            first.SequenceEqual(replay),
            "loot rolling replays identically for one death event");

        var rules = new HashSet<uint>(
            [12030u, 4529u, 4150u, 4003u, 4224u, 12040u]);
        var overCap = false;
        var dropped = 0;
        for (var index = 0; index < 64; index++)
        {
            var guid = new Guid(index, 0, 0, new byte[8]);
            var rolled = content.RollLoot("A_normal_stub_002", guid);
            overCap |= rolled.Count > 2;
            dropped += rolled.Count;
            foreach (var drop in rolled)
            {
                overCap |= !rules.Contains(drop.ItemId) || drop.Quantity != 1;
            }
        }

        Check.True(
            !overCap,
            "rolls never exceed the captured drop cap or item set");
        Check.True(dropped > 0, "rolls do produce ground items");

        Check.True(
            content.RollLoot("A_normal_stub_002", Guid.Empty).Count == 0 &&
            content.RollLoot("A_normal_unknown_001", deathEventId).Count == 0,
            "empty identities and unknown monsters roll nothing");
    }

    private static void CheckGroundKeys()
    {
        var deathEventId = new Guid("6f0f1c2a-5d3b-4a1e-9c44-70b2c9a31f5d");
        var first = MonsterLootGroundKey.Resolve(deathEventId, 0);
        var second = MonsterLootGroundKey.Resolve(deathEventId, 1);
        Check.True(
            first.High != second.High && first.Low == second.Low,
            "ground keys identify the item per drop and the kill per event");

        var otherKill = MonsterLootGroundKey.Resolve(
            new Guid("6f0f1c2a-5d3b-4a1e-9c44-70b2c9a31f5e"),
            0);
        Check.True(
            otherKill.Low != first.Low,
            "ground keys separate two kills of the same drop");

        Check.True(
            MonsterLootGroundKey.Resolve(deathEventId, 0) == first,
            "ground keys are deterministic");
    }

    private static void CheckCapturedPickupDescriptor()
    {
        // Captured C2S 10056 at 01:37:27.118 on 2026-09-15: Raw Gem 12040 into
        // bag page 0 index 0.
        var rawGem = Convert.FromHexString(
            "280048274823E21F010000000000000000000000082F00006C44A639" +
            "000000001CFD1A009BE47F00");
        Check.True(
            GameClientHandler.TryReadGroundLootPickup(
                rawGem.AsSpan(4),
                out var rawGemSlot,
                out var rawGemItem,
                out _,
                out _) &&
            rawGemSlot == 0 &&
            rawGemItem == 12040u,
            "captured ground pickup names item 12040 in bag slot 0");

        // Captured C2S 10056 at 01:37:27.888: Level 4 Emerald Pieces 4224 into
        // bag page 0 index 13.
        var emerald = Convert.FromHexString(
            "28004827E02FE21F01000000000000000D000000801000006C44A639" +
            "000000001CFD1A009BE47F00");
        Check.True(
            GameClientHandler.TryReadGroundLootPickup(
                emerald.AsSpan(4),
                out var emeraldSlot,
                out var emeraldItem,
                out _,
                out _) &&
            emeraldSlot == 13 &&
            emeraldItem == 4224u,
            "captured ground pickup names item 4224 in bag slot 13");

        // A thirty-two byte frame is not the captured descriptor at all.
        Check.True(
            !GameClientHandler.TryReadGroundLootPickup(
                rawGem.AsSpan(4, 32),
                out _,
                out _,
                out _,
                out _),
            "the pickup parser requires the exact 40-byte descriptor");

        var outOfRange = rawGem.ToArray();
        BinaryPrimitives.WriteUInt32LittleEndian(
            outOfRange.AsSpan(16, 4),
            24);
        Check.True(
            !GameClientHandler.TryReadGroundLootPickup(
                outOfRange.AsSpan(4),
                out _,
                out _,
                out _,
                out _),
            "the pickup parser rejects a slot index outside the bag page");
    }
}
