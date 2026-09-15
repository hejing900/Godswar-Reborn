# 客户端物品目录补齐（client-catalog-v1）交接说明

日期：2026-09-12
范围：`D:\Godswar-Reborn-main`（服务端）。分析侧脚本与报告在 `D:\Godswar Origin`。

---

## 一、目标与结果

把客户端 `Localization/en_us/Settings/Sys/ItemBaseAttribute.xml` 里有、服务端却没有
物品行的物品全部补齐。

| 指标 | 改动前 | 改动后 |
| --- | ---: | ---: |
| 客户端物品（唯一 ID） | 3472 | 3472 |
| 服务端有物品行 | 1844 | **3472** |
| 缺失 | **1628** | **0** |

补齐的 1628 个全部是 `GenerateItemTemplates.ps1` 的装备白名单之外的类型：
`consume item / skillitem / create / pet`。

---

## 二、为什么必须走内容发布管线（关键背景）

运行时物品目录**不是**读可变表 `item_templates`，而是读不可变发布修订：

- `PostgresItemTemplateCatalogLoader.LoadAsync` 从
  `item_template_content_publication`（family=`items`）指向的
  `item_template_content_definitions` 读取，并校验 `manifest_version == 9`、条目数、
  以及 `ItemTemplateContentRevisionHasher.ComputeV6` 的哈希。
- `item_templates` 只是**可变兼容层**，其唯一硬约束是 `character_items.prop_id` 的
  外键 `fk_character_items_prop_id_item_templates`。

因此：**只写 `INSERT INTO item_templates` 不会让物品在游戏里生效**，必须作为一个
reviewed family 进入发布流程，并且由发布器把定义投影回 `item_templates` 满足外键。

发布器在已有 v9 发布且所有完整性检查通过时走**快速路径**直接返回旧修订，
所以新增 family 必须同时挂上自己的完整性检查，否则改动不会被重新发布。

---

## 三、改动清单

### 3.1 新增文件

| 文件 | 说明 |
| --- | --- |
| `tools/GenerateClientCatalogItemSeeds.ps1` | 生成器：读客户端 XML + EquipName.dat，输出种子与 SQL |
| `tools/client-catalog-items/phase1-referenced.txt` | 202 条：服务端代码/迁移已引用却缺物品行 |
| `tools/client-catalog-items/phase2-lifing.txt` | 498 条：生活技能产业链 `Lifing*` |
| `tools/client-catalog-items/phase3-pet.txt` | 282 条：宠物消耗品/蛋/技能道具 `Pet*` |
| `tools/client-catalog-items/phase4-quest.txt` | 159 条：任务道具 `Quest*` |
| `tools/client-catalog-items/phase5-rest.txt` | 487 条：其余（促销、符石、传送、活动、材料） |
| `src/Godswar.Server/State/ClientCatalogItemSeed.Generated.cs` | 生成的种子（1628 条，684 KB） |
| `database/postgres/076_client_catalog_item_templates.sql` | 生成的 SQL 镜像（1628 条，641 KB） |
| `src/Godswar.Server/Infrastructure/Items/ClientCatalogItemContentBaseline.cs` | 内容基线（暴露 `ItemTemplates` / `ShippedItemCount`） |
| `src/Godswar.Server/Infrastructure/Items/PostgresItemTemplateBaselinePublisher.ClientCatalog.cs` | 发布族实现 |

### 3.2 修改文件

| 文件 | 改动 |
| --- | --- |
| `Infrastructure/Items/PostgresItemTemplateBaselinePublisher.cs` | `PublicationSource` 追加 `+client-catalog-v1`；新增 `PublishedClientCatalogItemsAreCompleteAsync` 完整性判定并纳入快速路径条件；快速路径与发布路径各加一次 `EnsureClientCatalogMutableTemplateCompatibilityAsync` |
| `Infrastructure/Items/PostgresItemTemplateBaselinePublisher.Elemental.V9Upgrade.cs` | `PrepareV9PublicationAsync` 增加 `ReconcileReviewedClientCatalogItemsAsync`；`ValidateSupportedPetItemsV9Predecessor` 改为接受"自身历史血统前缀" |
| `tests/.../PostgresItemTemplateContentIntegrationChecks.PetItemsV3Upgrade.cs` | 历史排除集加入整个 client-catalog 族；条目数改为 `1773 + ShippedItemCount`；新增并钉住 `ClientCatalogV1Revision` |
| `tests/.../PostgresItemTemplateContentIntegrationChecks.PetItemsV9Upgrade.cs` | 同上（排除集与条目数公式） |
| `tests/.../PostgresFactionCrierFoundationIntegrationChecks.cs` | 两个血统条目数改为按 `ShippedItemCount` 推导；去掉内容派生修订哈希的等值断言；来源后缀断言更新 |
| `tests/.../PetItemsV3UpgradePolicyChecks.cs` | `PublicationSource` 期望值追加 `+client-catalog-v1` |
| `tests/.../PostgresLegacyInstanceOpalPaymentIntegrationChecks.cs` | 来源断言由 `EndsWith("+opal-v1")` 改为 `Contains("+opal-v1")`（后续族会继续追加后缀） |

### 3.3 新增物品的统一口径

沿用仓库既有约定（对齐 `PetItemContentBaseline`）：

- `kind = 'consume item'`（`skillitem / create / pet` 也统一映射为它，
  客户端原始 `Type` 原样保留在 `stats.Type` 里）
- `equipment_slot = 0`，`class_ids = []`，`min_level / max_level / hand / skill_flag = NULL`
- `texture / icon` 取自客户端 XML
- `stats` = 客户端该节点的**全部属性**原样 JSON（含 `Use`、`Skill`、`BindType`、
  `Overlap`、`Money`、`PlayLv` 等），与服务端既有 `consume item` 处理保持一致

---

## 四、验证（已执行）

环境：docker `godswar-postgres`（postgres:17-alpine）。**始终用一次性克隆库**
（`pg_dump` 到临时库），开发库 `godswar` 全程未被改动（仍 `97A236AF…` / 1849 条），
临时库已删除。

| 项目 | 结果 |
| --- | --- |
| `dotnet build src/Godswar.Server/Godswar.Server.csproj -c Release` | 0 警告 0 错误 |
| 发布（升级路径，含开发库 76 条本地物品） | `329F51B1…`，**3477** = 1849 + 1628 |
| 发布（干净前驱 fixture 路径） | `A60B3E60…`，**3401** = 1773 + 1628 |
| 可变表投影 | `item_templates` 同步 3477 行 |
| `PostgreSQL item-template publication`（V9/V3 子项） | PASS |
| `Exact pets-v3 through capture-tool publication lineage` | PASS |
| `Immutable Socket Spell content and developer grants` | PASS |
| 全量协议检查套件 | 442 passed / 11 failed / 99 skipped —— **与改动前基线一致，零新增失败** |
| 覆盖率复核 | 客户端 3472 → 服务端 3472，**缺 0** |

复现：

```powershell
# 只读对比（分析侧）
pwsh -NoProfile -File "D:\Godswar Origin\compare_items.ps1"

# 重新生成种子与 SQL
pwsh -NoProfile -File "D:\Godswar-Reborn-main\tools\GenerateClientCatalogItemSeeds.ps1" `
  -ItemIdsFile "D:\Godswar-Reborn-main\tools\client-catalog-items\phase1-referenced.txt,D:\Godswar-Reborn-main\tools\client-catalog-items\phase2-lifing.txt,D:\Godswar-Reborn-main\tools\client-catalog-items\phase3-pet.txt,D:\Godswar-Reborn-main\tools\client-catalog-items\phase4-quest.txt,D:\Godswar-Reborn-main\tools\client-catalog-items\phase5-rest.txt"

# 构建
dotnet build "D:\Godswar-Reborn-main\src\Godswar.Server\Godswar.Server.csproj" -c Release
```

---

## 五、维护约定（以后继续加物品时）

1. 往 `tools/client-catalog-items/` 增删清单文件，重跑生成器（多文件用逗号分隔）。
   **必须把新增文件路径加进生成器调用**，否则不会进种子。
2. 新增物品会改变内容派生修订哈希，需要重新钉这些常量：
   - `PostgresItemTemplateContentIntegrationChecks.PetItemsV3Upgrade.cs` 的
     `ClientCatalogV1Revision`（两个 fixture 收敛到同一目标修订，实测可得）
   - 条目数已改成 `基准 + ShippedItemCount` 公式，**不需要**手工改数字
3. 生成器已把历史排除集做成"整个族"，所以历史 fixture 的前驱重建会自动保持精确。
4. **不要手改** `ClientCatalogItemSeed.Generated.cs` / `076_*.sql`，它们由生成器覆盖。

---

## 六、风险与注意事项

1. **物品存在 ≠ 物品有效果。** 本次只保证 1628 个物品能作为物品存在（可发放、可入包、
   有名称/图标/类型/完整客户端属性）。玩法效果需要另行实现：
   - `Lifing*` 498 条：服务端**没有生活技能系统**，目前只是可堆叠材料
   - 传送卷/配方 ~39 条：需要接地图传送目标
   - 礼包/宝箱 ~70 条：需要开箱产出表
   - 任务道具 `Quest*` 159 条：只有对应任务链存在才有意义
   - 符石 `9100-9199` 28 条：需要学会对应技能
   - 宠物蛋：`PetSpeciesCatalog` 已有物种表，孵化链路仍不完整
   抽查确认 `Use`/`Skill`/`BindType` 已随 `stats` 带过去，通用消耗路径能识别。
2. **未部署。** 运行中的 `godswar-server` 容器仍是旧镜像，本次改动只在源码树里。
   生效需要重建镜像并重启。
3. **未做游戏内实测**（发放 → 入包 → 使用 → 观察效果）。
4. **全新空库路径未验证**：被下述既有缺陷挡住。
5. **118 个"假缺失"的方法论教训**：宠物蛋 `10150+`、宠物技能书 `10464+/10510+`、
   魔玉 `11050-11093` 这些物品 ID 在源码里是**区间计算生成**的，字面量扫描扫不到。
   纯静态对比会误报为缺失。本次用线上已发布目录（`item-compare/live-published-ids.txt`）
   做了校正。**以后做同类静态对比，务必用一次真实发布目录做基准。**

---

## 七、既有问题（非本次引入，未处理）

1. **`database/postgres/005_item_attributes.sql` 的 SHA-256 不符**
   - 实际：`E2405A6AF3CA4B927C02B7DF8E910858585D98014C83EA44CE0244E55ABA0C7B`
   - 代码中钉的（`PostgresRelationalContentBaselineBootstrapper.Resources.cs`）：
     `2CE8B2539589D3666599C87B50106CE6D52C1C0576EDA227D9551045197E3EE0`
   - 后果：`LoadReviewedSql` 抛 `InvalidDataException`，**全新空库首次发布直接失败**，
     也挡住了 `PostgreSQL item-template publication` 的 V1/全新建库子项。
   - 修它等于给未知内容的改动背书，需先确认该文件是谁改的。
2. **11 个既有失败检查**（与本次改动无关，改动前后数量一致）：
   - `Pinned PostgreSQL item-template content boundary`、
     `Process-pinned runtime content source isolation`
     —— 均指向未改动的 `Infrastructure/Inventory/PostgresCapitalShopPurchaseStore.CapitalShopSale.cs`
     （第 254 行读可变 `item_templates`，违反架构棘轮）
   - `Data-boundary architecture ratchet`、`B20A legacy persistence retirement ratchet`、
     `Durable player ownership architecture ratchet`、`Durable character lifecycle handler and replay`、
     `Character camp starting location`、`Instance Caller expiring destination page context`、
     `Atomic Atlantis and Wonderland daily entry claims`、`Medusa Island variants…`、
     `Medusa explicit world-instance ownership boundary`

---

## 八、回滚

删除 3.1 的全部新增文件，撤销 3.2 的七处修改即可回到改动前状态
（没有任何数据库侧迁移需要回滚：`076_*.sql` 只是生成镜像，
运行时的 `item_templates` 行由发布器投影，回滚后发布器不再追加该族）。

注意：一旦某个库已经发布过带 `+client-catalog-v1` 的修订，回滚代码后该库的
`item_template_content_publication` 仍指向那个修订。此时发布器的
`ValidateSupportedPetItemsV9Predecessor` 会拒绝它（旧代码不认这个来源标签）。
需要把发布指针改回旧修订，或同时保留"接受自身历史血统前缀"那处修改。
