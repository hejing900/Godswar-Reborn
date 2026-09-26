# 利兰丁农场保卫战（Lelantine Farm Defence）复刻交接

> 活动正式名是 **利兰丁**（Lelantine），不是"米兰丁"。客户端脚本键为
> `Lelantine_Farm_003/004/005/006/007/008`，文本键前缀 `NF_L0_FRAM###`。

本文只记录**已在源码、抓包或客户端发布数据中核验过的**事实。凡是本服务端自行设计的
部分，都在对应位置明确标注 **authoring** 并给出理由；凡是用户口头给定、抓包里查不到
的规则，标注 **用户指定（非抓包复原）**。没有任何未经验证的推断被写成事实。

状态：**已在真机验收**（用户确认入图、NPC 对话、捐卵扣分/计分、两个积分查询全部正确）。

---

## 1. 已实现的功能

### 1.1 入口与地图
| 功能 | 实现位置 | 依据 |
|---|---|---|
| 两个主城的战场传送员新增"利兰丁农场保卫战"入口，sub id `282`（单线版 `1282` 同样接受） | `Domain/World/Content/BattlefieldTransporterProtocol.cs` | 抓包 `C2S 10069 {5194, 1, 282}` |
| 目标地图 **42**（`Lelantine_Farm`，客户端场景 226），落点=本方阵营基地 | 同上 | `008_maps.sql` + 农场 `Address.ini` |
| 等级 31–140 门槛，拒绝文案用农场自己的 `7005`/`7004`（挂在对话号 47 上才画得出来） | 同上 | 客户端 `NF_L0_Y7003/Y7005/Y7004` |
| **全天可进入**（其它战场保留原窗口） | `Application/WorldInstances/BattlefieldSchedulePolicy.cs` | 用户要求（便于测试） |

### 1.2 农场 NPC（对象 ID 是抓包实测值）
名册 8 个（`LelantineFarmProtocol.Npcs`），对象 ID 取自抓包连续段 **5615–5622**：

| NPC 键 | 对象 ID | 角色 | 行为 |
|---|---|---|---|
| `Lelantine_Farm_001` 发怒的尼恩托 | 5618 | 网兜发放（**未做**，见 §2） | — |
| `Lelantine_Farm_002` 快乐的凯尔西斯 | 5619 | 宠物评比（**未做**） | — |
| `Lelantine_Farm_003` 雅典先锋队队长 | **5615**（抓包） | 活动窗口 | `NpcDialogueBehavior.Farm` |
| `Lelantine_Farm_004` 雅典军需官 | **5616**（抓包） | 商店 | `CapitalNpcServiceKind.LelantineFarmQuartermaster` |
| `Lelantine_Farm_005` 雅典返乡 Helper | **5617**（抓包，坐标也是抓包） | 回主城 | `FarmReturnTeleporter` |
| `Lelantine_Farm_006` 斯巴达先锋队队长 | 5620 | 活动窗口 | 同 003 |
| `Lelantine_Farm_007` 斯巴达军需官 | 5621 | 商店 | 同 004 |
| `Lelantine_Farm_008` 斯巴达返乡 Helper | 5622 | 回主城 | 同 005 |

* **对象 ID 来源**：抓包 21:00:44 点 `5615` 答 `Lelantine_Farm_003`、21:01:31 点
  `5616` 答 `Lelantine_Farm_004`、21:01:36 点 `5617` 答 `Lelantine_Farm_005`；
  段连续，其余 5 个按同一编号顺延。
* **唯一被抓到的放置**：21:03:04 的 `10020` 世界物件帧把 `5617` 放在地图 42
  `(-141, 161)` 朝向 `2.30`，代码里就是这三个数。
* 其余坐标是 **authoring**（抓包没有），取自农场自己的 `Address.ini` 基座与命名点，
  已在 `LelantineFarmProtocol.cs` 注释里逐条写明。
* 外观字 `0x211`（抓包里先锋队队长所在对象的 WarField 类外观字）。
* 放置走版本链：**V7 冻结**，新增 `NpcContentBaselineV8`（398 条，
  `ExpectedRevision = C088E365A7D41B41663986237000FEC636CD31C34938D71CFD8A57F9D5BDA93C`），
  对话新增 `NpcDialogueBaselineV24`（文本 398、路由 36、菜单 93）。启动日志实测：
  `[npc-content] … revision=C088E365… entries=398`、
  `[npc-dialogue] … revision=4F17684A… texts=398 routes=36`。

### 1.3 农场窗口对话（对话号 47 = `NpcFunFarm.lua`）
| 点击 | 应答 | 说明 |
|---|---|---|
| 首开 / 页请求（选择字 < 0） | `101, 102, 103, 104` | 抓包原样 |
| 101 捐赠宠物卵 | `111`（捐赠页） | 抓包 `{47,111}` |
| 102 查看战场排名 | `11,12,13` 带值 | 见 §1.5 |
| 103 战场介绍 | `31,32,33,34` → `60/62/63/64` | 抓包 `{31..34}`、`{60/62/63/64}` |
| 104 查看阵营积分 | `23,24` 带值 | 抓包 `{23,24}` |
| 112 捐赠身上所有犬宝宝 | 按槽位顺序逐堆捐（单次上限 99，逐堆按各自资质计分） | 按钮本义 |
| 确定（提交） | 见 §1.4 | 实测 |

### 1.4 捐卵（含三处真实编码，全部实测）
* **确认字 = 0**：窗口的"确定"把点击路径首字发成 `0`（`WindowConfirmSubId`）。
* **输入数量在 payload + 0x38**：不是路径字里的数字。该偏移是本仓库既有的实测约定
  （`ScriptedNpcDialogueCatalog.DialogAmount`，2026-09-23 公会祭坛量得：10/123/5000/
  12345/100000/123123 都落在这个字上，没输入时是 -1）。
* **放进框里的卵 = 参数 6 的背包坐标**：`bagPage * 100 + pageSlot`，解码见
  `LelantineFarmProtocol.TryResolveSubmittedEggSlot`，复用
  `PetManagerProtocol.TryResolveAppearanceChangeMutation` 的同一条客户端约定
  （文本+道具控件页的 A1 动作）。实测：槽 42 → `118`，槽 41 → `117`。
* **计分**：只认三种资质 → 懦弱(1)=1 分、理智(5)=10 分、热情(8)=100 分；**其它资质拒绝计分**
  （不做区间外推）。资质就是 `character_items.item_quality`（`PetAptitude`）。
  **用户指定**（用户明确"只能按我指定的，不允许自己改档位"）。
* **单次 1–99 个**（客户端脚本自己的"每次输入值必须在1~99"）。
* 拒绝用脚本自带文案：`53` 越界 / `52` 该资质卵不足 / `54` 框里没有卵。
* 扣卵只扣**玩家放进框里的那一堆**（SQL 按 `slot_index` 锁定单堆，质价按该堆
  `item_quality`）。

### 1.5 两套积分与查询
| 查询 | 客户端选择子 | 显示 |
|---|---|---|
| 查看战场排名 | 11 / 12 / 13 | 个人积分 / 最高分 / 当前排名 |
| 查看阵营积分 | 23 / 24 | 斯巴达总分 / 雅典总分 |

* **数值编码**：客户端对每个号算 `(SubID - 选择子) / 1000`，所以服务端发
  `选择子 + 分数 * 1000`（`LelantineFarmProtocol.EncodeScore`）。依据：客户端
  `NpcFunFarm.lua` 的 `Index == 2` 分支（`math.mod(SubID,1000)==11` →
  `FRAM713..((SubID-11)/1000)`，12/13/23/24 同构）。
* **阵营积分 = 同阵营所有个人积分之和**（用户规则），由视图
  `lelantine_farm_personal_points` 直接求和得到，不存在第二份累计值。
* 最高分与排名：客户端排名页只有**一条**最高分行（`FRAM714`，位置 25,110），
  所以最高分取**全战场（双阵营）最高个人积分**，排名与它同序，两者天然一致。

### 1.6 击杀积分
* 地图 42 上：普通怪 1 分、精英 10 分、Boss 1000 分（文案 `NF_L0_FRAM462` 原文）。
* 普通怪有"不低于自身 10 级"限制（精英/Boss 无此限）。
* 分值是**服务端按已发布怪物排名**判定，不采信客户端。
* 写入 `lelantine_farm_kill_points`（主键 `character_id + faction`）。

### 1.7 捐卵广播（屏幕中间黄字）
| 项 | 值 | 依据 |
|---|---|---|
| 通道 | opcode **10038**（`PacketBuilder.PythonNote`，137 字节） | 服务端既有通道；抓包共 916 帧同形广播 |
| 类型 | **33**（`SrvMsg_NOTE_181`） | 客户端 `SrvMsg.lua:44` |
| 频道 | **0 = 屏幕中间** | `SrvMsg.lua:4` `CHANNEL_MIDDLE` → `AddProclaimMessage_UTF8` |
| 名字字段 | 捐卵角色名（帧 +9，64B） | 抓包 note 帧同布局 |
| 内容字段 | `51070#51090#<分数>`（斯巴达）/ `51080#51090#<分数>`（雅典） | `SrvMsg.lua:1106-1108` 的拼接顺序 + `790-806` 消息表 |
| 显示 | 「玩家名 捐献犬宝宝宠物蛋，斯巴达阵营获得110积分！」 | `LuaText.lua` `SM_51070/51080/51090` |
| 触发 | 单次捐卵得分 **> 100** | **用户指定（非抓包复原）** |
| 范围 | 当前地图所有人（含捐献者） | 用户要求"地图内所有人都能看到" |

**线上不传中文**：客户端用三个消息号拼出整句，所以黄字中文正常显示。
`tools/find_farm_broadcast.py` 是本次为此写的取证工具（全 12 份抓包逐帧扫描）。

### 1.8 数据库（新表 + 视图）
迁移必须在运行时目录里（`*sql` 那份是历史 bootstrap，不参与运行时迁移）。

| 对象 | 迁移 | 语义 |
|---|---|---|
| `lelantine_farm_donations` | `20260926_200_lelantine_farm_points` | 每笔捐卵流水：角色、阵营、物品、数量、得分 |
| `lelantine_farm_kill_points` | 同上（`210` 改主键） | 击杀个人分：主键 `character_id + faction` |
| `lelantine_farm_personal_points`（视图） | `20260926_210_lelantine_farm_personal_scores` | 个人积分的**唯一定义**：捐赠流水 + 击杀分按角色/阵营求和 |
| ~~`lelantine_farm_faction_points`~~ | `210` 里 `DROP` | 旧的"只累加捐赠"的阵营总数，与"阵营分=个人分之和"冲突，已删除 |

同一迁移还把击杀分主键从 `character_id` 改为 `character_id + faction`：不然换阵营后
同一行会混入两个阵营的分。个人积分读取全部 `::bigint`（见 §3 坑 7）。

---

## 2. 未实现 / 明确不做（不要当成已完成）

1. **网兜发放（奈托/军需官"领取网兜"）**：用户指示"第二步不用做"。点该分支仍返回脚本自带的
   `92`（"我不是已经给你网兜了么"）。**但网兜可以买**：军需官商店已按抓包 892 字节原帧
   上架 `10080`（木质网兜）/`10081`/`10082`/`10083`/`10084`，货币为**银币**。
2. **克西丝（`Lelantine_Farm_002`）宠物评比**：用户指示"客户端条件齐备才做"，
   目前未证明条件齐备（需要宠物属性/最低属性评比、5000 绑定金币奖励、仙宠灵露换取），**未做**。
3. **精英/Boss 特殊掉落**：用户指示"不做，后续用 GM 自己加"。
4. **45 分钟结算与胜负奖励**：`71/72/73` 领奖、胜负经验/宠物经验/天赋公式、称号
   （利兰丁守护神 `SM_51160`、地狱犬狩猎者 `SM_51010/51020`）、克西丝 5000 绑定金币
   （`LD_10003`）、地狱犬 BOSS 本体，**均未做**。本次只做用户点名的入图、对话、两套积分与查询、广播。
5. **`SrvMsg_Lelantine_msg` 里其余消息号**（`5201-5204`、`5301-5303`、`5402/5403`、`5602`）
   对应的战场提示广播**未接**（属于第 4 项的结算流程）。
6. **广播的视觉验收**：帧已按客户端脚本构造并有单测，但最后一次部署后用户尚未回报肉眼结果；
   若不出字，先看日志 `[farm] donation proclaimed … recipients=N` 判定是路由问题还是类型问题。
7. 农场地图**不允许阵营 PK**（文案 `NF_L0_FRAM462` 末句）未做专门限制。

---

## 3. 踩过的坑（服务器反复崩溃/掉线的完整清单）

> 顺序基本就是实际踩到的顺序。每条都写"症状 → 根因 → 现在的做法"。

1. **改了源码没重建镜像**：Dockerfile 是 `dotnet publish` + `COPY --from=build`，`docker restart`
   无效。**现在**：每次改动都 `docker compose --profile legacy-raw up -d --build server`。
2. **NPC 对话发布自检算式写错**：我按"公式推"算 `ExpectedMenuEntryCount`，得 131，实际 95，
   启动即拒绝发布→重启循环。**现在**：派生值全部改成从数据求和（`Profiles.Sum(...)`），不写公式。
3. **C# 静态字段初始化顺序**：`static readonly` 派生字段若声明在用它的字段**之前**，
   会算成 0 或抛 `TypeInitializationException`。**现在**：`ExpectedTextCount` → `Profiles` →
   `ExpectedMenuEntryCount` → `Bindings` → `ExpectedRouteCount` → `ExpectedHashedEntryCount`
   严格按依赖顺序声明（文件里有注释）。
4. **发布前置哈希白名单**：对话基线每次重发 revision 变一次，DB 里已发布的旧 revision 不在
   白名单就被拒→启动失败。**现在**：白名单里保留 V23 原始 + 依赖绑定 + 历代中间哈希；
   本次 V8/V24 发布后 DB 已是 `4F17684A…`，启动走"using official database publication"不再重发。
5. **DB 里残留中间态发布**：曾出现 DB 存着被拒的中间 revision，只能先把
   `npc_content_publication` 指回上一版再让它重发。**现在**：白名单 + 不改历史发布。
6. **禁止修改已应用迁移的 SQL**：checksum 是钉死的，改了就与 `schema_migrations` 不符。
   **现在**：农场积分规则变化写成**新迁移** `20260926_210_…`，不回头改 `200`。
7. **`SUM(bigint)` 返回 numeric → 运行期 `InvalidCastException` → 玩家掉线**（用户实测
   "提交后直接掉线"）。日志 `[game-fault] opcode=10069 … Unable to cast object of type
   'System.Decimal' to type 'System.Int64'`，随后 `[game] marked offline`。
   **现在**：所有聚合读取显式 `::bigint`（视图读取处有注释），并用 psql 验过返回类型。
8. **把"确认字"当数量**：确定点击的路径首字是 `0`，我早期把路径字当输入数量，导致
   "点确定没反应、卵不减、分不加"。**现在**：`WindowConfirmSubId = 0` 专门判定，
   数量读 `+0x38`，并有单测锁死"确认字永远不能当数量"。
9. **按槽位顺序扣卵**：早期实现忽略"玩家放进去的是哪一堆"，永远先扣第一堆（弱懦），
   于是"捐热情却扣弱懦、只给 1 分/个"。**现在**：读参数 6 的背包坐标，只扣那一堆，
   质价按该堆 `item_quality`；实测帧写成了单测。
10. **抓包结论曾经是错的**：我一度断言"抓包里没有农场 `10020` 帧、没进过农场图"，
    并因此**编造**了 NPC ID 5501–5508。实际是我搜十六进制时漏了单独的 `Lelantine_Farm`
    且把多帧 `CLEAR` 块当成单帧。**现在**：ID 全部换成抓包实测的 5615–5622，
    坐标除 5617 外明确标 authoring；取证工具 `tools/extract_farm_placements.py`、
    `tools/list_clicked_farm_npcs.py`、`tools/find_farm_broadcast.py` 留档可复现。
11. **迁移目录清单棘轮**：`PostgresMigrationFoundationChecks` 断言目录条数与 ID 顺序，
    我手工只补了农场两条，实际目录是 171 条。**现在**：按 DB `schema_migrations`
    的 `applied_at` 顺序重新生成 171 条清单，该检查已 PASS。
12. **`Check.Equal<T>` 需要 `IEquatable<T>`**：枚举不能直接 `Check.Equal`，
    要用 `Check.True(a == b, …)`（`CapitalNpcShopCurrency`、`BattlefieldDestinationKind` 踩过）。
13. **商店货币字节**：抓包帧里货币字节是 `1`，而 `TryGetShopCurrency(byte)` 没有 1 这一档
    （2=金/3=银/4=绑定金/5=荣誉/6=积分/7=勋章）。**现在**：只改第 9 字节为 3（银币），
    其余字节原样重放，并在代码里写明原因。
14. **`TryGetShopCurrency(service, …)` 返回白名单**：新增军需官 service 时忘了加白名单，
    接口返回 false（被新单测抓住）。**现在**：`IsShop`/`TryGetShopCurrency`/白名单三处都有。
15. **启动日志只打异常类型**：`PostgresWorldContentBootstrapper` 里两个 try/catch 是
    临时诊断，但**故意保留**——因为结构化启动日志只输出 `invaliddataexception`，
    真正的拒绝原因（第 2/4/5 条那些）只有这两行 `[npc-content] publication refused: …`
    能看见。
16. **`dotnet build` 缓存**：改完立刻跑检查可能用到旧产物，`.NET 10` 下出现过；
    必要时加 `--no-incremental`。
17. **检查基线要对照历史失败集**：全量跑固定有一批**与农场无关**的历史失败
    （战斗公式、架构棘轮、B18 网关抖动等）。判断"我有没有引入新失败"必须比对集合，
    不能只看总数。本次每轮都用"新增失败 = 0"作为标准。

---

## 4. 复现与验证

### 4.1 GM 工具（`tools/Godswar.LootTool`，第一个页签「利兰丁农场」）

同一 EXE 里现在有三个页签：**利兰丁农场 + 怪物掉落表 + 宠物档位**（发布物 `dist\GM工具.exe`）。

```powershell
cd D:\Godswar-Reborn-main\tools\Godswar.LootTool
.\publish-loot-tool.ps1          # 产出 dist\Godswar.LootTool.exe 与 dist\GM工具.exe（同一份）
.\start-loot-tool.ps1            # 开发期直接开窗口
.\start-loot-tool.ps1 -SelfTest  # 数据层自测（含农场只读+演练写入）
```

农场页能做什么（数据层全可改，策略值只读）：

| 子页 | 操作 | 写到哪 |
|---|---|---|
| 角色积分总览 | 按名字/ID 查；个人分、捐卵分、击杀分、排名、阵营总分 | 只读 |
| 捐卵流水 | 改分值 / 删行 / 给角色加一笔**调整行**（`item_id = 0`） | `lelantine_farm_donations` |
| 击杀积分 | 设值 / 清零 / 删行 | `lelantine_farm_kill_points` |
| 背包农场物品 | 看卵与网兜（含资质）；发卵（资质 1/5/8 任选）与网兜；删堆/删该物品全部堆 | `character_items` + `character_item_audit`（`source='gm-tool'`） |
| 清空/重置 | 清空某角色、清空某阵营的全部农场积分 | 两张流水表 |
| 只读：规则常量 | 16 条规则常量，**值从服务端源码读回**（不是工具内副本） | 只读 |
| 只读：已发布 NPC | `npc_content_publication` 头版本下地图 42 的 8 个农场 NPC 与坐标 | 只读 |

设计约束（有意为之）：
* **工具没有"直接改阵营分"的操作**——阵营分是流水派生值，改流水即改阵营分，
  避免出现第二份会漂移的数字。
* 所有写入都在事务里；发放/删除写 `character_item_audit`；`--dryRun` 全部走回滚事务。
* 目标角色**在线**时不要用发放/删除（服务器内存里的背包会覆盖写入）；
  改积分台账不受此限（服务端每次现查）。
* 自测里有两个**演练写入**（加分 +发卵），跑完总分与背包不变，用来证明写路径可用。

自测实测（对 `godswar_local`）：

```
[通过] 农场积分 schema 存在（视图 + 两张流水表）。
[信息] 阵营总分：斯巴达 903｜雅典 0｜有分角色 1 个｜捐卵流水 8 行｜击杀行 0 行
[通过] 阵营分 = 同阵营个人积分之和（斯巴达 903、雅典 0）；最高个人积分 903。
[通过] 当前发布的农场 NPC 8 个：Lelantine_Farm_003/5615 … Lelantine_Farm_008/5622
[通过] 从服务端源码读到 16 条农场规则常量。
[通过] 演练写入（给 test +12345 分）没有落库，总分不变。
```

### 4.2 服务端与检查

```powershell
# 编译 + 只跑农场相关检查
dotnet build tests/Godswar.Server.ProtocolChecks/Godswar.Server.ProtocolChecks.csproj -c Debug
dotnet run --project tests/Godswar.Server.ProtocolChecks -c Debug --no-build -- "Lelantine"

# 全量（对照历史失败集）
dotnet run --project tests/Godswar.Server.ProtocolChecks -c Debug --no-build

# 部署（必须重建镜像）
docker compose --profile legacy-raw up -d --build server
docker logs godswar-server --tail 50
```

取证工具（全部可重跑）：

```
python tools/extract_capture_window.py --from 21:00 --to 21:10 --opcodes 10067,10069,10070
python tools/trace_npc_chain.py 5615
python tools/list_clicked_farm_npcs.py
python tools/extract_farm_placements.py
python tools/find_farm_broadcast.py      # 广播取证（全抓包逐帧扫 10038 / 消息号）
```

实测捐卵/查询的服务器日志特征：

```
[farm] click character=test npc=5620 key=Lelantine_Farm_006 faction=sparta sub=0 subId=101 amount=2 args=[0,…]
[farm] donation accepted character=test faction=0 slot=42 eggs=2 points=200 factionTotal=… characterTotal=…
[farm] donation proclaimed character=test faction=0 points=200 map=42 recipients=N
[farm] personal score query character=test faction=0 personal=… highest=… rank=…
[farm] faction score query character=test faction=0 sparta=… athens=…
```

**本次全量检查：455 通过 / 20 失败 / 98 跳过。** 用改动前的失败集合逐条对比：
**新增失败 = 0**。相比上一轮，`PostgreSQL migration safety foundation`（迁移目录条数/顺序）
已在本轮修好；`B18C2 semantic gateway real-socket host integration` 是已知的真 socket 抖动
（同一条在上一轮失败、这一轮通过）。剩余 18 条是与农场无关的历史失败
（战斗公式、架构棘轮、NPC 发布金哈希、B20 持久化棘轮等），改动前就在失败。

---

## 5. 客户端证据索引（本机客户端安装目录）

| 文件 | 用到的位置 |
|---|---|
| `Localization/zh_cn/UI/XML/NpcFun/NpcFunFarm.lua` | 对话号 47 全部分支；`Index==2` 的 171-222 行是积分编码（`(SubID-选择子)/1000`） |
| `Localization/zh_cn/UI/XML/SrvMsg.lua` | 4-6 行频道；44-52 行 note 类型（`SrvMsg_NOTE_181 = 33`）；790-806 行 `SrvMsg_Lelantine_msg`；1106-1108 行广播拼接；1140-1146 行频道分发 |
| `Localization/zh_cn/UI/Base/LuaText.lua` | 935-1039 行全部农场文案（`Y7003/Y7004/Y7005`、`FRAM###`、`SM_510xx/511xx`、`LD_1000x`） |
| `Localization/zh_cn/UI/XML/NpcFun.xml` | `FirstWin` 窗口：`Text1..4`、`Button1..12`、`ItemBtn1`、`ButtonA1/A2`（确定/取消） |
| 客户端 `ItemColor.xml` | 资质表：1=懦弱的、5=理智的、8=热情的、14=众神的 |

---

## 6. 数据来源纪律

* 所有协议号、对话号、拒绝文案、坐标点、物品 ID、积分值，都在代码注释里标注
  `文件:行号` 或抓包时间戳。
* 明确区分三类来源：
  * **抓包实测**：NPC 对象 ID 段、`5617` 的坐标、入口 sub id、对话号 47、商店帧字节、
    公告帧形状；
  * **客户端发布数据**：文案、资质表、note 类型/频道/消息号、积分编码算式、
    背包坐标算式；
  * **用户指定**：卵的三档分值（1/10/100）、"其它资质不给分"、阵营分=个人分之和、
    广播阈值 >100、"全天可进入"、跳过的功能范围。
* 未找到的一律写"未找到"：参考服的农场广播实例（抓包内不存在）、
  农场 NPC 除 5617 外的坐标、结算奖励公式的最终取值。
