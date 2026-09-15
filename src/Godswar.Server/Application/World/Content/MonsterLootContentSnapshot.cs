using System.Collections.Frozen;
using System.Security.Cryptography;

namespace Godswar.Server.Application.World.Content;

/// <summary>
/// One editable monster loot header: which monster drops, and how many items a
/// single kill may leave on the ground.
/// </summary>
internal readonly record struct MonsterLootTableRule(
    string TemplateKey,
    int MaximumDrops);

/// <summary>One editable drop rule of a monster loot table.</summary>
internal readonly record struct MonsterLootRule(
    string TemplateKey,
    int LootIndex,
    uint ItemId,
    int ChanceBasisPoints,
    int MinimumQuantity,
    int MaximumQuantity);

/// <summary>A drop that survived its chance roll for one kill.</summary>
internal readonly record struct RolledMonsterLoot(
    int LootIndex,
    uint ItemId,
    int Quantity);

/// <summary>
/// One repeatable-read snapshot of the database-owned monster loot tables,
/// shaped like <c>MedusaMonsterContentSnapshot</c>. Schema creation stays
/// migration-owned; this type only validates and indexes what was read.
/// </summary>
internal sealed class MonsterLootContentSnapshot
{
    private readonly FrozenDictionary<string, MonsterLootTableRule> _tables;
    private readonly FrozenDictionary<string, MonsterLootRule[]> _loot;

    public MonsterLootContentSnapshot(
        IReadOnlyList<MonsterLootTableRule> tables,
        IReadOnlyList<MonsterLootRule> loot)
    {
        ArgumentNullException.ThrowIfNull(tables);
        ArgumentNullException.ThrowIfNull(loot);
        Validate(tables, loot);
        _tables = tables.ToFrozenDictionary(
            static table => table.TemplateKey,
            StringComparer.Ordinal);
        _loot = loot
            .GroupBy(static rule => rule.TemplateKey, StringComparer.Ordinal)
            .ToFrozenDictionary(
                static group => group.Key,
                static group => group
                    .OrderBy(static rule => rule.LootIndex)
                    .ToArray(),
                StringComparer.Ordinal);
    }

    public IReadOnlyCollection<MonsterLootTableRule> Tables =>
        _tables.Values;

    public IReadOnlyCollection<MonsterLootRule> Loot =>
        _loot.Values.SelectMany(static rules => rules).ToArray();

    public bool TryGetTable(
        string? templateKey,
        out MonsterLootTableRule table)
    {
        if (string.IsNullOrWhiteSpace(templateKey))
        {
            table = default;
            return false;
        }

        return _tables.TryGetValue(templateKey, out table);
    }

    /// <summary>
    /// Rolls one kill. The roll is deterministic in the death event so a replay
    /// of the same kill yields the same ground items, and it stops at the
    /// table's drop cap.
    /// </summary>
    public IReadOnlyList<RolledMonsterLoot> RollLoot(
        string templateKey,
        Guid deathEventId)
    {
        if (deathEventId == Guid.Empty ||
            !_tables.TryGetValue(templateKey, out var table) ||
            !_loot.TryGetValue(templateKey, out var rules))
        {
            return [];
        }

        var rolled = new List<RolledMonsterLoot>(table.MaximumDrops);
        Span<byte> input = stackalloc byte[20];
        Span<byte> hash = stackalloc byte[SHA256.HashSizeInBytes];
        deathEventId.TryWriteBytes(input[..16]);
        foreach (var rule in rules)
        {
            if (rolled.Count >= table.MaximumDrops)
            {
                break;
            }

            BitConverter.TryWriteBytes(input[16..], rule.LootIndex);
            SHA256.HashData(input, hash);
            if (BitConverter.ToUInt32(hash) % 10_000 >= rule.ChanceBasisPoints)
            {
                continue;
            }

            var range = checked(
                rule.MaximumQuantity - rule.MinimumQuantity + 1);
            var quantity = checked(
                rule.MinimumQuantity +
                (int)(BitConverter.ToUInt32(hash[4..]) % range));
            rolled.Add(new(rule.LootIndex, rule.ItemId, quantity));
        }

        return rolled.AsReadOnly();
    }

    private static void Validate(
        IReadOnlyList<MonsterLootTableRule> tables,
        IReadOnlyList<MonsterLootRule> loot)
    {
        var keys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var table in tables)
        {
            if (string.IsNullOrWhiteSpace(table.TemplateKey) ||
                table.MaximumDrops is < 1 or > 32 ||
                !keys.Add(table.TemplateKey))
            {
                throw new InvalidDataException(
                    $"Monster loot table {table.TemplateKey} is invalid.");
            }
        }

        var indexes = new HashSet<(string, int)>();
        foreach (var rule in loot)
        {
            if (!keys.Contains(rule.TemplateKey) ||
                rule.LootIndex is < 0 or >= 32 ||
                rule.ItemId == 0 ||
                rule.ChanceBasisPoints is < 1 or > 10_000 ||
                rule.MinimumQuantity is < 1 or > 255 ||
                rule.MaximumQuantity < rule.MinimumQuantity ||
                rule.MaximumQuantity > 255 ||
                !indexes.Add((rule.TemplateKey, rule.LootIndex)))
            {
                throw new InvalidDataException(
                    $"Monster loot rule {rule.TemplateKey}/{rule.LootIndex} is invalid.");
            }
        }

        foreach (var table in tables)
        {
            var count = loot.Count(rule =>
                string.Equals(
                    rule.TemplateKey,
                    table.TemplateKey,
                    StringComparison.Ordinal));
            if (count < table.MaximumDrops)
            {
                throw new InvalidDataException(
                    $"Monster loot table {table.TemplateKey} cannot drop {table.MaximumDrops} items from {count} rules.");
            }
        }
    }
}

internal static class MonsterLootContentCatalog
{
    private static MonsterLootContentSnapshot? _current;

    public static MonsterLootContentSnapshot Current =>
        Volatile.Read(ref _current) ?? throw new InvalidOperationException(
            "The database-owned monster loot content has not been loaded.");

    public static void Install(MonsterLootContentSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        Volatile.Write(ref _current, snapshot);
    }
}
