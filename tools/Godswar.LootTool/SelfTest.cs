using System.Globalization;
using System.Text;

namespace Godswar.LootTool;

/// <summary>
/// Headless verification of the tool's data layer, so the database behaviour can
/// be checked without clicking through the window. Writes a report next to the
/// executable and (when launched from a console) to standard output.
/// </summary>
internal static class SelfTest
{
    public static async Task<int> RunAsync()
    {
        var report = new StringBuilder();
        var failures = 0;
        void Line(string text = "")
        {
            report.AppendLine(text);
            Console.WriteLine(text);
        }

        var settings = LootToolSettings.Load();
        Line($"数据库      : {settings.Host}:{settings.Port}/{settings.Database}（用户 {settings.Username}）");
        Line($"客户端目录  : {settings.ClientRoot}");
        Line();

        await using var store = new LootStore();
        try
        {
            store.Connect(settings.BuildConnectionString());
        }
        catch (Exception ex)
        {
            Line($"[失败] 无法连接数据库: {ex.Message}");
            return Finish(report, 1);
        }

        var catalog = ClientTextCatalog.Load(settings.ClientRoot);
        Line($"[信息] 数据库 {store.DatabaseName}");
        Line($"[信息] 客户端中文名: 怪物 {catalog.MonsterNameCount} 条 / 物品 {catalog.ItemNameCount} 条");
        if (catalog.MonsterNameCount == 0)
        {
            Line("[警告] 没有读到怪物中文名，请检查客户端目录是否正确。");
            failures++;
        }

        List<MonsterRow> monsters;
        List<ItemRow> items;
        try
        {
            monsters = await store.LoadMonstersAsync();
            items = await store.LoadItemsAsync();
        }
        catch (Exception ex)
        {
            Line($"[失败] 读取怪物/物品目录失败: {ex.Message}");
            return Finish(report, 1);
        }

        Line($"[信息] 怪物模板 {monsters.Count} 个，其中已配掉落 {monsters.Count(static m => m.HasLootTable)} 个，" +
            $"能刷出来 {monsters.Count(static m => m.IsSpawned)} 个（刷怪点合计 {monsters.Sum(static m => m.SpawnCount)}）");
        Line($"[信息] 物品目录 {items.Count} 个");
        Line();

        var spawnedWithoutLoot = monsters
            .Where(static m => m.IsSpawned && !m.HasLootTable)
            .OrderByDescending(static m => m.SpawnCount)
            .ToList();
        if (spawnedWithoutLoot.Count > 0)
        {
            Line("── 会刷出来但还没配掉落的怪（可直接配） ─────────");
            foreach (var monster in spawnedWithoutLoot)
            {
                Line($"  {monster.TemplateKey,-30} 刷怪点 {monster.SpawnCount,3}  " +
                    $"{catalog.MonsterName(monster.TemplateKey, monster.EnglishName)}");
            }

            Line();
        }

        var itemsById = items.ToDictionary(static item => item.Id);
        var chineseNames = monsters.Count(m =>
            !string.IsNullOrWhiteSpace(catalog.MonsterName(m.TemplateKey, string.Empty)));
        Line($"[信息] 怪物模板中能解析出中文名的: {chineseNames} 个");
        Line();

        Line("── 现有掉落表内容 ──────────────────────────────");
        var configured = monsters.Where(static m => m.HasLootTable).ToList();
        if (configured.Count == 0)
        {
            Line("（当前数据库没有任何掉落表）");
        }

        foreach (var monster in configured)
        {
            var chinese = catalog.MonsterName(monster.TemplateKey, monster.EnglishName);
            var rules = await store.LoadRulesAsync(monster.TemplateKey);
            Line($"{monster.TemplateKey}  中文名={chinese}  英文名={monster.EnglishName}  " +
                $"区域={monster.Scenes}  地图={monster.Maps}  上限={monster.MaximumDrops}  " +
                $"启用={monster.Enabled}  刷怪点={monster.SpawnCount}" +
                (monster.IsSpawned ? string.Empty : "  ⚠ 该怪不会刷出来，掉落不会生效"));
            foreach (var rule in rules)
            {
                itemsById.TryGetValue(rule.ItemId, out var item);
                var itemName = item is null
                    ? "⚠ 未知物品"
                    : catalog.ItemName(item.NameKey, item.DisplayName);
                Line($"    序号 {rule.LootIndex,2}  物品 {rule.ItemId,6}  {itemName}  " +
                    $"概率 {(rule.ChanceBasisPoints / 100d).ToString("0.##", CultureInfo.InvariantCulture)}%  " +
                    $"数量 {rule.MinimumQuantity}-{rule.MaximumQuantity}  启用={rule.Enabled}");
            }
        }

        Line();
        Line("── 写入回环测试 ────────────────────────────────");
        var target = monsters.FirstOrDefault(static m => !m.HasLootTable);
        if (target is null)
        {
            Line("[跳过] 找不到未配置掉落的怪物，无法做写入回环。");
        }
        else
        {
            var probeItemId = itemsById.ContainsKey(4001) ? 4001 : items.Min(static i => i.Id);
            var probeKey = target.TemplateKey;
            Line($"目标怪物 {probeKey}（原本未配置），临时写入 1 条规则后删除。");
            try
            {
                await store.SaveLootAsync(
                    probeKey,
                    1,
                    true,
                    [new LootRuleInput(0, probeItemId, 2500, 1, 1, true)]);
                var header = await store.LoadHeaderAsync(probeKey);
                var rules = await store.LoadRulesAsync(probeKey);
                var ok = header is { MaximumDrops: 1, Enabled: true } &&
                    rules.Count == 1 &&
                    rules[0].ItemId == probeItemId;
                Line(ok
                    ? $"[通过] 写入后读回一致：上限={header!.MaximumDrops} 规则={rules.Count} 物品={rules[0].ItemId}"
                    : "[失败] 写入后读回不一致。");
                if (!ok)
                {
                    failures++;
                }

                await store.SaveLootAsync(
                    probeKey,
                    2,
                    true,
                    [
                        new LootRuleInput(0, probeItemId, 2500, 1, 1, true),
                        new LootRuleInput(1, probeItemId, 5000, 2, 3, true)
                    ]);
                var updated = await store.LoadRulesAsync(probeKey);
                Line(updated.Count == 2
                    ? "[通过] 追加规则成功，共 2 条。"
                    : $"[失败] 追加规则后只有 {updated.Count} 条。");
                if (updated.Count != 2)
                {
                    failures++;
                }

                await store.SaveLootAsync(
                    probeKey,
                    1,
                    true,
                    [new LootRuleInput(0, probeItemId, 2500, 1, 1, true)]);
                var pruned = await store.LoadRulesAsync(probeKey);
                Line(pruned.Count == 1
                    ? "[通过] 删除规则成功，被移除的序号已清理。"
                    : $"[失败] 删除规则后仍有 {pruned.Count} 条。");
                if (pruned.Count != 1)
                {
                    failures++;
                }

                try
                {
                    await store.SaveLootAsync(
                        probeKey,
                        3,
                        true,
                        [new LootRuleInput(0, probeItemId, 2500, 1, 1, true)]);
                    Line("[失败] 上限大于规则数竟然通过了校验。");
                    failures++;
                }
                catch (LootValidationException)
                {
                    Line("[通过] 上限大于规则数被校验拦截（服务端启动不变量）。");
                }

                var doubled = await store.MultiplyChancesAsync(2d, probeKey);
                var afterFactor = await store.LoadRulesAsync(probeKey);
                var factorOk = doubled == 1 && afterFactor[0].ChanceBasisPoints == 5000;
                Line(factorOk
                    ? "[通过] 批量按倍率调整：25% × 2 = 50%。"
                    : $"[失败] 批量倍率调整结果异常：{afterFactor[0].ChanceBasisPoints}bp");
                if (!factorOk)
                {
                    failures++;
                }

                var uniform = await store.SetChancesAsync(1234, probeKey);
                var afterUniform = await store.LoadRulesAsync(probeKey);
                var uniformOk = uniform == 1 && afterUniform[0].ChanceBasisPoints == 1234;
                Line(uniformOk
                    ? "[通过] 批量统一概率：12.34%。"
                    : $"[失败] 批量统一概率结果异常：{afterUniform[0].ChanceBasisPoints}bp");
                if (!uniformOk)
                {
                    failures++;
                }

                var clamped = await store.SetChancesAsync(99999, probeKey);
                var afterClamp = await store.LoadRulesAsync(probeKey);
                var clampOk = clamped == 1 && afterClamp[0].ChanceBasisPoints == 10000;
                Line(clampOk
                    ? "[通过] 超出范围的统一概率被夹到 100%。"
                    : $"[失败] 概率夹取异常：{afterClamp[0].ChanceBasisPoints}bp");
                if (!clampOk)
                {
                    failures++;
                }
            }
            finally
            {
                await store.DeleteLootTableAsync(probeKey);
                var restored = await store.LoadHeaderAsync(probeKey);
                Line(restored is null
                    ? $"[通过] 已清理临时掉落表，{probeKey} 恢复未配置状态。"
                    : $"[失败] 临时掉落表未清理干净：{probeKey}");
                if (restored is not null)
                {
                    failures++;
                }
            }
        }

        Line();
        Line("── 结构与一致性自检 ────────────────────────────");
        var problems = await store.SelfCheckAsync();
        foreach (var problem in problems)
        {
            Line($"[{problem.Severity}] {(problem.TemplateKey.Length > 0 ? problem.TemplateKey + "：" : string.Empty)}{problem.Message}");
        }

        failures += problems.Count(static p => p.Severity == "致命");

        Line();
        Line(failures == 0
            ? "结论：全部通过。"
            : $"结论：{failures} 项失败。");
        return Finish(report, failures == 0 ? 0 : 1);
    }

    private static int Finish(StringBuilder report, int exitCode)
    {
        try
        {
            var directory = Path.Combine(AppContext.BaseDirectory, "logs");
            Directory.CreateDirectory(directory);
            var path = Path.Combine(
                directory,
                $"selftest-{DateTime.Now:yyyyMMdd-HHmmss}.txt");
            File.WriteAllText(path, report.ToString());
            Console.WriteLine($"报告已写入：{path}");
        }
        catch (IOException)
        {
            // The console output is enough when the report cannot be written.
        }

        return exitCode;
    }
}
