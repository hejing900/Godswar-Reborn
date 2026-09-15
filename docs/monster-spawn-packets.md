# 刷怪与对象广播协议（抓包实证）

本文汇总参考服抓包里**世界对象 / 刷怪 / 公告**相关的帧，供后续开发直接照抄。
数据全部来自 `packet_transactions`（代理抓包库）；标注「推断」的地方才是推断。

## 1. 帧清单

| opcode | 方向 | 长度 | 作用 | 备注 |
|---|---|---|---|---|
| `10020` | S2C | 108 | **世界对象生成**（怪物 / NPC / 玩家） | 刷怪主帧，一次一个对象 |
| `10016` | S2C | 40 | 怪物状态 / 位置刷新 | 高频 |
| `10017` | S2C | 34 | 怪物状态刷新（带状态码） | 状态码见 §5 |
| `10023` | S2C | 8 | 单个对象消失 | 只带对象 id |
| `10024` | S2C | 12–68 | 批量对象消失 | 数量 + id 列表，怪物与 NPC 混合 |
| `10037` | S2C | 32 | 对象附加状态（少见） | 语义未定 |
| `10035` | 双向 | 40–216 | **聊天 / 全体公告**（UTF-16LE） | 见 §7 |

## 2. `10020` 世界对象生成帧（108 字节）

偏移用**帧绝对偏移**，与现有实现 `Domain/World/Content/CapturedMonsterSpawn.cs`
的校验器逐字节一致（「载荷偏移」一列是相对帧头 4 字节之后的位置，方便对着抓包看）。

| 帧偏移 | 载荷偏移 | 类型 | 字段名（沿用现有代码） | 含义与实测样例 |
|---|---|---|---|---|
| +0 | — | u16 | 声明长度 | 恒 108 |
| +2 | — | u16 | opcode | 10020 |
| +4 | +0 | u32 | **`ObjectType`** | **高 16 位 = 地图号**（`ObjectType >> 16`，实测雅典主城=1、雅典新手图=2，与 `CreateAuthoredSpawn` 的 `(mapId << 16)` 一致）；低字节 = 类别判别：`& 0xFF == 0x12` 是怪物、`0x11` 是 NPC（`CapturedMonsterSpawn.IsCapturedMonsterObjectType`）。低 16 位实测：NPC 人形 `0x0111`/`0x0211`、动物 `0x0212`、人形怪 `0x0012`、精英/首领人形 `0x0112` |
| +8 | +4 | u32 | **`ObjectId`** | NPC 5xxx；怪物 10xxx–12xxx |
| +12 | +8 | u32 | **`Tier`** | NPC = 1；怪物 = 模型档次（木桩 2、鹿 3、黄蜂 6、蛇/黄蜂002 9、波斯战士 16、鹰身女妖 19/20、狮子 22、蟒蛇 23、黄蜂nt 24、精英狮 25、幼龙 26、希腊战士 141、精英/首领 200） |
| +16 | +12 | u32 | （未命名） | 恒 0 |
| +20 | +16 | u32 | **`CurrentHealth`** | 与 +24 的 `MaximumHealth` 恒等；同一对象存活期间不变，不同对象可不同（鹿 283 或 306）→ **按对象等级缩放的血量**，不是模板常量 |
| +24 | +20 | u32 | **`MaximumHealth`** | 同 +20 |
| +28 | +24 | f32 | **`X`** | |
| +32 | +28 | f32 | **`Y`** | 实测怪物恒 0 |
| +36 | +32 | f32 | **`Z`** | |
| +40 | +36 | f32 | **`Facing`** | |
| +44 | +40 | 64B | **模板键** | ASCII，NUL 补 0 到帧尾。怪物 `A_normal_deer_001`；NPC `Athens_137_FemVillager3` |

> 更正：早期把 +16/+20 当成「每种怪的常量」。实测同模板下不同对象可取 283/306、354/378、427/452/477，且对象存活期间不变 —— 它是**该对象的血量**（代码里已经是 `CurrentHealth` / `MaximumHealth`）。

### 2.1 与 Sparta 侧现有产物对齐

| 现有产物 | 字段 |
|---|---|
| `Domain/World/Content/CapturedMonsterSpawn.cs` | `MapId, SceneKey, TemplateKey, DisplayName, ObjectId, X, Z, Packet`；`Tier` 取帧 +12、`CurrentHealth`/`MaximumHealth` 取 +20/+24、模板键取 +44，并按 `objectType & 0xFF == 0x12` 判怪物 |
| 表 `monster_spawn_definitions` | `revision, map_id, scene_key, template_key, display_name, object_id, pos_x, pos_z, clear_bytes`（原始 10020 帧） |
| `SpartaNewbieSpawnPlan.Generated.cs` / `AthensNewbieSpawnPlan.Generated.cs` | `Spawn(TemplateKey, Tier, MaximumHealth, …)` |
| `CapturedMonsterAppearanceState` | `X, Z, Facing, CurrentHealth, MaximumHealth` |

所以本文档与 Sparta 地图数据**是同一套帧格式与字段语义**，本文补的是：字段取值表（各怪的 Tier/血量）、id 分段规律、消失帧、以及参考服雅典/新区域的完整数据。

## 3. 模板键命名规律（推断，样本一致）

| 前缀 | 含义 | 例 |
|---|---|---|
| `A_` | 主城 / 低级区普通怪 | `A_normal_deer_001`、`A_normals_greecewarrior_003` |
| `A_elite_` | 精英 | `A_elite_BigLion_001` |
| `B_` / `B_normalA_` | 中级区普通怪 | `B_normalA_wraith_006` |
| `B_bossB_` | 世界首领 | `B_bossB_xerxes_001`（Mardonius，map 8 Thermopylae） |
| `C_elite_` / `c_eliteA_` | 高级区精英 / 塔 | `C_elite_mage_003`、`c_eliteA_AthensTower_001` |
| `C_boss_` | 高级首领 | `C_boss_greecewarrior_001` |

中间词 `normal / normals / normalsA / elite / boss` 表示档次，末尾编号是该档次的第几个模型。

## 4. 本次抓包里的怪物段

| 模板 | 数量 | id 段 | 外观 | 类型号 | 血量 | x / z 范围 |
|---|---|---|---|---|---|---|
| `A_normal_stub_002` | 18 | 10475–10504 | 0x0212 | 2 | 261 | 123.1~220.8 / 7.0~20.2 |
| `A_normal_deer_001` | 48 | 10505–10562 | 0x0212 | 3 | 283/306 | 101.9~201.0 / 19.8~95.2 |
| `A_normal_wasp_008` | 51 | 10563–10624 | 0x0212 | 6 | 354/378 | 100.8~191.9 / 80.9~140.2 |
| `A_normal_wasp_002` | 56 | 10625–10685 | 0x0212 | 9 | 427/452/477 | 100.9~191.9 / 140.9~191.9 |
| `A_normal_snake_001` | 22 | 10700–10729 | 0x0212 | 9 | 427/452 | 65.0~93.1 / 124.0~188.2 |
| `A_normals_greecewarrior_001` | 1 | 10756–10756 | 0x0012 | 141 | 71 | 124.7~124.7 / -56.9~-56.9 |
| `A_normalsA_greecewarrior_001` | 1 | 10757–10757 | 0x0012 | 141 | 71 | 100.7~100.7 / -141.9~-141.9 |
| `A_normals_greecewarrior_003` | 56 | 10759–10888 | 0x0012 | 141 | 71 | -82.3~183.2 / -191.6~9.4 |
| `A_normals_greecewarrior_008` | 11 | 10900–10913 | 0x0012 | 141 | 71 | -56.3~183.3 / -164.0~-7.8 |
| `A_normal_PersianWarriorst_005` | 41 | 10960–11000 | 0x0212 | 16 | 681/812/847/883 | 36.9~99.2 / -115.2~-32.9 |
| `A_normal_Harpiescy_001` | 11 | 11022–11037 | 0x0212 | 19 | 745/778/812 | 138.1~159.8 / -61.0~22.4 |
| `A_normal_Harpieswn_001` | 8 | 11067–11083 | 0x0212 | 20 | 745/778/812 | 145.4~155.1 / -63.9~22.3 |
| `A_normal_lionyz_002` | 56 | 11184–11240 | 0x0212 | 22 | 812/847/883 | -70.0~32.0 / -115.0~-32.2 |
| `A_normal_lioncz_003` | 42 | 11241–11282 | 0x0212 | 22 | 812/847/883 | -70.1~30.7 / -115.2~-30.8 |
| `A_normal_ydBoa_002` | 39 | 11499–11597 | 0x0212 | 23 | 883/920/957 | 25.1~78.0 / -14.1~63.9 |
| `A_normal_Waspnt_001` | 1 | 11709–11709 | 0x0212 | 24 | 957 | 1.0~1.0 / 18.0~18.0 |
| `A_normal_ydYoungDragon_004` | 21 | 11755–11803 | 0x0212 | 26 | 996/1036/1076 | -95.2~-75.8 / -130.1~-36.8 |
| `A_elite_BigLion_001` | 1 | 11953–11953 | 0x0212 | 25 | 35856 | -57.0~-57.0 / -92.0~-92.0 |
| `C_boss_greecewarrior_001` | 1 | 11955–11955 | 0x0112 | 200 | 8177792 | 86.0~86.0 / -170.8~-170.8 |
| `C_elite_greecewarrior_006` | 4 | 11956–11968 | 0x0112 | 200 | 1825400 | 87.9~107.0 / -217.0~-174.9 |
| `C_elite_mage_003` | 6 | 11957–11972 | 0x0112 | 200 | 1241272 | 78.9~119.3 / -210.1~-166.9 |
| `c_eliteA_AthensTower_001` | 2 | 11973–11974 | 0x0112 | 200 | 7301600 | 98.0~108.0 / -221.0~-221.0 |
| `B_eliteA_wraith_004` | 1 | 11980–11980 | 0x0212 | 141 | 71 | 75.3~75.3 / 53.9~53.9 |
| `B_normalA_wraith_006` | 28 | 11983–12060 | 0x0212 | 141 | 71 | -76.9~158.9 / -209.7~31.9 |

规律：

1. **同一模板一段连续 id**，长度 1–56；相邻模板之间常留几个空号。
2. id **全局递增**：斯巴达主城 10000–10296 → 雅典主城 10457–10913 → 本次新区域 10960–12060（推断：下一张图应从当前最大值继续）。
3. 坐标按**网格**排（黄蜂 z 落在 81/95/141/145 等行上，x 按 ~10–12 递增），不是随机撒点。
4. 动物用 `0x0212`，人形怪用 `0x0012` / 精英首领用 `0x0112`。

## 5. 状态与消失帧

下面用**载荷偏移**（帧头 4 字节之后），这些帧没有对应的现有解析器。

```
10016 (40B)  载荷: u32 对象id | u32 1 | u32 1      | f32 x | f32 0 | f32 z | f32 ? | f32 ?
10017 (34B)  载荷: u32 对象id | u32 1 | u32 状态码 | f32 x | f32 0 | f32 z | u16 ?
             状态码实测：1, 3, 7, 9, 10, 11, 12, 13
10023 (8B)   载荷: u32 对象id                      单个消失
10024 (变长) 载荷: u32 数量 | u32 id × N           批量消失（怪物 + NPC 混合）
10037 (32B)  20 00 35 27 | 88 00 4d 00 | …         少见，语义未定
```

## 6. 与现有斯巴达刷怪数据的关系

| | 我们库里斯巴达（map 0） | 参考服雅典（map 1） |
|---|---|---|
| 帧 | `10020` 108B，字段完全一致 | 同 |
| id 段 | 10000–10296 | 10457–10913 |
| 模板数 | 7（含 2 精英） | 23+ |
| 外观 | 全 `0x0212` | 动物 `0x0212`、人形 `0x0012` / `0x0112` |
| 每段数量 | 46–60（精英各 1） | 1–56 |

结论：**我们的斯巴达表与参考服是同一套格式**（本身就是抓包产物，`monster_spawn_definitions.clear_bytes` 里存着原始帧），可直接当模板对照。
我们自建的新手村/郊区怪用的是合成 id（44000+ / 45000+），格式一致但 id 段不符合参考服的连续分配习惯；若要「严格像参考服」，按 §4 规则重排即可。

## 7. `10035` 全体消息 / 公告

```
+0  u32  发送者对象 id（0 = 系统）
+4  u32  文本字节数
+8  u32  样式：132 = 系统公告；1800(0x708) = 玩家频道；客户端上行额外带 0x01000000
+12      UTF-16LE 正文（无 BOM）
```

实测：

- 系统公告每约 5.5–6 分钟一次：`Welcome to GodsWar Origin. Server Bonus: Exp: x1.00 | TExp: x1.00 / Field Bonus: x0.00`
- 玩家全体频道：`xArRoWx:B> subrubs eggs 300g for full inventory`
- 上行 / 回声：客户端 `C2S 10035`（+8 带 `0x01000000`）→ 服务端 `S2C 10035` 广播给所有人。

## 8. 已产出数据文件

| 文件 | 内容 |
|---|---|
| `artifacts/monsters/reference-spawn-objects.tsv` | 全部怪物对象：模板 / id / 外观 / 类型号 / 血量 / x / z / 朝向 / 下发次数 / 首末时间 |
| `artifacts/monsters/reference-spawn-npcs.tsv` | 同期 NPC 对象（用于判断地图） |
| `artifacts/monsters/reference-spawn-summary.tsv` | 按模板汇总（数量 / id 段 / 外观 / 类型号 / 血量取值 / 坐标范围） |

## 9. 复现方式（无需新脚本）

```sql
SELECT to_char(captured_at AT TIME ZONE 'Asia/Shanghai','HH24:MI:SS.MS'),
       encode(clear_bytes,'hex')
FROM packet_transactions
WHERE opcode = 10020 AND captured_at >= now() - interval '45 minutes'
ORDER BY captured_at;
```

解析：跳过 4 字节帧头 → 按 §2 读字段 → 模板键取 +40 起的可打印 ASCII。

## 10. 尚未解决 / 不能外推的部分

1. ~~帧里没有地图号~~ —— **有**：`ObjectType` 高 16 位就是地图号（§2），雅典主城=1、雅典新手图=2 已据此分类完毕。
2. **坐标不能外推**：每张图的刷怪坐标只对那张图有效，别的图必须另行抓包或自行设计。
3. `+16` 的低层含义、`10037` 语义、`10024` 的触发时机尚未确定。
4. 首领 `B_bossB_xerxes_001`（Mardonius，map 8）**没有在抓包里单独广播过**：全库搜 `Mardonius` / `xerxes` / `Thermopylae` 零命中，而客户端本地文本有这个名字（`LuaText.lua`、任务 1382），所以「首领刷新公告」若存在，很可能是**服务端只发触发 id、客户端本地渲染名字**，需要专门抓一次首领刷新的时刻才能定论。

## 11. 已写进服务端的部分

| 内容 | 位置 |
|---|---|
| 抓包直接产出的刷怪数据（雅典主城 map 1：294 只 / 9 种；雅典新手图 map 2：330 只 / 17 种） | `Infrastructure/WorldContent/AthensCapturedSpawnPlan.Generated.cs` |
| 展开成 10020 帧并接入内容目录 | `PostgresWorldContentReaderLoader.Monsters.cs`：`CreateCapturedAthensCitySpawns` / `CreateCapturedAthensNewbieSpawns` / `CreateCapturedPlanSpawns`，在 `AppendAuthoredSpawns` 里追加 |
| 帧构造 | 复用 `CreateAuthoredSpawn`，新增 `appearance` / `facing` 参数：抓包数据用参考服自己的外观字（人形 `0x0012`、兽 `0x0212`、精英 `0x0112`）与朝向，自建计划仍用 `0x212` / `1f` |
| 编号 | 保留参考服自己的对象 id（主城 10457–10913、新手图 10960–12060），不再另行分配 |
| 回归断言 | `QuestProtocolChecks.CheckCapturedAthensSpawnPlans`（数量、id 段、去重、两条定点记录） |
