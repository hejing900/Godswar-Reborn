using System.Buffers.Binary;
using System.Reflection;
using Godswar.Server.Game;
using Godswar.Server.Protocol;
using Godswar.Server.State;
using Godswar.Server.World.Systems.Combat;

namespace Godswar.Server.ProtocolChecks;

internal static partial class IntonedCombatSkillHandlerChecks
{
    private static ManualTimeProvider NewFlameClock()
    {
        var clock = new ManualTimeProvider();
        clock.Advance(DateTimeOffset.UtcNow - DateTimeOffset.UnixEpoch);
        return clock;
    }

    private static async Task<Fixture> CreateFlameFixtureAsync(
        PlayerRuntimeMode mode, ManualTimeProvider clock, bool aggressive = false,
        uint monsterHealth = 50_000)
    {
        var monsters = new[] { 2f, 4f, 10f }.Select((x, index) =>
        {
            var monster = CreateMonster();
            var id = MonsterObjectId + (uint)index;
            BinaryPrimitives.WriteUInt32LittleEndian(monster.Packet.AsSpan(8), id);
            if (aggressive)
                BinaryPrimitives.WriteUInt32LittleEndian(monster.Packet.AsSpan(12),
                    MonsterAggroPolicy.MinimumAggressiveTier);
            BinaryPrimitives.WriteUInt32LittleEndian(monster.Packet.AsSpan(20), monsterHealth);
            BinaryPrimitives.WriteUInt32LittleEndian(monster.Packet.AsSpan(24), monsterHealth);
            BinaryPrimitives.WriteSingleLittleEndian(monster.Packet.AsSpan(28), x);
            return monster with { ObjectId = id, X = x };
        }).ToArray();
        var fixture = await Fixture.CreateAsync($"Flame{mode}", currentHp: 50,
            playerRuntimeMode: mode, lifeAbsorptionFlat: FlameHealing,
            monsters: monsters, flameBlastTimeProvider: clock,
            monsterRuntimeMode: mode == PlayerRuntimeMode.Legacy
                ? MonsterRuntimeMode.Legacy : MonsterRuntimeMode.Ecs);
        fixture.Character.Level = 140;
        fixture.Character.CalculatedStats = new CharacterStats
        {
            MagicAttack = 1_000, Hit = 1_000_000, LifeAbsorptionFlat = FlameHealing
        };
        fixture.Store.Skills = [new() { SkillId = (int)FlameSkillId, Level = 5 }];
        fixture.Registry.UpdateCharacter(fixture.Socket.Session, fixture.Character,
            advanceWorldRevision: false);
        return fixture;
    }

    private static GamePacket CreateFlameCast(Fixture fixture, float centerX)
    {
        var packet = CreateSkillCastPacket(fixture.Character.PositionX,
            fixture.Character.PositionZ).Buffer.ToArray();
        BinaryPrimitives.WriteUInt32LittleEndian(packet.AsSpan(8), FlameSkillId);
        BinaryPrimitives.WriteUInt32LittleEndian(packet.AsSpan(16), uint.MaxValue);
        BinaryPrimitives.WriteSingleLittleEndian(packet.AsSpan(32), centerX);
        BinaryPrimitives.WriteSingleLittleEndian(packet.AsSpan(36), 0);
        return new(packet);
    }

    private static async Task BeginFlameCastAsync(Fixture fixture, float centerX)
    {
        // Match RunAsync's command admission: receiving the previous cast's
        // packets does not mean its pending-cast cleanup has released the gate.
        var gate = (SemaphoreSlim)typeof(GameClientHandler)
            .GetField("_characterStateGate", BindingFlags.Instance | BindingFlags.NonPublic)!
            .GetValue(fixture.Handler)!;
        await gate.WaitAsync();
        try { await InvokePacketAsync(fixture.Handler, CreateFlameCast(fixture, centerX)); }
        finally { gate.Release(); }
        var start = await fixture.Socket.ReadPacketAsync(40);
        Check.True(ReadOpcode(start) == 10040 &&
            BinaryPrimitives.ReadUInt32LittleEndian(start.AsSpan(8)) == FlameSkillId &&
            BinaryPrimitives.ReadUInt32LittleEndian(start.AsSpan(16)) == uint.MaxValue &&
            BinaryPrimitives.ReadSingleLittleEndian(start.AsSpan(32)) == centerX,
            "a real accepted574 request starts the correct native ground-cast animation");
    }

    private static uint[] FlameMonsterHealth(Fixture fixture) =>
        Enumerable.Range(0, 3).Select(index =>
        {
            Check.True(fixture.Registry.TryGetMonsterSnapshot(0, MonsterObjectId + (uint)index,
                    out var monster), "Flame Blast fixture retains every authoritative target");
            return monster.CurrentHealth;
        }).ToArray();

    private static async Task<byte[]> ReadAfterFlameClaimsAsync(Fixture fixture)
    {
        var packet = await fixture.Socket.ReadPacketAsync();
        var claimed = new HashSet<uint>();
        while (ReadOpcode(packet) == Opcodes.MonsterClaimState)
        {
            var id = BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(4));
            Check.True(packet.Length == 12 && id >= MonsterObjectId &&
                id < MonsterObjectId + 3 && claimed.Add(id),
                "only one new claim for each actual field target may precede damage");
            packet = await fixture.Socket.ReadPacketAsync();
        }
        return packet;
    }

    private static (object Gate, Dictionary<ulong, Task> Tasks) FlameFields(GameClientHandler handler)
    {
        const BindingFlags flags = BindingFlags.NonPublic | BindingFlags.Instance;
        var type = typeof(GameClientHandler);
        return (type.GetField("_flameBlastSync", flags)!.GetValue(handler)!,
            (Dictionary<ulong, Task>)type.GetField("_flameBlastTasks", flags)!.GetValue(handler)!);
    }

    private static int FlameFieldCount(GameClientHandler handler)
    {
        var fields = FlameFields(handler);
        lock (fields.Gate) return fields.Tasks.Count;
    }

    private static async Task WaitForFlameTimersAsync(Fixture fixture,
        ManualTimeProvider clock, int expectedFields)
    {
        await WaitUntilAsync(() => FlameFieldCount(fixture.Handler) == expectedFields &&
            clock.ScheduledTimerCount == expectedFields, TimeSpan.FromSeconds(3));
    }

    private static Task StopFlameFieldsAsync(GameClientHandler handler) =>
        (Task)(typeof(GameClientHandler).GetMethod("StopFlameBlastFieldsAsync",
            BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(handler, null)
            ?? throw new InvalidOperationException("Flame Blast cleanup returned no task."));

    private static void CheckFlameEventDomains(Fixture fixture)
    {
        var fields = FlameFields(fixture.Handler);
        ulong field;
        lock (fields.Gate) field = fields.Tasks.Keys.Single();
        Check.True(fixture.Registry.TryGetMonsterSnapshot(0, MonsterObjectId, out var monster),
            "pulse identity check uses the actual admitted field and target generation");
        var normal = CombatEventIdentity.ForPlayerMonsterSkill(CharacterId, MonsterObjectId,
            monster.SpawnGeneration, monster.HealthRevision, 1, FlameSkillId, 0);
        var first = CombatEventIdentity.ForFlameBlastPulse(CharacterId, MonsterObjectId,
            monster.SpawnGeneration, monster.HealthRevision, field, FlameSkillId, 1, 0);
        var second = CombatEventIdentity.ForFlameBlastPulse(CharacterId, MonsterObjectId,
            monster.SpawnGeneration, monster.HealthRevision, field, FlameSkillId, 2, 0);
        var recast = CombatEventIdentity.ForFlameBlastPulse(CharacterId, MonsterObjectId,
            monster.SpawnGeneration, monster.HealthRevision, field + 1, FlameSkillId, 1, 0);
        Check.Equal(4, new HashSet<ulong> { normal, first, second, recast }.Count,
            "initial skill, separate pulse ordinals and recasts cannot reuse a lifesteal/reward event identity");
    }
}
