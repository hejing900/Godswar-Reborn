using System.Buffers.Binary;
using Godswar.Server.Game;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;

namespace Godswar.Server.ProtocolChecks;

internal static partial class IntonedCombatSkillHandlerChecks
{
    public const string FlameBlastPulsesCheckName =
        "Flame Blast fields retain per-monster healing and independent pulses";
    private const uint FlameSkillId = 574;
    private const int FlameHealing = 7;

    public static async Task RunFlameBlastPulsesAsync()
    {
        foreach (var mode in new[] { PlayerRuntimeMode.Legacy, PlayerRuntimeMode.Ecs })
        {
            await CheckFlameBlastFivePulsesAsync(mode);
            await CheckFlameBlastOverlapsAsync(mode);
            await CheckSharedFlameFormulaAsync(mode);
        }
    }

    private static async Task CheckFlameBlastFivePulsesAsync(PlayerRuntimeMode mode)
    {
        var clock = NewFlameClock();
        await using var fixture = await CreateFlameFixtureAsync(mode, clock);
        var totals = await CastAndReadInitialFlameAsync(fixture, centerX: 3);
        await WaitForFlameTimersAsync(fixture, clock, 1);
        clock.Advance(TimeSpan.FromMilliseconds(3999));
        Check.Equal(0, fixture.Socket.Available, "Flame Blast cannot damage before its first four-second deadline");

        // Placement belongs to the ground point, not the caster's later location.
        fixture.Character.PositionX = 20;
        fixture.Registry.UpdateCharacter(fixture.Socket.Session, fixture.Character,
            advanceWorldRevision: true);
        totals += await AdvanceAndReadFlameAsync(fixture, clock,
            TimeSpan.FromMilliseconds(1), expectedFields: 1);
        for (var ordinal = 2; ordinal <= 4; ordinal++)
            totals += await AdvanceAndReadFlameAsync(fixture, clock,
                TimeSpan.FromSeconds(4), expectedFields: ordinal == 4 ? 0 : 1);

        Check.True(totals >= 5, $"{mode}: several real target hits survive all five damage passes");
        Check.Equal(50 + totals * FlameHealing, fixture.Character.CurrentHp,
            $"{mode}: each damaged monster contributes one actual heal across the field lifetime");
        Check.Equal(InitialMana - 180, fixture.Character.CurrentMp,
            "later pulses neither reserve nor charge the initial mana cost again");
        var finalHealth = FlameMonsterHealth(fixture);
        clock.Advance(TimeSpan.FromSeconds(40));
        await Task.Yield();
        Check.True(finalHealth.SequenceEqual(FlameMonsterHealth(fixture)) &&
            fixture.Socket.Available == 0 && FlameFieldCount(fixture.Handler) == 0,
            "five total pulses expire without a sixth damage pass or residual field");
    }

    private static async Task CheckFlameBlastOverlapsAsync(PlayerRuntimeMode mode)
    {
        var clock = NewFlameClock();
        await using var fixture = await CreateFlameFixtureAsync(mode, clock);
        var totals = await CastAndReadInitialFlameAsync(fixture, 3);
        await WaitForFlameTimersAsync(fixture, clock, 1);

        // Verify the real admission rejection before advancing the fixture's
        // cooldown authority; this is not a direct invocation of completion.
        await BeginFlameCastAsync(fixture, 3);
        var error = await fixture.Socket.ReadPacketAsync(12);
        var interruption = await fixture.Socket.ReadPacketAsync(8);
        Check.True(error.SequenceEqual(PacketBuilder.LocalizedError(NativeErrorCodes.SkillNotReady)) &&
            interruption.SequenceEqual(PacketBuilder.SkillCastInterrupt(LocalObjectId)),
            "a premature Flame Blast recast retains the ordinary cooldown rejection");
        Check.Equal(1, FlameFieldCount(fixture.Handler), "a rejected recast creates no field");
        Check.Equal(InitialMana - 180, fixture.Character.CurrentMp, "rejected recast consumes no mana");

        // The scheduler clock is injected separately from existing cooldowns.
        // Prune the expired fixture lease explicitly instead of waiting seconds.
        fixture.Registry.PruneHostileSkillCooldowns(DateTimeOffset.UtcNow.AddSeconds(3));
        clock.Advance(TimeSpan.FromSeconds(2));
        totals += await CastAndReadInitialFlameAsync(fixture, 3);
        await WaitForFlameTimersAsync(fixture, clock, 2);
        for (var step = 0; step < 8; step++)
            totals += await AdvanceAndReadFlameAsync(fixture, clock,
                TimeSpan.FromSeconds(2), expectedFields: step < 6 ? 2 : step == 6 ? 1 : 0);

        Check.Equal(50 + totals * FlameHealing, fixture.Character.CurrentHp,
            $"{mode}: overlapping independent fields each heal for their own committed target hits");
        Check.Equal(InitialMana - 360, fixture.Character.CurrentMp,
            "two accepted fields consume exactly two initial mana costs");
        Check.True(totals >= 10 && FlameFieldCount(fixture.Handler) == 0,
            "both fields run their remaining four pulses and retire independently");
    }

    private static async Task<int> CastAndReadInitialFlameAsync(Fixture fixture, float centerX,
        int expectedManaCost = 180, IReadOnlyCollection<uint>? expectedDamageValues = null,
        Func<uint, byte>? expectedStyle = null)
    {
        var before = FlameMonsterHealth(fixture);
        var beforeHp = fixture.Character.CurrentHp;
        var beforeMana = fixture.Character.CurrentMp;
        await BeginFlameCastAsync(fixture, centerX);
        var impact = await ReadAfterFlameClaimsAsync(fixture);
        Check.True(impact.Length == 24 && ReadOpcode(impact) == 10046 &&
            BinaryPrimitives.ReadUInt32LittleEndian(impact.AsSpan(12)) == FlameSkillId &&
            BinaryPrimitives.ReadSingleLittleEndian(impact.AsSpan(16)) == centerX &&
            BinaryPrimitives.ReadSingleLittleEndian(impact.AsSpan(20)) == 0,
            "the accepted ground cast retains its original574 impact and fixed ground center");
        var cluster = await fixture.Socket.ReadPacketAsync();
        var after = FlameMonsterHealth(fixture);
        var changed = ChangedFlameTargets(before, after);
        Check.True(ReadOpcode(cluster) == 10047 && cluster.Length == 17 + 12 * changed.Length &&
            BinaryPrimitives.ReadInt32LittleEndian(cluster.AsSpan(8)) == changed.Length &&
            BinaryPrimitives.ReadUInt32LittleEndian(cluster.AsSpan(12)) == FlameSkillId,
            "initial cast keeps its ordinary574 cluster damage, including an empty selected field");
        for (var index = 0; index < changed.Length; index++)
        {
            Check.Equal(MonsterObjectId + (uint)changed[index],
                BinaryPrimitives.ReadUInt32LittleEndian(cluster.AsSpan(17 + index * 12)),
                "initial cluster contains exactly the monsters with committed damage");
            if (expectedDamageValues is not null)
            {
                var appliedDamage = before[changed[index]] - after[changed[index]];
                Check.True(expectedDamageValues.Contains(appliedDamage),
                    "accepted initial Flame damage uses the projected normal or critical skill outcome");
                Check.Equal(appliedDamage,
                    BinaryPrimitives.ReadUInt32LittleEndian(cluster.AsSpan(25 + index * 12)),
                    "initial native cluster reports the same skill damage committed to HP");
                if (expectedStyle is not null)
                    Check.Equal(expectedStyle(appliedDamage), cluster[21 + index * 12],
                        "initial Flame number style matches that target's actual normal or critical damage");
            }
        }
        var mana = await fixture.Socket.ReadPacketAsync(12);
        Check.True(ReadOpcode(mana) == 10135 &&
            BinaryPrimitives.ReadInt32LittleEndian(mana.AsSpan(8)) == beforeMana - expectedManaCost,
            "the initial574 cast consumes its projected MP exactly once");
        await ReadFlameHealingAsync(fixture, changed.Length, beforeHp);
        return changed.Length;
    }

    private static async Task<int> AdvanceAndReadFlameAsync(Fixture fixture,
        ManualTimeProvider clock, TimeSpan advance, int expectedFields,
        Func<uint, byte>? expectedStyle = null)
    {
        var before = FlameMonsterHealth(fixture);
        var beforeHp = fixture.Character.CurrentHp;
        var beforeMana = fixture.Character.CurrentMp;
        clock.Advance(advance);
        await WaitForFlameTimersAsync(fixture, clock, expectedFields);
        var after = FlameMonsterHealth(fixture);
        var changed = ChangedFlameTargets(before, after);
        if (changed.Length > 0)
        {
            var packet = await ReadAfterFlameClaimsAsync(fixture);
            for (var index = 0; index < changed.Length; index++)
            {
                if (index > 0) packet = await fixture.Socket.ReadPacketAsync(32);
                var target = changed[index];
                Check.True(packet.Length == 32 && ReadOpcode(packet) == 10045 &&
                    BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(4)) == LocalObjectId &&
                    BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(8)) == MonsterObjectId + (uint)target &&
                    BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(12)) is 0 or 1 &&
                    BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(20)) == 250 &&
                    BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(16)) == before[target] - after[target],
                    "each pulse uses the captured250 damage envelope for exactly one actual target mutation");
                if (expectedStyle is not null)
                    Check.Equal((uint)expectedStyle(before[target] - after[target]),
                        BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(12)),
                        "recurring Flame number style matches that target's actual normal or critical damage");
            }
            await ReadFlameHealingAsync(fixture, changed.Length, beforeHp);
        }
        Check.True(after[2] == before[2] && fixture.Character.CurrentMp == beforeMana &&
            fixture.Socket.Available == 0,
            "a pulse excludes the out-of-area mob and sends no recast, impact, mana or extra heal");
        return changed.Length;
    }

    private static int[] ChangedFlameTargets(uint[] before, uint[] after) =>
        Enumerable.Range(0, before.Length).Where(index => after[index] < before[index]).ToArray();

    private static async Task ReadFlameHealingAsync(Fixture fixture, int hits, int beforeHp)
    {
        for (var index = 0; index < hits; index++)
            AssertLifeAbsorptionHealingPacket(await fixture.Socket.ReadPacketAsync(32),
                FlameHealing, fixture.Character.PositionX, fixture.Character.PositionZ,
                "Flame Blast per-target healing");
        if (hits > 0)
        {
            var vitals = await fixture.Socket.ReadPacketAsync(16);
            Check.True(ReadOpcode(vitals) == 10097 &&
                BinaryPrimitives.ReadInt32LittleEndian(vitals.AsSpan(8)) == beforeHp + hits * FlameHealing &&
                BinaryPrimitives.ReadInt32LittleEndian(vitals.AsSpan(12)) == fixture.Character.CurrentMp,
                "one final HP/MP snapshot follows all actual per-target healing numbers");
        }
        Check.Equal(beforeHp + hits * FlameHealing, fixture.Character.CurrentHp,
            "pulse healing equals the sum of damaged-mob contributions");
    }
}
