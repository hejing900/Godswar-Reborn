# 宠物打工 + 照护恢复道具 — 交接（未完成部分）

> 本轮已完成并**部署上线**的部分见文末「已完成」。
> 本文重点记录**唯一卡住的一项**：把 11 个全新照护道具发布进运行时物品目录。

最后更新：2026-09-24（本轮部署：`godswar-server Up (healthy)`）

---

## 1. 现象（实测，不是推断）

把 11 个全新道具加入权威基线 `PetItemContentBaseline.ReviewedItems` 后，服务器**启动失败并无限重启**：

```
startup_failure_frame  postgresitemtemplatebaselinepublisher.validatepetitemrows
server_lifecycle       outcome=startup_failed   （每 ~8 秒重试一次）
```

回退基线 → 服务器立即恢复正常。所以**触发点 100% 是这个基线改动**。

## 2. 已定位的机制

物品内容发布是**不可变 + 指针式**的：

| 表 | 作用 |
|---|---|
| `item_template_content_revisions` | 每个发布批次一行（`revision` = 内容 SHA256、`entry_count`、`manifest_version`） |
| `item_template_content_definitions` | 批次内的物品行（只读，有 immutable 触发器） |
| `item_template_content_publication` | 单行指针 `family='items'` → 指向上表中的 revision |

查询结果（部署后实测）：

```
revision                                                          entry_count  manifest  sealed
D4FEF729173DAC258ED74A1D7DEBAA9B3DB71C77EC462BAE2233777951B0A07D  3484        9         t   <-- 指针
CD568D5A621117E16A432BD28F0BAE5BEF798998D42BB3C4147DDBBA346F951D  3477        9         t
329F51B197D7B5115B5121B9D8DA41EF99A9E1352813FBDF9FD072DD4D8D4D3D  3477        9         t
```

运行时目录 `IItemTemplateCatalog`（`PostgresItemTemplateCatalogLoader`）**只读当前指针指向的那一批**：

```sql
FROM item_template_content_definitions WHERE revision = @revision   -- 见 Loader.cs:177
```

`PostgresItemTemplateBaselinePublisher.PublishAsync` 的逻辑（行号对应现状代码）：

1. 读指针（`TryReadPublishedRevisionAsync`，:301）
2. **若指针是 v9** → 先 `VerifyPublishedV9ReleaseAsync`，再逐个跑 `PublishedXxxAreCompleteAsync`；
   全 true 就走**复用分支**（:48–185），只做校验，**不产出新批次**：
   - `PublishedPetItemsAreCompleteAsync`（`PetItems.cs:48`）
   - `EnsurePetItemMutableTemplateCompatibilityAsync`（`PetItems.cs:116`）→ 内层 `ValidatePetItemRows`（:268）
3. 只有复用分支没走成，才 `PrepareV9PublicationAsync` + `InsertRevisionAsync` 产出新批次

**卡点就在这里**：期望集合 `PetItemCompatibilityItemIds` 直接来自 `PetItemContentBaseline.ItemTemplates`（`PetItems.cs:9`）。加了 11 件后，它和「谁有权写进不可变批次」的定义脱节——复用分支既不补写，新批次又不产出，于是 `ValidatePetItemRows` 报「124 件里有 N 件在已发布批次里不存在」并抛异常。

补一个实测细节：指针批次的 `revision` 是**内容哈希**，所以手工造一个假 revision 字符串必然被 `VerifyPublishedV9ReleaseAsync` 的重算校验拒绝；而 `item_template_content_publication` 行有 `trg_item_template_content_publication_no_delete` 触发器，**删不掉**，只能 UPDATE 且必须通过 `validate_item_template_content_publication()`。

## 3. 两条可行路线（都未实施）

### 路线 A（符合现有架构，推荐）：加一个 v10 清单版本

1. 在 `ItemTemplateContentRevisionHasher` 加 `ComputeV10`（内容 = 现 V6 + 宠物照护道具集合指纹），
   让「基线变了」必然推出新哈希；
2. 在 `PinnedItemTemplateCatalog` 增加 `manifestVersion: 10` 分支（`:389` 那个 switch）；
3. `PostgresItemTemplateBaselinePublisher` 增加 v9→v10 升级路径（照 `Elemental.V9Upgrade.cs` 的写法），
   把宠物道具一并写入新批次；
4. 数据库侧同步放开 `ck_item_content_manifest_version` 到 10（照 `ItemContentV9.cs` 的 `UpgradeItemManifestVersionListToV9` 写法加 `...ToV10`）；
5. 把 11 件道具加回 `PetItemContentBaseline`，同步更新 `PetItemContentChecks.ExpectedItems`（含按 ID 排序！）。

预计改动：4~5 个文件 + 1 条迁移。这是仓库里**每次发新物品内容都在走的同一条路**，风险最低。

### 路线 B（小、但是架构例外）：让照护道具绕开不可变目录

`PetCareItemPolicy.TryResolve` 现在从 `IItemTemplateCatalog` 读元数据。可改为从**可变表** `item_templates`
（本轮迁移 `20260924_152` 已经把 18 件全部写进去了，实测已存在）读，policy 内做同样的逐字段 fail-closed 校验。

- 优点：改动最小，立刻可用；
- 缺点：破了「运行时只信不可变发布」的仓库铁律，需要你明确点头。

## 3. 现状（已重新核对数据库，2026-09-24 二次部署后）

**运行时目录（`item_template_content_publication` 指向的 D4FEF729…）实测已包含 14 件照护道具：**

```
4060 4061 4062  10000 10001 10002  10020 10021 10022  10040 10041 10042  10060 10061
```

**未发布、因此服务端会安全地"当作不认识的物品"放过（不路由、不报错）的 4 件：**

```
10003（食草第四档 +100/+40）  10023（食肉第四档）  10043（料理第四档）  10090（仙宠泉水 +100 寿命）
```

### 已经修掉的真正原因（本轮）

用户反馈"几种物品的使用也无效"。根因**不是**发布机制，而是 **`10051` 兼容路由漏登记**：

`GameClientHandler.InventoryActivation.cs` 里，服务端对每个"背包消耗品家族"都要显式登记，
否则 raw-local 客户端右键使用时直接 `[equip-re] BreakItem ignored: ... is not genuine equipment` 丢弃。
对照 `持久极效宠物经验药水` 的做法（见 `docs/experience-boost-potions.md` §Change inventory），
本轮补上了：

- `var isPetCareItem = PetCareItemPolicy.IsReviewedItem(itemId);`
- 加进 `if (isPetEgg || … || isPetCareItem || …)` 判定
- 加进 `AllowLegacyPlayerMutationFallback` 的 operation 名字（`"pet_care_item"`）

同时 `PetCareItemPolicy` 新增 `TryResolvePublished`：**未发布的已核对道具返回 false 而不是抛异常**，
所以 10003/10023/10043/10090 目前是"安静地不支持"，不会崩、不会断线。

### 剩下要做的（可选，优先级低）

要把那 4 件也变成可用，只有路线 A（新增清单版本/新发布批次）。它们都是**同一套规则的更高档位**
（第四档食物与前三档同形；10090 是寿命 +100），所以缺它们不影响规则正确性，只影响这 4 个 ID 可用性。

## 4. 已完成（本轮，已部署验证）


| 项 | 状态 |
|---|---|
| `State/PetCareItemPolicy.cs` | 12 食（3 食性 × 4 档）+ 2 佳酿 + 仙宠泉水 + 3 精力水；含「喂错食性半饱、不加好感」与「精力按宠物自身上限 20/45/95%」 |
| `State/PetWorkPolicy.cs` | `Pet_Job.xml` **140 行全量转写**（银币/金币双通道，开支+经验+专长）、`CostBase=1,3,8,24`、`GainBase=1,3.5,10,32`、中止 20%、打工天赋位 |
| `Infrastructure/Pets/PostgresPetDurableCommandExecutor.CareItem.cs` | 喂食事务（锁出战宠物 → 加值夹上限 → 消耗道具 → 背包 CAS） |
| `...PostgresPetDurableCommandExecutor.Work.cs` | 打工事务：派出/查到期/结算（发经验 + 专长点写入 `character_base."SkillPoint"`） |
| `Game/GameClientHandler.PetWork.cs` | 打工时钟：登录即结算已到期宠物，之后每 20 秒巡检 |
| `Packets/PacketBuilder.PetWork.cs` | 10291（经验 u32@+4 / 专长 u16@+8 / 剩余 u16@+a / 开支 u16@+c / 货币 u8@+e）、10294（窗口状态） |
| 迁移 `..._152_pet_care_consumable_templates` | 18 件照护道具写入 `item_templates`（实测已在库） |
| 迁移 `..._153_pet_work_state` | `work_plan jsonb` / `work_started_at` / `work_settles_at` + 4 条一致性 CHECK |
| 协议检查 | `72 passed / 0 failed / 23 skipped` |

**未取证项**：打工 C2S 请求 opcode。服务端 `default:` 分支已把未识别包打日志
（`[game] unknown ... opcode=... len=... hex`），客户端登录后点一次「打工」即可从日志读出。
顺带记录：本轮部署后日志里已出现 `[game] unknown Unknown opcode=10243 len=8 0800032808000000`，待判读。
