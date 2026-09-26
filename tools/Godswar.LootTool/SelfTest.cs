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

        failures += await CheckFarmAsync(settings, Line);

        Line();
        Line(failures == 0
            ? "结论：全部通过。"
            : $"结论：{failures} 项失败。");
        return Finish(report, failures == 0 ? 0 : 1);
    }

    /// <summary>
    /// The farm tab's data layer: the view the faction totals come from, the two
    /// ledgers, the published roster, the rule constants read back out of the
    /// server's source, and a write probe that runs inside a transaction it then
    /// rolls back - so the live score board is measured without being changed.
    /// </summary>
    private static async Task<int> CheckFarmAsync(
        LootToolSettings settings,
        Action<string> line)
    {
        var failures = 0;
        line(string.Empty);
        line("── 利兰丁农场（本次新增） ──────────────────────");

        await using var farm = new FarmStore();
        try
        {
            farm.Connect(settings.BuildConnectionString());
        }
        catch (Exception ex)
        {
            line($"[失败] 农场页无法连接数据库：{ex.Message}");
            return 1;
        }

        if (!await farm.HasFarmSchemaAsync())
        {
            line("[失败] 该库没有 lelantine_farm_personal_points 视图/两张流水表；" +
                 "服务端迁移 20260926_210 未应用。");
            return 1;
        }

        line("[通过] 农场积分 schema 存在（视图 + 两张流水表）。");

        var totals = await farm.LoadTotalsAsync();
        line($"[信息] 阵营总分：斯巴达 {totals.SpartaPoints}｜雅典 {totals.AthensPoints}｜" +
             $"有分角色 {totals.Members} 个｜捐卵流水 {totals.DonationRows} 行｜击杀行 {totals.KillRows} 行");

        // The invariant the whole feature rests on: each camp's total is the sum
        // of that camp's personal scores, and the activity's high score is the
        // highest personal score.
        var characters = await farm.LoadCharactersAsync(null, limit: 500);
        var sparta = characters.Where(static row => row.Faction == LelantineFarmRules.SpartaCamp)
            .Sum(static row => row.Personal);
        var athens = characters.Where(static row => row.Faction == LelantineFarmRules.AthensCamp)
            .Sum(static row => row.Personal);
        var highest = characters.Count == 0 ? 0 : characters.Max(static row => row.Personal);
        var invariant = sparta == totals.SpartaPoints && athens == totals.AthensPoints;
        line(invariant
            ? $"[通过] 阵营分 = 同阵营个人积分之和（斯巴达 {sparta}、雅典 {athens}）；" +
              $"最高个人积分 {highest}。"
            : $"[失败] 阵营分与个人分之和不一致：视图 斯巴达 {totals.SpartaPoints}/雅典 {totals.AthensPoints}，" +
              $"逐人求和 斯巴达 {sparta}/雅典 {athens}。");
        if (!invariant)
        {
            failures++;
        }

        var ranked = characters.Where(static row => row.Personal > 0).ToList();
        var rankOk = ranked.All(row => row.Rank >= 1);
        line(rankOk
            ? $"[通过] 有分角色 {ranked.Count} 个都拿到了排名。"
            : "[失败] 有分角色的排名出现 0。");
        if (!rankOk)
        {
            failures++;
        }

        var npcs = await farm.LoadPublishedNpcsAsync();
        var npcOk = npcs.Count > 0 &&
            npcs.All(static npc => npc.MapId == LelantineFarmRules.MapId) &&
            npcs.Select(static npc => npc.ObjectId).Distinct().Count() == npcs.Count;
        line(npcOk
            ? $"[通过] 当前发布的农场 NPC {npcs.Count} 个：" +
              string.Join("、", npcs.Select(static npc => npc.NpcKey + "/" + npc.ObjectId))
            : $"[失败] 已发布农场 NPC 异常：{npcs.Count} 个。");
        if (!npcOk)
        {
            failures++;
        }

        var constants = FarmStore.LoadRuleConstants();
        var missing = constants.Where(static constant =>
            constant.Value.StartsWith("（未找到源码", StringComparison.Ordinal)).ToList();
        line(missing.Count == 0
            ? $"[通过] 从服务端源码读到 {constants.Count} 条农场规则常量。"
            : $"[警告] {missing.Count} 条常量未读到源码（工具不在仓库内？）：" +
              string.Join("、", missing.Select(static constant => constant.Name)));
        if (missing.Count > 0)
        {
            failures++;
        }

        // A write probe that cannot leave a trace: everything happens in a
        // transaction that is rolled back, and the totals are read again after
        // the rollback to prove the score board is untouched.
        var probe = characters.FirstOrDefault();
        if (probe is null)
        {
            line("[信息] 库里没有任何角色，跳过写入探针。");
            return failures;
        }

        var faction = probe.Faction is 0 or 1
            ? probe.Faction
            : (byte)LelantineFarmRules.SpartaCamp;
        try
        {
            await farm.AddAdjustmentAsync(
                probe.Id,
                faction,
                12345,
                dryRun: true);
            var after = await farm.LoadTotalsAsync();
            var rolledBack = after.SpartaPoints == totals.SpartaPoints &&
                after.AthensPoints == totals.AthensPoints &&
                after.DonationRows == totals.DonationRows;
            line(rolledBack
                ? $"[通过] 演练写入（给 {probe.Name} +12345 分）没有落库，总分不变。"
                : "[失败] 演练写入竟然改了数据。");
            if (!rolledBack)
            {
                failures++;
            }
        }
        catch (Exception ex)
        {
            line($"[失败] 演练写入抛错：{ex.Message}");
            failures++;
        }

        var bag = await farm.LoadFarmBagAsync(probe.Id);
        line($"[信息] {probe.Name} 背包里的活动物品：{(bag.Count == 0 ? "无" : string.Join(
            "、",
            bag.Select(static row =>
                $"{row.DisplayName}({row.ItemId}) 品质{row.Quality}×{row.Stack} 槽{row.Slot}")))}");

        try
        {
            var plan = await farm.GrantItemAsync(
                probe.Id,
                LelantineFarmRules.HoundEggItemId,
                quantity: 99,
                quality: LelantineFarmRules.EggRungs[2].Aptitude,
                note: "selftest-dry-run",
                dryRun: true);
            var planned = plan.Placements.Sum(static placement => placement.Added);
            line(planned == 99
                ? $"[通过] 发放演练：{plan.CharacterName} 的 99 个忠犬卵（资质 {plan.Quality}）" +
                  $"落在 {plan.Placements.Count} 个堆位，未写库。"
                : $"[失败] 发放演练只规划了 {planned} 个。");
            if (planned != 99)
            {
                failures++;
            }
        }
        catch (FarmToolException ex) when (
            ex.Message.Contains("背包已满", StringComparison.Ordinal))
        {
            // A full bag is the tool reporting a real blocker, not a defect; the
            // operator has to free a slot before any handout can land.
            line($"[信息] 发放演练跳过（{probe.Name} 的背包已满，工具已正确拒绝写入）：{ex.Message}");
        }

        return failures;
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
