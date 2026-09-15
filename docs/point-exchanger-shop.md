# 积分兑换者（Point Exchanger）商店目录

NPC：`Sparta_077` / `Athens_077`，客户端 interactionId `5074` / `5216`，actor `5076` / `5216`
中文名：斯巴达 **积分兑换者**，雅典 **积分兑换员**

## 结论一句话

服务端**早就有** `10071` 商店目录下发和 `10073` 购买协议，缺的只是这一个 NPC 的目录数据。
做法完全照抄已跑通的 **B-GOLD 商店**（`BindingGoldShopCatalogGzip`），不新增任何协议。

## 帧布局（三方一致，已定死）

| 位置 | 含义 |
|---|---|
| 帧 `+0` | u16 帧长（含头） |
| 帧 `+2` | u16 opcode = 10071 |
| 帧 `+4` | u32 NPC ID（服务端出口改写） |
| 帧 `+8` | u8 分类 |
| 帧 `+9` | u8 货币：`0x02`=金币，`0x03`=银币，`0x04`=绑定金币 |
| 帧 `+10` | u8 本帧条目数 |
| 帧 `+11` | u8 新上架标记（1=新分类首页，0=续帧） |
| 帧 `+12` | u32 余额（服务端出口改写） |
| 记录 `+0` | u32 道具 ID |
| 记录 `+64` | u32 标记 `0xFFFF04xx` |
| 记录 `+68` | u32 单价 |
| 记录 `+84` | u32 数量 |

帧头 **16** 字节，记录 **88** 字节，帧长 = `16 + N × 88`。

> 踩坑记录：一开始把帧头当成 12 字节、把道具 ID 当成记录 `+0`、价格当成 `+68`，
> 解密出来的 ID 和价格整体错位 4 字节（一会儿全 0、一会儿 4 亿多）。
> 权威依据是**已跑通的 B-GOLD 目录**：它同样是 `16 + N × 88`，`+12` 是余额，
> 记录 `+0` 是道具 ID、`+68` 是单价。用它对照才定死。

## 抓包数据

来源：`packet_transactions` 表，opcode 10071，2026-09-13 两次独立抓包，
帧长完全一致（`1420 / 100 / 1332 / 1068 / 980`），共 55 条记录、4 个分类。

每帧**最后一条记录比满步长少 4 字节**（缺的是尾部数量字段）。因为其余目录族和
客户端商人窗口都按固定 88 字节步长寻址，生成目录时把该尾巴补零到满步长。

## 剔除项

`14073`（分类 2，售价 2400）在客户端 `ItemBaseAttribute.xml` 中**没有定义**。
服务端既有做法（`PacketBuilder.CapitalNpcShops.cs` 的
`UnsupportedBoundGoldVendorItemIds`）就是剔除这类条目，否则 Origin 构造商人窗口时
会解引用缺失定义。因此目录最终为 **54 件**。

## 落地产物

- `src/Godswar.Server/Packets/PacketBuilder.PointExchangerShop.cs`
  —— gzip+base64 目录常量 + 自校验解压（帧数/总长/opcode/捕获 NPC ID 全部断言）。
- `Domain/World/Content/CapitalNpcServiceProtocol.cs`
  —— 新增 `CapitalNpcServiceKind.PointExchanger`；`TryResolve` 映射
  `Sparta_077/5074` 与 `Athens_077/5216`；纳入 `IsShop` 与 `TryGetShopCurrency`。
- `Packets/PacketBuilder.CapitalNpcShops.cs`
  —— `GetCapitalShopCatalogSource` 增加 `PointExchanger => PointExchangerShopCatalog.Value`。
- `tests/Godswar.Server.ProtocolChecks/CapitalNpcServiceProtocolChecks.cs`
  —— 端点表新增两条；新增目录断言（5 帧 / 54 条 / shopType 4 / 首末条目与价格 / 不含 14073）。

> `Athens_077` 必须是 **5216**。曾按邻近项误推为 5217，而 5217 是 `Athens_078`
> 健身教练——那会把健身教练变成商店。已按 `NpcActorPlacementCatalog.cs` 核实。

## 待确认：货币

帧 `+9` = `0x04`，按既有映射（`TryGetShopCurrency(byte)`）落到
`CapitalNpcShopCurrency.BindingGold`，即**绑定金币**。

但该 NPC 设定是「积分兑换」，而角色钱包当前只有
银币 / 金币 / 绑定金币 / 勋章积分 / 天赋点 / 圣衣点，**没有通用「积分」字段**。
若要用独立积分，需要：新增角色积分字段 + 迁移、新增货币枚举值、
调整余额投影与扣除逻辑。当前先沿用既有机制让窗口能开、能买。
