using System.Data;
using Godswar.Server.Application.World.Content;
using Npgsql;

namespace Godswar.Server.Infrastructure.WorldContent;

/// <summary>
/// Loads one repeatable-read snapshot of the adjustable monster loot tables.
/// Schema creation remains exclusively migration-owned, exactly like the
/// Medusa monster content reader.
/// </summary>
internal sealed class PostgresMonsterLootContentSnapshotReader
{
    private const int MaximumTables = 4_096;
    private const int MaximumRules = 32_768;

    private readonly NpgsqlDataSource _dataSource;

    public PostgresMonsterLootContentSnapshotReader(
        NpgsqlDataSource dataSource)
    {
        _dataSource = dataSource ??
            throw new ArgumentNullException(nameof(dataSource));
    }

    public static async Task<MonsterLootContentSnapshot> LoadAsync(
        string connectionString,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(connectionString);
        await using var dataSource = NpgsqlDataSource.Create(connectionString);
        return await new PostgresMonsterLootContentSnapshotReader(dataSource)
            .ReadAsync(cancellationToken);
    }

    public async Task<MonsterLootContentSnapshot> ReadAsync(
        CancellationToken cancellationToken = default)
    {
        await using var connection =
            await _dataSource.OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(
            IsolationLevel.RepeatableRead,
            cancellationToken);

        var tables = await ReadTablesAsync(
            connection,
            transaction,
            cancellationToken);
        var loot = await ReadLootAsync(
            connection,
            transaction,
            cancellationToken);
        var snapshot = new MonsterLootContentSnapshot(tables, loot);
        await transaction.CommitAsync(cancellationToken);
        return snapshot;
    }

    private static async Task<IReadOnlyList<MonsterLootTableRule>>
        ReadTablesAsync(
            NpgsqlConnection connection,
            NpgsqlTransaction transaction,
            CancellationToken cancellationToken)
    {
        await using var command = new NpgsqlCommand(
            """
            SELECT template_key, maximum_drops
            FROM public.monster_loot_tables
            WHERE enabled
            ORDER BY template_key
            LIMIT @maximumRows;
            """,
            connection,
            transaction);
        command.Parameters.AddWithValue("maximumRows", MaximumTables);
        var result = new List<MonsterLootTableRule>();
        await using var reader =
            await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            result.Add(new(
                reader.GetString(0),
                reader.GetInt16(1)));
        }
        return result.AsReadOnly();
    }

    /// <summary>An attribute column, where <c>NULL</c> means "not configured".</summary>
    private static short? Optional(NpgsqlDataReader reader, int ordinal) =>
        reader.IsDBNull(ordinal) ? null : reader.GetInt16(ordinal);

    private static async Task<IReadOnlyList<MonsterLootRule>>
        ReadLootAsync(
            NpgsqlConnection connection,
            NpgsqlTransaction transaction,
            CancellationToken cancellationToken)
    {
        await using var command = new NpgsqlCommand(
            """
            SELECT rule.template_key, rule.loot_index, rule.item_id,
                   rule.chance_basis_points, rule.minimum_quantity,
                   rule.maximum_quantity, rule.bound_on_pickup,
                   rule.item_quality, rule.item_grade,
                   rule.attribute1, rule.attribute_level1,
                   rule.attribute2, rule.attribute_level2,
                   rule.attribute3, rule.attribute_level3,
                   rule.attribute4, rule.attribute_level4,
                   rule.attribute5, rule.attribute_level5
            FROM public.monster_loot_rules rule
            JOIN public.monster_loot_tables header
              ON header.template_key = rule.template_key
            WHERE rule.enabled AND header.enabled
            ORDER BY rule.template_key, rule.loot_index
            LIMIT @maximumRows;
            """,
            connection,
            transaction);
        command.Parameters.AddWithValue("maximumRows", MaximumRules);
        var result = new List<MonsterLootRule>();
        await using var reader =
            await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            result.Add(new(
                reader.GetString(0),
                reader.GetInt16(1),
                checked((uint)reader.GetInt32(2)),
                reader.GetInt32(3),
                reader.GetInt16(4),
                reader.GetInt16(5),
                reader.IsDBNull(6) ? null : reader.GetBoolean(6),
                new Godswar.Server.State.ItemGrantAttributes(
                    reader.IsDBNull(7) ? (short)1 : reader.GetInt16(7),
                    reader.IsDBNull(8) ? (short)1 : reader.GetInt16(8),
                    Optional(reader, 9), Optional(reader, 10),
                    Optional(reader, 11), Optional(reader, 12),
                    Optional(reader, 13), Optional(reader, 14),
                    Optional(reader, 15), Optional(reader, 16),
                    Optional(reader, 17), Optional(reader, 18))));
        }
        return result.AsReadOnly();
    }
}
