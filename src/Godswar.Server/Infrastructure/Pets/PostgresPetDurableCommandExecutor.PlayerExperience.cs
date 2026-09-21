using Godswar.Server.Application.Pets;
using Godswar.Server.State;
using Npgsql;

namespace Godswar.Server.Infrastructure.Pets;

internal sealed partial class PostgresPetDurableCommandExecutor
{
    private Task<PetTransition> UsePlayerExperiencePillAsync(NpgsqlConnection connection,
        NpgsqlTransaction transaction, int characterId, int bagSlot, LockedBagItem item,
        LockedCharacter character, CancellationToken token) =>
        ExecuteWithBagConsumableCooldownAsync(connection, transaction, characterId, bagSlot, item,
            ct => CreditPlayerExperiencePillAsync(connection, transaction, characterId, bagSlot, item, character, ct), token);

    private async Task<PetTransition> CreditPlayerExperiencePillAsync(NpgsqlConnection connection,
        NpgsqlTransaction transaction, int characterId, int bagSlot, LockedBagItem item,
        LockedCharacter character, CancellationToken token)
    {
        if (item.Stack < 1 || item.PropId != PlayerExperienceItemPolicy.ItemId ||
            !_itemContent.Templates.TryGet(PlayerExperienceItemPolicy.ItemId, out _))
            return new(PetDurableReceiptStatus.UnsupportedItem, KitBagSlot: bagSlot);

        // ExecuteAsync already holds this character's ownership fence and row lock.
        long experience;
        bool sealedLevel;
        long progressionRevision;
        await using (var read = CreateCommand("""
            SELECT fighter_job_exp, fighter_level_sealed, progression_reward_revision
            FROM public.character_base WHERE id = @characterId FOR UPDATE;
            """, connection, transaction))
        {
            read.Parameters.AddWithValue("characterId", characterId);
            await using var reader = await read.ExecuteReaderAsync(token);
            if (!await reader.ReadAsync(token)) throw new InvalidDataException("The locked EXP recipient disappeared.");
            experience = reader.GetInt64(0);
            sealedLevel = reader.GetBoolean(1);
            progressionRevision = reader.GetInt64(2);
        }
        if (!PlayerExperienceItemPolicy.TryApply(character.Level, experience, sealedLevel, out var result))
            return new(PetDurableReceiptStatus.PlayerExperienceMaximumReached, KitBagSlot: bagSlot);

        var evidence = new PlayerExperienceItemEvidence(item.ItemId, bagSlot, PlayerExperienceItemPolicy.ItemId,
            result.ExperienceGained, character.Level, experience, sealedLevel, result.Level, result.Experience,
            progressionRevision, checked(progressionRevision + 1));
        if (!evidence.IsValid) throw new InvalidDataException("The EXP Pill progression evidence is invalid.");
        await using (var update = CreateCommand("""
            UPDATE public.character_base SET fighter_job_lv = @level, fighter_job_exp = @experience,
                progression_reward_revision = @revision
            WHERE id = @characterId AND progression_reward_revision = @expectedRevision;
            """, connection, transaction))
        {
            update.Parameters.AddWithValue("level", result.Level);
            update.Parameters.AddWithValue("experience", result.Experience);
            update.Parameters.AddWithValue("revision", evidence.NewProgressionRevision);
            update.Parameters.AddWithValue("characterId", characterId);
            update.Parameters.AddWithValue("expectedRevision", progressionRevision);
            if (await update.ExecuteNonQueryAsync(token) != 1)
                throw new InvalidDataException("The EXP Pill progression revision did not advance exactly once.");
        }
        var consumed = await ConsumeOneStackItemAsync(connection, transaction, characterId, bagSlot, item, token);
        var inventoryRevision = await AdvanceInventoryRevisionAsync(connection, transaction,
            characterId, character.InventoryRevision, token);
        return new(PetDurableReceiptStatus.PlayerExperienceAdded, KitBagSlot: bagSlot, PlayerExperience: evidence,
            InventoryMutations: [new InventoryMutation(item.ItemId, consumed.MutationKind,
                item.BeforeState, consumed.AfterState, "player_experience_item_consumed", inventoryRevision)]);
    }
}
