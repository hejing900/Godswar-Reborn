# 港湾遇袭 entry route (2026-09-29)

接通了"副本召集官 → 港湾遇袭"的入场线路。怪物与掉落**不在本次范围内**（由运营用
GM/内容工具往地图里发布），所以本次只做准入、分档、落点、副本生命周期与中止出口。

## 抓包与客户端证据（都是客户端自带数据，逐条可复核）

| 项 | 值 | 出处 |
| --- | --- | --- |
| 入口按钮 | 根 16 → 单页 230 | 9-28 抓包；`InstanceCallerProtocol.HarborAttackRootSubId/PageSubId` |
| 页面文案 | `▽港湾遇袭(50级以上玩家可进入)` | `D:\Godswar Origin\Localization\zh_cn\UI\Base\LuaText.lua:3905`（`NF_EM_B230`） |
| 另一档 | `▽港湾遇袭(30-60)`（本服务端不发放） | 同上 :3904（`NF_EM_B229`） |
| 页面正文 | `我们的港口被破坏…英雄们出发吧！` | 同上 :3901（`NF_EM_T0229`） |
| 页面结构 | `Index==1 SubID==16` 只画按钮；`Index==2` 的 229/230/231 各自成页 | `D:\Godswar Origin\Localization\zh_cn\UI\XML\NpcFun\NpcFunRepetition.lua:34-41,129-144` |
| 地图 | 208 `Salame` = 被攻击的海湾1（客户端场景 **229**）；209 `Salame2` = 被攻击的海湾（场景 **230**） | `State/MapTemplateSeed.Generated.cs:97-98`；`docs/地图编号对照表-20260928.md:202-203` |
| 终局 boss | **丝希娜 = Christina**（`B_bossSA(Q)_mage_018`） | zh_cn `LuaText.lua:712`「丝希娜：我们会再见的。」↔ en_us `LuaText.lua:898`「Christina: We will meet again.」；`MonsterTemplateSeed.Generated.cs:1156,1168` |
| 骷髅王 | `B_bossSA(Q)_skeleton_001` = 血腥骷髅（Bloody Skeleton） | zh_cn `LuaText.lua:710-711`；同上 :1155,1167 |

等级不足时仍回参考服原话（`1510`，`NF_L0_R1510`）——9-28 抓包点击该页得到的正是这句，
说明参考服确有此副本、只是抓包角色等级不够。

## 本服务端规则（运营决定，非抓包值）

| 规则 | 值 |
| --- | --- |
| 等级分档 | 队长 **50–69 → 208**；**70+ → 209** |
| 等级门槛 | 全员 ≥ 50 |
| 人数 | 至少 3 人，上限为队伍上限 5 人 |
| 每日次数 | 每人 **1 次**，无付费重试（`free_entry_limit 1 + paid_retry_limit 0`） |
| 时限 | **30 分钟**，到期后全员传回本阵营主城 |
| 落点 | 208/209 共用 **(118, 0)**，见下 |

分档取**队长（申请者）等级**：客户端只回传一个页号，无法区分两档，所以地图由服务端按申请人
等级选择。若要改成"按队内最高等级"，只需改
`InstanceCallerProtocol.ResolveHarborAttackDestination` 的入参。

## 落点是怎么定的

客户端 `Localization/en_us/Monster/Salame/Address.ini`、`Salame2/Address.ini` 的
`AddressCount` 都是 **0**，即客户端没有发布任何到点坐标；参考服坐标也不可得。因此落点是从
客户端碰撞块表反推的作者值：

1. 定位块表：`Map/Salame.hmp`（9,098,632 字节，SHA-256
   `7E8F66DBD6380EA4A8F35A4F291DBB106AEF81DA3D189B726FCBD848A95429C3`）与
   `Salame2.hmp` **逐字节相同**；表头 `(128,128,4.0,4.0)`；块表位于偏移 **185,732**，
   长度 2048×2048（0=可走，非 0=阻挡）。
2. 偏移规则用仓库里两张已钉死的图校验：`Fane.hmp → 262432`（
   `tools/ExtractWonderlandNavigation.py`）、`Medusa_Island.hmp → 356684`
   （`docs/medusa-island-client-terrain-audit.md`）。再用仙境已文档化的三个锚点反验投影：
   `(169,-216)`、`(159,-163)`、`(-15,-185)` 在正确偏移下全部可走，偏移差 60 字节时
   其中两个变阻挡。
3. 投影：`col = floor((X+256)*4)`，`row = floor((256-Z)*4)`，`index = row*2048+col`。
4. 取整张图净空最大的点：**(118, 0)**，方形无阻挡净空 **21.75** 单位（离线计算的最大值）。

怪物一律 Y=0，与现有三个副本一致（客户端 `CTerrain` 的平面转换把 Y 写 0）。

## 代码改动

| 文件 | 改动 |
| --- | --- |
| `Domain/World/Content/InstanceCallerProtocol.cs` | `HarborAttack` 种类；208/209、场景 229/230、50/70 级分档、最少 3 人、落点常量；`ResolveHarborAttackDestination`、`TryResolveHarborAttackEntry`；目的地新增 `ClientSceneId` 与 `MinimumPartySize` |
| `Domain/World/Instances/DynamicDungeonContentMapPolicy.cs` | 208/209 进入动态副本图集合；新增 `IsHarborAttackMap` |
| `Application/WorldInstances/HarborAttackPolicy.cs` | 30 分钟时限与面板上限 |
| `Application/WorldInstances/LegacyInstanceDailyEntryContracts.cs` | 第三种 kind 的策略；免费次数改为按 kind（港湾 1，其余沿用 3） |
| `State/DatabaseMigrations/...HarborAttackDailyEntry.cs` | `20260929_216`：按**约束定义**（不是名字）找到两张表上的 `instance_kind` 检查并替换为 `BETWEEN 1 AND 3`，插入 `(3, 1, 0)` |
| `Game/GameClientHandler.InstanceCaller.cs` | 页 230 且等级达标 → 解析目的地并进入倒计时；等级不足照旧落到 1510 |
| `Game/GameClientHandler.InstanceEntryCountdown.cs` | 入场窗口场景号改为读目的地自带的 `ClientSceneId`（不再硬编码 224/227） |
| `Game/GameSessionRegistry.LegacyInstanceEntry.cs` | 人数改为"上限 + 下限"（下限取目的地，上限取 `PartyProtocol.MaximumMembers`） |
| `Game/GameClientHandler.LegacyInstanceEncounter.cs` | `HarborAttack` 分支启动副本运行 |
| `Game/GameSessionRegistry.HarborAttack.cs`（新） | 运行记录、面板发布（10232/10218/10229）、到期/中止后传回主城、空实例退役 |
| `Game/GameSessionRegistry.MonsterWorld.cs` | 世界 tick 调用港湾推进 |
| `Game/GameClientHandler.HarborAttackTermination.cs`（新） | 面板"终止"与 12 字节终止请求的接管 |
| `Game/GameSessionRegistry.WonderlandChests.cs` | **修复本副本原有的编译缺口**：补回测试引用的 `AddWonderlandTreasureChests` |

### 中止（投票）

沿用客户端既有的两个原生终止控件（10313 面板动作 0 / 10221 十二字节请求），**不改客户端**：

- **单人在副本内**：1 票 > 半数 → 确认即结束。
- **多人**：每个在副本内的成员点一次该控件 = 一票赞成；赞成数 **> 副本内当前人数的一半** 时才中止。
  未通过时向全团广播一行系统提示（`10169`）显示 `已同意 x/y`；通过后广播通过提示并送全员回本阵营主城。
- 判定基于"**当前在副本内的人**"，所以队员陆续离开后，剩下的人不会被卡住。

### 队员入场：与队长同一套 60 秒窗口

队长的申请现在会把**同一对原生入场封包（10222 + 10216）**发给队伍里其他成员，即队员看到与队长完全相同的
"进入副本"窗口（客户端零改动）：

- 队员在自己 60 秒内点"进入" → 记为已确认，随队长一起进入。
- 队员不点 → 窗口自行关闭，**不进入**，并且**不扣当日次数**（走既有的
  `ReleaseLegacyInstanceDailyEntryMembersAsync` 释放路径，与其它副本"没进就不扣"一致）。
- 掉线/拒绝/队长取消 → 窗口一并关闭（10231 清窗）。

### 副本内死亡

死亡后在副本入口 `(118, 0)` 原地复活，恢复 10% 生命/魔法，副本计时与队伍不变；只有本地角色的免费复活会被接受，
重复请求不会推进生命代数。副本已到期或被中止后不再原地复活（此时由回城流程处理）。

### 副本中止（历史形态，已废弃）

最初的实现是**团长单人中止**，已被上面的投票取代。

## 验证

- `Godswar.Server` Debug 与 Release 构建：0 警告 0 错误；测试工程同样 0 警告 0 错误。
- 新增 3 项检查全部通过（均为 Debug 实跑）：
  - 「港湾遇袭 party entry windows, confirmed-only admission, abort vote, and in-run revival」
    ——实跑覆盖：队员收到与队长相同的窗口、只有点了进入的队员入场、没点的队员留在主城**且其次数被释放**、
    1/2 票不中止、2/2 票中止并送回主城、副本内死亡在 `(118, 0)` 复活。
  - 「港湾遇袭 entry route, level bands, roster floor, and daily allowance」
  - 「PostgreSQL migration safety foundation」（含港湾迁移内容断言）
- 迁移在**一次性数据库**上跑完全部 177 条迁移：`legacy_instance_settings` 出现
  `(3, 1, 0)`，两张表的 `instance_kind` 约束都变为 `BETWEEN 1 AND 3`，插入 kind=4 被拒。
  该临时库随后删除，未触碰开发库。
- 全量协议检查：**456 通过 / 22 失败**（接手时基线 439 / 37）。与基线逐项对比**未引入任何新失败**，
  并顺带修掉 15 项既有失败——其中大部分由本次修复的一个回归引起：拆分
  `AddWonderlandInstanceNpcs` 时丢掉了"仅在仙境运行中注入"的判断，导致每次进图都会把仙境传送 NPC
  塞进当前地图名单（这也是 8/9 项 Atlantis/Wonderland 检查在早期基线里失败的原因）。
  其余 22 项在基线与本次改动后**同样失败**，属本副本既存状态。

## 部署记录（2026-09-29 UTC 16:41）

| 项 | 值 |
| --- | --- |
| 镜像 | `godswar-reborn-main-server:latest` |
| 镜像摘要 | `sha256:310abd0057289e79c8da579dec71eaafa9290f994929b6c53311c9f0179b3ccc` |
| 源码 commit | `d1935c8`（工作树含本次改动） |
| 容器 | `godswar-server` Up (healthy)，restarts 0，启动错误行 0 |
| 端口 | 未变：`127.1.1.110:5999`、`127.1.1.110:7000` |
| 运行库 | **`godswar_local`**（compose 用 `.env` 覆盖了库名；`godswar` 是另一个陈旧库） |
| 迁移 | `[db] applied schema migration 20260929_216_harbor_attack_daily_entry`，库内 177 条，head 为 216 |
| 生效策略 | `legacy_instance_settings` = (1: 3/1)、(2: 3/NULL)、(3: 1/0) |
| 实机 | 启动后已有真实客户端 `test` 登录、发技能、回城传送正常 |

备份与回滚说明在 `backups/harbor-attack-<时间戳>/`（含 `DEPLOY-README.txt`、`godswar_local-postdeploy.dump`）。
注意：**部署前的那次备份抓错了库**（抓的是 `godswar`，不是运行库 `godswar_local`），因此 216 号迁移没有迁移前快照；
该迁移是纯增量（放宽 `instance_kind` 约束 + 插入一行），`DEPLOY-README.txt` 里给了逐条回滚 SQL。

## 尚未做（下一步）

1. **60 秒没点进入的队员如何补进**：文章第 3 条要求团长在"交际面板 → 副本"里手动输入角色名邀请。
   目前没点窗口的队员就是没进（次数不扣），需要抓包确认该面板发出的 opcode 后才能做邀请。
2. **镜像上限与排队号码**：需要一个全局并发副本上限 + 队列，当前无上限。
3. 怪物与掉落：由运营用内容工具发布到 208/209。

## 需要实机确认的一点

投票依赖客户端把"副本进程窗口"里的终止控件也画给**非团长成员**。服务端接受任何在副本内成员发出的该控件，
但客户端是否给队员显示这个按钮，需要进游戏点一次确认；若客户端只给团长画，则投票需要换一个承载面。
