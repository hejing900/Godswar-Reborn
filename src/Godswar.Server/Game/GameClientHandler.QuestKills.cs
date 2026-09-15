using Godswar.Server.Domain.World.Content;
using Godswar.Server.Packets;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// Credits a kill to any carried quest whose objective it satisfies.
    /// </summary>
    /// <remarks>
    /// The objectives come from the client's own quest text, which names both the
    /// target and how many of it the quest wants - "Kill 10 Dumb Wood Men". A kill
    /// is matched on the monster's display name, so only the right kind counts,
    /// and the position the client shows is the fallback for a name that cannot be
    /// resolved.
    /// <para>
    /// One kill credits at most one objective, and each objective keeps its own
    /// counter, so a quest with three targets needs all three and killing one kind
    /// past its count does not stand in for another.
    /// </para>
    /// </remarks>
    private async Task RecordQuestKillAsync(
        MonsterDamageResult damageResult,
        CancellationToken cancellationToken)
    {
        if (_character is null || _character.Quests.Count == 0)
        {
            return;
        }

        // Map ids are signed in the monster content and unsigned in the
        // objectives, so a negative id simply matches nothing.
        var mapId = (uint)Math.Max(0, (int)damageResult.Monster.Definition.MapId);
        var monsterName = damageResult.Monster.Definition.DisplayName;
        var x = damageResult.Monster.HomeX;
        var z = damageResult.Monster.HomeZ;

        var changed = false;
        foreach (var quest in _character.Quests)
        {
            var objectives = StarterQuestObjectives.For(quest.QuestId);
            if (objectives.Count == 0)
            {
                continue;
            }

            for (var slot = 0; slot < objectives.Count; slot++)
            {
                var objective = objectives[slot];
                var counter = StarterQuestObjectives.Counter(quest.Progress, slot);
                if (counter >= objective.Required)
                {
                    continue;
                }

                if (!StarterQuestObjectives.Matches(
                        objective,
                        mapId,
                        monsterName,
                        x,
                        z))
                {
                    continue;
                }

                quest.Progress = StarterQuestObjectives.WithCounter(
                    quest.Progress,
                    slot,
                    counter + 1);
                changed = true;
                // stderr: stdout diagnostics are folded into counters by the
                // legacy log suppressor, so this is the channel that survives.
                Console.Error.WriteLine(
                    $"[quest] kill counted character={_character.Name} " +
                    $"quest={quest.QuestId} target=\"{objective.Target}\" " +
                    $"match=\"{StarterQuestObjectives.NameOf(objective)}\" " +
                    $"{counter + 1}/{objective.Required} " +
                    $"monster=\"{monsterName}\" map={mapId} " +
                    $"x={x:0.##} z={z:0.##}");
                await SendQuestObjectiveProgressAsync(
                    quest.QuestId,
                    objective.MonsterId,
                    cancellationToken);
                if (StarterQuestObjectives.IsSatisfied(
                        objectives,
                        quest.Progress))
                {
                    // The last kill is what makes the quest handable, so the
                    // "objectives are met" frame goes out now rather than with the
                    // accept answer.
                    await SendQuestObjectivesMetAsync(
                        quest.QuestId,
                        cancellationToken);
                }
                else if (StarterQuestObjectives.Counter(
                             quest.Progress,
                             slot) >= objective.Required)
                {
                    // That kill finished this objective and the quest still wants
                    // another kind, but the window counts the one objective it was
                    // told about - so the next objective is published here,
                    // otherwise the remaining kills would only be counted on the
                    // server and the window would never show them.
                    await SendQuestSnapshotAsync(
                        $"objective-advanced quest={quest.QuestId} slot={slot}",
                        cancellationToken);
                }

                break;
            }
        }

        if (changed)
        {
            await SaveQuestStateAsync(cancellationToken);
        }
    }

    /// <summary>
    /// Tells the client that one of a quest's objectives moved on.
    /// </summary>
    /// <remarks>
    /// The reference server sends opcode 10087 for every counted kill - quest, the
    /// npc the quest belongs to, a step of one and the target monster id - and that
    /// is what makes the quest window count up until the quest shows as finished.
    /// Without it the window has no progress to show.
    /// </remarks>
    private async Task SendQuestObjectiveProgressAsync(
        uint questId,
        uint monsterId,
        CancellationToken cancellationToken)
    {
        if (StarterQuestChain.Find(questId) is not { } step)
        {
            return;
        }

        await _session.SendAsync(
            PacketBuilder.QuestObjectiveProgress(
                questId,
                ResolveQuestNpcId(step.GiverKey),
                monsterId),
            cancellationToken,
            "QuestObjectiveProgress",
            framed: false);
    }

    /// <summary>
    /// Tells the client that a quest's objectives are met and it can be handed in.
    /// </summary>
    /// <remarks>
    /// This is the 10084 frame the talk quests get with their accept answer. A kill
    /// quest gets it once the last required kill lands, which is what moves the
    /// quest window from "in progress" to "finished".
    /// </remarks>
    private async Task SendQuestObjectivesMetAsync(
        uint questId,
        CancellationToken cancellationToken)
    {
        if (StarterQuestChain.Find(questId) is not { } step)
        {
            return;
        }

        // A responder that will not resolve is never published: the client looks
        // the npc up and a frame naming zero crashes it. Skipping leaves the quest
        // handable at the responder once the map content resolves again.
        var responderNpcId = ResolveQuestNpcId(step.ResponderKey);
        if (responderNpcId == 0)
        {
            Console.Error.WriteLine(
                $"[quest] skipped objectives-met without a responder " +
                $"character={_character?.Name ?? "(none)"} quest={questId} " +
                $"responder={step.ResponderKey}");
            return;
        }

        await _session.SendAsync(
            PacketBuilder.QuestConfirm(
                responderNpcId,
                questId),
            cancellationToken,
            "QuestObjectivesMet",
            framed: false);
    }
}
