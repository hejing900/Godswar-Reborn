# 雅典商人区（Merchant Quarter）移植记录

> 数据源：抓包代理 2026-09-24 的会话 `b1825b76-d48b-45a9-b3e9-bd8326cc3baa`
> （本地时间 22:29:59 – 23:36，63918 包）。**只采用这一次会话的数据。**

---

## 1. 关键协议发现：点 NPC → 开商店的真实流程

抓包实证（`npc 5166`，本地时间 23:31:17 – 23:31:18）：

```
C2S 10067 {npc 5166}                    ← 玩家点击 NPC
S2C 10067 {npc 5166, flags=0, fn=0, "Athens_026"}   ← 点击应答，功能号 0
C2S 10068 {npc 5166}  (8 字节，仅 NPC id)            ← 客户端请求打开商店
S2C 10071 × 5                                        ← 服务端直接推送货架
```

**要点**：这类商人**没有函数号、没有对话索引**（`10067` 应答的 packed 功能号为 `0`），
`S2C 10067` 的 payload 布局为：

| 偏移 | 含义 |
|---|---|
| `+0` | u16 帧长（48） |
| `+2` | u16 opcode = 10067 |
| `+4` | u32 运行时 NPC id（与 `10020`/`10071` 用的是同一套 id） |
| `+8` | u32 flags |
| `+12` | u32 功能号，**base-1000 打包**（每 3 位十进制是一个功能号，低位在前） |
| `+16` | ASCII 零结尾 NPC 脚本键（如 `Athens_026`） |

例：`Athens_071` → `0x2eed` → 功能号 `[12, 13]`（正是称谓鉴定 + 称谓奖励）；
`Athens_074` → `0x2fb4e50` → `[16, 24, 50]`（商城窗口用的 16）。这与
`ScriptedNpcDialogueCatalog.Routing.cs` 里"`10067` 的 `+12` 是 base-1000 打包的功能号列表"
完全吻合，这次拿到了**解码方法**。

> 复现工具：`tools/decode_click_answers.py`（逐 NPC 打印功能号），
> 配合 `tools/enum_captured_npc_interactions.py`（每个 NPC 的 `10077`/`10080` 菜单）。

## 2. 货架帧格式与分页

沿用 `docs/point-exchanger-shop.md` 已定死的布局：

- 帧头 **16** 字节：`+0` u16 帧长、`+2` u16 opcode=10071、`+4` u32 NPC id、
  `+8` u8 分类、`+9` u8 货币、`+10` u8 本帧条目数、`+11` u8 新分类首页、
  `+12` i32 余额
- 记录 **88** 字节：`+0` u32 道具ID、`+68` u32 单价、`+84` u32 数量
- 帧长 = `16 + N × 88`

**分页语义（本次新增证据）**：一个分类超过一帧时，首页 `+11 = 1`，
续页 `+11 = 0`，且两页物品**不重叠**。例：

```
npc 5166 分类 0：首页 16 条 (1000…1403)，续页 8 条 (1404…1411)  → 共 24 条
```

生成目录时**必须保留续页帧**；只取首页会丢货。

## 3. 移植内容

### 3.1 商店目录（14 个）

`src/Godswar.Server/Packets/PacketBuilder.CapturedAthensMerchantShops.cs`
—— 每个商人一个 gzip+base64 常量，就是参考服务器的原始 `10071` 字节流，
出口只改写 NPC id 与实时余额（沿用既有 `InflateCatalog` 机制，未新增协议）。

| NPC id | 脚本键 | 名称（`npc_text_templates`） | 帧 | 商品 | 货币 |
|---|---|---|---|---|---|
| 5166 | Athens_026 | [Warrior]Demetrius | 5 | 63 | 绑定金币 |
| 5167 | Athens_027 | [Scholar]Renee | 5 | 63 | 绑定金币 |
| 5168 | Athens_028 | [Jewelry]Artisan | 6 | 76 | 绑定金币 |
| 5169 | Athens_029 | [Armor]Cobbler | 7 | 91 | 绑定金币 |
| 5234 | Athens_096 | [Warrior Supplier]Alexiou | 5 | 63 | 绑定金币 |
| 5237 | Athens_099 | [Skill Merchant]Thisbe | 8 | 86 | 绑定金币 |
| 5240 | Athens_102 | [Armor Merchant]Judaeus | 6 | 78 | 绑定金币 |
| 5245 | Athens_107 | [Scholar Supplier]Moya | 5 | 63 | 绑定金币 |
| 5246 | Athens_108 | [Jewelry Merchant]Antigone | 2 | 24 | 金币 |
| 5259 | Athens_121 | Alchemy Recipe Vendor | 5 | 79 | 银币 |
| 5260 | Athens_122 | Ingredients Vendors | 8 | 96 | 绑定金币 |
| 5273 | Athens_135 | Forging Recipe Vendor | 5 | 76 | 银币 |
| 5274 | Athens_136 | Mythcrafting Recipe Vendor | 5 | 80 | 银币 |
| 5275 | Athens_137 | Scholarship Recipe Vendor | 6 | 93 | 银币 |

合计 721 件**去重**商品（含重复列举共 918 条记录）。
**这 721 件全部已在运行时 `item_templates` 中发布，零缺口**——
不会重演 `docs/shop-purchase-unavailable-20260924.md` 的"看得到买不到"。

### 3.2 未移植：`Athens_095`（npc 5233）

它的帧 `+9 = 0x01`，而运行时货币表只认 `2=金币 / 3=银币 / 4=绑定金币`
（`CapitalNpcServiceProtocol.TryGetShopCurrency(byte)`）。该代码语义**未取证**，
因此整个商店先不移植，而不是猜一个余额。它只有 1 帧 8 条记录。
若日后确认代码，直接加进 `MERCHANTS` 即可（生成器会校验帧内货币一致性）。

### 3.3 代码接线（复用既有机制，无新协议）

- `Domain/World/Content/CapitalNpcServiceProtocol.cs`
  —— 新增 14 个 `CapitalNpcServiceKind`、`TryResolve` 映射、纳入 `IsShop`
    与 `TryGetShopCurrency`。
- `Packets/PacketBuilder.CapitalNpcShops.cs`
  —— `GetCapitalShopCatalogSource` 新增分支转 `GetCapturedAthensMerchantCatalogSource`。

映射键用的是**抓包里的 NPC id**：`CapturedNpcPlacementPolicy.Place()`
会把 `ObjectId` 与 `InteractionId` 同时设成抓包值，所以客户端回传的就是这个 id。
这与抓包实测一致（`Athens_026` ↔ 5166）。

> 注意：数据库 `npc_spawn_definitions` 里这些 NPC 的 object id 是**抓包前的旧值**
> （`Athens_026` = 5165），差 1。以抓包为准，不要照抄库里那一列。

## 4. 顺带补齐：NPC 摆放缺 7 个

`CapturedNpcPlacementPolicy.DropAbsentFromCapture` 会丢掉"抓包没记录的 NPC"，
而旧导出比新抓包少 7 个，导致它们在地图上直接消失：

| 地图 | npcKey | objectId |
|---|---|---|
| 1 | Athens_038 / 049 / 050 / 051 / 054 / 087 | 5176 / 5187 / 5188 / 5189 / 5192 / 5225 |
| 11 | Marathon_006 | 5480 |

补齐后 `CapturedNpcPlacements.Generated.cs`：map 1 由 119 → **125**，
map 11 由 9 → **10**（map 0/2/3/4 不变）。

连带修正两处由此失效的断言：

- `QuestProtocolChecks`：`CountFor(1)` 期望 119 → 125；
- 同文件的"未记录 NPC 会被丢弃"用例原本用 `Athens_051`（现在抓包**有**它了），
  换成真正未记录的 `Athens_047`；
- `CapitalNpcServiceProtocolChecks`：`Athens_087` 由"重编号到 5294"
  改回抓包 id **5225**（`CapitalNpcServiceProtocol.cs` 内注释同步更新）。

## 5. 生成链（都可复现，重跑两次 hash 一致）

```
# 商店目录
python tools/enum_captured_shops.py --json artifacts/npc-port/captured-shops.json
python tools/gen_captured_shop_catalogs.py --session <uuid>
python tools/emit_shop_catalog_cs.py          # 货币由帧内 +9 推导，不手抄
python tools/assemble_athens_merchant_source.py

# NPC 摆放
python tools/enum_captured_npc_placements.py               # 抓包 → artifacts
python tools/merge_captured_npc_exports.py --apply         # 合并进 npc-translation（含备份）
python tools/gen_captured_npc_placements.py                # → Generated.cs
```

缺口体检：

```
python tools/report_npc_port_gaps.py          # 抓包 vs 服务端三层差异
python tools/check_shop_items_published.py    # 货架商品是否都已发布
python tools/check_merchant_catalog_membership.py
python tools/inspect_shop_frames.py --session <uuid>       # 分页/重复判定
python tools/dump_merchant_frame.py --source catalog --npc <id>
```

## 6. 一条经验：不要手抄帧里的字段

第一版把 `5260` 的货币写成"银币"，因为它叫 *Ingredients Vendors*；
抓包实际是 `0x4`（绑定金币）。生成器因此改成**从帧内 `+9` 反向推导**货币，
并校验"同一商店所有帧货币一致且已映射"，手抄错误从此无法进入源码。

同理，测试断言里的期望余额不是固定值，而是按货币取
（`CapitalNpcShopBalances.Get(charge)`）——金币商人广告的是 `Gold` 余额，
不是绑金余额。

## 7. 验证状态

- `dotnet build GodswarServer.sln -c Release`：0 警告 0 错误
- `Godswar.Server.ProtocolChecks`：**450 通过 / 11 失败 / 98 跳过**
  - 11 个失败在本次改动前就存在（架构 ratchet、迁移目录计数 156/168、
    `HandlePacketAsync` 断言等），失败集逐字未变；
  - 本次新增的 14 个商店断言已并入
    `CapitalNpcServiceProtocolChecks.CheckShopCatalogs`
    （帧数 / 条目数 / 货币字节 / 首末商品与单价）。

---

## 8. 后续时段（23:48–23:57）复核

同一个会话 `b1825b76` 到 23:59:58 又长了 16k 包，按 23:48–23:58 再扫一遍：

| 项 | 结果 |
|---|---|
| `10020` 世界对象 | 647 个（64 NPC + 583 怪物），**NPC 与已移植的 169 条完全一致**：0 新增、0 模板差异 |
| `10071` 货架 | 3 个：`5225`、`5285`、`5289` |
| `10077`/`10080` 菜单 | 各 19 个 NPC，均已有对话路由 |

窗口内三个货架与既有抓包**逐帧一致（仅帧头 npc id 不同）**，实测结论两条：

1. **`5285` 就是 `5237`（技能商人）的同一份货架**。两者各 8 帧、逐字节只差
   帧偏移 `+4` 的 npc id（`0xa5` vs `0x75`）；`CapitalNpcShopCatalog` 本来就在
   出口改写该字段，所以**直接复用 `AthensSkillMerchant` 目录，不新增任何副本**。
2. **`Athens_Newbie_004` 的映射键是错的**。它在 map 2 上被
   `CapturedNpcPlacementPolicy` 规范化为抓包 id **5285**，而
   `TryResolve` 用的是 NPC.ini 的发布值 `54453`，所以这个商店此前**永远打不开**。
   已改为 `5285`，并在 `CapitalNpcServiceProtocolChecks` 端点表中锁死
   （`Sparta_Newbie_004` 的 46565 本来就是对的，一并补上断言）。
3. `5289`（`Athens_Newbie_016`）帧内货币是 `0x01`，运行时表未定义，**跳过**——
   与 `5233` 同一处理原则：不猜余额。它只有 2 帧 20 条。

> 复现：`tools/gen_captured_shop_catalogs.py` 新增 `--from/--to`（本地时间）
> 可直接限定窗口生成目录。

---

## 9. 外域地图内容移植（00:25–00:37 窗口）

玩家继续游走到主城以外的地图，同一会话里又扫出三张服务端从未覆盖过的：

| 地图 | SceneKey | NPC（抓包 / 内容侧） | 怪物（本次新增） |
|---|---|---|---|
| 9 Thebes | `Thebes_All` | 16 / 10 | **308** |
| 15 Derveni | `Derveni_All` | 3 / 4 | **273** |
| 19 Plataea | `Plataea_All` | 0 | **185** |

三张图都在 `map_templates` 内，所以内容发布器的 mapId 校验直接通过。

### 9.1 怪物缺口与补写

上次发现 proxy 缺 `--monster-map-id` 会整段跳过怪物写入，这次沿用同一条通路补写：
`tools/import_captured_monsters.py` 把 `packet_transactions` 里的 10020 帧按 proxy
的同一套校验（objectType 判别符 `0x12`、tier/HP 非零、坐标有限、模板必须在
`monster_templates` 中按该地图可解析）回放进 `monster_spawn_packets`，再跑项目既有的
`tools/ExportMonsterContentBaseline.ps1` 重导内嵌 baseline。

本次 `--only-maps 9 15 19` 写入 **766 只**，未触碰 map 1/2：

```
map 1|351   map 2|904   map 3|263   map 9|308
map 11|452  map 15|273  map 18|185  map 19|185
```

baseline：2155 → **2921** 条，`MonsterContentBaselineV1` 的 pin 同步为
`0DA1196A…C87754` / `25867D2A…34D9C3`。

### 9.2 NPC：摆放表与权威目录

`CapturedNpcPlacements` 新增 map 9（16）与 map 15（3），走同一条生成链
（`enum_captured_npc_placements.py <dir> 9 15` → `gen_captured_npc_placements.py`）。

权威目录新增 `NpcActorPlacementCatalog.SecondaryCities.cs`，把 **Thebes / Derveni /
Megara** 三张图放在同一个「外域城市」文件里（Megara 原本单独一个文件，一并并入，
避免继续堆地图专属文件）。这些行是必需的：内容侧发布的是旧 ini 身份
（`Thebes_All_001` 在 55284、`Megara_All_001` 在 53307，坐标差约 1 单位），
只有经 `CapturedNpcPlacementPolicy` 才会被改写成参考服自己的 id / 外观 / 坐标 / 朝向。

只登记抓包确实放置过的模板；抓包没记录的发布行（如 `Megara_All_012`、
`Derveni_All_004/005`）**故意不登记**——抓包覆盖的地图，其内容以参考服实际放置的为准。

连带影响：生成的 fallback 对话基线由 369 涨到 **376** 条（`NpcTemplateSeeds.Texts`
里多匹配上 7 个外域 NPC 名），golden 哈希同步更新为 `6F42A442…D21996`。

### 9.3 验证

- `dotnet build GodswarServer.sln -c Release`：**0 警告 0 错误**
- 全量协议测试：**450 通过 / 11 失败 / 98 跳过**，失败集与改动前逐字一致
- 回滚材料：`artifacts/npc-port/pre-monster-import-2/`（上一版 baseline）、
  `artifacts/npc-port/pre-map9-15/`（改前的 7 份 NPC 导出）

### 9.4 发布链路怎么才算验过（重要）

尝试用**真启动服务端**来验发布，结论是**这个环境起不来，且与本次改动无关**：

```
[status] startup_failure  frame=postgresschemamigrationplan.build
```

`PostgresSchemaMigrationPlan.Build` 要求数据库已应用历史是注册目录的**精确有序前缀**，
而两个库都在**同一位置（第 59 位）**断裂：

| 位置 | 数据库 | 代码目录 |
|---|---|---|
| 59 | `20260804_058_stock_holy_stone_material_templates` | `20260805_059_holy_spirit_effectiveness_values` |

数据库里的 `_058` 在当前代码目录中**不存在**（`godswar` 缺 25 个目录条目、多 18 个；
`godswar_local` 缺 2、多 6）。这是**既有的环境/代码漂移**，不是本次引入的；
`Postgres migration safety foundation` 那个「expected 156, actual 169」的既有失败正是同一件事。

所以发布验证改走**代码本身**：`QuestProtocolChecks.CheckCapturedAthensSpawnPlans`
直接调用 `MonsterContentBaselineV1.LoadDefinitions()`，而该方法内部会强制三件事——

1. 制品 SHA256 必须等于 `ExpectedArtifactSha256`；
2. 反序列化条目数必须等于 `ExpectedEntryCount`；
3. `WorldContentRevisionHasher.HashMonsters` 的结果必须等于 `ExpectedRevision`。

任何一项不符都会抛异常、把测试打红。该测试现在**通过**，并且已扩展到断言
map 3/9/11/15/18/19 的怪物数量、object-id 区间与逐行字段完整性，所以：

> **新 baseline（2921 条）确实能被服务端加载并通过全部三道校验**，
> 且 6 张新增地图的怪物确实在其中。剩下的是启动时 `EnsurePublishedAsync`
> 把它写进 `monster_content_publication`——那条路径由既有的
> `PostgresWorldContentReaderIntegrationChecks` 覆盖（需 `GODSWAR_TEST_POSTGRES_CONNECTION_STRING`）。

> 附：想在本机跑通服务端，得先把上面第 59 位的迁移漂移补齐——
> 这属于既有问题，未在本次范围内改动。



