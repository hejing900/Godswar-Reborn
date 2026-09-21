# NPC 各级对话显示机制

客户端只有一个 NPC 对话窗口（`UI/XML/NpcFun.xml` 的 `FirstWin`），所有 NPC 功能都往它里面写。
**「显示第几级」由三个独立的数字控制**，本文逐级说明每个数字管什么、服务端怎么给。

依据：客户端脚本 `Localization/<locale>/UI/XML/NpcFun/*.lua`、文案 `UI/Base/LuaText.lua`、
本服务端实现、参考服抓包。

---

## 1. 帧序与字段

```
C2S 10067  点 NPC
S2C 10067  flags + 打包功能 id 列表 + 脚本名
C2S 10068  就绪
C2S 10069  玩家点了一个选项
S2C 10070  服务端回一批消息 id
```

之后每次点击都是 `10069 → 10070` 一对，直到客户端 `EndMessage` 关窗。

### 1.1 `S2C 10067`（定长 48）

| 偏移 | 宽度 | 含义 |
| --- | --- | --- |
| 0 / 2 | 2 / 2 | 长度 / opcode `10067` |
| +4 | 4 | NPC 对象 id |
| +8 | 4 | **flags**：`0x200` = 功能菜单，其它 = 纯描述 |
| +12 | 4 | **打包的功能 id 列表** |
| +16 | 32 | 脚本名（ASCII 定长，如 `Sparta_074`） |

打包规则（`PacketBuilder.PackNpcDialogIndices`）：**最多 3 个，每个 1–999，
十进制千进制、低位在前、不重复**。

```
[16, 24, 50]  ->  16 + 24*1000 + 50*1000000  =  50024016  (0x02FB4E50)
[16, 24]      ->  16 + 24*1000               =  24016
[26]          ->  26
```

### 1.2 `C2S 10069`

读取器 `GameClientHandler.PacketDecoding.cs:14`：

| 偏移 | 含义 |
| --- | --- |
| +0 | NPC 对象 id |
| +4 | 功能 id（`dialogIndex`） |
| +8 | 客户端当前页（与 +4 同值） |
| +12 | 通用读取器眼里的 `subId` |
| +16 起 | 变长 int32 参数 |

**决定玩家意图的是 `+16`，不是 `+12`。**
客户端在 `+12` 里保留**上一次**的按钮，把**本次点击**写进 `+16`。
用 `+12` 会一直读到当前页的第一个按钮，表现为"每一步都在原地重复"。

```csharp
// GameClientHandler.NpcDialog.cs:56
var selection = payload.Length >= 20
    ? BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(16, 4))
    : subId;
if (selection < 0) selection = subId;      // -1 = 请求初始按钮集
```

实测：打开许愿池后点第一个按钮，`+16=101`；点职业按钮，`+16=501`。

### 1.3 `S2C 10070`

| 偏移 | 宽度 | 含义 |
| --- | --- | --- |
| 0 / 2 | 2 / 2 | 长度 / opcode `10070`（`0x2756`） |
| +4 | 4 | NPC 对象 id |
| +8 | 4 | 功能 id —— **原样回显 `10069` 的 `+4`** |
| +12 | 4×N | **消息 id 列表**，N = 1–20 |

`+8` 没有"页"的语义，服务端不需要维护当前页状态，照抄客户端发来的功能 id 即可：

```csharp
private async Task SendWishingPoolPageAsync(uint npcId, int page, int[] reply, ...)
    => PacketBuilder.NpcFunctionActionResponse(npcId, page, reply);
```

---

## 2. 三层模型

| 层 | 名字 | 取值 | 管什么 |
| --- | --- | --- | --- |
| 一 | `Type`（功能 id） | `NpcFun.lua` 的 `NPC_FLAG_SYS_*` | 调哪个脚本函数 |
| 二 | `Index`（页序） | 1–3 | 脚本里哪一页 |
| 三 | `SubID`（消息 id） | 脚本自定义 | 页内显示哪一条 |

`NpcFun.lua:177` 的 `Set_NpcFun_Text(Type,Index,BtnID,SubID)` 按 `Type` 分派：

```lua
elseif Type == NPC_FLAG_SYS_SKILLBOOK then
    NpcFunSkillbook_SetText(Type,Index,BtnID,SubID)
elseif Type == NPC_FLAG_SYS_LUCKYGODS then
    NpcFunLuckyGods_SetText(Type,Index,BtnID,SubID)
```

功能常量（`NpcFun.lua` 顶部，全表约 100 项）：

```lua
NPC_FLAG_SYS_BREAK      = 4    ----装备分解
NPC_FLAG_SYS_SKILLBOOK  = 16   ----抽取技能书
NPC_FLAG_SYS_ZEUS       = 26   ---宙斯献礼
NPC_FLAG_SYS_HOLYSTONE  = 30   ----圣石
NPC_FLAG_SYS_LUCKYGODS  = 50   --许愿池幸运神明
```

服务端项目里这些 id 以常量落库：
`GearEnhancerProtocol.DialogIndex = 4`、`HolyStoneProtocol.DialogIndex = 30`、
`WarehouseNpcProtocol.ManagerDialogIndex = 106`、`OnlineAwardProtocol.DialogIndex = 49`、
`InstanceCallerProtocol.DialogIndex = 9`。

---

## 3. 第二层 `Index`：一屏之内的分页

`Index` 由客户端引擎按 `10067` 打包列表给出：**列表里的第 N 个功能 id 对应 `Index = N`**。
脚本据此整页换逻辑：

```lua
-- NpcFunSkillbook.lua
function NpcFunSkillbook_SetText(Type,Index,BtnID,SubID)
    if Index == 1 then
        FirstWin_Text1:SetText(NF_L0_JN1);   -- 许愿池介绍
        FirstWin_Text1:Visible(true);
    elseif Index == 2 then
        FirstWin_Text1:SetText(NF_L0_JN2);   -- "Which type of skill book do you wish to have?"
        FirstWin_Text1:Visible(true);
    end;
    -- 以下按 SubID 分流，两种 Index 共用
```

### 3.1 因此列表顺序就是页序

想让功能 id `F` 显示成第 `N` 页，**打开对话时把它放在列表第 `N` 位**：

```csharp
// GameClientHandler.NpcDialogOpen.cs:442
private static readonly int[] WishingPoolPages = [16, 24, 50];
await PacketBuilder.NpcDialogOpenAck(npc.InteractionId, WishingPoolPages, npc.NpcKey);
// Type=16 -> Index 1 -> NpcFunSkillbook 第 1 页
// Type=24 -> Index 2
// Type=50 -> Index 3 -> NpcFunLuckyGods 第 3 页
```

列表最多 3 个元素，所以一个 NPC 一次最多暴露 3 个 `Index`。
**`Index` 在 `10067` 那一刻就定死，中途改不了** —— 要换页只能重新打开对话，
把列表顺序调换。

### 3.2 实测对照

商城（`Athens_074` / npc `5212`，参考服抓包）：
客户端先请求功能 id `16`，服务端回 `101/201`；选 `101` 后服务端发四个窗口帧。
同一个 NPC 在功能 id `24` 上挂第二个服务，菜单是 `101/1/2`，首个选择回 `601`。

许愿池（`Sparta_074` / npc `5071`）同样用 `[16, 24, 50]`，
**16 是许愿页、50 是说明页、24 留给商城那套**。

---

## 4. 第三层 `SubID`：逐级显示的主力

页内所有文案和按钮都由 `SubID` 挑，**与 `Index` 无关，任何页下都生效**。
两个脚本各用一种编码风格。

### 4.1 风格 A：尾数族 + 级数（`NpcFunSkillbook.lua`）

```lua
if math.mod(SubID,100) == 0 then          -- 尾 0：结果文本
    if     SubID/100 == 1 then ... JN100  --   1xx 等级不足
    elseif SubID/100 == 2 then ... JN200  --   2xx 选择错误
    elseif SubID/100 == 3 then ... JN300  --   3xx 金币不足
    elseif SubID/100 == 4 then ... JN400  --   4xx 背包已满
    elseif SubID/100 == 5 then ... JN500  --   5xx 免费次数用完
    end;
    NPCFUN:EndMessage(true);              -- 整族都会关窗
elseif math.mod(SubID,100) == 1 then      -- 尾 1：可点按钮
    if (SubID-1)/100 == 1 then ... JN101  --   101 免费许愿
    elseif (SubID-1)/100 == 2 then ... JN201  --   201 付费许愿
    elseif (SubID-1)/100 == 3 then ... JN301  --   301 战士
    ...                                    --   401 冠军 / 501 法师 / 601 牧师
elseif math.mod(SubID,100) == 2 then      -- 尾 2：倒计时（带数字拼接）
    FirstWin_Text1:SetText(NF_L0_JN3 .. 分 .. NF_L0_JN4 .. 秒 .. NF_L0_JN5);
elseif math.mod(SubID,100) == 3 then      -- 尾 3：抽中结果
    if (SubID-3)/100 == 1 then ... JN103  --   1xx 普通书
    elseif (SubID-3)/100 == 2 then ... JN203  --   2xx 高级书
    elseif (SubID-3)/100 == 3 then ... JN303  --   3xx 终极书
    end;
elseif math.mod(SubID,100) == 4 then      -- 尾 4：Draw again（只显 ButtonA3）
elseif math.mod(SubID,100) == 5 then      -- 尾 5：剩余次数（红色数字）
```

**级数 = `SubID / 100`（整数除），家族 = `SubID % 100`。**
要显示"第 2 级结果"就是 `200`，要显示"第 1 级按钮"就是 `101` ——
同一页里靠这个数字切出任意多级文案，**不需要动 `Index`**。

许愿池实测用的就是这个：`101/201` 入口，`301–601` 职业，结果 `[203]`，
冷却 `[分*100+秒+2]`，门槛 `[100]`，次数用完 `[500]`，金币不足 `[300]`，背包满 `[400]`。

### 4.2 风格 B：数字本身即语义（`NpcFunLuckyGods.lua`）

幸运神明的 `SubID` 是显式枚举，没有族规律：

| `SubID` | 行为 |
| --- | --- |
| `100` | 说明 `L001` + 按钮"选择波塞冬" `L002` |
| `101` | 按钮"选择阿波罗" `L003` |
| `1000` | 按钮"领取奖励" `L007` |
| `1001` | `L012` "必须达到55级以上才可以许愿" + 结束 |
| `104` | `L013` "今天的许愿次数已经用完" + 结束 |
| `201` | `L016` "很抱歉，你暂时还没有任何奖励" + 结束 |
| `%10==2` | `L022 + N + L023`，连中 7 次给经验 |
| `%100==3` | `L005` "你没有进行任何选择" + 结束 |
| `%100==4` / `%100==5` | 按钮"选择阿波罗" / "领取奖励" |
| `%10==6` | `L017 + N + L018`，"5分钟才能选一次！请再过 N 分钟" |
| `%10==7` | `L011 + N + L015`，"见好就收…还能许愿 N 次" |
| `%10==8` | `L008 + N + L015`，"运气不好，你选择错了" |
| `%10==9` | `L004 + N + L014`，"恭喜！你将获得 N 经验" |

**反向解析：脚本里 `(SubID - k) / 10` 就是服务端要算的数。**
例：要显示"再过 N 分钟"，发 `N*10 + 6`。

### 4.3 `BtnID`：按钮槽由应答内位置决定

引擎给 `10070` 里**第 i 个**消息 id 分配按钮槽 `BtnID = i`（1 起），
脚本用 `win:GetChild("FirstWin_Button" .. BtnID)` 取到 `FirstWin_ButtonN`。
窗口 `NpcFun.xml` 有 12 个编号按钮槽 + `FirstWin_ButtonA1/A2/A3` 三个固定位
（`A3` 被尾 4 的 "Draw again" 独占）。

**发的顺序就是按钮从上到下的顺序**，脚本再用 `SetPosition` 微调坐标。

---

## 5. 操作层：多级跳转

页内多级（§4）之外，"点一个按钮展开下一层"是靠 **`10070` 回发的消息 id
本身充当下一层的入口**，服务端持一张"点击 → 展开"表。

```csharp
// GameClientHandler.NpcDialogOpen.cs:392 —— 语义就这十行
var reply = subId == -1
    ? OpeningMenu
    : Levels.TryGetValue(subId, out var next) ? next : OpeningMenu;
await _session.SendAsync(
    PacketBuilder.NpcFunctionActionResponse(npc.InteractionId, dialogIndex, reply), ...);
```

- **`subId == -1` 是"请求初始按钮集"**，不是具体选项。抓包里
  `10069 {npc, 24, 24, -1}` 就是这个意思。
- 层级深度不受 `Index` 的 3 页限制：全程 `Index` 不变，靠 `SubID` 逐级往下跳。
- 表的 key / value 必须全部是脚本里真实存在的 `SubID`，
  且**必须落在当前 `Index` 那一页的分支里** —— 跨页的 id 在本页没有处理分支，
  发出去等于点了没反应。这一步要逐条对着脚本核。

---

## 6. 已踩实的坑

1. **`+16` 才是玩家点击，`+12` 是上一次的按钮。** 读错表现为"每一步都在重复当前页"。
2. **按钮 id 与结果文本不能混在同一条 `10070`。**
   发 `[2, 301, 401, 501, 601]` 或 `[100, 301, 401, 501, 601]` 都会**直接关窗**：
   结果族（尾 0 / 尾 2）自带 `NPCFUN:EndMessage(true)`，客户端把整条应答当结果处理。
   正确形状是只含按钮 id：`[301,401,501,601]`。
3. **`101` 是免费许愿，`100` 不是。** `100` 属于尾 0 的"等级不足"结果文本。
4. **`flags` 必须是 `0x200`**，否则客户端不进功能菜单分支，点了没反应。
5. **打包列表 1–999、不重复、最多 3 个**，越界或重复会抛异常。
6. **同一个 NPC 挂多个服务时，分支顺序要抢在通用分支前面。**
   首都 NPC 同时挂商城与许愿池，商城会把共用的 dialog 索引吃掉却不作应答：

```csharp
// GameClientHandler.NpcDialog.cs:49
if (IsWishingPool(npcId)) { ... return; }              // 必须先判
if (await TryHandleMallFunctionActionAsync(...)) { return; }
```

7. **一条应答只放一个族**：有按钮就全是尾 1，有结果就全是尾 0/尾 3。
8. **文案必须能在 `LuaText.lua` 逐条对上。** 对不上就是族或级数算错了。

---

## 7. 引擎侧（Lua 层看不到）

| 行为 | 说明 |
| --- | --- |
| `NPCFUN:EndMessage(true)` | 无 Lua 定义；结果族调用后关窗 |
| `Index` 赋值 | 引擎按 `10067` 打包列表位置计算 |
| `BtnID` 分配 | 引擎按应答内位置递增 |

---

## 8. 新增一个 NPC 功能对话

1. `NpcFun.lua` 找 `NPC_FLAG_SYS_* = N`。
2. 读 `NpcFun<Name>_SetText`，确定文案落在**哪个 `Index` 页**、**哪个 `SubID`**。
3. 把功能 id `N` 放进 `10067` 打包列表的**第 `Index` 位**（1–3 个，1–999，不重复）。
4. `10067` 用 `flags 0x200` + 打包值 + 脚本名。
5. `10069` 取 `+16` 当玩家选项，`-1` 当"要初始按钮集"。
6. `10070` 的 `+8` 回显 `10069` 的 `+4`；`+12` 起放消息 id，**只放一个族**。
7. 多级跳转另建"点击 → 展开"表，key/value 全部来自当前 `Index` 页的分支。
8. 每次对着 `LuaText.lua` 核对文案。

### 参考实现

| 功能 | 有抓包 | 位置 |
| --- | --- | --- |
| 许愿池 | 是（`docs/wishing-pool-capture-20260915.md`） | `GameClientHandler.NpcDialogOpen.cs` |
| 商城 | 是（`Athens_074` npc 5212） | `GameClientHandler.Mall.cs` |
| 宙斯献礼 | 否 | `GameClientHandler.NpcDialogOpen.cs:392` |
