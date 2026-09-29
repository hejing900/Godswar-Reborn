# 交接文档 —— 用 GM 工具配置刷怪点与怪物属性（可行性评估 + 待办）

> 覆盖时段：2026-09-27 下午 → 2026-09-28 00:58（本地时间，UTC+8）
> 当前状态：**只做了调研与方案设计，一行代码都没改。** 刷怪/怪物属性仍然是原来的实现。
> 写作时快照：
> - 容器 `godswar-server` = `Up (healthy)`，镜像 `godswar-reborn-main-server:latest`（构建于 `2026-09-27T16:38:35Z`）
> - 容器 `godswar-postgres` = `Up (healthy)`（`postgres:17-alpine`）
> - 数据库 **`godswar_local`**（由 `.env` 的 `POSTGRES_DB` 决定，不是 `godswar`），迁移数 **175**
> - 协议检查基线：**456 通过 / 20 失败 / 101 跳过**（那 20 条是既有漂移：NPC 对话 golden 哈希、架构棘轮、战斗 ECS 等，与本主题无关）

---

## 0. 一句话摘要

用户问了两件事：**① 刷怪能不能改成 GM 工具配刷新点；② 每种怪物的属性能不能用 GM 工具配。**
结论：**两件都能做，但现状差别很大** —— 怪物属性里只有暴击抗性已经是"库表可改"，攻防命闪暴全是**代码公式**；刷新点是"每修订不可变"的抓包基线数据。
推荐落地方式：**运行时覆盖表（方案 B）**，即"权威内容一字不动 + 加一张 GM 表 + 启动时读进内存按优先级叠加"，和现有的掉落表 / 任务奖励表完全同构。

---

## 1. 现状（全部已核实，附证据）

### 1.1 刷怪的数据流

```
抓包（参考服原生 10020 外观包）
        │  复核
        ▼
MonsterContentBaseline.v1.gz        ← 编译进服务端的基线（内嵌资源）
        │  PostgresMonsterContentBaselinePublisher（启动时发布）
        ▼
monster_content_revisions + monster_spawn_definitions + monster_content_publication
        │  PostgresWorldContentReaderLoader.LoadPublishedMonsterSpawnsAsync（启动时读当前修订）
        ▼
CapturedMonsterSpawn[]  →  玩家进图时 MapInstance.InitializeMonsters()  →  运行时刷怪
```

| 事实 | 值 / 证据 |
|---|---|
| 基线资源 | `src\Godswar.Server\Infrastructure\WorldContent\Baselines\MonsterContentBaseline.v1.gz`（85,546 字节；同目录还有 `.bak-orig`、`NpcContentBaseline.v1.br`） |
| 基线期望值 | `MonsterContentBaselineV1.cs`：`ExpectedEntryCount = 3191`、`ExpectedRevision = 968B5D9E…`、`ExpectedArtifactSha256 = FB5AB488…`、`Source = reviewed-capture-promotion-v1` |
| 当前发布修订 | `968B5D9EF97C62279EB1E84F7E6CD45AEC403EFD14CBF106652BEB8BB538A305`，`entry_count = 3191`，`source = reviewed-capture-promotion-v1` |
| 库里存了几个修订 | **5 个**（`monster_content_revisions`），生效的只有 `monster_content_publication.family='monsters'` 指向的那一个 |
| 刷新点总数 | 当前修订 **3191** 条（表里含历史修订共 11,591 行） |
| 分地图刷新点 | map0=270、map1=351、map2=904、map3=263、map9=308、map11=452、map15=273、map18=185、map19=185 |
| 表结构 | `monster_spawn_definitions(revision, map_id, scene_key, template_key, display_name, object_id, pos_x, pos_z, clear_bytes)` |
| 不可变约束 | `trg_monster_spawn_definitions_immutable`（拒 UPDATE/DELETE）、`trg_monster_spawn_definitions_bounded_insert` |
| 包体长度约束 | `ck_monster_spawn_definitions_clear_bytes`：`octet_length BETWEEN 108 AND 1200` |
| 怪物身份表 | `gameplay_monster_templates` 1246 条（`rank/is_boss/is_elite/is_pet/collision_range/attack_type`，**不可变触发器** `trg_gameplay_monsters_immutable`）；源表是 `monster_templates`（1246 条，无触发器，**运行时读不到它**） |
| 发布器语义 | `PostgresGameplayContentPublisher.cs` 类注释原文：*"Runtime readers never consult the source tables; later content changes must publish a new revision."* —— 已有发布时只做校验，**不会**因为源表被改而重新发布 |

### 1.2 刷新点包体布局（服务端已解析，且运行时会改写）

`CapturedMonsterSpawn.Validate` + `PacketBuilder.Monsters.cs` 共同确定：

| 偏移 | 含义 | 谁在写 |
|---|---|---|
| 0 | 包长（必须 = 实际长度） | 抓包 |
| 2 | 操作码 `10020` | 抓包 |
| 4 | 对象类型（低字节 `0x12` = 怪物；高位区分普通/精英/BOSS） | 抓包 |
| 8 | 对象 ID（必须与列的 `object_id` 一致） | 抓包 |
| 12 | `tier`（**就是怪物等级**，≠0） | 抓包 |
| 20 / 24 | 当前 HP / 最大 HP（≠0） | **运行时会改写** |
| 28 / 32 / 36 | x / y / z | x、z **运行时会改写** |
| 40 | 朝向 | **运行时会改写** |
| 44 起 | 模板 key（ASCII，NUL 结尾，必须与列的 `template_key` 一致） | 抓包 |
| 44 之后剩余 | 外观/模型等字节 | 未完全逆向，**必须沿用模板原样** |

`PacketBuilder.CapturedMonsterAppearance()` 只改写 20/24/28/36/40；`object_id`(8) 和 `tier`(12) 目前不写，但既然校验器已经在读它们，写入它们没有技术障碍。

### 1.3 已有的"手工造点"先例（这是方案可行的最强证据）

- `src\Godswar.Server\Game\MapInstance.Wonderland.Preparation.cs:47`
- `src\Godswar.Server\Game\WorldInstances\MedusaWorldInstanceEntryPreparation.cs:239`

两处都是代码里直接 `new CapturedMonsterSpawn(...)` 造出刷新点，说明"从零造一个能进图的怪"服务端已经会做。

### 1.4 怪物属性：三类来源

| 属性 | 现在的来源 | 是否已在库里 |
|---|---|---|
| 等级 | 包体 offset 12 的 `tier`（每个刷新点各自一份） | 在库（但每点一份，不是每种怪一份） |
| 当前/最大 HP | 包体 offset 20 / 24（**每个刷新点各自一份**） | 在库（同上） |
| 物攻 / 魔攻 / 物防 / 魔防 / 命中 / 闪避 / 暴击 | **代码公式** `MonsterCombatProfileCatalog.Resolve` | **不在库** |
| 暴击抗性 | 库表 `monster_combat_balance`（26 行） | **在库，已可改** |
| 攻击类型（物理/魔法/特殊） | 抓包恢复 + 模板 | 半在库（模板列 `attack_type`） |
| 精英/BOSS/碰撞半径/等级档 | `gameplay_monster_templates` | 在库（不可变） |
| 掉落 | `monster_loot_rules` | **在库，GM 工具已支持** |
| 经验 | 代码常量表 `MonsterRewardCatalog.MonsterExperience`（按 tier 索引）× 全局倍率 | 部分在库：`monster_reward_settings` 只有 1 行（全局经验倍率、最大等级差） |

**属性公式（`MonsterCombatProfileCatalog.Resolve`，原文参数）**：

```
level            = clamp(tier, 1, 10000)
rankScale        = BOSS 13000 / 精英 11500 / 普通 10000   （万分比）
physicalAttack   = Scale(21 + 3L + L/3,        rankScale)
magicAttack      = Scale(23 + 3L + L/2,        rankScale)
physicalDefense  = Scale(10 + 6L + L²/10,      rankScale)
magicDefense     = Scale(10 + 5L + L²/12,      rankScale)
hit              = Scale(100 + 20L,            rankScale)
dodge            = Scale(50 + 12L,             rankScale)
critical         = Scale(25 + 8L,              rankScale)
criticalResist   = Scale(25 + 10L,             rankScale)
被动怪（MonsterAggroPolicy.IsPassiveTemplate）→ 攻击强制为 1
```

**已经存在的"覆盖"三级优先链（同一个方法里）**：

```csharp
var profile = AuthoredOverrides.TryGetValue((mapId, objectId, templateKey), out var authored)
    ? authored                                   // ① 代码里写死的逐点覆盖
    : Resolve(monster.Tier, template, ...);      // ② 公式生成

if (DatabaseCriticalResistances.TryGetValue((mapId, templateKey), out var resistance))
    profile = profile with { CriticalResistance = resistance };   // ③ 库表覆盖公式结果
```

第③步就是"运行时覆盖"的现成范例，注释写明意图：*"Database tuning takes precedence over generated and per-run profiles."*

### 1.5 重生节奏

| 类型 | 决定方 | 当前值 |
|---|---|---|
| 普通怪 | 代码 `MonsterMapRuntime.DefaultRespawnDelay` | **10 秒**（尸体 5 秒消失 `DefaultCorpseDespawnDelay`） |
| 世界 BOSS | 库表 `gameplay_world_boss_definitions.respawn_interval_seconds` | **19 个 BOSS，全部 43200 秒（12 小时）**；另有 1 个待定区域 |
| 温泉关精英鸟 `B_eliteB_stymphalianbird_001` | 代码 `MonsterRespawnPolicyRules.AuthoredRespawnIntervals` | **1 小时** |
| 亚特兰蒂斯波次 / 美杜莎 / 仙境 / 副本 | 代码（`RespawnPolicy.Never`，事件驱动） | 不进刷新表 |

普通怪那个延迟**没有任何配置入口**：`MonsterMapRuntime` 的 `respawnDelay` 参数无调用方传值，`MonsterRuntimeOptions` 里只有运行时模式（默认 `Ecs`）。

---

## 2. "运行时覆盖"到底是什么意思

**定义**：权威内容（不可变发布表、抓包基线、编译期公式）**一字不动**；另外新增一张 GM 可写的小表，服务端**启动时**把它读进内存形成"覆盖字典"，运行时在取值那一刻按优先级把覆盖值盖在基线值上。

落到本主题要表达三种语义：

| 语义 | 怎么表达 | 为什么需要 |
|---|---|---|
| **改字段** | `(地图 + 场景 + 模板)` 或 `(地图 + 对象ID)` 匹配基线里的点 → 覆盖 x/z、等级、HP、重生秒数、五维属性 | 不可变表改不了单行 |
| **加点** | GM 表里标 `source='gm'` 的行 → 启动时**追加**到该地图点列表（object id 由现有分配器给） | 不能往不可变表 INSERT（有 `bounded_insert` 与修订计数校验） |
| **屏蔽点** | 一行 `enabled=false` → 启动时把基线里那个点过滤掉 | 不可变表删不掉，这是唯一"删点"手段 |

### 2.1 与"生成新修订"（方案 A）的对比

| | A. 生成新修订 | **B. 运行时覆盖（推荐）** |
|---|---|---|
| 动什么 | 重写权威内容：新的 3191 条刷新点 + 移动 `monster_content_publication` 指针 | 权威内容不动，另加一张几十~几百行的 GM 表 |
| 卡点 | 不可变触发器；修订哈希被 `ExpectedRevision` / golden 校验多处 pin，一动要连带改 | 不碰触发器、不碰修订哈希 |
| 生效 | 重启后读新修订 | 重启后读覆盖表（现有 GM 表都是启动快照，**不是热更新**） |
| 回滚 | 基本不可逆，只能再发一个修订 | **删掉那行就回到基线值** |
| 审计 | 无（修订只是个哈希） | 表上带 `updated_at / updated_by` |
| 代价 | 改动大、风险高 | 权威内容与最终生效值不再一眼一致 → 必须配日志/工具提示/校验 |

### 2.2 参考的同款先例（照抄即可）

| 领域 | GM 表 | 启动安装点 | 运行时使用 |
|---|---|---|---|
| 掉落 | `monster_loot_rules` / `monster_loot_tables` | `ServerRuntimeContentComposition.Startup.cs:60` `MonsterLootContentCatalog.Install(...)` | 拾取时查快照 |
| 任务奖励 | `quest_reward_slots` / `quest_reward_values` | 同文件 `:61` `QuestRewardContentCatalog.Install(...)` | 发奖/发菜单时查快照 |
| 怪物暴抗 | `monster_combat_balance` | 进 `MonsterCombatProfileCatalog.Create()` 的 `DatabaseCriticalResistances` | `Resolve()` 里 `profile with { ... }` |

（`ServerRuntimeBootstrapContext.cs:90-93` 有一份同样的安装调用，改的时候两处都要照顾到。）

---

## 3. 拟改动的清单（尚未开始）

### 3.1 服务端

1. 新增迁移 `2026xxxx_2xx_monster_overrides`（**两条新表**，或一张表两种行）：
   - `monster_spawn_overrides`：`map_id`、`scene_key`、`match_object_id`（可空）、`match_template_key`（可空）、`enabled`、`pos_x`、`pos_z`、`facing`、`level`、`current_health`、`maximum_health`、`respawn_seconds`、`source`（`override` / `gm`）、`updated_at`、`updated_by`
   - `monster_attribute_overrides`：`map_id`、`template_key`、`level`、`physical_attack`、`magic_attack`、`physical_defense`、`magic_defense`、`hit`、`dodge`、`critical`、`critical_resistance`、`attack_kind`、`collision_range`、`updated_at`、`updated_by`
   - **所有可空列 `NULL` = 不覆盖**（沿用掉落/任务奖励的语义）
2. 读取器 `PostgresMonsterOverrideSnapshotReader`（`IsolationLevel.RepeatableRead`），快照类型 `MonsterOverrideSnapshot`（放在 `Application/World/Content/`），静态目录 `MonsterOverrideCatalog.Install/Current`。
3. 启动安装：`ServerRuntimeContentComposition.Startup.cs` 与 `ServerRuntimeBootstrapContext.cs` 各加一行（与 `MonsterLootContentCatalog.Install` 并列），并**打印生效条数**日志。
4. 运行时叠加点：
   - **属性**：`MonsterCombatProfileCatalog.Resolve(CapturedMonsterSpawn)` —— 在现有第③步之后再叠一层（或把它扩成完整的字段覆盖）。
   - **刷点**：`PostgresWorldContentReaderLoader.LoadPublishedMonsterSpawnsAsync` 读完后、`CapturedMonsterSpawn.Validate` 之前/之后，做 `过滤(enabled=false) → 改字段 → 追加(gm 点)`；追加点需要生成包体（以模板包体为底，写 8/12/20/24/28/36/40）。
   - 或更晚一层：`GameClientHandler.LoginWorldEntry.cs:465` 取 `mapContent.Monsters` 之后、`GameSessionRegistry.WorldRouting.cs:371` `map.InitializeMonsters(...)` 之前做叠加——**这里最容易做，也最容易回滚**。
5. object id 分配：复用现有分配器与 `EnsureMonsterObjectIdsDoNotCollideWithNpcs`，GM 新增点必须拿一个该地图未占用的 id。

### 3.2 迁移登记的硬性要求（踩过坑，必读）

- 新迁移必须**登记进 `PostgresSchemaMigrationCatalog.All`**（`src\Godswar.Server\State\DatabaseMigrations\PostgresSchemaMigrationCatalog.cs`）。**忘了登记 = 迁移永远不会执行**，而读取器去 select 新列 → 服务端 `42703` 崩溃循环。2026-09-27 刚踩过一次（`20260927_214_reward_item_attributes`）。
- 迁移 id 必须**严格升序**排在所有已应用 id 之后（当前最后是 `20260927_214_reward_item_attributes`）。
- 同步更新：`tests\Godswar.Server.ProtocolChecks\PostgresMigrationFoundationChecks.Catalog.cs` 的计数（现 **175**）与 `PostgresMigrationFoundationChecks.ExpectedIds.cs` 的 id 列表。
- 部署后用 `SELECT migration_id, checksum FROM schema_migrations ORDER BY migration_id DESC LIMIT 3;` 确认落地。

### 3.3 GM 工具（`tools\Godswar.LootTool`）

- 新增"刷怪"页签：按地图列出刷新点（模板名 / 坐标 / 等级 / HP / 重生秒数 / 来源），可按地图、模板、显示名筛；支持改字段、加自定义点（`source='gm'`）、禁用基线点。
- 新增"怪物属性"页签：按 `地图 + 模板` 列出，覆写等级 / HP / 五维 / 攻击类型 / 碰撞半径；未勾选的列写 `NULL`（= 不覆盖）。
- 两个页签都要**显式标注"这是覆盖，未填 = 沿用抓包/公式"**，并复用现有 Store 的"缺列时降级/隐藏"做法。
- 自测：仿照现有 `--selftest` 的写—读回环 + 缺列拦截。

### 3.4 检查（协议/自测）

- 迁移契约检查（表/约束/触发器存在）。
- 快照读取检查（NULL = 不覆盖；`enabled=false` 过滤；`source='gm'` 追加）。
- 覆盖优先级检查（属性覆盖 > `monster_combat_balance` > 公式；刷点覆盖 > 基线）。
- 一次真库（disposable）集成检查：写一行覆盖 → 读出叠加后的 profile/刷新点 → 清理。

---

## 4. 待办事项（TODO）

> 勾选框是给后续接手人用的，**目前全部未开始**。
> 优先级：P0 = 阻塞项/必须先做；P1 = 主体功能；P2 = 打磨；P3 = 可选。

### P0 —— 开工前必须先定的事

- [ ] **定范围**：只做「怪物属性覆盖」，还是「属性 + 刷点」一起做（刷点工作量与风险明显更大）。
- [ ] **定匹配粒度**：属性按 `地图 + 模板`（一种怪一条）还是允许 `地图 + 对象ID`（逐个刷新点）？刷点改动按 `对象ID` 还是按 `地图 + 模板` 批量？
- [ ] **定 HP 语义**：HP 现在是"每个刷新点一份"（包体自带），而用户想配的可能是"每种怪一份"。需要决定：按模板批量套用一个 HP，还是保持逐点（逐点则 GM 表要能按模板批量展开）。
- [ ] **定重生秒数是否纳入**（普通怪现在是全局 10 秒，无配置入口；纳入就等于顺手做掉一个长期缺口）。

### P1 —— 主体功能

- [ ] 迁移：新建 `monster_spawn_overrides` + `monster_attribute_overrides`（含 `updated_at/updated_by`、必要 CHECK、注释），**并登记进 `PostgresSchemaMigrationCatalog.All`**。
  - 验收：`schema_migrations` 里出现新 id；`\d monster_attribute_overrides` 正确；服务端重启后 `Up (healthy)`。
- [ ] 更新迁移计数与 id 列表（`PostgresMigrationFoundationChecks.Catalog.cs` 175 → 176、`ExpectedIds.cs` 追加）。
  - 验收：`dotnet run --project tests\Godswar.Server.ProtocolChecks -c Debug -- "PostgreSQL migration safety foundation"` 通过。
- [ ] 快照读取器 + 目录（`PostgresMonsterOverrideSnapshotReader`、`MonsterOverrideSnapshot`、`MonsterOverrideCatalog`）。
- [ ] 启动安装（两处 `Install` 调用点）+ **生效条数日志**。
- [ ] 属性叠加：接进 `MonsterCombatProfileCatalog.Resolve`，优先级 = GM 覆盖 > `monster_combat_balance` > 公式（要明确并写进注释与检查）。
- [ ] 刷点叠加：过滤（`enabled=false`）→ 改字段 → 追加（`source='gm'`，含包体生成与 object id 分配）。
- [ ] 包体生成工具方法：以模板包体为底写 `8/12/20/24/28/36/40`，并复用 `CapturedMonsterSpawn.Validate` 自检（长度自校验、模板 key、坐标一致性都要过）。
- [ ] GM 工具两个页签 + 存取 + 筛选 + 校验（模板必须存在于已发布内容、坐标在图内、object id 不撞 NPC/其他怪）。

### P2 —— 验证与打磨

- [ ] 协议检查：迁移契约、快照语义（NULL=不覆盖）、覆盖优先级、`enabled=false` 过滤、`gm` 点追加。
- [ ] disposable 库集成检查（沿用现有 `godswar_b09_*` 命名与 `GODSWAR_TEST_POSTGRES_CONNECTION_STRING`）。
- [ ] 全量回归：`dotnet run --project tests\Godswar.Server.ProtocolChecks -c Debug -- --results-json <path>`，确认失败数**不超过既有的 20 条**。
- [ ] 游戏内验收：进图能看见 GM 新加的点 → 能打 → 打死按配置重生 → 覆盖后的属性生效（伤害/血量对得上）→ object id 与 NPC/其他怪不冲突。
- [ ] 文档：把最终实现补进本文件（或另起一篇 `docs\handover-<日期>-monster-overrides.md`）。`docs\` 下没有总索引文件，无需登记到别处。

### P3 —— 可选

- [ ] GM 工具的"导出/导入覆盖"（便于换服/备份）。
- [ ] 覆盖冲突检测（同一 `地图+模板` 多行、指向不存在模板、坐标越界）在工具里做前置提示。
- [ ] 把 `monster_reward_settings`（经验倍率）也纳入同一个 GM 页签。

---

## 5. 坑与注意事项（务必先读）

1. **未配置 ≠ 0**。属性相关列一律用 `NULL` 表示"不覆盖"。属性 id `0` 是合法的 `AttackA`（物理攻击力 I），写 `0` 会让每件装备/每只怪多出一条幽灵属性行 —— 2026-09-27 刚修过这个 bug（`ItemGrantAttributes` 改可空、写入真发 `NULL`）。
2. **迁移必须登记进 `All`**（见 3.2），否则新列不存在而读取器去 select → `42703` 崩溃循环。
3. **运行时读的是发布修订，不是源表**。改 `monster_templates` 不会生效（`PostgresGameplayContentPublisher` 只在没有发布时从源表提升一次）。
4. **不可变触发器**：`monster_spawn_definitions`、`gameplay_monster_templates` 都拒 UPDATE/DELETE；"删点"只能用 `enabled=false` 过滤。
5. **包体 44 字节之后未完全逆向**，新增点必须以某个已抓到的同类模板为底改字段，不能凭空造外观。
6. **修订哈希被 pin**：`MonsterContentBaselineV1.ExpectedRevision`、`ExpectedArtifactSha256`，以及一批 golden 校验；方案 B 的整个意义就是绕开它们。
7. 容器重建后**服务端需要重新安装快照**（覆盖表是启动读取），改完记得重启并看日志里的生效条数。
8. 现有 GM 表都在 `ServerRuntimeContentComposition.Startup.cs` **和** `ServerRuntimeBootstrapContext.cs` 两处安装，别只改一处。

---

## 6. 验证/复现命令速查

```powershell
# 当前发布修订与刷新点数量
docker exec godswar-postgres psql -U godswar -d godswar_local -c "
SELECT publication.family, publication.revision, release.entry_count, release.source,
       (SELECT count(*) FROM monster_spawn_definitions d WHERE d.revision = publication.revision) AS spawn_rows
FROM monster_content_publication publication
JOIN monster_content_revisions release ON release.revision = publication.revision;"

# 分地图刷新点
docker exec godswar-postgres psql -U godswar -d godswar_local -c "
SELECT map_id, count(*) AS spawns, count(DISTINCT template_key) AS templates
FROM monster_spawn_definitions
WHERE revision = (SELECT revision FROM monster_content_publication WHERE family='monsters')
GROUP BY map_id ORDER BY map_id;"

# 不可变触发器 / 包体长度约束
docker exec godswar-postgres psql -U godswar -d godswar_local -tAc "
SELECT tgname FROM pg_trigger WHERE tgrelid='monster_spawn_definitions'::regclass AND NOT tgisinternal ORDER BY 1;"

# 世界 BOSS 重生间隔
docker exec godswar-postgres psql -U godswar -d godswar_local -c "
SELECT count(*) AS bosses, min(respawn_interval_seconds) AS min_s, max(respawn_interval_seconds) AS max_s
FROM gameplay_world_boss_definitions;"

# 协议检查（可带名字过滤）
dotnet run --project tests\Godswar.Server.ProtocolChecks -c Debug -- "PostgreSQL migration safety foundation"

# 部署（改完服务端）
docker compose --profile legacy-raw up -d --build server
docker ps --filter name=godswar-server --format '{{.Status}}'
```

---

## 7. 明确"不做"的事

- 不改 `MonsterContentBaseline.v1.gz` 及其 `.bak-orig`。
- 不改 `monster_spawn_definitions` / `gameplay_monster_templates` 这两张不可变表的数据。
- 不重算/替换既有发布修订（方案 B 的全部意义在于避开修订哈希）。
- 不动抓包里尚未逆向的包体字节。

---

## 8. 相关文件索引

| 主题 | 文件 |
|---|---|
| 刷新点读取 | `src\Godswar.Server\Infrastructure\WorldContent\PostgresWorldContentReaderLoader.Monsters.cs` |
| 基线定义/编解码 | `src\Godswar.Server\Infrastructure\WorldContent\MonsterContentBaselineV1.cs`、`MonsterContentBaselineCodec.cs` |
| 基线发布 | `src\Godswar.Server\Infrastructure\WorldContent\PostgresMonsterContentBaselinePublisher.cs` |
| 刷点领域模型（含包体布局与校验） | `src\Godswar.Server\Domain\World\Content\CapturedMonsterSpawn.cs` |
| 外观包改写 | `src\Godswar.Server\Packets\PacketBuilder.Monsters.cs` |
| 怪物战斗属性（公式 + 现有覆盖链） | `src\Godswar.Server\Game\MonsterCombatProfileCatalog.cs`（`Resolve` 三级优先链）、`MonsterCombatProfileCatalog.Overrides.cs`（`AuthoredOverrides` 逐点覆盖 + `DatabaseCriticalResistances` 库覆盖 + `WithAuthoredOverrides`） |
| 重生策略 | `src\Godswar.Server\Game\MonsterRespawnPolicy.cs`、`MonsterMapRuntime.cs`、`Game\WorldBossCatalog.cs` |
| 进图刷怪 | `src\Godswar.Server\Game\GameClientHandler.LoginWorldEntry.cs`、`GameSessionRegistry.WorldRouting.cs`、`MapInstance.MonsterInitialization.cs` |
| 手工造点先例 | `src\Godswar.Server\Game\MapInstance.Wonderland.Preparation.cs`、`Game\WorldInstances\MedusaWorldInstanceEntryPreparation.cs` |
| GM 覆盖安装点 | `src\Godswar.Server\ServerRuntimeContentComposition.Startup.cs`、`ServerRuntimeBootstrapContext.cs` |
| 迁移目录（必须登记） | `src\Godswar.Server\State\DatabaseMigrations\PostgresSchemaMigrationCatalog.cs` |
| 迁移契约检查 | `tests\Godswar.Server.ProtocolChecks\PostgresMigrationFoundationChecks.Catalog.cs`、`…ExpectedIds.cs` |
| GM 工具 | `tools\Godswar.LootTool\`（`QuestRewardPanel.cs`、`LootStore.cs`、`QuestRewardStore.cs`、`SelfTest.cs`、`README.md`） |
