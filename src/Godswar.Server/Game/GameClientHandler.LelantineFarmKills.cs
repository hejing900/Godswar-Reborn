using Godswar.Server.Application.WorldInstances;
using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// Credits a kill to the character's own Lelantine Farm score when the
    /// monster died on the farm.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The score is the activity's personal half: the faction's donated total
    /// comes from pet eggs alone, and a kill scores for the fighter who landed
    /// the last hit. The award is read from the monster's published rank so only
    /// the farm roster's own normal/elite/boss split decides it, never a client
    /// claim.
    /// </para>
    /// <para>
    /// A normal monster only scores when it is no more than ten levels below the
    /// attacker, which is the activity's own stated rule. Elites and the boss
    /// carry no such gap.
    /// </para>
    /// </remarks>
    private async Task RecordFarmKillAsync(
        MonsterDamageResult damageResult,
        CancellationToken cancellationToken)
    {
        if (_character is null ||
            damageResult.Monster.Definition.MapId !=
                LelantineFarmProtocol.MapId ||
            !LelantineFarmPointsPolicy.TryResolveFaction(
                _character.Camp,
                out var faction))
        {
            return;
        }

        var definition = damageResult.Monster.Definition;
        var (points, isElite, isBoss) = ResolveFarmKill(definition.TemplateKey);
        if (points <= 0)
        {
            return;
        }

        // The runtime carries a monster's level as its tier.
        var monsterLevel = checked((int)Math.Min(
            definition.Tier,
            (uint)int.MaxValue));
        if (!LelantineFarmPointsPolicy.IsKillEligible(
                _character.Level,
                monsterLevel,
                isElite,
                isBoss))
        {
            Console.WriteLine(
                $"[farm] kill below the level gap, not credited " +
                $"character={_character.Name} level={_character.Level} " +
                $"monster=\"{definition.DisplayName}\" " +
                $"monsterLevel={monsterLevel} gap=" +
                $"{LelantineFarmPointsPolicy.NormalMonsterMaximumLowerLevelGap}");
            return;
        }

        await _farmPoints.CreditFarmKillAsync(
            _character.Id,
            faction,
            points,
            cancellationToken);
        Console.WriteLine(
            $"[farm] kill credited character={_character.Name} " +
            $"faction={faction} monster=\"{definition.DisplayName}\" " +
            $"template={definition.TemplateKey} object={definition.ObjectId} " +
            $"points={points}");
    }

    /// <summary>
    /// The award for one farm monster, resolved from the published template
    /// content rather than from the spawn's own name.
    /// </summary>
    private (int Points, bool IsElite, bool IsBoss) ResolveFarmKill(
        string templateKey)
    {
        foreach (var template in _gameplayCatalogs.Content.MonsterTemplates)
        {
            if (!string.Equals(
                    template.TemplateKey,
                    templateKey,
                    StringComparison.Ordinal) ||
                template.SourceMapId != LelantineFarmProtocol.MapId)
            {
                continue;
            }

            return (
                LelantineFarmPointsPolicy.ResolveKillPoints(
                    template.Rank,
                    template.IsElite,
                    template.IsBoss),
                template.IsElite,
                template.IsBoss);
        }

        Console.Error.WriteLine(
            "[farm] kill not credited: no published farm template " +
            $"'{templateKey}'");
        return (0, false, false);
    }
}
