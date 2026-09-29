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

                // 「拾取后绑定」三态回环：true / false / NULL 都要原样写回，
                // NULL 绝不能被落成 false（那会把「跟随物品模板」改成「可交易」）
                if (!await store.HasBoundOnPickupColumnAsync())
                {
                    Line("[跳过] 数据库的 monster_loot_rules 还没有 bound_on_pickup 列" +
                         "（服务端迁移 20260927_213 未应用），跳过「拾取后绑定」回环。");
                    // 列不在时也不许静默按默认值写：选了「可交易 / 拾取绑定」必须被拦住
                    try
                    {
                        await store.SaveLootAsync(
                            probeKey,
                            1,
                            true,
                            [
                                new LootRuleInput(
                                    0,
                                    probeItemId,
                                    2500,
                                    1,
                                    1,
                                    true,
                                    true)
                            ]);
                        Line("[失败] 库里还没有 bound_on_pickup 列，却把「拾取绑定」写进去了。");
                        failures++;
                    }
                    catch (LootValidationException ex)
                    {
                        Line($"[通过] 缺列时写「拾取绑定」被拦住：{ex.Message}");
                    }
                }
                else
                {
                    foreach (var (bound, label) in new (bool?, string)[]
                             {
                                 (true, "拾取绑定"),
                                 (false, "可交易"),
                                 (null, "跟随物品(默认)")
                             })
                    {
                        await store.SaveLootAsync(
                            probeKey,
                            1,
                            true,
                            [
                                new LootRuleInput(
                                    0,
                                    probeItemId,
                                    2500,
                                    1,
                                    1,
                                    true,
                                    bound)
                            ]);
                        var readBack = (await store.LoadRulesAsync(probeKey))[0]
                            .BoundOnPickup;
                        var boundOk = readBack == bound;
                        Line(boundOk
                            ? $"[通过] 拾取后 = {label}：" +
                              $"写入 {DescribeBound(bound)} 读回 {DescribeBound(readBack)}。"
                            : $"[失败] 拾取后 = {label} 写回不一致：" +
                              $"期望 {DescribeBound(bound)}，实际 {DescribeBound(readBack)}。");
                        if (!boundOk)
                        {
                            failures++;
                        }
                    }
                }

                // 12 列「物品属性」回环：品质10 / 等级12 / 属性 24 等级5、133、90 → 读回一致 → 还原 NULL
                if (!await store.HasItemAttributeColumnsAsync())
                {
                    Line("[跳过] 数据库的 monster_loot_rules 还没有那 12 列物品属性" +
                         "（服务端迁移 20260927_214 未应用），跳过掉落物品属性回环。");
                    // 列不在时也不许静默写：配过属性必须被拦住
                    try
                    {
                        await store.SaveLootAsync(
                            probeKey,
                            1,
                            true,
                            [
                                new LootRuleInput(
                                    0,
                                    probeItemId,
                                    2500,
                                    1,
                                    1,
                                    true,
                                    null,
                                    ProbeAttributes)
                            ]);
                        Line("[失败] 库里还没有那 12 列物品属性，却把属性写进去了。");
                        failures++;
                    }
                    catch (LootValidationException ex)
                    {
                        Line($"[通过] 缺列时写物品属性被拦住：{ex.Message}");
                    }
                }
                else
                {
                    await store.SaveLootAsync(
                        probeKey,
                        1,
                        true,
                        [
                            new LootRuleInput(
                                0,
                                probeItemId,
                                2500,
                                1,
                                1,
                                true,
                                null,
                                ProbeAttributes)
                        ]);
                    var withAttributes = (await store.LoadRulesAsync(probeKey))[0].Attributes;
                    var attributesOk = withAttributes == ProbeAttributes;
                    Line(attributesOk
                        ? $"[通过] 掉落物品属性写入后读回一致：{withAttributes!.Summary}"
                        : $"[失败] 掉落物品属性写回不一致：期望 {ProbeAttributes.Summary}，" +
                          $"实际 {withAttributes?.Summary ?? "NULL"}。");
                    if (!attributesOk)
                    {
                        failures++;
                    }

                    // 还原成 NULL：不配置就是要回到 NULL，不能留下 0
                    await store.SaveLootAsync(
                        probeKey,
                        1,
                        true,
                        [new LootRuleInput(0, probeItemId, 2500, 1, 1, true)]);
                    var restored = (await store.LoadRulesAsync(probeKey))[0].Attributes;
                    var restoredOk = restored is { IsEmpty: true };
                    Line(restoredOk
                        ? "[通过] 掉落物品属性已还原成不配置（12 列 NULL）。"
                        : $"[失败] 掉落物品属性没有还原干净：{restored?.Summary ?? "NULL"}。");
                    if (!restoredOk)
                    {
                        failures++;
                    }
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

        failures += await CheckQuestRewardAsync(settings, items, Line);

        failures += CheckQuestCatalogue(settings, Line);

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

    /// <summary>
    /// 任务奖励页签的数据层：两张覆盖表在（服务端迁移跑过）时做一次
    /// 「写入 → 读回 → 删除」回环，目标任务取自本库真实存在的任务 ID；
    /// 结束时把写进去的行删干净，不留垃圾数据。旧库没有这两张表时只报跳过。
    /// </summary>
    /// <summary>
    /// 「任务奖励」页签的搜索源：客户端自己带的 Quest.xml + Text\Quest\*.dat。
    /// 客户端目录不存在时跳过（工具在没装客户端的机器上照样能跑其它段落）。
    /// </summary>
    private static int CheckQuestCatalogue(LootToolSettings settings, Action<string> line)
    {
        var failures = 0;
        line(string.Empty);
        line("── 任务目录解析（本次新增） ────────────────────");

        if (string.IsNullOrWhiteSpace(settings.ClientRoot) ||
            !Directory.Exists(settings.ClientRoot))
        {
            line($"[跳过] 客户端目录不可用（{settings.ClientRoot}），跳过任务目录解析。");
            return failures;
        }

        var stopwatch = System.Diagnostics.Stopwatch.StartNew();
        var catalog = QuestCatalog.Load(settings.ClientRoot);
        stopwatch.Stop();

        if (catalog.Error is { Length: > 0 })
        {
            line($"[失败] 任务目录解析失败：{catalog.Error}");
            return 1;
        }

        line($"[通过] 任务表 {catalog.QuestXmlPath}");
        line($"[信息] 语言目录 {catalog.Language}｜解析到 {catalog.Quests.Count} 个任务" +
             $"（标题来自 Text\\Quest\\*.dat 的 {catalog.TitleCount} 条，" +
             $"其余回落为 LvX 任务ID）｜耗时 {stopwatch.ElapsedMilliseconds} ms");

        var countOk = catalog.Quests.Count > 0;
        line(countOk
            ? "[通过] 任务条数 > 0。"
            : "[失败] 任务表里一条都没解析出来。");
        if (!countOk)
        {
            failures++;
        }

        var sparta = catalog.Quests.Count(static quest => quest.Faction == 0);
        var athens = catalog.Quests.Count(static quest => quest.Faction == 1);
        var unknown = catalog.Quests.Count - sparta - athens;
        line($"[信息] 阵营分布：斯巴达 {sparta}｜雅典 {athens}｜未标注 {unknown}");

        var levels = catalog.Quests.Select(static quest => quest.MinLevel).ToList();
        var levelOk = levels.Count > 0 && levels.Min() >= 0 && levels.Max() <= 1000;
        line(levelOk
            ? $"[通过] 等级区间合理：{levels.Min()}–{levels.Max()}。"
            : $"[失败] 等级区间异常：{levels.Min()}–{levels.Max()}。");
        if (!levelOk)
        {
            failures++;
        }

        // 抽几条逐项校验：ID/等级/阵营/标题都要像样
        var samples = catalog.Quests
            .Where(static quest => quest.TitleFromClient)
            .OrderBy(static _ => Guid.NewGuid())
            .Take(5)
            .ToList();
        if (samples.Count == 0)
        {
            line("[失败] 一条标题都没从 Text\\Quest\\*.dat 里读出来（格式变了？）。");
            failures++;
        }

        foreach (var quest in samples)
        {
            var ok = quest.Id > 0 &&
                quest.MinLevel >= 0 &&
                quest.Faction is -1 or 0 or 1 &&
                quest.Title.Contains("Lv", StringComparison.Ordinal);
            line(ok
                ? $"[通过] 抽样 ID={quest.Id} 等级={quest.MinLevel} " +
                  $"阵营={quest.FactionName} 发布NPC={quest.GiverName} 标题={quest.Title}"
                : $"[失败] 抽样异常：ID={quest.Id} 等级={quest.MinLevel} " +
                  $"阵营={quest.Faction} 标题={quest.Title}");
            if (!ok)
            {
                failures++;
            }
        }

        // 已知的真实任务：新手任务 518 是斯巴达的 1 级任务（客户端文本 [Lv1]初入斯巴达）
        var starter = catalog.Quests.FirstOrDefault(static quest => quest.Id == 518);
        if (starter is null)
        {
            line("[信息] 没找到任务 518（这份客户端可能不含新手任务），跳过该抽样。");
        }
        else
        {
            var starterOk = starter.Faction == 0 && starter.MinLevel == 1;
            line(starterOk
                ? $"[通过] 任务 518：等级 {starter.MinLevel}、阵营 {starter.FactionName}、" +
                  $"标题 {starter.Title}。"
                : $"[失败] 任务 518 的资料不对：等级 {starter.MinLevel}、" +
                  $"阵营 {starter.Faction}、标题 {starter.Title}。");
            if (!starterOk)
            {
                failures++;
            }
        }

        // 附加属性表（「属性…」弹窗的下拉）：清单来自客户端 ItemAppendAttribute.xml
        // （真实运行时还会并上服务端 item_attribute_templates），中文名来自 EquipDescription.dat
        var attributes = ItemAttributeCatalog.Load(settings.ClientRoot, []);
        var attributesOk = attributes.Attributes.Count > 0;
        line(attributesOk
            ? $"[通过] 附加属性表：{attributes.Attributes.Count} 条，其中 " +
              $"{attributes.ChineseNameCount} 条有中文名（{attributes.ClientTextPath}）"
            : $"[失败] 没读到附加属性表：{attributes.Error}");
        if (!attributesOk)
        {
            failures++;
        }
        else
        {
            foreach (var sample in attributes.Attributes.Take(2))
            {
                line($"[信息] 属性 {sample.Id} → {sample.DisplayName}" +
                     $"（{sample.NameKey}，最高 {sample.MaxLevel} 级" +
                     $"{(sample.Percent ? "，百分比" : string.Empty)}）");
            }

            if (attributes.ChineseNameCount == 0)
            {
                line("[警告] 属性中文名一条都没读到（" + attributes.ClientTextPath +
                     "），下拉里只能显示英文标签。");
            }
        }

        return failures;
    }

    private static async Task<int> CheckQuestRewardAsync(
        LootToolSettings settings,
        IReadOnlyList<ItemRow> items,
        Action<string> line)
    {
        var failures = 0;
        line(string.Empty);
        line("── 任务奖励（本次新增） ────────────────────────");

        await using var store = new QuestRewardStore();
        try
        {
            store.Connect(settings.BuildConnectionString());
        }
        catch (Exception ex)
        {
            line($"[失败] 任务奖励页无法连接数据库：{ex.Message}");
            return 1;
        }

        if (!await store.HasQuestRewardSchemaAsync())
        {
            // 服务端迁移可能还没跑：这是旧库的正常状态，跳过而不是失败
            line($"[跳过] {QuestRewardStore.MissingSchemaMessage(store.DatabaseName)}");
            return 0;
        }

        line("[通过] 任务奖励 schema 存在（quest_reward_slots + quest_reward_values）。");

        var overridden = await store.LoadQuestRowsAsync();
        line(overridden.Count == 0
            ? "[信息] 当前没有任何任务被覆盖（两张表都是空的）。"
            : $"[信息] 已覆盖任务 {overridden.Count} 个：" + string.Join(
                "、",
                overridden.Select(static row => $"{row.QuestId}（{row.Status}）")));

        // 回环目标：本库真实存在的任务（character_quests / quest_monster_references），
        // 取不到才退回抓包奖励记录里的新手任务 518/519/520（服务端 StarterQuestRewardRecords）。
        var probeQuestId = await store.FindProbeQuestIdAsync(
            overridden.Select(static row => row.QuestId).ToHashSet(),
            [518, 519, 520]);
        if (probeQuestId == 0)
        {
            line("[跳过] 找不到既真实存在、又没有覆盖的任务 ID，跳过回环（不动现有 GM 数据）。");
            return failures;
        }

        if (items.Count < 2)
        {
            line($"[跳过] 物品目录只有 {items.Count} 条，无法构造两个槽位，跳过回环。");
            return failures;
        }

        var firstItemId = items.Any(static item => item.Id == 4001)
            ? 4001
            : items.Min(static item => item.Id);
        var secondItemId = items.First(item => item.Id != firstItemId).Id;
        var firstSlot = (short)0;
        var secondSlot = (short)3;
        var probeValues = new QuestRewardValues(1234, 5, 678, 9);
        line($"[信息] 回环目标任务：{probeQuestId}（当前未覆盖，测完删干净）；" +
            $"物品用 {firstItemId} / {secondItemId}。");

        // 校验必须是写库前拦截，所以这里顺手验一遍错误输入不会落库
        async Task ExpectRejectedAsync(
            IReadOnlyList<QuestRewardSlotInput> badSlots,
            bool overrideValues,
            QuestRewardValues badValues,
            string what)
        {
            try
            {
                await store.SaveAsync(
                    probeQuestId,
                    badSlots,
                    overrideValues,
                    badValues);
                line($"[失败] {what} 竟然通过了校验。");
                failures++;
            }
            catch (QuestRewardToolException ex)
            {
                line($"[通过] {what} 被校验拦截：{ex.Message}");
            }
        }

        try
        {
            await store.SaveAsync(
                probeQuestId,
                [
                    new QuestRewardSlotInput(firstSlot, firstItemId),
                    new QuestRewardSlotInput(secondSlot, secondItemId)
                ],
                overrideValues: true,
                probeValues);
            var slots = await store.LoadSlotsAsync(probeQuestId);
            var values = await store.LoadValuesAsync(probeQuestId);
            // 读回来的行永远带一个（可能是空的）属性记录，所以比较时也要带上
            var roundTripOk = slots.Count == 2 &&
                slots[0] == new QuestRewardSlot(firstSlot, firstItemId, new ItemAttributeValues()) &&
                slots[1] == new QuestRewardSlot(secondSlot, secondItemId, new ItemAttributeValues()) &&
                values == probeValues;
            line(roundTripOk
                ? $"[通过] 写入后读回一致：槽位 {slots[0].SlotIndex}/{slots[1].SlotIndex} " +
                  $"物品 {slots[0].ItemId}/{slots[1].ItemId}，" +
                  $"数值 经验 {values!.Experience}/TP {values.TalentPoints}/" +
                  $"银币 {values.Silver}/金币 {values.Gold}"
                : $"[失败] 写入后读回不一致：槽位 {slots.Count} 个，" +
                  $"数值 {(values is null ? "无" : "有")}。");
            if (!roundTripOk)
            {
                failures++;
            }

            var listed = (await store.LoadQuestRowsAsync())
                .FirstOrDefault(row => row.QuestId == probeQuestId);
            var listedOk = listed is { SlotCount: 2, HasValues: true };
            line(listedOk
                ? $"[通过] 并集列表认出了刚写入的任务：{probeQuestId} → {listed!.Status}。"
                : $"[失败] 并集列表没有正确反映 {probeQuestId}（{(listed is null ? "没出现" : listed.Status)}）。");
            if (!listedOk)
            {
                failures++;
            }

            await store.SaveAsync(
                probeQuestId,
                [new QuestRewardSlotInput((short)1, secondItemId)],
                overrideValues: false,
                new QuestRewardValues(0, 0, 0, 0));
            var replaced = await store.LoadSlotsAsync(probeQuestId);
            var uncovered = await store.LoadValuesAsync(probeQuestId);
            var replaceOk = replaced.Count == 1 &&
                replaced[0] == new QuestRewardSlot(1, secondItemId, new ItemAttributeValues()) &&
                uncovered is null;
            line(replaceOk
                ? "[通过] 槽位是全量替换：改成只留槽位 1 后，原来的槽位 0/3 已删除；" +
                  "取消「覆盖数值」后 quest_reward_values 的行也没了（恢复内置）。"
                : $"[失败] 全量替换语义不对：剩余槽位 {replaced.Count} 个，" +
                  $"数值行 {(uncovered is null ? "已删除" : "仍在")}。");
            if (!replaceOk)
            {
                failures++;
            }

            await store.SaveAsync(
                probeQuestId,
                [],
                overrideValues: true,
                probeValues);
            var valuesOnly = (await store.LoadQuestRowsAsync())
                .FirstOrDefault(row => row.QuestId == probeQuestId);
            var valuesOnlyOk = valuesOnly is { SlotCount: 0, HasValues: true };
            line(valuesOnlyOk
                ? $"[通过] 只覆盖数值、不覆盖物品也能保存：{valuesOnly!.Status}。"
                : $"[失败] 只覆盖数值的结果不对（{(valuesOnly is null ? "没出现" : valuesOnly.Status)}）。");
            if (!valuesOnlyOk)
            {
                failures++;
            }

            // 12 列「物品属性」回环（任务奖励这一侧）
            if (!await store.HasItemAttributeColumnsAsync())
            {
                line("[跳过] 数据库的 quest_reward_slots 还没有那 12 列物品属性" +
                     "（服务端迁移 20260927_214 未应用），跳过奖励物品属性回环。");
                try
                {
                    await store.SaveAsync(
                        probeQuestId,
                        [new QuestRewardSlotInput(firstSlot, firstItemId, ProbeAttributes)],
                        overrideValues: false,
                        new QuestRewardValues(0, 0, 0, 0));
                    line("[失败] 库里还没有那 12 列物品属性，却把奖励物品属性写进去了。");
                    failures++;
                }
                catch (QuestRewardToolException ex)
                {
                    line($"[通过] 缺列时写奖励物品属性被拦住：{ex.Message}");
                }
            }
            else
            {
                await store.SaveAsync(
                    probeQuestId,
                    [new QuestRewardSlotInput(firstSlot, firstItemId, ProbeAttributes)],
                    overrideValues: false,
                    new QuestRewardValues(0, 0, 0, 0));
                var readSlots = await store.LoadSlotsAsync(probeQuestId);
                var withAttributes = readSlots
                    .FirstOrDefault(slot => slot.SlotIndex == firstSlot)
                    ?.Attributes;
                var attributesOk = withAttributes == ProbeAttributes;
                line(attributesOk
                    ? $"[通过] 奖励物品属性写入后读回一致：{withAttributes!.Summary}"
                    : $"[失败] 奖励物品属性写回不一致：期望 {ProbeAttributes.Summary}，" +
                      $"实际 {withAttributes?.Summary ?? "NULL"}。");
                if (!attributesOk)
                {
                    failures++;
                }

                // 还原成 NULL
                await store.SaveAsync(
                    probeQuestId,
                    [new QuestRewardSlotInput(firstSlot, firstItemId)],
                    overrideValues: false,
                    new QuestRewardValues(0, 0, 0, 0));
                var restored = (await store.LoadSlotsAsync(probeQuestId))
                    .FirstOrDefault(slot => slot.SlotIndex == firstSlot)
                    ?.Attributes;
                var restoredOk = restored is { IsEmpty: true };
                line(restoredOk
                    ? "[通过] 奖励物品属性已还原成不配置（12 列 NULL）。"
                    : $"[失败] 奖励物品属性没有还原干净：{restored?.Summary ?? "NULL"}。");
                if (!restoredOk)
                {
                    failures++;
                }
            }

            await ExpectRejectedAsync(
                [new QuestRewardSlotInput((short)8, firstItemId)],
                overrideValues: false,
                new QuestRewardValues(0, 0, 0, 0),
                "槽位 8 超出 0-7");
            await ExpectRejectedAsync(
                [new QuestRewardSlotInput((short)0, 0)],
                overrideValues: false,
                new QuestRewardValues(0, 0, 0, 0),
                "勾选的槽位没有物品");
            await ExpectRejectedAsync(
                [new QuestRewardSlotInput(firstSlot, int.MaxValue)],
                overrideValues: false,
                new QuestRewardValues(0, 0, 0, 0),
                "item_templates 里不存在的物品");
            await ExpectRejectedAsync(
                [],
                overrideValues: true,
                new QuestRewardValues(-1, 0, 0, 0),
                "负数经验值");
        }
        finally
        {
            // 不管中间哪一步炸了，写进去的行都要删干净
            try
            {
                await store.DeleteOverridesAsync(probeQuestId);
                var leftSlots = await store.LoadSlotsAsync(probeQuestId);
                var leftValues = await store.LoadValuesAsync(probeQuestId);
                var clean = leftSlots.Count == 0 && leftValues is null;
                line(clean
                    ? $"[通过] 已清理自测写入的行，任务 {probeQuestId} 回到未覆盖（沿用内置）。"
                    : $"[失败] 任务 {probeQuestId} 还有残留：槽位 {leftSlots.Count} 个，" +
                      $"数值行 {(leftValues is null ? "无" : "有")}。");
                if (!clean)
                {
                    failures++;
                }
            }
            catch (Exception ex)
            {
                line($"[失败] 清理自测写入失败：{ex.Message}");
                failures++;
            }
        }

        return failures;
    }

    /// <summary>三态在报告里怎么念：NULL 就是「NULL（跟随物品模板）」。</summary>
    private static string DescribeBound(bool? boundOnPickup) => boundOnPickup switch
    {
        true => "true（拾取绑定）",
        false => "false（可交易）",
        null => "NULL（跟随物品模板）"
    };

    /// <summary>
    /// 自测用的物品属性：品质10 / 等级12 / 属性 24 等级5、133（不配等级）、90（不配等级）。
    /// 摘要正好是「品质10 等级12 属性:24/5、133/-、90/-」。
    /// </summary>
    private static ItemAttributeValues ProbeAttributes { get; } = new(
        Quality: 10,
        Grade: 12,
        Attribute1: 24,
        AttributeLevel1: 5,
        Attribute2: 133,
        Attribute3: 90);

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
