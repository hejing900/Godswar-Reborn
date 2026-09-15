# 任务系统当前状态（2026-09-13 记录）

> 这份文件只记录**当前实际行为**和**已核对的事实**。标注为「推断」的部分没有验证，不要当结论用。
> 第 1~6 节是修复前的状态；第 8 节是本轮修复（已部署）。

## 1. 当前实现到什么程度

| 步骤 | 状态 |
| --- | --- |
| 任务 518「[Lv1]初入斯巴达」接取 | 正常 |
| 任务 518 交付（NPC 5103 Sparta_106） | 正常 |
| 任务 519「[Lv2]与村长会面」接取 | 正常 |
| 任务 519 交付 | **失败**：走到该交任务的 NPC（5054 Sparta_057）点开窗口，没有任务选项 |
| 上线自动接取 | 已消除：登录快照在角色没有进行中任务时是空的 |
| 接取后重新上线 | **缺陷**：任务被放弃，要从第一个任务重新接 |

## 2. 已验证的服务端持久化（不是推断）

```
character_base:
  id=4  1v24123   quest_current_id=519   quest_completed_ids={518}
```

服务端把「518 已交付」「519 已接取」都正确写库了。所以「重新上线任务被放弃」不是服务端丢数据，
而是客户端在收到登录快照后没有把它当作进行中的任务。

## 3. 客户端实际包格式（本次从抓包逐字节核对）

偏移都从**整包开头**算，即 +4 是 4 字节包头（2 字节长度 + 2 字节 opcode）之后的第一个字。

| 包 | 长度 | 字段 |
| --- | --- | --- |
| C2S 10081 | 12 | +4 = 0，**+8 = 玩家点击的任务**（本客户端接取走这个包） |
| C2S 10082 | 648 | +4 = 客户端堆指针，+8 = -1，**+12 = 任务** |
| C2S 10083 | 20 | +4 = 句柄，+8 = 场景号 0x1AF720，+12 = 任务，+16 = -1 |
| C2S 10084 | 16 | +4 = 0，**+8 = 要交付的任务**，+12 = 0 |
| S2C 10090 | 2048 | +4 = 条数，+8 = 任务，+12 = 发放 NPC，+16 = 接手 NPC，+20 = 0 |
| S2C 10083 | 17 | +4 = 任务，+8 = 接手 NPC，+12 = 任务，+16 = 1 |
| S2C 10082 | 648 | +4 = 发放 NPC，+8 = 接手 NPC，+12 = 任务，+16 = 记录条数 |
| S2C 10084 | 12 | +4 = 接手 NPC，+8 = 任务 |
| S2C 10086 | 120 | +4 = 发放 NPC，+8 = 接手 NPC，+12 = 任务 |
| S2C 10076 | 356 | +4 = 下一个发放 NPC，+8 = 下一个任务 |
| S2C 10077 | 12+8n | +4 = NPC，+8 = 条数，然后 (任务, 可用标志) 每条 8 字节 |
| S2C 10080 | 12+4n | +4 = NPC，+8 = 条数，然后任务 ID 每条 4 字节 |

本次客户端抓包还确认了两点：

- 本客户端**不发 10083**，接取只走 10081（所以服务端不能依赖 10083 来记住"当前推荐任务"）。
- 本客户端登录时服务端**已经**在发 10077 / 10080 标记表（来自 NPC 内容基线）。已核对的 5103 与 5054 两张表：
  - 5103 的 10077（可发放）= {519, 522, 524}，10080（可交付）= {518, 521, 523}
  - 5054 的 10077（可发放）= {520, 521, 525, 527, 528, 529}，10080（可交付）= {519, 520, 524, 526, 527, 528}
  - **519 在 5054 的交付表里是存在的**，所以"窗口没有任务选项"不是这张表缺项。

## 4. 当前缺陷的根因（推断，未验证）

所有任务帧的**头部 ID 字段**已经按任务替换，但帧体里那段「记录块」仍然是抓包里 518 的内容：

- 10082 是从**记录条数**（+16）之后开始，步长 72 字节，物理 8 个槽位，只有前 N 个有效。
- 抓包里 518 = 1 条有效（首字 3876 = 新手礼包 Lv1），519 = 4 条有效（首字 1000/1400/1700/1800 = 四职业 1 级武器，即客户端文案「AcceptReward 您可以从以下物品中选择一个」的四选一）。
- 10090 的帧体里也有一段同型记录块，抓包 #104 中 3876 落在帧体 +108。

推断（**没有验证**）：因为 519 的接取应答仍带着 518 的记录块，
客户端里 519 这条任务的目标/记录是错的 —— 于是
(a) 到 5054 时不认为有可交付的任务，(b) 重新上线后把这条任务丢掉。
518 之所以整条流程能走通，正是因为那段记录块本来就是 518 的抓包内容。

## 5. 记录块的解码结论（子代理取证，未改任何代码）

完整报告：`D:\Godswar Origin\npc-translation\quest-record-decode.md`

- 步长 72 成立、记录边界成立。
- 记录首字是**物品 ID**（高置信）：3876 = `ItemBaseAttribute.xml` 的 `Novice1`，名称 `EquipName.dat` = `Newbie Gift Bag (Lv. 1)`；1000/1400/1700/1800 = 四职业 1 级武器。
- 记录内 +4/+8/+12/+16 以及那个 131 的语义**未确定**，子代理明确没有猜。
- 结论：这套奖励**必须服务端下发**，客户端 `Quest.xml` / `RookieQuestReward.xml` / 任务文本里都没有这些 ID。
- 抓包里只有 518、519 两条任务的记录块，**520 没有**。

## 6. 下一步（等指示，未动手）

1. 把记录块做成**每任务一张数据表**（任务 ID → 记录列表），所有任务共用一个拼包函数 —— 这是"奖励统一计算"的落点。
2. 518 / 519 的记录可直接取抓包字节；**520 需要再抓一次包或从参考服取**。
3. 登录快照的帧体记录块也要按当前任务替换，否则"重新上线任务被放弃"不会好。
4. 未完成的一件事：把真实客户端包在本地回放、断言服务端应答的自动化测试（刚开头就停了）。

## 7. 本次改过的文件（已部署）

- `src/Godswar.Server/Game/GameClientHandler.Quests.cs` —— 接取/交付全部按客户端发来的任务 ID 驱动；登录快照只发进行中的任务；交付后按抓包顺序回 10086→10076→10077→10080→10097。
- `src/Godswar.Server/Packets/PacketBuilder.QuestFrames.cs` —— 各帧按任务参数化；10077 / 10080 两张表由任务链推导生成。
- `src/Godswar.Server/Packets/PacketBuilder.QuestHandIn.cs` —— 只剩 10097 模板。
- `src/Godswar.Server/Protocol/Opcodes.cs` —— 修正并记录上述偏移表。
- `tests/Godswar.Server.ProtocolChecks/QuestProtocolChecks.cs` —— 断言改为按任务参数化的构造函数。

## 8. 本轮修复（已部署，全部有抓包依据）

### 8.1 「519 在 5054 交不了、窗口没有任务选项」

抓包铁证 —— 同一客户端点击三个 NPC 的服务端应答：

```
S2C 10067  30005327  e3130000  03000000 ... "Sparta_094"   5091 标志 = 3
S2C 10067  30005327  ef130000  03000000 ... "Sparta_106"   5103 标志 = 3
S2C 10067  30005327  be130000  00000000 ... "Sparta_057"   5054 标志 = 0
```

5054 的对话帧是「仅描述」窗口（标志 0），所以根本没有任务页。
修复：凡是**当前有任务可发或可交**的 NPC，一律用 `PacketBuilder.NpcQuestDialogOpenAck`（标志 3）
打开任务页，不再写死只有 5091/5103 两个 NPC。判断条件是任务链数据，不是 NPC 名字。

### 8.2 「重新上线任务被放弃，又要从第一个任务接」

抓包证明：23:21:59 客户端又发了一次接取 518（`C2S 10081 +8=518`），
服务端接了 → `quest_current_id` 被 519 覆盖成 518。
两个原因，都改了：

1. 登录时随 NPC 出生流下发的 10077 标记表是**世界内容**（所有玩家同一份，抓包里 5091 的 518 永远标志 1），
   不随角色进度变化 → 客户端永远看到 518 可接。
   修复：链上 NPC 的 10077 / 10080 表在发送前**按角色进度重建**（可用标志只给"当前可接的那个任务"，
   内容表原有的非链任务条目保留）。
2. 服务端的 `IsChainUnlocked` 对链上第一行无条件放行 → 已完成的任务还能再接。
   修复：已完成的任务一律拒绝；并且**正在携带的任务不会被顶掉**（接取请求若不是当前携带的任务就拒绝）。

### 8.3 验证

`Quest protocol framing` PASS，协议自检 443 通过 / 11 失败（还是原有那 11 个）。新增断言包括：

- 通用任务对话帧与抓包里的 5091 / 5103 对话帧**逐字节相同**；
- 用抓包里 5103 的真实 10077 / 10080 表 → 解析 → 重建 → 与抓包**逐字节相同**；
- 已完成任务的可用标志被清零。

### 8.4 仍未解决

10082 / 10090 帧体内那段 72 字节奖励记录块仍是抓包 518 的内容（见第 4、5 节）。
本轮修复不依赖它，但如果 519 交付后奖励显示不对，根因就在这里。

## 9. 对话标志位修复（已部署，有抓包依据）

### 9.1 问题

有路由功能的 NPC（例如 `Sparta_100` = 仓库管理员 Savva）在需要交任务时，点开只有 bank 选项，
没有交任务选项。

### 9.2 证据

参考服自己发的对话帧里，标志位是**位掩码**，并且发过叠加值（去重统计）：

| 标志位 | 含义 | 次数 |
| --- | --- | --- |
| 0x03 | 任务 | 223 |
| 0x04 | 商店 | 16 |
| 0x20 | 仓库/银行 | 5 |
| **0x23** | **银行 + 任务** | **1**（npc 5097 = Sparta_100 = Savva） |
| **0x07** | **商店 + 任务** | **3**（npc 5093 = Sparta_096） |
| 0x40 | 宝箱 | 1 |
| 0x200 | 功能列表 | 16 |
| 0x100 | 教学 | 1 |

三帧叠加值的 packed 字段（+12）都是 0，脚本键分别是 `Sparta_100` / `Sparta_096`。

### 9.3 修复

标志位改为**按位或**：NPC 当前有任务可发/可交时，把 `QuestOpenFlags (3)` 或进它原有的页面标志里。

- `PacketBuilder.WarehouseDialogOpenAck(..., extraFlags)` → 0x20 | 3 = 0x23
- `NpcDescriptionDialogOpenAck` / `NpcShopDialogOpenAck` / `NpcPrizeChestDialogOpenAck` / `NpcQuestDialogOpenAck`
  都加了 `extraFlags`
- `0x200`（功能列表）那一路**没有**叠加：抓包里没有 0x203 这种组合，不猜。

## 10. 尚未解决：任务目标（击杀条件）

### 10.1 现状

现在接取任何任务都会被标记为可交。但 518 / 519 / 522 / 525 这类是**纯对话任务**
（`Quest.xml` 里 `CreatureMapID=""`），立即可以交是**正常**的。
问题是击杀任务也一样能直接交。

### 10.2 客户端数据里的目标定义（已核对）

`Localization/en_us/Settings/Sys/Quest.xml`，任务链 30 条里：

- **20 条是击杀任务**（`CreatureMapID` 非空，`CreatureMapPos` 是目标坐标）：
  520(0: 186,8) 521(0: 139,52) 523(0: 188,111) 524(0: 162,198) 526(0: 117,104) 527(0: 56,133)
  528(0: 4 个坐标) 531/532/533/537/539/543/545/546/547(地图 4) 549/550/552(地图 13) 185(0: 186,-2)
- **10 条是对话任务**：518 519 522 525 529 530 534 538 548 551

### 10.3 缺口

1. **没有任何击杀任务的抓包。** 手上两份抓包只覆盖 518 / 519 两个对话任务，
   所以「服务端用什么帧告诉客户端目标已完成」这件事**没有参考样本**，按规矩不能猜。
2. **世界里没有对应怪物。** 地图 0 在 (186,8) 附近目前只有占位怪
   （`A_normal_stub_001` / 「Dumb Wood Man」共 3 只），没有 520 要杀的银尾蝎。
   就算做了服务端击杀计数，也没有真实目标可统计。

### 10.4 可选路线

- A（推荐）：抓一次参考服跑击杀任务的包（接取 → 击杀 → 交付），照参考服实现。
- B：先做服务端侧的击杀计数 + 交付拦截（客户端可能仍显示"可交"，但拿不到奖励），
  等有参考包再补客户端表现。

## 11. 奖励记录块数据化（已部署）

原本所有任务的 10082 / 10090 帧体都带着抓包 518 的奖励记录块。现已按任务替换。

- 记录区 = 4 个 72 字节槽位（288 字节）。10082 里在 payload +68（帧偏移 +72），
  10076 里在 payload +64（帧偏移 +68）——两个偏移都对着抓包核过：
  包 247 的 `240f0000`（3876 新手礼包）落在帧 +72。
- 数据表：`src/Godswar.Server/Domain/World/Content/StarterQuestRewardRecords.cs`，
  由 `tools/gen_quest_reward_records.py` 从抓包生成（包 247 = 518 一个槽，
  包 1373 = 519 四个槽 = 四职业 1 级武器四选一）。
- **没有抓包记录的任务保持模板原样**，不写空区：凭空造一段奖励区属于发明。
- 以后新增任务：往这张表加一行即可，不改代码。

验证（`Quest protocol framing` PASS，443 通过 / 11 失败仍为原有）：

- 518 的应答槽区与抓包逐字节相同，首字 3876；
- 519 的应答槽区与抓包逐字节相同，首字 1000、第四槽 1800（证明不再复用 518 的礼包）；
- 无记录的任务（如 520）槽区与模板一致。

## 12. 重新上线回到「等接第一个任务」的根因（已部署）

**加载侧少读了两个字段**，不是客户端问题。

服务端保存一直是对的（库里 `quest_current_id` 正常），但登录时读角色走的**不是**同一个查询：

- 写/列表/装备变更等走 `PostgresGameStore.CharacterColumns`（`src/Godswar.Server/State/PostgresGameStore.cs`）
  —— 这里之前加了 `quest_current_id` / `quest_completed_ids`。
- **登录**走 `PostgresCharacterSnapshotReader.Core.cs` 里的 `CoreCharacterQuery`，
  它的字段列表到 `COALESCE(cb.exchange_medal, 0)` 就结束了，**根本没有任务列**。

所以每次上线 `QuestCurrentId` 都是 0、`QuestCompletedIds` 都是空：

- 登录快照 count = 0 → 客户端认为没有任何进行中的任务；
- 可接任务 = 链上第一个未完成 = 518 → 回到「等接第一个任务」。

修复（4 处）：

1. `CharacterIdentitySnapshot` 增加 `QuestCurrentId` / `QuestCompletedIds`（用 `init` 属性，不动构造函数，避免扩散）。
2. `CoreCharacterQuery` 末尾加 `COALESCE(cb.quest_current_id, 0)`（序号 63）、
   `COALESCE(cb.quest_completed_ids, ARRAY[]::integer[])`（序号 64）。
3. `ReadCoreCharacter` 读这两个序号。
4. `CharacterLoadSnapshotHydrator` 把它们写进 `GameCharacter`。

新增回归护栏：`QuestProtocolChecks.CheckQuestStateIsLoadedEverywhere` 扫描上面两个源文件，
要求都包含任务列 —— 以后再往角色查询加任务字段，只加一处就会测试失败。

## 13. 工作进度存档（本次收工点，2026-09-13）

### 13.1 线上跑的是什么（已验证可用）

容器 `godswar-server` 跑的是镜像 **`godswar-reborn-main-server:quest-delete-ok-20260913`**
（id `17999d5b502a`）。这一版用户已实测通过：

- 518→519→520 任务链接取、交付、上下线持久化；
- 上线不再自动接取；完成过的任务不再重复接取；
- 有路由功能的 NPC（仓库 Savva / 商店）任务选项与原有功能**同时**出现（标志位按位或）；
- 任务窗口的 del 删除按钮有反应（服务端回 10083）。

可用镜像标签（回滚用）：

| 标签 | 内容 |
| --- | --- |
| `quest-chain-ok-20260913` | 任务链刚跑通 |
| `quest-dialog-flags-20260913` | 加上对话标志位位掩码 |
| `quest-delete-ok-20260913` | **当前线上版**，删除可用 |

### 13.2 工作区里没做完的部分（没编译进镜像、没部署）

正在做：**多任务持久化 + 击杀条件**。服务端**能编译通过**，但测试没跑绿。

已完成的代码：

- `State/DatabaseMigrations/PostgresSchemaMigrationCatalog.CharacterQuests.cs` —— 新迁移
  `20260908_146_character_quests`：建 `character_quests(character_id, quest_id, state, progress,
  accepted_at)`，并把旧的 `quest_current_id` / `quest_completed_ids` 两列**回填**成行。
  迁移表已注册（`All.Count` 146→147，`ExpectedIds` 已加）。
- `State/CharacterQuest.cs` —— `CharacterQuest(QuestId, Progress)` + `CharacterQuestStatus`（0 进行中 / 1 已完成）。
- `State/GameCharacter.cs` —— `QuestCurrentId` 换成 `List<CharacterQuest> Quests`。
- `State/PostgresGameStore.QuestState.cs` —— 一次语句写全部任务行（删除不在集合里的、upsert 其余）。
- `State/PostgresGameStore.cs` 的 `CharacterColumns`、`PostgresGameStore.Characters.cs` 的读取、
  `Infrastructure/Characters/PostgresCharacterSnapshotReader.Core.cs` 的 `CoreCharacterQuery`
  —— 都改成用 `character_quests` 的三个聚合数组（序号 58/59/60 与 63/64/65）。
- `Application/Characters/CharacterAccountSnapshot.cs` —— `QuestCurrentId` 换成
  `ImmutableArray<LoadedQuestSnapshot> Quests`。
- `Game/CharacterLoadSnapshotHydrator.cs` —— 水合多任务。
- `Game/GameClientHandler.CharacterRefresh.cs` —— `InstallUpdatedCharacter` 保留任务状态（防止装备变更时把任务清空）。
- `Game/GameClientHandler.QuestKills.cs` —— **新增**：怪物死亡时按目标坐标给任务记进度，
  进度用**位掩码**（每个目标一位），所以任意顺序击杀都能完成，同一坐标杀两次不能顶替另一个目标。
  挂钩点在 `GameClientHandler.Progression.cs` 的 `PrepareMonsterKillRewardAsync` 开头。
- `Game/GameClientHandler.Quests.cs` —— 改为多任务：不再"一次只能一个"，交付时**目标未完成则拒绝**
  （不发奖励、不清任务），登录快照发布**全部**携带任务。
- `Domain/World/Content/StarterQuestObjectives.cs` —— **生成**：20 条击杀任务的地图+坐标（来源客户端
  `Quest.xml` 的 `CreatureMapID`/`CreatureMapPos`），匹配半径 40。
- `Domain/World/Content/StarterQuestRewardRecords.cs` —— **重新生成**：记录区起点改为 payload **60**、
  每条 8 个 72 字节槽（576 字节），物品在槽 **+8**、标志在 **+32**。
- `Packets/PacketBuilder.QuestFrames.cs` —— `QuestSnapshot` 改为多任务（N 个 96 字节描述符 + N 条 72 字节记录）；
  奖励记录偏移改为 10082 帧 64 / 10076 帧 60。
- 生成器：`tools/gen_quest_objectives.py`、`tools/gen_quest_reward_records.py`（都在仓库里）。

### 13.3 收工时的确切状态

**（2026-09-14 更新：第 1 条已修完，测试全绿，代码就绪待部署）**

- `dotnet build src/Godswar.Server/Godswar.Server.csproj -c Release` → **成功，0 警告 0 错误**。
- 协议自检 → **443 通过 / 11 失败，11 个全是原有的**（Atlantis/Medusa/数据边界那几条）。
  `Quest protocol framing` **PASS**，含本次新增断言：
  - **单任务登录快照与抓包逐字节相同**（描述符帧偏移 8、记录帧偏移 104）；
  - 双任务快照的描述符与记录位置；
  - 奖励记录区 576 字节、物品在槽 +8（518 一个槽 = 3876，519 四个槽 = 1000/1400/1700/1800）；
  - 击杀目标：518 无目标、520 一个、528 两个、链上共 20 条击杀任务，坐标匹配命中/不命中；
  - 两个角色读取路径都必须从 `character_quests` 取任务（`quest.state = 0/1`）。

**部署被 5999 端口阻塞**：`docker-compose.yml` 把服务端映射在 `127.1.1.110:5999`，
而原版参考服 `gworiginsv.exe`（PID 4212，启动于 00:11:52）占着该地址，
`godswar-server` 因此停在 `Created` 起不来（此时经代理连 5999 会连到参考服）。
用户选择自己先关掉参考服；关掉后执行
`docker compose --profile legacy-raw up --build -d server` 即可。

历史（修复前）：曾为 442 通过 / 12 失败，唯一新失败是
`quest 518 reward area length: expected 288, actual 576` —— 记录区扩到 8 槽后期望值未同步，已修。

### 13.4 关键事实（复查时别再算错）

- **72 字节记录**：`+0=0 +4=0 +8=奖励物品 +12..+28=-1×5 +32=填充标志(01010101 已用 / 01000101 空) +36..+68=0`。
  这条结构在 **10082 和 10090 里完全一样**，只是所在区域起点不同。
- **10082**：60 字节头 + 8 条记录（帧偏移 64 起）；奖励物品落在帧 72（抓包包 247 的 `240f0000`）。
- **10076**：同型记录，帧偏移 60 起，只有 4 条。
- **10090**：payload `+0=条数`；帧偏移 8 起是 96 字节描述符（`+0 任务 +4 发放 +8 接手`）；
  帧偏移 `8+96N` 起是 72 字节记录。**N=1 与抓包逐字节相同**（有测试断言）。
  N≥2 是按同一结构推的：`4 + 96N + 72×27` 只对 N=1 成立（2048 装不下），所以记录跟着描述符走 ——
  **这一段没有参考样本，必须让客户端实测确认**（发布上限先设 12 个）。
- **删除仍未持久化**：客户端点 del 发的 `C2S 10083` 与它上线时自动发的**字节完全相同**，
  服务端分辨不出"查询"和"删除"，所以删掉的任务重上线会复活。要解决只能抓一次参考服的删除包。

### 13.5 下次接着做的事

1. 改 `QuestProtocolChecks.CheckQuestRewardRecords` 的 288→576 与 `CountFilledSlots` 判断，跑绿测试。
2. 起服务器 → 验证：同时接两个任务 → 上下线 → 客户端是否两个都还在（这是 13.4 里 N≥2 布局的实测）。
3. 验证击杀门禁：接 520 后不打怪**不能**交付；到 (186,8) 附近杀掉占位怪后**能**交付。
4. 抓包代理进程仍在跑（本次没关），数据库表 `character_quests` 在服务器启动时会自动建表并回填。

## 14. 2026-09-14 追加：多目标任务、monster id 0、斯巴达小区刷怪

### 14.1 已验证的新事实

- **客户端每个任务只维护"一个当前目标槽"**：怪物ID + 需求数，来源是接受帧（10082 的帧 +32/+48）
  和登录快照（10090 描述符 +40/+56/+68/+80）。10087 的 step 字段在参考服 4 个抓包里**恒为 1**，
  它是"本次击杀的增量"，不是"第几个目标"。所以：**一个目标做完、下一个目标没人发布，窗口就永远停在旧目标**。
- **monster id = 0 的任务**（生成器没解析出客户端怪物表 id）表现是：击杀**不计数**、窗口**没有自动寻路**。
  参考服 10087 用的就是客户端怪物表 id（520 的 Dumb Wood Man = 1027），所以这个字段必须是真 id。
- quest 528 是**双目标**：1×Addiya the Destroyer（1492）+ 8×`Fake Treasures`；任务文本叫 `Fake Treasures`，
  客户端怪物表里叫 `Juno's Box`（1023，map 0 有 46 只，模板 `A_normal_ark_001`）。

### 14.2 本次改动（已构建、回归 443 通过 / 11 既有失败，等待部署）

| 改动 | 文件 |
| --- | --- |
| 目标名与客户端怪物名不一致时，生成 `Match` 名并按它匹配击杀 | `tools/gen_quest_objectives.py`、`StarterQuestObjectives.cs`（重新生成） |
| 复数折叠补全（wolves→wolf、spies→spy、plains→plain、ies/ves 规则、去空格兜底），修掉 12 个 monster 0 中的 8 个 | 同上 |
| `ActiveSlot()`：登录快照报"第一个没做完的目标"，全做完才报最后一个 | `StarterQuestObjectives.Progress.cs`（新） |
| 击杀打满某个目标但任务未完成时，**重发一次任务快照**，把窗口的当前目标切到下一个 | `GameClientHandler.QuestKills.cs` |
| 快照发送方法改名 `SendQuestSnapshotAsync(reason, ct)`（登录传 `"login"`），帧内容不变 | `GameClientHandler.Quests.cs`、`GameClientHandler.LoginWorldEntry.cs` 调用点 |
| 回归守卫：528 的箱子目标名/id、`ActiveSlot` 行为、531/532/235 的 id、除 244/478/479 外不得有 monster 0 | `tests/.../QuestProtocolChecks.cs` |

仍然解析不出怪物 id 的 3 条（有意保留，不猜）：244 `Amazon Warriors`（map 16，表里只有 Amazon Scout/Fighters/Raider）、
478/479 `of Empusa's Dressing Boxes`（MinLevel=200 的废弃行，客户端 map 4 根本没有对应怪）。

### 14.3 斯巴达小区（map 4 / Sparta_Newbie）刷怪

- 生成器 `tools/gen_suburb_monsters.py`：以任务表坐标为刷怪中心，范围 = 到最近任务点距离的一半（夹 12~30），
  数量按地图 0 实测的"需求数→刷怪数"对应，按中心+内外圈均匀铺开，同点多怪种按相位错开。
- 产出：`npc-translation/suburb-spawn-plan.txt`（对照表）、
  `src/Godswar.Server/Infrastructure/WorldContent/SpartaNewbieSpawnPlan.Generated.cs`（19 个任务点、267 只怪）。
- 旧的 5 个硬编码练级区（160 只）已删除，`PostgresWorldContentReaderLoader.Monsters.cs` 改读生成表；
  发包、对象 ID（44001 起）、`Validate()` 校验全部复用原有代码。

### 14.4 待实测（重启后）

1. `1v24123` 打 **533**（Peninsula Bandits 15 + Bloodthirsty Blademasters 15，map 4）：
   打满 15 个 Bandits 时窗口应**自动切到 Blademasters 并从 1/15 开始跳**；
2. `1v24123` 的 **531**（Woodland Wolves，id 现为 1431）：窗口显示 `x/20` 且**有自动寻路**；
3. 若窗口仍不切换，下一步改用 10081 详情帧（`PacketBuilder.QuestObjectiveDetail`，已生成但从未使用）推进目标。

## 15. 2026-09-14 续：两个阵营的任务链 + 雅典新手图刷怪

### 15.1 阵营怎么分（从客户端数据测出来的，不是猜的）

- 客户端把两条进程线按 **任务 id 差 1000** 成对发布：id≤1000 的 589 条里 **588 条**有 +1000 镜像
  （518↔1518、531↔1531、549↔1549…），镜像两侧的 NPC 前缀也成对：
  `Sparta↔Athens`、`Sparta_Newbie↔Athens_Newbie`、`Peloponnese↔Marathon`、
  `Nemea↔Parnitha`、`Argolis↔Megara`、`Derveni↔Plataea`；
  两个阵营共用的区域（Thebes / Thermopylae / Parnassus / Mycenae / Troy / WarField）靠 id 分边。
- 判定规则（`tools/gen_sparta_quest_chain.py` 的 `camp_of`）：发放者/接手者前缀属于雅典侧 → 雅典；
  属于斯巴达侧 → 斯巴达；两边都不是（共用区域）→ id≤1000 斯巴达、>1000 雅典。
  只有 3 处例外，其中 2 条是 QuestScroll（物品触发，会被排除），另 1 条是真·雅典任务 1000。

### 15.2 结果

| 项目 | 之前 | 现在 |
| --- | --- | --- |
| 链行数 | 221 | **920**（斯巴达 459 + 雅典 461） |
| 有击杀目标的任务 / 目标数 | 79 / 79 | **402 / 421** |
| 现在能打通 | 32 | **66** |
| 新手图刷怪 | map 4（斯巴达小区）267 只 | map 4 267 只 + **map 2（雅典近郊）267 只** |

- 链文件 `StarterQuestChain.cs` 的 `Step` 增加 `Camp` 字段，`NextQuestId` **只在同阵营内**连；
  教程仍排在本阵营同级之前。老的 221 行全部保留（唯一剔除的是 209：它的接手 NPC
  `Peloponnese_All_006` 我们没发布，玩家交不了、帧里 npc 会变 0）。
- 运行时按 `GameCharacter.Camp` 过滤：`NextAcceptableQuest()` 与 `IsChainUnlocked()` 只走本阵营的行
  （`GameClientHandler.ChainCampFor(camp)`），所以斯巴达角色永远不会被派去雅典 NPC。
- 刷怪生成器 `tools/gen_suburb_monsters.py` 参数化：`python tools/gen_suburb_monsters.py <map>`，
  `PLANS` 里登记 4→`SpartaNewbieSpawnPlan`、2→`AthensNewbieSpawnPlan`，场景键从
  `MapTemplateSeed.Generated.cs` 读（不再硬编码）。两张图都是同一套规则：
  任务点为中心、范围=到最近任务点距离的一半（12~30）、数量按地图 0 实测的"需求数→刷怪数"、
  中心+内外圈均匀铺开、同点多怪种错相位。对象 ID：map 4 从 44001、map 2 从 45001 起。
- 雅典新手链的怪都落在 map 2 的客户端模板上（海蛇、波斯渗透者、哈比、平原狮、黄蜂、玉龙、
  毒蜂女王、狮王、海龟…），19 个任务点全部有模型。

### 15.3 这一轮被守卫抓出来的解析缺陷（都已修）

| 现象 | 根因 | 修法 |
| --- | --- | --- |
| quest 568 出现假目标 `player Level 70 or higher` | PvP 目标被当成打怪目标 | `PLAYER_TARGET` 直接剔除 |
| quest 574/627 的 `Theban/Mycenaean Spearmen` 解析不到怪 | 复合词复数 `spearmen→spearman` 没折叠 | 词尾 `-men → -man`（Python + 服务端 `ShapeSet`） |
| quest 1480/1481 的 `Wild Oxen` 解析不到怪 | 不规则复数 `oxen→ox` | `IRREGULAR_PLURALS` 表 |
| quest 340 出现 `thePurple Winged Demons` | 颜色标签把 `the` 和名字粘在一起 | 剥离粘连的 `the` |
| quest 535/536 出现假目标 `claim rewards from the board`（怪物 id 1031） | **`Boa` 是 `board` 的子串**，字符串子串匹配误命中 | 改为**按词边界**匹配（Python `contains_words` + 服务端 `ContainsWords`） |
| quest 1626 出现假目标 `strongest boss` | 逗号同位语被拆成第二个目标 | 无动词从句必须被客户端怪物表认出来；且同任务已有真目标时丢弃 id=0 的从句 |

守卫基线（棘轮）：无 monster id 的任务 = 8 条（244/478/479/1221/1482/1483/1557/1561）；
11 张图上共 40 个目标客户端没有对应怪（内容缺口，非协议问题）。

