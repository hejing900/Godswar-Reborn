# 交接文档 —— 部署、购买故障根因、阵营逻辑、传送卷调研

> 覆盖时段：2026-09-24 22:00 → 2026-09-25 19:46（本地时间，UTC+8）
> 当前状态：**服务器健康运行，经济基线故障已修复并验证；传送卷调研已完成，未实施。**
> 写作时快照：容器 `godswar-server` = `Up (healthy)`，镜像 `godswar-reborn-main-server:latest`（构建于 2026-09-24 17:56:32 UTC），端口 `127.1.1.110:5999` / `7000`。

---

## 0. 一句话摘要

本轮修好了一个**让 test2 完全买不了东西**的故障（根因是克隆角色时 `account_id` 没被重写，导致经济基线校验永远失败），并把"两个阵营是不是两套逻辑"和"传送卷坐标在哪"这两个问题查清并留了文档。**没有实施任何新功能。**

---

## 1. 当前部署状态（可直接用）

### 1.1 运行中的服务

| 项 | 值 |
|---|---|
| 容器 | `godswar-server`，`Up (healthy)` |
| 镜像 | `godswar-reborn-main-server:latest`，`sha256:1b679b8c…`，构建于 **2026-09-24 17:56:32 UTC** |
| 端口 | `127.1.1.110:5999` → 5999（登录）、`127.1.1.110:7000` → 7000（游戏） |
| 管理模式 | `legacy-raw` profile（`GODSWAR_AUTH_ALLOW_LEGACY_RAW_AUTHENTICATION=true`） |
| 数据库 | **`godswar_local`**（由 `.env` 的 `POSTGRES_DB` 决定，不是 `godswar`） |
| 迁移数 | **169** |
| 管理 HTTP | 容器内 `127.0.0.1:9090`，健康检查 `secure-healthcheck.sh` |

### 1.2 关键：镜像是否包含最新代码

**包含。** 判定方法（不要只看 `docker images` 的 "18 hours ago"）：

```
镜像构建时间    2026-09-24T17:56:32Z
源码最后改动    2026-09-25 01:01:50 本地 = 2026-09-24 17:01:50 UTC   ← 早于构建
容器内 DLL      /app/Godswar.Server.dll  Sep 24 17:56
```

容器于 2026-09-25 11:35:32Z 重启过，用的仍是同一镜像，所以跑的确实是当前代码。

### 1.3 三个角色

| id | 名字 | 账号 | camp | 等级 | 当前地图 |
|---:|---|---|---:|---:|---:|
| 2 | `test` | `123`（id 1） | 0 斯巴达 | 140 | 9 |
| 4 | `test2` | `111`（id 6） | 1 雅典 | 140 | 2 |
| 100 | `Officer` | `fixture`（id 5） | 0 斯巴达 | 140 | 0 |

`test2` 是本轮从 `test` 克隆出来的（装备/技能/天赋/任务/货币全量复制），营地由 0 改为 1。

### 1.4 重新部署的命令

```powershell
docker compose --profile legacy-raw build server
docker compose --profile legacy-raw up -d server
docker ps --filter name=godswar-server --format '{{.Status}}'
docker logs godswar-server 2>&1 | Select-String 'outcome=|startup_failure|"level":"error"'
```

启动成功的标志：日志出现 `server_lifecycle outcome=ready`，且 `login_listener` / `game_listener` / `management_http` 三个 `critical_task_state state=running`。

---

## 2. 【已修复】test2 所有商店与商城都无法购买

### 2.1 用户报告

> 「雅典的NPC商店和商城买不了东西，理论上不管是斯巴达还是雅典只要是同一个坐标的NPC背后逻辑都是一样的」

用户的判断是对的 —— **与阵营、与地图、与商店实现都无关**。

### 2.2 故障现象（日志原文）

```
[npc-shop] purchase rejected character=test2 npc=5234 item=1402 quantity=1 status=CharacterNotFound
[npc-shop] purchase rejected character=test2 npc=5246 item=3101 quantity=1 status=CharacterNotFound
[npc-shop] purchase rejected character=test2 npc=5240 item=2203 quantity=1 status=CharacterNotFound
[mall]     purchase rejected character=test2 item=10090 quantity=1 unitPrice=11 status=CharacterNotFound
```

对照组：同一份代码，`character=test` 购买**成功**：

```
[mall] purchased character=test item=4210 quantity=1 unitPrice=41 currency=Gold balance=5791904
```

所以故障是**角色维度**的，不是功能维度的。

### 2.3 排查路径（下次可复用）

购买事务在 `PostgresCapitalShopPurchaseStore.PurchaseCapitalShopItemAsync` 里有两道门：

1. `LockCapitalShopCharacterAsync`：
   ```sql
   SELECT ... FROM public.character_base
   WHERE id = @characterId AND account_id = @accountId
     AND lifecycle_state = 'active'
   FOR UPDATE;
   ```
   查库确认 `test2` 是 `id=4, account_id=6, lifecycle_state='active'` —— **这道门是过的**。

2. `PostgresCharacterEconomyBaseline.EnsureAsync`：要求存在
   `character_economy_baseline(character_id=4, account_id=6, wallet_revision=0, inventory_revision=0)`。
   实际数据是：
   ```
   character_id | account_id | wallet_revision | inventory_revision
         2      |     1      |        0        |         0        ← test，正确
         4      |     1      |        0        |         0        ← test2，错！应为 6
   ```
   `ExistsAsync` 查 `(4, 6, 0, 0)` → 查不到 → 走 INSERT 重建 → 被
   `ON CONFLICT (character_id) DO NOTHING` 挡住（`character_id` 是主键，行已存在）
   → 最终 `ExistsAsync` 仍为 false → 返回 `false` → 外层报 **`CharacterNotFound`**。

**难点**：`CharacterNotFound` 这个名字极具误导性，角色明明存在。真实含义是"经济基线不可用"。

### 2.4 根因：克隆脚本的缺陷

`tools/clone_character.py` 的 `build_child_insert`：

```python
overrides = {
    column: new_key,                      # character_id / user_id
    "character_name": f"'{args.name}'",
}
targets = [c for c in columns(database, table) if c != "id"]
sources = [overrides.get(c, quote(c)) for c in targets]
```

它只重写**指向角色的那一列**，**没有重写 `account_id`**。于是任何同时带
`character_id`（或 `user_id`）和 `account_id` 的子表，克隆行都会保留**源账号**的 `account_id`。

本轮的 `COPY_TABLES`：

```python
COPY_TABLES = [
    ("character_items", "user_id"),          # 无 account_id
    ("character_skills", "user_id"),         # 无 account_id
    ("character_talents", "user_id"),        # 无 account_id
    ("character_zodiac_skill_grids", "user_id"),  # 无 account_id
    ("character_quests", "character_id"),    # 无 account_id
    ("character_economy_baseline", "character_id"),  # ← 有 account_id，中招
]
```

全库扫描（`artifacts/npc-port/find_clone_account_mismatch.py`）：角色域基表 57 张，其中 18 张带
`account_id`，**实际出错只有 `character_economy_baseline` 一张**（其余 17 张 `test2` 没有任何行）。

> 注意：`character_inventory_baseline_items` 也带 `account_id`，但克隆脚本没复制它，
> 所以 `test2` 是 **0 行**。它只喂对账报告（`reconciliation.enabled=false`），**不影响购买**，本轮未动。

### 2.5 修复动作（已执行并验证）

两张基线表都是 **append-only** 的，带 `BEFORE DELETE OR UPDATE` 触发器：

```
trg_character_economy_baseline_immutable          BEFORE DELETE OR UPDATE
trg_character_economy_baseline_no_truncate        BEFORE TRUNCATE
trg_character_inventory_baseline_items_immutable  BEFORE DELETE OR UPDATE
→ 函数 reject_character_economy_evidence_mutation()，ERRCODE 55000
```

所以常规 `UPDATE` 会被拒绝。修复在**单个事务**内临时停用触发器、改一个字段、立刻恢复：

```sql
BEGIN;
ALTER TABLE public.character_economy_baseline
    DISABLE TRIGGER trg_character_economy_baseline_immutable;
UPDATE public.character_economy_baseline
SET account_id = 6
WHERE character_id = 4 AND account_id = 1;
ALTER TABLE public.character_economy_baseline
    ENABLE TRIGGER trg_character_economy_baseline_immutable;
COMMIT;
```

**验证结果（全部通过）**：

| 检查 | 结果 |
|---|---|
| 基线表 | `4 \| 6 \| 0 \| 0` ✅ |
| 模拟 `EnsureAsync` 精确 SQL | 返回 `t` ✅ |
| 触发器恢复 | `tgenabled = 'O'`（启用）✅ |
| 再改一行应被拒 | `ERROR: Economy evidence table ... is append-only.` ✅ |
| 全库重扫 | `no mismatched account ids found` ✅ |

### 2.6 ⚠️ 待用户确认

用户**尚未回报购买是否真的成功**（他随后转去问阵营逻辑）。下次接手请先让用户实测一次
雅典商店 + 商城购买，并查日志确认出现 `[npc-shop] purchased` / `[mall] purchased`。

### 2.7 未修的关联缺陷（重要）

`tools/clone_character.py` 的 `account_id` 缺陷**仍在**。下次再克隆角色会重踩同一个坑。建议改法：
在 `build_child_insert` 的 overrides 里加上当表含 `account_id` 时改写为新账号，
或在克隆后跑一遍 `artifacts/npc-port/find_clone_account_mismatch.py` 做校验。

另外该脚本的 `COPY_TABLES` 不包含 `character_inventory_baseline_items`，克隆角色的对账基线会是空的。

---

## 3. 阵营逻辑：一套代码，不是两套

用户问：「现在两个阵营走的是同一条逻辑吗？还是两个阵营有两套点击NPC和购买逻辑」

**答：同一条逻辑，一套代码。** 证据如下。

### 3.1 点击入口只有一个

`GameClientHandler.Dispatch.cs` 里 `NpcDialogOpen`(10067) 只路由到一个
`HandleNpcDialogOpenAsync`，链路内部**没有按阵营分支**：

```
HandleNpcDialogOpenAsync
  → warehouse → newbie-guide → quest → duel-arena → capital
  → guild-registrar → dialogue routes → description
```

### 3.2 服务解析是一张表

`CapitalNpcServiceProtocol.TryResolve` 是**一个** `(npcKey, interactionId)` switch，
两个阵营共用同一条臂：

```csharp
("Sparta_087", 5084u) or ("Athens_087", 5225u) => CapitalNpcServiceKind.BoundGoldVendor,
```

统计（`artifacts/npc-port/report_camp_logic_split.py`，共 28 条臂）：

| 覆盖范围 | 臂数 |
|---|---|
| 两个阵营都有 | 13 |
| **仅斯巴达** | **0** |
| 仅雅典 | 15（14 个雅典商户区商店 + 雅典技能商） |

"仅雅典"不是逻辑分叉，而是**斯巴达城里本来就没有这些商人** —— 对比两城抓包，
**0 个共享键**（斯巴达 123 个 `Sparta_*`，雅典 125 个 `Athens_*`）。两城是两套 NPC 身份、
一套行为逻辑，靠 `service` 枚举把"是哪城的哪个NPC"翻译成"提供什么服务"。

### 3.3 目录与出价完全不看阵营

- `Packets/PacketBuilder.CapitalNpcShops.cs`：`.Camp` 出现 **0 次**
- `Domain/World/Content/CapitalNpcServiceProtocol.cs`：`.Camp` 出现 **0 次**

```csharp
GetCapitalShopCatalogSource(service)   // 按 service 选目录
TryGetCapitalShopCatalogCurrency(...)  // 按 service 定货币
TryResolveCapitalNpcShopOffer(...)     // 不看 camp
```

### 3.4 购买事务一致

`HandleCapitalNpcShopPurchaseAsync`：

```
TryResolveMapNpc(npcId) → TryResolve(npc) → IsShop → TryResolveCapitalNpcShopOffer
→ PurchaseCapitalShopItemAsync（同一个事务）
```

### 3.5 唯一的阵营差异：商城目录

购买链路上 `.Camp` 只出现在商城：

```csharp
// GameClientHandler.CapitalNpcServices.cs L354 / L364
PacketBuilder.TryResolveMallCatalogOffer(_character.Camp, ...)

// PacketBuilder.MallCatalog.cs
public static byte[] MallCatalog(byte camp) =>
    (camp == GameDefaults.AthensCamp
        ? AthensMallCatalog.Value
        : SpartaMallCatalog.Value).Clone();
```

这是**内容差异不是逻辑差异**：两个阵营的商城确实卖不同的东西，各用抓包抓到的目录
（两份都是 19,568 字节）。选定目录后，解析出价、扣钱、发货仍走同一事务。

（另有一处无关的 `.Camp`：`GameClientHandler.NpcDialogOpen.cs:856`，许愿池全服公告里判断阵营是否合法。）

### 3.6 对排查的意义

§2 那个 `CharacterNotFound` 能**同时**打中雅典商店和商城，正是因为它们在
`TryResolveCapitalNpcShopOffer` 之后是同一份代码，而故障在更底层（经济基线校验）。
**遇到"某类功能全挂"，先找所有入口的公共下游。**

---

## 4. 已知缺陷清单（本轮发现，均未修）

### 4.1 发布的雅典目录有 15 个 NPC 不在抓包中 → 5 处 ID 撞号

`artifacts/npc-port/report_athens_id_collisions.py`。

发布目录（`NpcActorPlacementCatalog.cs` 的 Athens 列表）111 行，其中 96 行能被抓包覆盖、
**15 行不能**。而抓包把其余 NPC 的 object id 整体**下移一位**
（例：`Athens_048` 发布 5187 → 抓包/生成 5186），于是这 15 个保留旧 ID 的 NPC 撞上重编号后的 NPC：

| 未覆盖的NPC | 保留ID | 撞上（抓包重编号后） |
|---|---:|---|
| `Athens_008` | 5147 | `Athens_007` |
| `Athens_016` | 5155 | `Athens_015` |
| `Athens_024` | 5163 | `Athens_023` |
| `Athens_034` | 5173 | `Athens_033` |
| `Athens_082` | 5221 | `Athens_083` |

`CapturedNpcPlacementPolicy.ApplyToMap` 有去重逻辑（撞号者被抬到 `max+1`），所以**不会崩**，
但会静默改名，客户端可能找不到对应 NPC。未覆盖的 15 个键：
`Athens_003/004/005/008/009/010/011/013/016/017/024/034/080/081/082`。

### 4.2 `ApplyCapturedSpawnCompatibility` 的雅典分支永不命中

`CapitalNpcServiceProtocol.ApplyCapturedSpawnCompatibility`：

```csharp
(1, "Athens_142", 5281u) => npc with { TemplateKey = "Athens_142_Hallo", ... }
```

但 `CapturedNpcPlacementPolicy` 会先把 `Athens_142` 的 ID 改成抓包的 **5280**，
于是这个 `5281u` 的匹配条件**永远不成立**，该兼容性改写是死代码。
（`Athens_142` 的 `TryResolve` 分支用的是 `5280u`，那个是对的。）

### 4.3 ~~`FilterUnsupportedCatalogItems` 不递减条目数~~ —— 已核验，**不是缺陷**

> ⚠️ 更正：`docs/shop-purchase-unavailable-20260924.md` §4 曾记录"该函数只前移记录、
> 不递减帧头 `+10` 的条目数"。**本轮核验结论是代码已经正确**，那条记录不再成立。

`Packets/PacketBuilder.CapitalNpcShops.cs:383-432` 实际行为：

```csharp
filtered[packetOffset + 10] = checked((byte)retainedCount);   // L421 递减条目数
filtered.AsSpan(
        packetOffset + ShopCatalogHeaderBytes + (retainedCount * ShopCatalogItemBytes),
        payloadBytes - (retainedCount * ShopCatalogItemBytes))
    .Clear();                                                  // L422-427 清零尾部
```

条目数被 `retainedCount` 正确覆盖，尾部剩余记录被清零，包长保持不变（帧长本来就固定）。
被过滤的 id 是 `[4064, 4177, 4515, 10059]`。
**无需修复**；建议顺手更正 `shop-purchase-unavailable-20260924.md` §4。

### 4.4 迁移基础检查与本轮改动不同步

`tests/Godswar.Server.ProtocolChecks/PostgresMigrationFoundationChecks.ExpectedIds.cs` 的
`ExpectedMigrationIds` 仍是 156 条（实际 169），其 `CheckForwardOnlyCatalog` 的计数断言也是 156。
这是**预先存在**的失败项，与本轮改动无关。

### 4.5 测试套件基线

```
Protocol checks: 450 passed, 11 failed, 98 skipped
```

这 11 个失败是**基线**（ratchet / 迁移计数 / 状态布局类），与本轮改动无关。
`B13 bounded management HTTP surface` 是**间歇性**失败，单独跑或重跑会通过 —— 不要"修"它。

运行方式（注意：这个测试工程是**控制台程序**，不是 xunit）：

```powershell
& 'tests\Godswar.Server.ProtocolChecks\bin\Release\net10.0\Godswar.Server.ProtocolChecks.exe'
# 不要用 dotnet test（无输出），也不要用 dotnet <exe>（BadImageFormatException）
```

---

## 5. 传送卷调研（已完成，未实施）

详细内容见 **`docs/teleport-scrolls-client-survey.md`**，这里只放结论。

### 5.1 核心结论

**客户端没有传送卷的落点坐标。**

链路是：`物品 FlyBook n` → `Skill` → `ScriptID "FlyToXxx"` → 坐标（**服务端**）。

全客户端扫描（`tools/` 下的脚本，4,707 个文本文件 + `Origin.exe` / `Launch.exe` /
`gworiginsv.exe` / `patcher.exe` / `GodsWar.map`）：**`FlyTo` 只出现在 `Magic.ini` 里**
（作为 `ScriptID`），别处一处都没有。

客户端唯一的坐标表是 `Address.ini`（命名落点），**只有地图 0（斯巴达）和地图 1（雅典）有坐标**，
其余地图的 `Address.ini` 一个坐标都没有。

### 5.2 传送卷清单

**29 个**（`FlyBook1`–`FlyBook29`，物品 ID 4300–4329），28 个技能（`FlyBook9` 是随机传送）。
完整表格见 `docs/teleport-scrolls-client-survey.md`。

### 5.3 坐标的真实来源：抓包落点帧

大抓包在 **`godswar` 库**（313,995 条），不是 `godswar_local`（那里只有 2,696 条）。

opcode `10018` S2C = 服务端落点帧（28 字节：`+4` objId、`+8` f32 X、`+16` f32 Z、`+20` 地图号低16位）。
抓包共 32 帧、**18 个不同落点**：

| 地图 | x | z | | 地图 | x | z |
|---:|---:|---:|---|---:|---:|---:|
| 1 | 102 | -212 | | 9 | 47 | 107 |
| 1 | 20 | -100 | | 9 | 150 | -146 |
| 1 | 120 | -200 | | 11 | 15 | -30 |
| 2 | 209 | 22 | | 11 | 150 | -146 |
| 2 | 20 | -100 | | 11 | 182 | -36 |
| 2 | 120 | -200 | | 15 | -167 | -217 |
| 2 | 150 | -146 | | 18 | **-30** | **-202** |
| 2 | 186 | -122 | | 18 | **56** | **88** |
| 3 | 66 | 190 | | 19 | -194 | 192 |

**交叉验证**：地图 18 的 `(56, 88)` 正是上一轮按"先做包里有的"写进
`Domain/World/Content/ReviveLandingCatalog.cs` 的梅加拉复活点 —— 抓包证实了它。

**一个未解释的细节**：抓包雅典落点是 `(102, -212)`，客户端地址点是 `(102, -217)` ——
**x 相同、z 差 5**。说明服务端落点不是照抄客户端地址点。

### 5.4 服务端现状：28 个技能只实现了 4 个

`Game/BackhaulSkillCatalog.cs`：

| 技能 | 卷轴 | 现服务端目标 |
|---:|---|---|
| 3000 | FlyBook1 雅典城 | `GameDefaults.StartingPosition*` |
| 3001 | FlyBook2 雅典郊区 | map 2 `(102, -217)` |
| 3025 | FlyBook5 斯巴达城 | `GameDefaults.StartingPosition*` |
| 3026 | FlyBook6 斯巴达郊区 | map 4 `(102, -217)` |

- **其余 24 个技能没有定义 → 那些传送卷用了毫无反应。**
- 已实现的 2 个目标和抓包**对不上**：抓包是 map 1 `(102,-212)`、map 2 `(209,22)`。

---

## 6. 本轮的工具与证据产物

### 6.1 新增工具

| 工具 | 用途 |
|---|---|
| `tools/dump_client_address_points.py` | 提取客户端所有 `Address.ini` 命名落点 → JSON |
| `tools/resolve_teleport_scroll_targets.py` | 传送卷 → 技能 → ScriptID → 落点匹配 |
| `tools/find_captured_teleports.py` | 在 `godswar` 库里按 skill id 找传送记录 |
| `tools/scan_capture_for_scroll_skills.py` | 全表扫描 28 个传送技能 id 落在哪个 opcode |
| `tools/decode_teleport_cast_frames.py` | 解 `10194` C2S 施法帧 |
| `tools/recover_teleport_destinations.py` | 关联"施法 → 后续 10018 落点帧" |
| `tools/list_captured_landings.py` | **列出全部 10018 落点坐标**（最有用的一个） |
| `tools/clone_character.py` | 克隆角色（**含 §2.4 的 `account_id` 缺陷**） |

### 6.2 本轮的分析脚本（`artifacts/npc-port/`）

| 脚本 | 用途 |
|---|---|
| `find_clone_account_mismatch.py` | **全库扫描克隆后 account_id 不匹配**（故障复现/校验） |
| `report_camp_logic_split.py` | 统计 TryResolve 里臂的阵营覆盖 |
| `compare_capital_npc_sets.py` | 对比两城 NPC 集合 |
| `check_athens_merchant_endpoints.py` | 核对 27 个雅典服务端点与抓包是否一致 |
| `report_athens_id_collisions.py` | 雅典 ID 撞号报告（§4.1） |
| `check_athens_placement.py` | 发布目录 vs 生成表 vs 抓包三方对照 |
| `diff_athens_exports.py` | 对比改动前后的雅典导出（证明 0 行数值变化） |
| `pick_athens_landing.py` | 网格扫描雅典最安全落点 |
| `extract_teleport_scrolls.py` / `find_teleport_items.py` | 传送卷清单提取 |

### 6.3 数据产物

| 文件 | 内容 |
|---|---|
| `artifacts/npc-port/client-address-points.json` | 客户端命名落点（地图 0 有 186 点，地图 1 有 195 点） |

### 6.4 数据库备份

| 文件 | 大小 | 用途 |
|---|---:|---|
| `artifacts/db-repair/backup/godswar_local-before-deploy.sql` | 43.6 MB | 部署前 |
| `artifacts/db-repair/backup/godswar_local-before-clone.sql` | 42.4 MB | 克隆前 |
| `artifacts/db-repair/backup/godswar-full.sql` | 119.9 MB | `godswar` 库（含大抓包）全量 |

---

## 7. 操作备忘

### 7.1 常用命令

```powershell
# 查测试角色
docker exec godswar-postgres psql -U godswar -d godswar_local -t -A -F' | ' `
  -c 'SELECT c.id, c.name, c.account_id, a.username, c."Map", c."Pos_X", c."Pos_Z" FROM character_base c JOIN accounts a ON a.id=c.account_id ORDER BY c.id;'

# 购买相关日志
docker logs godswar-server 2>&1 | Select-String 'npc-shop|\[mall\]|capital open'

# 内存中的位置（不下线不落库）
# 位置存档用乐观并发 position_revision；WalkEnd 会 force 落库
```

### 7.2 坑（本轮踩过的）

| 坑 | 说明 |
|---|---|
| `CharacterNotFound` 名字误导 | 真实含义是"经济基线不可用"，角色存在也会报这个（§2.3） |
| 基线表 append-only | `character_economy_baseline` / `character_inventory_baseline_items` 有 `BEFORE DELETE OR UPDATE` 触发器，必须临时 `DISABLE TRIGGER`（§2.5） |
| 基线 `wallet_revision` 必须为 0 | CHECK 约束 `ck_character_economy_baseline_revisions` 强制 `wallet_revision = 0 AND inventory_revision = 0` |
| 大抓包不在 `godswar_local` | 在 `godswar` 库（313,995 条 vs 2,696 条） |
| 测试工程不是 xunit | 直接跑 exe，别用 `dotnet test`（§4.5） |
| 客户端 ini 编码混用 | `AddressConfig.ini` 是 UTF-8，`Address.ini` 是 UTF-16LE（带 BOM）；`ItemBaseAttribute.xml` 是 UTF-8 BOM |
| 客户端 XML 是伪 XML | `ItemBaseAttribute.xml` 单根元素下混多种标签，用 `ET.parse` 取不到，用正则 |
| PowerShell 引号 | `psql -c` 里带双引号列名时，用 here-string `@"..."@`，不要用 `\"` 转义 |
| 地图号 | **0=斯巴达，1=雅典**（曾经搞反过，`CapturedNpcPlacementPolicy` 的 `AlreadyPublishedFromCapture = [0, 4]` 指斯巴达城和新手图，不含雅典） |

### 7.3 端口占用

5999 / 7000 / 13333 被 Docker 代理进程占用；本地调试验证需换端口（此前用过 `15999` / `17000`）。

---

## 8. 建议的后续工作（按优先级）

| 优先级 | 事项 | 依据 |
|---|---|---|
| **1** | 请用户实测雅典商店 + 商城购买，确认 §2 修复真的生效 | §2.6 |
| **2** | 修 `tools/clone_character.py` 的 `account_id` 缺陷，并在克隆后跑校验脚本 | §2.4 / §2.7 |
| **3** | 决定雅典 15 个未覆盖 NPC + 5 处撞号怎么处理 | §4.1 |
| **4** | 删掉或修好 `ApplyCapturedSpawnCompatibility` 的死分支 | §4.2 |
| **5** | 按抓包补全传送卷：至少先修已实现 4 个的坐标，再逐步补 24 个 | §5.4 |
| **6** | 补 `character_inventory_baseline_items`（克隆角色对账基线为空） | §2.7 |
| **7** | 更正 `docs/shop-purchase-unavailable-20260924.md` §4 的过时结论 | §4.3 |
| **8** | 更新 `PostgresMigrationFoundationChecks.ExpectedIds.cs`（156 → 169） | §4.4 |

---

## 9. 本轮没有做的事（明确边界）

- **没有实施任何新功能**。NPC 放置、雅典商户目录、宠物删除等代码都是**上一轮**（≤ 2026-09-25 01:01）改的，本轮只是把它们部署进容器并验证。
- **没有改 `tools/clone_character.py`**（缺陷仍在，见 §2.7）。
- **没有补传送卷坐标**，只做了调研。
- **没有修 §4 里的任何一个缺陷**。
- 本轮对**源码的唯一改动**是新增 `docs/teleport-scrolls-client-survey.md`、本文件，以及
  `tools/` 下 7 个调研脚本、`artifacts/npc-port/` 下若干分析脚本。
  其余改动都在**数据库**里（§2.5 的基线修复、以及把 `test2` 从地图 0 移到地图 1）。
