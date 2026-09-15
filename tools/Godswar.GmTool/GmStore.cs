using System.Globalization;
using Npgsql;
using NpgsqlTypes;

namespace Godswar.GmTool;

/// <summary>
/// Read queries and the single audited write path used by the GM tool.
/// Everything here talks to PostgreSQL directly; the running game server is
/// never contacted, so an online character can be overwritten by its next
/// checkpoint. Callers must gate the write path on explicit operator consent.
/// </summary>
internal sealed class GmStore(NpgsqlDataSource dataSource, ClientLocalization localization)
{
    public const int KitBagLocation = 1;
    public const int KitBagSlots = 96;
    public const int KitBagSlotsPerPage = 24;
    public const int MaximumGrantQuantity = 9999;

    private readonly NpgsqlDataSource _dataSource = dataSource;
    private readonly ClientLocalization _localization = localization;

    public async Task<object> ReadServerInfoAsync(CancellationToken cancellationToken)
    {
        await using var connection = await _dataSource.OpenConnectionAsync(cancellationToken);
        await using var command = new NpgsqlCommand(
            """
            SELECT current_database(),
                   (SELECT count(*)::integer FROM character_base),
                   (SELECT count(*)::integer FROM character_items),
                   (SELECT revision FROM item_template_content_publication
                     WHERE family = 'items'),
                   (SELECT count(*)::integer
                      FROM item_template_content_definitions d
                      JOIN item_template_content_publication p
                        ON p.revision = d.revision AND p.family = 'items'),
                   (SELECT count(*)::integer FROM item_templates);
            """,
            connection);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        await reader.ReadAsync(cancellationToken);
        return new
        {
            database = reader.GetString(0),
            characters = reader.GetInt32(1),
            itemRows = reader.GetInt32(2),
            publishedRevision = reader.IsDBNull(3) ? null : reader.GetString(3),
            publishedItems = reader.GetInt32(4),
            stagedItems = reader.GetInt32(5)
        };
    }

    public async Task<IReadOnlyList<object>> SearchCharactersAsync(
        string? name,
        int limit,
        CancellationToken cancellationToken)
    {
        await using var connection = await _dataSource.OpenConnectionAsync(cancellationToken);
        await using var command = new NpgsqlCommand(
            """
            SELECT cb.id,
                   cb.name,
                   a.username,
                   cb.account_id,
                   cb.profession,
                   cb.camp,
                   cb."GM"::integer,
                   cb.fighter_job_lv,
                   cb.scholar_job_lv,
                   cb."Money",
                   cb."Stone",
                   cb."SkillPoint",
                   cb."Map"::integer,
                   cb."Pos_X",
                   cb."Pos_Z",
                   cb."curHP",
                   cb."MaxHP",
                   cb."curMP",
                   cb."MaxMP",
                   cb.bag_num,
                   cb.store_num,
                   cb."LastLogin_time",
                   a.login_status::integer,
                   a.last_login_time,
                   a.last_logout_time,
                   COALESCE(bag.used, 0)::integer AS bag_used
            FROM character_base cb
            JOIN accounts a ON a.id = cb.account_id
            LEFT JOIN LATERAL (
                SELECT count(*) AS used
                FROM character_items ci
                WHERE ci.user_id = cb.id AND ci.item_location = 1
            ) bag ON true
            WHERE (@like IS NULL OR cb.name ILIKE @like)
            ORDER BY cb.name
            LIMIT @limit;
            """,
            connection);
        command.Parameters.Add(new NpgsqlParameter("like", NpgsqlDbType.Text)
        {
            Value = string.IsNullOrWhiteSpace(name) ? DBNull.Value : $"%{name.Trim()}%"
        });
        command.Parameters.AddWithValue("limit", Math.Clamp(limit, 1, 200));

        var rows = new List<object>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new
            {
                id = reader.GetInt32(0),
                name = reader.GetString(1),
                account = reader.GetString(2),
                accountId = reader.GetInt32(3),
                profession = reader.GetInt16(4),
                professionName = ProfessionName(reader.GetInt16(4)),
                camp = reader.GetInt16(5),
                gm = reader.GetInt32(6),
                fighterLevel = reader.GetInt32(7),
                scholarLevel = reader.GetInt32(8),
                money = reader.GetInt32(9),
                stone = reader.GetInt32(10),
                skillPoint = reader.GetInt32(11),
                map = reader.GetInt32(12),
                positionX = reader.GetFloat(13),
                positionZ = reader.GetFloat(14),
                currentHp = reader.GetInt32(15),
                maxHp = reader.GetInt32(16),
                currentMp = reader.GetInt32(17),
                maxMp = reader.GetInt32(18),
                bagPages = reader.GetInt16(19),
                warehouseSlots = reader.GetInt32(20),
                lastLogin = reader.GetDateTime(21),
                loginStatus = reader.GetInt32(22),
                accountLastLogin = reader.GetDateTime(23),
                accountLastLogout = reader.GetDateTime(24),
                bagUsed = reader.GetInt32(25)
            });
        }

        return rows;
    }

    public async Task<object?> ReadCharacterAsync(int characterId, CancellationToken cancellationToken)
    {
        await using var connection = await _dataSource.OpenConnectionAsync(cancellationToken);

        var baseRow = await ReadSingleRowAsync(
            connection,
            """
            SELECT cb.*, a.username, a.login_status::integer AS account_login_status,
                   a.last_login_time, a.last_logout_time, a.total_online_time
            FROM character_base cb
            JOIN accounts a ON a.id = cb.account_id
            WHERE cb.id = @id;
            """,
            characterId,
            cancellationToken);
        if (baseRow is null)
        {
            return null;
        }

        var stats = await ReadSingleRowAsync(
            connection,
            "SELECT * FROM character_stat_summary WHERE user_id = @id;",
            characterId,
            cancellationToken);
        var talents = await ReadRowsAsync(
            connection,
            "SELECT * FROM character_talent_stat_summary WHERE user_id = @id;",
            characterId,
            cancellationToken);

        var equipment = await ReadRowsAsync(
            connection,
            """
            SELECT ci.slot_index,
                   ci.prop_id,
                   COALESCE(it.display_name, '(unknown item)') AS display_name,
                   COALESCE(it.kind, '') AS kind,
                   COALESCE(it.icon, '') AS icon,
                   ci.item_quality,
                   ci.item_grade,
                   ci.bound,
                   ci.stack,
                   ci.item_exp,
                   ci.holy_suit_code,
                   ci.holy_socket_count
            FROM character_items ci
            LEFT JOIN item_templates it ON it.id = ci.prop_id
            WHERE ci.user_id = @id AND ci.item_location = 0
            ORDER BY ci.slot_index;
            """,
            characterId,
            cancellationToken);

        var bag = await ReadRowsAsync(
            connection,
            """
            SELECT ci.slot_index,
                   ci.prop_id,
                   COALESCE(it.display_name, '(unknown item)') AS display_name,
                   COALESCE(it.kind, '') AS kind,
                   COALESCE(it.icon, '') AS icon,
                   ci.item_quality,
                   ci.item_grade,
                   ci.bound,
                   ci.stack
            FROM character_items ci
            LEFT JOIN item_templates it ON it.id = ci.prop_id
            WHERE ci.user_id = @id AND ci.item_location = 1
            ORDER BY ci.slot_index;
            """,
            characterId,
            cancellationToken);

        var warehouseCount = await ReadCountAsync(
            connection,
            "SELECT count(*)::integer FROM character_items WHERE user_id = @id AND item_location = 2;",
            characterId,
            cancellationToken);

        var skills = await ReadRowsAsync(
            connection,
            """
            SELECT cs.skill_id,
                   COALESCE(st.display_name, '') AS display_name,
                   COALESCE(st.base_name, '') AS base_name,
                   cs.skill_level,
                   COALESCE(cs.source, '') AS source
            FROM character_skills cs
            LEFT JOIN skill_templates st ON st.skill_id = cs.skill_id
            WHERE cs.user_id = @id
            ORDER BY cs.skill_id
            LIMIT 200;
            """,
            characterId,
            cancellationToken);

        var pets = await ReadRowsAsync(
            connection,
            """
            SELECT id, name, species_id, level, rank
            FROM character_pets
            WHERE user_id = @id
            ORDER BY id
            LIMIT 100;
            """,
            characterId,
            cancellationToken);

        return new
        {
            character = baseRow,
            stats,
            talents,
            equipment,
            bag,
            warehouseItems = warehouseCount,
            skills,
            pets
        };
    }

    public async Task<IReadOnlyList<object>> SearchItemsAsync(
        string? query,
        string? kind,
        int limit,
        CancellationToken cancellationToken)
    {
        var exact = int.TryParse(query, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : (int?)null;
        var like = string.IsNullOrWhiteSpace(query) ? null : $"%{query.Trim()}%";
        // The server's display_name is English; resolve localized terms against
        // the installed client's EquipName.dat so a GM can search in Chinese.
        var localizedKeys = _localization.ResolveKeys(query ?? string.Empty);
        var searchLocalized = localizedKeys.Count > 0;

        await using var connection = await _dataSource.OpenConnectionAsync(cancellationToken);
        await using var command = new NpgsqlCommand(
            """
            WITH catalog AS (
                SELECT t.id, t.kind, t.name_key, t.display_name,
                       t.equipment_slot, t.stats, 0 AS preference
                FROM item_templates t
                UNION ALL
                SELECT d.id, d.kind, d.name_key, d.display_name,
                       d.equipment_slot, d.stats, 1 AS preference
                FROM item_template_content_definitions d
                JOIN item_template_content_publication p
                  ON p.revision = d.revision AND p.family = 'items'
            ),
            deduped AS (
                SELECT DISTINCT ON (id) *
                FROM catalog
                ORDER BY id, preference
            )
            SELECT deduped.id,
                   deduped.kind,
                   deduped.name_key,
                   deduped.display_name,
                   deduped.equipment_slot,
                   COALESCE(NULLIF(deduped.stats ->> 'Overlap', '')::integer, 1) AS stack_cap,
                   COALESCE(deduped.stats ->> 'Icon', '') AS icon,
                   COALESCE(deduped.stats ->> 'Texture', '') AS texture,
                   COALESCE(deduped.stats ->> 'PlayLv', '') AS play_level,
                   COALESCE(deduped.stats ->> 'Money', '') AS money,
                   label.value AS kind_label
            FROM deduped
            LEFT JOIN (VALUES
                ('weapon', '武器'), ('shield', '盾'), ('head', '头盔'),
                ('armor', '盔甲'), ('cloth', '布甲'), ('cuff', '护腕'),
                ('leggins', '护胫'), ('glove', '手套'), ('shoes', '鞋'),
                ('girdle', '腰带'), ('amulet', '护身符'), ('ring', '戒指'),
                ('stylish', '时装'), ('mount', '坐骑'), ('mounthead', '坐骑头部'),
                ('mountarmor', '坐骑护甲'), ('mountsoul', '坐骑之魂'),
                ('mountornament', '坐骑饰品'), ('mountamulet', '坐骑护符'),
                ('consume item', '消耗品'), ('skillitem', '技能道具'),
                ('create', '采集物'), ('pet', '宠物道具')
            ) AS label(kind, value) ON label.kind = deduped.kind
            WHERE (
                    (@exact IS NOT NULL AND deduped.id = @exact)
                    OR (@like IS NOT NULL AND (
                            deduped.display_name ILIKE @like
                            OR deduped.name_key ILIKE @like))
                    OR (@searchLocalized AND deduped.name_key = ANY(@localizedKeys))
                    OR (@exact IS NULL AND @like IS NULL AND NOT @searchLocalized)
                  )
              AND (@kind = '' OR deduped.kind = @kind)
            ORDER BY CASE WHEN @exact IS NOT NULL AND deduped.id = @exact THEN 0 ELSE 1 END,
                     deduped.id
            LIMIT @limit;
            """,
            connection);
        command.Parameters.Add(new NpgsqlParameter("exact", NpgsqlDbType.Integer)
        {
            Value = exact.HasValue ? exact.Value : DBNull.Value
        });
        command.Parameters.Add(new NpgsqlParameter("like", NpgsqlDbType.Text)
        {
            Value = (object?)like ?? DBNull.Value
        });
        command.Parameters.AddWithValue("kind", (kind ?? string.Empty).Trim());
        command.Parameters.AddWithValue("searchLocalized", searchLocalized);
        command.Parameters.Add(new NpgsqlParameter(
            "localizedKeys",
            NpgsqlDbType.Array | NpgsqlDbType.Text)
        {
            Value = localizedKeys.Count == 0 ? [string.Empty] : localizedKeys
        });
        command.Parameters.AddWithValue("limit", Math.Clamp(limit, 1, 500));

        var rows = new List<object>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            var nameKey = reader.GetString(2);
            rows.Add(new
            {
                id = reader.GetInt32(0),
                kind = reader.GetString(1),
                kindLabel = reader.IsDBNull(10) ? reader.GetString(1) : reader.GetString(10),
                nameKey,
                displayName = reader.GetString(3),
                localizedName = _localization.LocalizedName(nameKey),
                equipmentSlot = reader.GetInt16(4),
                stackCap = reader.GetInt32(5),
                icon = reader.GetString(6),
                texture = reader.GetString(7),
                playLevel = reader.GetString(8),
                money = reader.GetString(9)
            });
        }

        return rows;
    }

    public async Task<IReadOnlyList<string>> ReadItemKindsAsync(CancellationToken cancellationToken)
    {
        await using var connection = await _dataSource.OpenConnectionAsync(cancellationToken);
        await using var command = new NpgsqlCommand(
            "SELECT DISTINCT kind FROM item_templates ORDER BY kind;",
            connection);
        var kinds = new List<string>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            kinds.Add(reader.GetString(0));
        }

        return kinds;
    }

    /// <summary>
    /// Plans (and optionally commits) a stack-aware kit-bag grant.
    /// </summary>
    public async Task<GrantOutcome> GrantAsync(
        GrantRequest request,
        CancellationToken cancellationToken)
    {
        await using var connection = await _dataSource.OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        var character = await ReadSingleRowAsync(
            connection,
            """
            SELECT cb.id, cb.name, cb.bag_num, a.login_status::integer,
                   a.last_login_time, a.last_logout_time
            FROM character_base cb
            JOIN accounts a ON a.id = cb.account_id
            WHERE cb.id = @id
            FOR UPDATE OF cb;
            """,
            request.CharacterId,
            transaction,
            cancellationToken);
        if (character is null)
        {
            throw new GmToolException($"角色不存在：id={request.CharacterId}");
        }

        var item = await ReadSingleRowAsync(
            connection,
            """
            SELECT id, kind, name_key, display_name,
                   COALESCE(NULLIF(stats ->> 'Overlap', '')::integer, 1) AS stack_cap,
                   COALESCE((stats ? 'BindType')::boolean, false) AS binds
            FROM item_templates
            WHERE id = @id;
            """,
            request.ItemId,
            transaction,
            cancellationToken);
        if (item is null)
        {
            throw new GmToolException(
                $"物品 {request.ItemId} 不在 item_templates 中（外键目标缺失），无法发放。" +
                "如果这是新补齐的物品，请先让服务器完成一次内容发布。");
        }

        var characterName = (string)character["name"]!;
        var bagPages = Convert.ToInt32(character["bag_num"], CultureInfo.InvariantCulture);
        var loginStatus = Convert.ToInt32(character["login_status"], CultureInfo.InvariantCulture);
        var lastLogin = (DateTime)character["last_login_time"]!;
        var lastLogout = (DateTime)character["last_logout_time"]!;

        var quantity = Math.Clamp(request.Quantity, 1, MaximumGrantQuantity);
        var stackCap = Math.Max(1, Convert.ToInt32(item["stack_cap"], CultureInfo.InvariantCulture));
        var bound = (bool)item["binds"]! ? 1 : 0;

        // Fill existing partial stacks first so the bag stays compact.
        var plan = new List<GrantPlacement>();
        var claimedSlots = new HashSet<int>();
        var remaining = quantity;
        if (stackCap > 1)
        {
            await using var stackCommand = new NpgsqlCommand(
                """
                SELECT slot_index, stack
                FROM character_items
                WHERE user_id = @user AND item_location = @location
                  AND prop_id = @item AND stack < @cap
                ORDER BY slot_index
                FOR UPDATE;
                """,
                connection,
                transaction);
            stackCommand.Parameters.AddWithValue("user", request.CharacterId);
            stackCommand.Parameters.AddWithValue("location", KitBagLocation);
            stackCommand.Parameters.AddWithValue("item", request.ItemId);
            stackCommand.Parameters.AddWithValue("cap", stackCap);

            var candidates = new List<(int Slot, int Stack)>();
            await using (var reader = await stackCommand.ExecuteReaderAsync(cancellationToken))
            {
                while (await reader.ReadAsync(cancellationToken))
                {
                    candidates.Add((reader.GetInt16(0), reader.GetInt16(1)));
                }
            }

            foreach (var (slot, stack) in candidates)
            {
                if (remaining <= 0)
                {
                    break;
                }

                var add = Math.Min(stackCap - stack, remaining);
                plan.Add(new GrantPlacement(slot, stack, stack + add, add));
                remaining -= add;
            }
        }

        while (remaining > 0)
        {
            var freeSlot = await ReadFreeKitBagSlotAsync(
                connection,
                transaction,
                request.CharacterId,
                claimedSlots.ToArray(),
                cancellationToken);
            if (freeSlot is null)
            {
                throw new GmToolException(
                    $"角色 {characterName} 的背包已满（{KitBagSlots} 格全部占用），本次未写入任何数据。");
            }

            var add = Math.Min(stackCap, remaining);
            plan.Add(new GrantPlacement(freeSlot.Value, 0, add, add));
            claimedSlots.Add(freeSlot.Value);
            remaining -= add;
        }

        var outcome = new GrantOutcome(
            request.CharacterId,
            characterName,
            request.ItemId,
            (string)item["display_name"]!,
            (string)item["kind"]!,
            quantity,
            stackCap,
            bound,
            bagPages,
            plan.Count(p => p.NewRow && p.Slot >= bagPages * KitBagSlotsPerPage),
            new GrantPresence(loginStatus, lastLogin, lastLogout, lastLogin > lastLogout),
            request.DryRun,
            plan);

        if (request.DryRun)
        {
            await transaction.RollbackAsync(cancellationToken);
            return outcome;
        }

        foreach (var placement in plan)
        {
            if (placement.NewRow)
            {
                await using var insert = new NpgsqlCommand(
                    """
                    INSERT INTO character_items (
                        user_id, item_location, slot_index, prop_id,
                        item_quality, item_grade, bound, stack, item_exp, holy_suit_code)
                    VALUES (@user, @location, @slot, @item, 1, 1, @bound, @stack, 0, 0);
                    """,
                    connection,
                    transaction);
                insert.Parameters.AddWithValue("user", request.CharacterId);
                insert.Parameters.AddWithValue("location", KitBagLocation);
                insert.Parameters.AddWithValue("slot", placement.Slot);
                insert.Parameters.AddWithValue("item", request.ItemId);
                insert.Parameters.AddWithValue("bound", (short)bound);
                insert.Parameters.AddWithValue("stack", (short)placement.After);
                await insert.ExecuteNonQueryAsync(cancellationToken);
            }
            else
            {
                await using var update = new NpgsqlCommand(
                    """
                    UPDATE character_items
                    SET stack = @stack, updated_at = now()
                    WHERE user_id = @user AND item_location = @location
                      AND slot_index = @slot;
                    """,
                    connection,
                    transaction);
                update.Parameters.AddWithValue("stack", (short)placement.After);
                update.Parameters.AddWithValue("user", request.CharacterId);
                update.Parameters.AddWithValue("location", KitBagLocation);
                update.Parameters.AddWithValue("slot", placement.Slot);
                await update.ExecuteNonQueryAsync(cancellationToken);
            }

            await using var audit = new NpgsqlCommand(
                """
                INSERT INTO character_item_audit (
                    source, action, user_id, item_location, slot_index,
                    prop_id, item_quality, item_grade, item_exp, old_item)
                VALUES ('gm-tool', @action, @user, @location, @slot,
                        @item, 1, 1, 0,
                        jsonb_build_object(
                            'note', @note,
                            'previousStack', @previousStack,
                            'grantedStack', @grantedStack));
                """,
                connection,
                transaction);
            audit.Parameters.AddWithValue(
                "action",
                placement.NewRow ? "gm-grant-insert" : "gm-grant-stack");
            audit.Parameters.AddWithValue("user", request.CharacterId);
            audit.Parameters.AddWithValue("location", KitBagLocation);
            audit.Parameters.AddWithValue("slot", placement.Slot);
            audit.Parameters.AddWithValue("item", request.ItemId);
            audit.Parameters.Add(new NpgsqlParameter("note", NpgsqlDbType.Text)
            {
                Value = string.IsNullOrWhiteSpace(request.Note)
                    ? DBNull.Value
                    : request.Note
            });
            audit.Parameters.Add(new NpgsqlParameter("previousStack", NpgsqlDbType.Smallint)
            {
                Value = placement.NewRow ? DBNull.Value : (short)placement.Before
            });
            audit.Parameters.Add(new NpgsqlParameter("grantedStack", NpgsqlDbType.Smallint)
            {
                Value = (short)placement.After
            });
            await audit.ExecuteNonQueryAsync(cancellationToken);
        }

        await transaction.CommitAsync(cancellationToken);
        return outcome;
    }

    private static async Task<int?> ReadFreeKitBagSlotAsync(
        NpgsqlConnection connection,
        NpgsqlTransaction transaction,
        int characterId,
        int[] claimedSlots,
        CancellationToken cancellationToken)
    {
        await using var command = new NpgsqlCommand(
            """
            SELECT candidate.slot
            FROM generate_series(0, @maximum) AS candidate(slot)
            WHERE candidate.slot <> ALL(@claimed)
              AND NOT EXISTS (
                SELECT 1 FROM character_items ci
                WHERE ci.user_id = @user
                  AND ci.item_location = @location
                  AND ci.slot_index = candidate.slot)
            ORDER BY candidate.slot
            LIMIT 1;
            """,
            connection,
            transaction);
        command.Parameters.AddWithValue("maximum", KitBagSlots - 1);
        command.Parameters.Add(new NpgsqlParameter(
            "claimed",
            NpgsqlDbType.Array | NpgsqlDbType.Integer)
        {
            Value = claimedSlots
        });
        command.Parameters.AddWithValue("user", characterId);
        command.Parameters.AddWithValue("location", KitBagLocation);
        var value = await command.ExecuteScalarAsync(cancellationToken);
        return value is null or DBNull ? null : Convert.ToInt32(value, CultureInfo.InvariantCulture);
    }

    private static async Task<Dictionary<string, object?>?> ReadSingleRowAsync(
        NpgsqlConnection connection,
        string sql,
        int id,
        CancellationToken cancellationToken) =>
        await ReadSingleRowAsync(connection, sql, id, null, cancellationToken);

    private static async Task<Dictionary<string, object?>?> ReadSingleRowAsync(
        NpgsqlConnection connection,
        string sql,
        int id,
        NpgsqlTransaction? transaction,
        CancellationToken cancellationToken)
    {
        await using var command = new NpgsqlCommand(sql, connection, transaction);
        command.Parameters.AddWithValue("id", id);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        var row = new Dictionary<string, object?>(StringComparer.Ordinal);
        for (var ordinal = 0; ordinal < reader.FieldCount; ordinal++)
        {
            row[reader.GetName(ordinal)] = await reader.IsDBNullAsync(ordinal, cancellationToken)
                ? null
                : reader.GetValue(ordinal);
        }

        return row;
    }

    private static async Task<List<Dictionary<string, object?>>> ReadRowsAsync(
        NpgsqlConnection connection,
        string sql,
        int id,
        CancellationToken cancellationToken)
    {
        await using var command = new NpgsqlCommand(sql, connection);
        command.Parameters.AddWithValue("id", id);
        var rows = new List<Dictionary<string, object?>>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            var row = new Dictionary<string, object?>(StringComparer.Ordinal);
            for (var ordinal = 0; ordinal < reader.FieldCount; ordinal++)
            {
                row[reader.GetName(ordinal)] = await reader.IsDBNullAsync(ordinal, cancellationToken)
                    ? null
                    : reader.GetValue(ordinal);
            }

            rows.Add(row);
        }

        return rows;
    }

    private static async Task<int> ReadCountAsync(
        NpgsqlConnection connection,
        string sql,
        int id,
        CancellationToken cancellationToken)
    {
        await using var command = new NpgsqlCommand(sql, connection);
        command.Parameters.AddWithValue("id", id);
        var value = await command.ExecuteScalarAsync(cancellationToken);
        return value is null or DBNull ? 0 : Convert.ToInt32(value, CultureInfo.InvariantCulture);
    }

    private static string ProfessionName(short profession) => profession switch
    {
        0 => "战士 Warrior",
        1 => "勇士 Champion",
        2 => "祭司 Priest",
        3 => "法师 Mage",
        _ => $"未知({profession})"
    };
}

internal sealed record GrantRequest(
    int CharacterId,
    int ItemId,
    int Quantity,
    bool DryRun,
    string? Note);

internal sealed record GrantPlacement(int Slot, int Before, int After, int Added)
{
    public bool NewRow => Before == 0;
}

internal sealed record GrantPresence(
    int LoginStatus,
    DateTime LastLogin,
    DateTime LastLogout,
    bool LastLoginOnly);

internal sealed record GrantOutcome(
    int CharacterId,
    string CharacterName,
    int ItemId,
    string ItemName,
    string ItemKind,
    int Quantity,
    int StackCap,
    int Bound,
    int BagPages,
    int SlotsBeyondUnlockedPages,
    GrantPresence Appearance,
    bool DryRun,
    IReadOnlyList<GrantPlacement> Placements);

internal sealed class GmToolException(string message) : Exception(message);
