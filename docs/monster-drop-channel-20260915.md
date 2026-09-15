# 掉落通道（普通怪 → 掉落 → 拾取入包）

状态：**已实现、已过测试，尚未部署**（2026-09-15）。
参考服证据：`captures/monster-drop-20260915.txt`（杀怪 + 拾取窗口 166 帧）。

## 1. 参考服的完整链路

```
怪物死亡
  S2C 10023            怪物消失标记
  S2C 10031 (13)       经验
  S2C 10027 (116)      击杀奖励（天赋/经验）
  S2C 10029 (12+72n)   地面掉落列表        ← 掉落的唯一来源
玩家走过去拾取
  C2S 10056 (40)       地面物品描述符
  S2C 10056 (40)       同一描述符，+32/+36 被服务端填成匹配到的地面物品键
```

### S2C 10029（掉落列表）

| 偏移 | 内容 |
| --- | --- |
| +4 | 怪物对象 ID |
| +8 | 条数 |
| 记录 +0 | 物品 ID |
| 记录 +4 | 每次掉落各不相同（实测 -1 / 0 / 4 / 344，含义未定） |
| 记录 +8..+20 | -1 ×4 |
| 记录 +24 | `数量 << 24 | 0x0101` |
| 记录 +28..+60 | 0 |
| 记录 +64 / +68 | 地面物品唯一键（高位按掉落、低位按本次击杀） |

### C2S 10056（拾取，40 字节）

| 帧偏移 | 内容 |
| --- | --- |
| +4 | 客户端指针 |
| +8 | 常量 1 |
| +12 | 目标背包页 |
| +16 | 页内序号 |
| +20 | 物品 ID |
| +24 | 客户端指针 |
| +32 / +36 | 地面物品键（客户端这里填的是垃圾值，服务端应答时才填真值） |

**注意**：客户端**不**回传地面物品键，所以服务端只能靠"物品 ID + 就近尸体"认领；
整库 149k+ 帧里 `C2S 10048`（原 `PickupDrops`）出现 **0 次**，`C2S 10056` 出现 2284 次。

## 2. 我们的实现（与梅杜莎掉落完全同构）

掉落表**和其他内容一样是数据库拥有的**，形状照抄 `medusa_monster_rules` +
`medusa_monster_loot_rules`：

| 位置 | 作用 |
| --- | --- |
| `State/DatabaseMigrations/PostgresSchemaMigrationCatalog.MonsterLootPolicy.cs`（新，`20260915_147_monster_loot_policy`） | 建 `monster_loot_tables`（表头：`template_key`、`maximum_drops`、`enabled`）+ `monster_loot_rules`（掉落行：`loot_index`/`item_id`/`chance_basis_points`/`minimum_quantity`/`maximum_quantity`/`enabled`，外键指向表头 `ON DELETE CASCADE`，`item_id` 外键指向 `item_templates`），并种下抓包验证过的 3 只怪 |
| `Application/World/Content/MonsterLootContentSnapshot.cs`（新） | `MonsterLootContentSnapshot`（校验 + 按模板 key 索引 + `RollLoot` 确定性掉落）；`MonsterLootContentCatalog.Install/Current` 与 `MedusaMonsterContentCatalog` 同款 |
| `Infrastructure/WorldContent/PostgresMonsterLootContentSnapshotReader.cs`（新） | repeatable-read 快照读取（只读 `enabled`），对应 `PostgresMedusaMonsterContentSnapshotReader` |
| `ServerRuntimeContentComposition.Startup.cs` / `ServerRuntimeBootstrapContext.cs` | 启动时读快照并 `Install`，与梅杜莎内容同一处 |
| `Game/GameSessionRegistry.MonsterLoot.cs` | `PrepareMonsterLoot`（普通怪，走 `MonsterLootContentCatalog.Current`）+ `TryReserveGroundLootPickup`（按物品 ID / 地面键认领，校验尸体 12 码内） |
| `Game/MonsterLootGroundKey.cs`（新） | 地面物品键（协议身份，不是内容），10029 记录 +64/+68 与拾取应答共用 |
| `Game/GameClientHandler.Progression.cs` | 击杀结算后：先试梅杜莎规则，再回退普通掉落表；只发有内容的那一帧 |
| `Game/GameClientHandler.MonsterLoot.cs` | `TryHandleGroundLootPickupAsync`：入包 → 回 40 字节描述符（+32/+36 填地面键）→ 背包刷新 |
| `Game/GameClientHandler.PacketDecoding.cs` | `TryReadGroundLootPickup`：把抓到的 10056 描述符解析成 {目标格, 物品, 地面键} |
| `tests/.../MonsterLootContentTestFixture.cs`（新） | `[ModuleInitializer]` 安装测试用快照，与 `MedusaRewardPolicyTestFixture` 同款 |
| `tests/.../MonsterLootChannelChecks.cs`（新） | migration 建表与种子、表内容、确定性、数量上限、地面键、两帧真实抓包描述符 |

拾取入包复用原有的持久化路径（`PickupMonsterLootAsync`：写 `monster_loot_pickup_claims`、
推进 `inventory_revision`、落 `command_audit`），所以掉落入包是**防重放**的。

## 3. 当前已配的掉落内容（全部来自抓包，写在 migration 里）

| 怪物模板 | `maximum_drops` | 掉落（`loot_index` → 物品） |
| --- | --- | --- |
| `A_normal_stub_001` | 1 | 0 → 4529 弱效宠物经验药水 |
| `A_normal_stub_002` | 2 | 0 → 12030 草药、1 → 4529 弱效宠物经验药水、2 → 4150 小金袋、3 → 4003 强效治疗药水、4 → 4224 4级祖母绿碎片、5 → 12040 原石 |
| `A_normal_deer_001` | 1 | 0 → 4001 中效治疗药水 |

> 概率统一是 **2500 bp（25%）的占位值**（单次击杀推不出真实概率）；数量固定 1；
> `A_normal_stub_002` 的上限 2 是照着抓包里"每次 1~2 件"设的。
> 概率一改就是一条 SQL（或以后那个编辑软件），**不用改代码、不用重新部署编译**。

## 4. 怎么加/改掉落

- **加怪**：`INSERT INTO monster_loot_tables(template_key, maximum_drops) VALUES (...)`，
  再插对应的 `monster_loot_rules` 行。
- **改概率/数量**：直接 `UPDATE monster_loot_rules SET chance_basis_points = ...`。
- 重启服务端（或以后接热加载）后生效；模板 key 就是 `monster_templates.template_key`
  （也是客户端 10020 帧里那串）。

## 5. 还没做

- 概率的真实数值，以及分档掉落表（普通/精英/世界BOSS/副本）。
- `记录 +4` 那个每掉落不同的字段含义未定，我们目前写 -1。
- 世界BOSS / 副本怪仍走各自原有路径（梅杜莎走 `medusa_monster_rules` + `medusa_monster_loot_rules`）。
