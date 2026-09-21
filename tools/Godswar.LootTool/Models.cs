namespace Godswar.LootTool;

/// <summary>
/// One row of the monster picker. Loot is keyed by <c>template_key</c>, but
/// <c>monster_templates</c> holds one row per (source_key, template_key), so the
/// list is aggregated to one row per template key.
/// </summary>
internal sealed record MonsterRow(
    string TemplateKey,
    string ChineseName,
    string EnglishName,
    string Rank,
    string Scenes,
    string Maps,
    bool HasLootTable,
    short MaximumDrops,
    int RuleCount,
    bool Enabled,
    int SpawnCount)
{
    public string DisplayName =>
        string.IsNullOrWhiteSpace(ChineseName) ? EnglishName : ChineseName;

    public string LootSummary => HasLootTable
        ? $"{RuleCount} 条规则 / 上限 {MaximumDrops}"
        : "未配置";

    public string Status => HasLootTable
        ? (Enabled ? "已配置" : "已配置(停用)")
        : "未配置";

    /// <summary>
    /// Spawn points in the published world content. A template that never
    /// spawns can never be killed, so its loot can never trigger.
    /// </summary>
    public bool IsSpawned => SpawnCount > 0;

    public string SpawnSummary => SpawnCount > 0
        ? SpawnCount.ToString()
        : "0（不会掉落）";
}

/// <summary>Header row of <c>monster_loot_tables</c>.</summary>
internal sealed record LootHeader(short MaximumDrops, bool Enabled);

/// <summary>One row of <c>monster_loot_rules</c>.</summary>
internal sealed record LootRule(
    short LootIndex,
    int ItemId,
    int ChanceBasisPoints,
    short MinimumQuantity,
    short MaximumQuantity,
    bool Enabled);

/// <summary>One selectable item, joined with the client's localized name.</summary>
internal sealed record ItemRow(
    int Id,
    string NameKey,
    string DisplayName,
    string ChineseName,
    string Kind)
{
    public string SearchText => $"{Id}\t{NameKey}\t{DisplayName}\t{ChineseName}\t{Kind}";
}

/// <summary>A monetarised rule as edited in the grid.</summary>
internal sealed record LootRuleInput(
    short LootIndex,
    int ItemId,
    int ChanceBasisPoints,
    short MinimumQuantity,
    short MaximumQuantity,
    bool Enabled);

/// <summary>Problems found by the built-in schema/consistency self-check.</summary>
internal sealed record LootProblem(string Severity, string TemplateKey, string Message);
