namespace Godswar.Server.State;

internal sealed partial class PostgresGameStore
{
    /// <summary>
    /// Persists every quest the character carries, plus the ones it has finished.
    /// </summary>
    /// <remarks>
    /// A character can hold several quests at once, so the whole set is written in
    /// one statement: the rows that are no longer part of it are deleted, and the
    /// rest are upserted with their own state and progress. The character's
    /// current and completed quests are one list here - a finished quest is simply
    /// a row in the completed state, which is what stops it being offered again.
    /// </remarks>
    public async Task SaveCharacterQuestStateAsync(
        int accountId,
        int characterId,
        IReadOnlyList<CharacterQuest> quests,
        IReadOnlyList<uint> completedQuestIds,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(quests);
        ArgumentNullException.ThrowIfNull(completedQuestIds);

        var questIds = new int[quests.Count + completedQuestIds.Count];
        var states = new short[questIds.Length];
        var progresses = new int[questIds.Length];
        for (var index = 0; index < quests.Count; index++)
        {
            questIds[index] = checked((int)quests[index].QuestId);
            states[index] = CharacterQuestStatus.InProgress;
            progresses[index] = quests[index].Progress;
        }

        for (var index = 0; index < completedQuestIds.Count; index++)
        {
            var target = quests.Count + index;
            questIds[target] = checked((int)completedQuestIds[index]);
            states[target] = CharacterQuestStatus.Completed;
            progresses[target] = 0;
        }

        await using var command = _dataSource.CreateCommand("""
            DELETE FROM character_quests quest
            USING character_base character
            WHERE quest.character_id = character.id
              AND character.id = @characterId
              AND character.account_id = @accountId
              AND NOT (quest.quest_id = ANY(@questIds));

            INSERT INTO character_quests
                (character_id, quest_id, state, progress)
            SELECT
                @characterId,
                incoming.quest_id,
                incoming.state,
                incoming.progress
            FROM unnest(@questIds, @states, @progresses)
                AS incoming(quest_id, state, progress)
            WHERE EXISTS (
                SELECT 1
                FROM character_base character
                WHERE character.id = @characterId
                  AND character.account_id = @accountId)
            ON CONFLICT (character_id, quest_id)
            DO UPDATE SET
                state = EXCLUDED.state,
                progress = EXCLUDED.progress;
            """);
        command.Parameters.AddWithValue("questIds", questIds);
        command.Parameters.AddWithValue("states", states);
        command.Parameters.AddWithValue("progresses", progresses);
        command.Parameters.AddWithValue("characterId", characterId);
        command.Parameters.AddWithValue("accountId", accountId);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }
}
