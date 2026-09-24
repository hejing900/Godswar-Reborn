# 任务经验加成「鉴定」抓包与实现（2026-09-24）

> 数据来源全部标注：【实测·抓包】= `packet_transactions` / 抓包文本日志；
> 【原文·客户端】= `D:\Godswar Origin\Localization\zh_cn` 下的 Lua/XML；【自定】= 本仓库自己定的值，未对照原服。

本轮抓包会话：`packet_capture_sessions.id = 0bc1930b-4435-4145-86ef-dcb75fde8fe4`，
文本日志 `captures/godswar-proxy-20260924-203209.log`。

---

## 一、点的是哪个按钮

【原文·客户端】`UI/XML/QuestInfoUI.xml:212-214` —— 任务窗口第三个页签：

```xml
<SpanQuests Type="Tab" ... SText="QI_X0_7" ...>
    <Text Template="T_NoBackgroundText" Rectangle="15,15,300,470" Font="MainMap" Text="" TextFormat="16"/>
    <Button Template="T_Button4" ID="361400" Rectangle="120,340,202,367" SText="QI_X0_8"/>
</SpanQuests>
```

【原文·客户端】`UI/Base/text.lua:746-747`：

```lua
QI_X0_7 = "经验加成"                 -- en_us: "Increase EXP gain"
QI_X0_8 = "我要鉴定"                 -- en_us: "Appraisal"
```

【原文·客户端】该页的承诺写在 `text.lua:1319`（服务端公告文案 `SrvMsg.lua:845-847`，公告类型 `NOTE_20 = 2`）：

```lua
SM_L0_05 = "玩家"
SM_L0_06 = "通过了任务经验加成的鉴定，完成任务时可额外获得10%的经验！"
```

## 二、帧格式（【实测·抓包】）

```
C2S 10093 : 06 00 | 6D 27 | 00 00        长度 6 + 号 10093 + 2 字节负载
S2C 10093 : 08 00 | 6D 27 | 00 00 00 00  长度 8 + 号 10093 + 4 字节负载
```

全库四次点击（09-22 一次、09-24 三次，同一账号 `wcdma2000`、同一角色 `2v41e12`）
**逐字节相同**：

| 时刻（本地） | C2S | S2C |
|---|---|---|
| 09-22 00:17:35.588 / .997 | `06006d270000` | `08006d2700000000` |
| 09-24 20:34:44.321 / .618 | `06006d270000` | `08006d2700000000` |
| 09-24 20:40:48.417 / .719 | `06006d270000` | `08006d2700000000` |
| 09-24 20:41:34.369 / .956 | `06006d270000` | `08006d2700000000` |

每次回包后 2 秒内服务端只发心跳 `10015` 与世界同步 `10016/10017/10020`，
**没有公告、没有状态包、没有物品包**（SQL 见本文件第三节）。

## 三、能确定与不能确定的

**能确定：**

1. 请求**不带参数**：四次点击的负载两个字节恒为 `00 00`，客户端不区分"查询"与"执行"，
   服务端只能把"收到 10093"当作鉴定请求本身。
2. 应答是**一个 32 位值**，参考服四次都给 0。
3. 参考服对这个号**什么都没给**：既没有公告，也没有任何后续包。

**不能确定（未实测，不编）：**

1. 那 4 个 0 是「未通过 / 当前无加成」还是「通用应答」——只有一个取值，分不出来。
2. 参考服的门槛（"满足服务端要求"到底要求什么）。
3. 通过时那 4 个字节该填什么。

## 四、本仓库的实现（【自定】部分已标出）

| 位置 | 内容 |
|---|---|
| `Protocol/Opcodes.cs` | 新增 `Opcodes.QuestAppraisal = 10093`（带抓包注释） |
| `Packets/PacketBuilder.QuestAppraisal.cs` | 应答帧 `08006D27` + `int32` 值 |
| `Game/GameClientHandler.QuestAppraisal.cs` | 收包即鉴定；门槛与payout 见 `QuestAppraisalPolicy` |
| `Game/GameClientHandler.Quests.cs` | 交付时把经验乘上该角色的鉴定加成（**只作用于任务交付**，怪物经验不走这里） |
| `Infrastructure/Quests/PostgresQuestAppraisalStore.cs` | 落库读写（一次幂等插入） |
| `State/DatabaseMigrations/PostgresSchemaMigrationCatalog.QuestExperienceAppraisal.cs` | 建表 `character_quest_appraisal`（迁移 id `20260924_166_quest_experience_appraisal`） |

**【自定】两处玩法数值**（都在 `QuestAppraisalPolicy`）：

- `BonusBasisPoints = 1000`（+10%）：这是客户端自己的 `SM_L0_06` 文案写的数，不是抓包测出来的。
- `MinimumLevel = 1`（等于不设门槛）：参考服门槛未知；要加门槛改这一个常量即可。

**应答值约定【自定】**：未通过填 `0`（与抓包逐字节一致），通过填 `BonusBasisPoints`（`1000`）。
参考服通过时填什么没有样本，客户端拿到非 0 会怎么显示也未实测。

**公告【自定】**：客户端自己会按 `NOTE_20`(类型 2) 拼 `SM_L0_05+名字+SM_L0_06`，
但那个带类型的公告形式本仓库没有实现，所以本服发的是成品文本的绿色居中公告
（`PacketBuilder.CenteredGreenAnnouncement`，只能是短 ASCII，所以文案是英文）。

## 五、复现这份数据的 SQL

```sql
SELECT to_char(captured_at AT TIME ZONE 'Asia/Shanghai','MM-DD HH24:MI:SS.MS') AS t,
       direction, declared_length, encode(clear_bytes,'hex')
FROM packet_transactions WHERE opcode = 10093 ORDER BY captured_at;
```
