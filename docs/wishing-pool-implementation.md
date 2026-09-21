# 许愿池（Wishing Pool）实现说明

范围：`D:\Godswar-Reborn-main` 服务端许愿池功能的**现行实现**。
对话分级显示的通用原理见 `docs/npc-function-dialog-mechanism.md`；抓包原件见
`docs/wishing-pool-capture-20260915.md`。

---

## 1. 入口与 NPC

| 项 | 值 |
| --- | --- |
| NPC 脚本名 | `Sparta_074` / `Athens_074` |
| 对象 id | `5071`（Sparta）/ `5213`（Athens） |
| 功能 id（`Type`） | `16` = `NPC_FLAG_SYS_SKILLBOOK` |
| 打包列表 | `[16, 24, 50]` → `0x02FB4E50` |
| flags | `0x200`（= 功能菜单，非纯描述） |

代码位置：

- `GameClientHandler.NpcDialogOpen.cs` — `IsWishingPool`（id 判定 + 脚本名判定）、
  `SendWishingPoolMenuAsync`（发 `10067`）、`HandleWishingPoolActionAsync`（路由）、
  `HandleWishingPoolWishAsync`（一次许愿全流程）、`BroadcastWishingPoolGrantAsync`、
  `SendWishingPoolPageAsync`。
- `GameClientHandler.NpcDialog.cs` — `10069` 分发，许愿池分支**必须放在商城分支之前**。

### 1.1 为什么排在商城前面

同一对首都 NPC 同时挂了商城服务，商城分支会把共用的 dialog 索引吃掉却不作应答。
所以 `IsWishingPool(npcId)` 判定必须早于 `TryHandleMallFunctionActionAsync`：

```csharp
// GameClientHandler.NpcDialog.cs:49
if (IsWishingPool(npcId)) { ... return; }
if (await TryHandleMallFunctionActionAsync(...)) { return; }
```

### 1.2 选项字段取 `+16`，不取 `+12`

客户端在第二字里保留**上一次**的按钮、把**本次点击**写进第三字。
用通用读取器（第二字）会一直读到当前页的第一个按钮，每一步都像在原地重复。

```csharp
// GameClientHandler.NpcDialog.cs:56
var selection = payload.Length >= 20
    ? BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(16, 4))
    : subId;
if (selection < 0) { selection = subId; }   // -1 = 列表初始化请求
```

---

## 2. 页面路由

`10069` 的 `dialogIndex`（= 功能 id）原样回显进 `10070` 的 `+8`，服务端不维护当前页。
`HandleWishingPoolActionAsync` 按功能 id 分派：

| 功能 id | 收到的 `selection` | 回发的 `SubID` | 含义 |
| --- | --- | --- | --- |
| `16` | `101` / `201` | `[301,401,501,601]` | 免费 / 付费 → 选职业 |
| `16` | `301/401/501/601` | 视结果，见 §4 | 执行许愿 |
| `16` | 其它 | `[101, 201]` | 回到许愿入口菜单 |
| `50` | — | `[1001]` | 说明页 |
| 其它 | — | `[101, 1, 2]` | 兜底 |

免费与付费在"选职业"这一步**无法区分**（两者点职业都送 `301–601`），
所以入口点击时把状态寄存在 `_wishingPoolPaidWishPending`，等职业点击到来时消费：

```csharp
_wishingPoolPaidWishPending = selection == 201;   // 记下是不是付费
...
var paid = _wishingPoolPaidWishPending;           // 职业点击时取用
_wishingPoolPaidWishPending = false;
```

**应答只放同一家族的消息 id。** 职业按钮与结果文本不能混在一条 `10070` 里：
结果文本（尾 0）自带 `NPCFUN:EndMessage(true)`，混进去会让客户端把整条应答当结果、直接关窗。

---

## 3. 免费许愿的门槛与配额

常量在 `GameClientHandler.NpcDialogOpen.cs`：

| 常量 | 值 | 出处 |
| --- | --- | --- |
| `WishingPoolMinimumLevel` | `30` | `NF_L0_JN100` 原文 |
| `WishingPoolPaidWishGoldCost` | `230` | `NF_L0_JN103` 原文 |
| `WishingPoolCatalog.AdvancedTierWeight` | `200` / 10000 | 高级档 2% |
| `WishingPoolUsage.DailyLimit` | `3` | `NF_L0_JN1` 原文 |
| `WishingPoolUsage.Interval` | `1h` | `NF_L0_JN1` 原文 |

判定顺序（`HandleWishingPoolWishAsync`）：

1. `_character.Level < 30` → 回 `[100]`，结束。
2. **免费分支**：读配额 → 剩余 0 回 `[500]`；距上次不足 1 小时回 `[分*100+秒+2]`。
3. 发书（§4），**付费的 230 金币在这笔事务里扣**。
4. 发书失败按原因回文案：

| 失败原因 | 回的 `SubID` | 文案 |
| --- | --- | --- |
| `InsufficientGold` | `300` | You don't have enough Gold to throw into the wishing pool. |
| `InsufficientCapacity` | `400` | 背包已满 |
| 其它 | 不发，只打日志 | — |

5. **免费分支**：写配额（只有成功才写）。
6. 回抽中结果：普通档 `[103]`、高级档 `[203]`；高级档再加全领域广播（§5、§6）。

### 3.0 付费余额只在事务里判，不用内存缓存

`HandleWishingPoolWishAsync` **没有** `_character.Gold < 230` 这类预检。
唯一权威是 §5.1 事务里 `SELECT … FOR UPDATE` 读到的库值：
内存里的 `Gold` 若过期，预检会拦下一笔账号其实付得起的许愿。
金币不足的文案由商店返回的 `InsufficientGold` 驱动。

### 3.1 配额持久化

表 `public.character_wishing_pool_usage`（迁移 `20260916_156_wishing_pool_usage_state`）：

| 列 | 说明 |
| --- | --- |
| `character_id` | 主键 |
| `usage_date` | 所属**领域日**（`RealmCalendar.GetDay`） |
| `used_count` | 当日已用次数 |
| `last_used_at` | 上次许愿时刻，用于 1 小时间隔 |
| `last_skill_book_item_id` | 上次发出的书 |
| `updated_at` | — |

读：`ReadAsync` 发现 `usage_date` 不是今天，就回报"全新的一天"（次数 0、无冷却），
**每日重置不需要任何定时任务**。
写：`RecordAsync` 用 `INSERT … ON CONFLICT DO UPDATE`，跨日则 `used_count` 归 1，同日则 +1。

冷却编码公式（脚本 `math.mod(SubID,100)==2` 分支的逆运算）：

```
SubID = ((int)剩余.TotalMinutes * 100 + 剩余.Seconds) * 100 + 2
```

---

## 4. 抽书：职业、等级、权重

`WishingPoolCatalog`（`State/WishingPoolCatalog.cs`）。

### 4.1 职业来自点击的按钮，不是角色职业

```csharp
301 => 0,   // Warrior
401 => 1,   // Champion
501 => 3,   // Mage
601 => 2,   // Priest
```

注意 3 和 2 是**反的**：目录表 `gameplay_class_definitions` 里
`0 战士 / 1 冠军 / 2 牧师 / 3 法师`，所以法师按钮 → 3、牧师按钮 → 2。

### 4.2 分档抽取

先抽**档**，再在档内抽**级**：

```csharp
AdvancedTierWeight  = 200;    // 高级档 2%
OrdinaryTierWeight  = 9800;   // 普通档 98%

OrdinaryLevelWeights = [(1, 70), (2, 30)];   // 档内：1 级 70%、2 级 30%
AdvancedLevelWeights = [(3, 60), (4, 40)];   // 档内：3 级 60%、4 级 40%

MaximumWishSkillLevel = 4;                   // 高级档封顶 lv4，不发 5 级

public static int DrawSkillLevel()
{
    var roll = Random.Shared.Next(TierWeightTotal);   // 10000
    return roll < AdvancedTierWeight
        ? PickWeighted(AdvancedLevelWeights)
        : PickWeighted(OrdinaryLevelWeights);
}
```

每一级的实际概率：

| 级 | 档 | 概率 |
| --- | --- | --- |
| 1 | 普通 | 98% × 70% = **68.6%** |
| 2 | 普通 | 98% × 30% = **29.4%** |
| 3 | 高级 | 2% × 60% = **1.2%** |
| 4 | 高级 | 2% × 40% = **0.8%** |

档内比例是服务端定的（`70/30`、`60/40`），改档位比例只需改这两个表。

`IsAdvancedTier(level)` 是**唯一**的档判据，广播与抽中结果文案都引用它，
避免多处各写一套阈值而漂移。

| 档 | 图标带（`skill_book_templates.stats->>'Icon'`） |
| --- | --- |
| 普通 | `540,756` `576,756` `612,756` `648,756` |
| 高级 | `756,720` `792,720` `828,720` `864,720` |

### 4.3 选书

`Resolve(books, class, level)` 在 `skill_book_templates` 里筛
`SkillLevel == level && ClassIds.Contains(class)`，再从中随机取一本。

---

## 5. 发放与扣费

`GameClientHandler.WishingPool.Grant.cs` → `TryGrantWishingPoolSkillBookAsync(class, goldCost, ct)`。
**不走 GM/开发者发物通道**（该通道只允许材料与 GM 物品白名单，技能书不在内，且该通道计划移除）。

`PostgresGameStore.AddWishingPoolSkillBookAsync` 一个事务内完成：

1. `SELECT "Stone" FROM character_base WHERE account_id=… AND id=… FOR UPDATE` → `goldBefore`
2. `goldBefore < goldCost` → 返回 `InsufficientGold`（提交空事务）
3. 读已占用背包格 → 找第一个空格；没有 → `InsufficientCapacity`
4. `INSERT INTO character_items (…)` 写入技能书
5. `goldCost > 0` 时扣费：

```sql
UPDATE character_base
SET "Stone" = "Stone" - @goldCost
WHERE account_id = @accountId AND id = @characterId
  AND "Stone" = @goldBefore AND "Stone" >= @goldCost;
```

影响行数 ≠ 1 就抛异常（乐观并发：期间被别人改过就整笔回滚）。

6. 提交 → 回读角色 → 打日志：

```
[wishing-pool] gold charged character=… before=… cost=230 after=…
```

### 5.1 货币映射

角色金币 = `character_base."Stone"`（旧库命名），不是 `"Money"`（那是银币）。
`BindingGold` 是另一列，不参与。

### 5.2 回填客户端

```csharp
var walletChanged = goldCost > 0;
InstallUpdatedCharacter(grant.Character!);            // 内存角色换成提交后状态
_registry.UpdateCharacter(_session, _character, advanceWorldRevision: false);
if (walletChanged)
{
    // 只改库不发包，客户端会一直画旧金额。
    await _session.SendAsync(
        BuildLocalPlayerStatusUpdate(),              // 10166，金币在 +124
        cancellationToken,
        "WishingPoolWalletStatus");
}
await SendKitBagRefreshAsync(cancellationToken);      // 背包刷新，书才出现
```

**两个包都要发**：

| 包 | 作用 | 漏发的表现 |
| --- | --- | --- |
| `SendKitBagRefreshAsync` | 背包刷新 | 书不出现 |
| `BuildLocalPlayerStatusUpdate`（`10166`） | 钱包状态 | **书出现了、金币不变** |

`10166` 里金币在 `PlayerStatusGoldOffset = 124`、银币 `120`、绑定金 `136`
（`PacketBuilder.PlayerStatusUpdate.cs`）。这是仓库里所有动钱包的地方的统一做法，
参照 `GameClientHandler.CapitalNpcServices.cs:146-163` 的 NPC 商店卖出流程。

只在 `goldCost > 0` 时发：免费许愿不动钱包，不必多推一个包。

---

## 6. 广播

只在该次抽到**高级档**（3 级或 4 级）时触发：

```csharp
var advanced = WishingPoolCatalog.IsAdvancedTier(grant.SkillLevel);
if (advanced)
    await BroadcastWishingPoolGrantAsync(grant.DisplayName, cancellationToken);
```

普通档（1–2 级）不广播。

文案用**物品名**（`book.DisplayName`，来自 `skill_book_templates`），不是物品 id：

```
{角色名} got {书名} from the Wishing Pool!
```

### 6.1 通道与颜色

`PacketBuilder.CenteredGreenAnnouncement`（`Packets/PacketBuilder.PythonNote.cs`）：

| 字段 | 值 |
| --- | --- |
| opcode | `10038`（`PythonNote`），定长 `137` 字节 |
| `+4` | `50`（direct text type） |
| `+8` | `0`（居中频道 `CenterChannel`；个人频道是 `1`） |
| `+9` / `+73` | 两段定长 64 字节 ASCII |

着色用库存标记，绿字前缀 `|cFF00FF00`、末尾 `|cFFFFFFFF` 复位：

```csharp
return CenteredAnnouncement(CenteredGreenTextPrefix + message + CenteredTextColorReset);
```

正文上限 **106 个可打印 ASCII**（超出、含控制字符、含 `|c` 都会抛异常）。
文本按 63 字节拆进两段，客户端拼接后渲染，拆分不影响可见文本。

### 6.2 全领域投递

`GameSessionRegistry.BroadcastToAllSessionsAsync` 遍历 `_sessions.Keys` 逐个发送，
**不按地图/副本过滤**，所以收件人在哪张地图都能收到。
单个会话异常（关闭、IO）被吞掉，不影响其余投递，返回投递成功数。

---

## 7. 依赖装配

| 组件 | 位置 |
| --- | --- |
| `_wishingPoolUsage` | `GameClientHandler` 字段（可空：没有它就只拒免费许愿） |
| `_wishingPoolPaidWishPending` | `GameClientHandler` 字段 |
| `PostgresWishingPoolUsageStore` | `Infrastructure/WishingPool/` |
| 构造注入 | `GameClientHandler.Construction.cs`、`GameClientHandlerFactory.cs` |
| 运行时装配 | `Infrastructure/PostgresApplicationDataRuntime.cs`（`WishingPoolUsage` 属性） |

`_wishingPoolUsage is null` 时免费许愿打 `[wishing-pool] free wish unavailable: no usage store` 并返回；
付费许愿不依赖它。

---

## 8. 结果码对照（客户端脚本原文）

| 发出 | 脚本常量 | 英文原文 |
| --- | --- | --- |
| `100` | `JN100` | Players below level 30 cannot make wishes in the wishing pool. |
| `300` | `JN300` | You don't have enough Gold to throw into the wishing pool. |
| `400` | `JN400` | Your bag is full, even though your wish comes true, no skill books will be obtained. |
| `500` | `JN500` | You have used up your free chances. |
| `103` | `JN103` | Your wish has come true, but it's only a common skill book. |
| `203` | `JN203` | Your wish has come true, you are lucky to have obtained an advanced skill book. |
| `[分*100+秒+2]` | `JN3/JN4/JN5` | You need N minutes M seconds to make another wish for free |
| `101/201` | `JN101/JN201` | `*Make wishes for free` / `*Throw Gold into the Wishing pool` |
| `301/401/501/601` | `JN301…JN601` | `*a Warrior/Champion/Mage/Priest Skill Book` |

### 8.1 未被发出的结果码

| 码 | 脚本常量 | 现状 |
| --- | --- | --- |
| `200` | `JN200` 选择错误 | 不发：职业按钮 `301–601` 全部合法，没有"选错"分支 |
| `303` | `JN303` 终极技能书 | 不发：抽取封顶 4 级，终极（5 级）不在抽取范围内 |

> `JN103` 的原文后半句是 "Do you want to spend 230 Gold in making another wish?"，
> 那是原服的**二次付费重抽**入口，本实现没做；`103` 现在只用来报"抽到普通档"。

### 8.2 配额在成功时才消耗

免费分支的 `RecordAsync` 位于发书**之后**，因此等级不足、冷却中、次数用完、背包已满
这四种情况都**不消耗**当日次数，也不刷新 1 小时冷却。
付费分支完全不读写配额表。
