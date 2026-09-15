using Godswar.Server.Networking;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;
using Godswar.Server.World.Systems.Combat;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private CombatResolution ResolveHostileMonsterSkillDamage(
        GameCharacter character,
        SkillCombatDefinition combat,
        MonsterRuntimeSnapshot target,
        ulong admittedCombatRevision,
        int targetOrder,
        DateTimeOffset authoritativeAt,
        in ClientStatusAggregate runtimeModifiers)
    {
        var eventId = CombatEventIdentity.ForPlayerMonsterSkill(
            character.Id,
            target.ObjectId,
            target.SpawnGeneration,
            target.HealthRevision,
            admittedCombatRevision,
            (uint)combat.SkillId,
            targetOrder);
        var targetStats = _gameplayCatalogs.MonsterCombatProfiles
            .Resolve(target.Definition)
            .ToTargetStats();
        targetStats = _registry.AdjustPveMonsterTargetStats(
            _session,
            target,
            authoritativeAt,
            targetStats);
        var resolution = SkillCombatResolver.ResolveDamage(
            character,
            combat,
            targetStats,
            eventId,
            targetOrder,
            runtimeModifiers);
        return _registry.AdjustPveOutgoingResolution(
            _session,
            character,
            target,
            CombatEventProvenance.DirectSkill,
            authoritativeAt,
            resolution,
            admittedCombatRevision);
    }

    private async Task PublishUnreportedHostileMonsterSkillMissAsync(
        GamePacket packet,
        SkillCastRequest cast,
        SkillCombatDefinition combat,
        uint targetSpawnGeneration,
        bool publishCastVisual,
        int currentMana,
        CombatResolution resolution,
        CancellationToken cancellationToken)
    {
        var character = _character!;
        _registry.UpdateCharacter(
            _session,
            character,
            advanceWorldRevision: false);

        // 未命中同样需要终结帧(SkillCastImpact),否则客户端会一直停留在施法状态。
        // A miss must also emit the impact terminator frame; without it the
        // client remains visually locked in its casting state.
        var selfImpact = PacketBuilder.SkillCastImpact(
            packet.Buffer,
            LocalPlayerObjectId);

        var casterNotified = true;
        try
        {
            if (publishCastVisual)
            {
                await _registry.DeliverMonsterPacketToViewerAsync(
                    _session,
                    character.CurrentMap,
                    cast.TargetObjectId,
                    PacketBuilder.SkillCastVisual(
                        packet.Buffer,
                        LocalPlayerObjectId),
                    targetSpawnGeneration,
                    cancellationToken,
                    "SkillMissCastSelf");
            }

            await _registry.DeliverMonsterPacketToViewerAsync(
                _session,
                character.CurrentMap,
                cast.TargetObjectId,
                selfImpact,
                targetSpawnGeneration,
                cancellationToken,
                "SkillMissCastImpactSelf");

            if (combat.Mp > 0)
            {
                await _session.SendAsync(
                    PacketBuilder.PlayerManaUpdate(
                        LocalPlayerObjectId,
                        currentMana),
                    cancellationToken,
                    "SkillMissManaSelf");
            }
        }
        catch (Exception ex) when (
            ex is IOException or ObjectDisposedException)
        {
            casterNotified = false;
            Console.WriteLine(
                $"[skill] miss caster notification failed character={character.Name} target={cast.TargetObjectId}: {ex.Message}");
        }

        var impactRecipients =
            await _registry.BroadcastToMonsterViewersAsync(
                character.CurrentMap,
                cast.TargetObjectId,
                PacketBuilder.SkillCastImpact(
                    packet.Buffer,
                    CurrentPlayerObjectId),
                cancellationToken,
                _session,
                "SkillMissCastImpactWorld",
                expectedSpawnGeneration: targetSpawnGeneration);
        var visualRecipients = publishCastVisual
            ? await _registry.BroadcastToMonsterViewersAsync(
                character.CurrentMap,
                cast.TargetObjectId,
                PacketBuilder.SkillCastVisual(
                    packet.Buffer,
                    CurrentPlayerObjectId),
                cancellationToken,
                _session,
                "SkillMissCastWorld",
                expectedSpawnGeneration: targetSpawnGeneration)
            : 0;
        await PersistSkillVitalsAsync(
            character,
            areaSkill: false,
            cancellationToken);
        Console.WriteLine(
            $"[skill] unreported miss character={character.Name} skill={cast.SkillId} target={cast.TargetObjectId} event={resolution.EventId} hit={resolution.Rolls.HitRollBasisPoints}/{resolution.Rolls.HitChanceBasisPoints} mp={currentMana}/{character.MaxMp} caster-notified={casterNotified} viewers={visualRecipients} impacts={impactRecipients}");
    }
}
