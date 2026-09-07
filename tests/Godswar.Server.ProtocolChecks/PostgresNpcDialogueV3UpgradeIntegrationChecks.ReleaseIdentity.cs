using Godswar.Server.Infrastructure.WorldContent;
using Npgsql;
using NpgsqlTypes;

namespace Godswar.Server.ProtocolChecks;

internal static partial class PostgresNpcDialogueV3UpgradeIntegrationChecks
{
    private static async Task CheckLegacyV21ReleaseUpgradeAsync(
        NpgsqlDataSource dataSource, string connectionString)
    {
        // Recreate the exact previously deployed V21 payload-keyed publication.
        // Its sealed rows must survive promotion to the dependency-bound key.
        await using (var command = dataSource.CreateCommand(
            """
            INSERT INTO npc_dialogue_revisions
                (revision, spawn_revision, text_count, profile_count,
                 route_count, menu_entry_count, source)
            SELECT @legacy, spawn_revision, text_count, profile_count,
                   route_count, menu_entry_count, source
            FROM npc_dialogue_revisions WHERE revision = @release;
            INSERT INTO npc_dialogue_texts
                (revision, npc_key, scene_key, display_name, description)
            SELECT @legacy, npc_key, scene_key, display_name, description
            FROM npc_dialogue_texts WHERE revision = @release;
            INSERT INTO npc_dialogue_profiles
                (revision, profile_key, dialog_index, behavior, initial_request_sub_id)
            SELECT @legacy, profile_key, dialog_index, behavior, initial_request_sub_id
            FROM npc_dialogue_profiles WHERE revision = @release;
            INSERT INTO npc_dialogue_profile_entries
                (revision, profile_key, menu_order, sub_id)
            SELECT @legacy, profile_key, menu_order, sub_id
            FROM npc_dialogue_profile_entries WHERE revision = @release;
            INSERT INTO npc_dialogue_bindings
                (revision, npc_key, client_script_key, profile_key, route_order)
            SELECT @legacy, npc_key, client_script_key, profile_key, route_order
            FROM npc_dialogue_bindings WHERE revision = @release;
            UPDATE npc_dialogue_publication SET revision = @legacy,
                publisher = 'protocol-check-v21-legacy', published_at = now()
            WHERE family = 'npc-dialogues';
            """))
        {
            command.Parameters.AddWithValue("legacy", NpgsqlDbType.Varchar,
                NpcDialogueBaselineV21.ExpectedRevision);
            command.Parameters.AddWithValue("release", NpgsqlDbType.Varchar,
                PostgresNpcDialogueBaselinePublisher.CurrentReleaseRevision);
            await command.ExecuteNonQueryAsync();
        }
        var legacy = await PostgresWorldContentReaderLoader.LoadAsync(connectionString);
        Check.Equal(NpcDialogueBaselineV21.ExpectedRevision,
            legacy.Manifest.NpcDialogues.Sha256,
            "loader retains the historical V21 payload release");
        var before = await ReadLegacyV21SnapshotAsync(dataSource);
        var upgraded = await PostgresNpcDialogueBaselinePublisher
            .EnsurePublishedAsync(connectionString);
        Check.True(upgraded.Created && upgraded.Revision ==
            PostgresNpcDialogueBaselinePublisher.CurrentReleaseRevision,
            "legacy V21 publication promotes to its dependency-bound identity");
        Check.Equal(before, await ReadLegacyV21SnapshotAsync(dataSource),
            "promotion leaves every immutable legacy V21 row unchanged");
        var current = await PostgresWorldContentReaderLoader.LoadAsync(connectionString);
        Check.Equal(legacy.Manifest.NpcDialogues.Sha256,
            current.Manifest.NpcDialogues.Sha256,
            "promotion changes release identity without changing dialogue payload");
    }

    private static async Task<string> ReadLegacyV21SnapshotAsync(NpgsqlDataSource dataSource)
    {
        await using var command = dataSource.CreateCommand(
            """
            SELECT md5(string_agg(row_json::text, E'\n' ORDER BY row_json::text))
            FROM (
                SELECT to_jsonb(r) AS row_json FROM npc_dialogue_revisions r WHERE revision = @revision
                UNION ALL
                SELECT to_jsonb(r) FROM npc_dialogue_texts r WHERE revision = @revision
                UNION ALL
                SELECT to_jsonb(r) FROM npc_dialogue_profiles r WHERE revision = @revision
                UNION ALL
                SELECT to_jsonb(r) FROM npc_dialogue_profile_entries r WHERE revision = @revision
                UNION ALL
                SELECT to_jsonb(r) FROM npc_dialogue_bindings r WHERE revision = @revision
            ) rows;
            """);
        command.Parameters.AddWithValue("revision", NpgsqlDbType.Varchar,
            NpcDialogueBaselineV21.ExpectedRevision);
        return (string)(await command.ExecuteScalarAsync())!;
    }
}
