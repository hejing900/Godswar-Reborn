# Godswar 掉落表编辑工具（Godswar.LootTool）

Windows 桌面程序（WinForms），直连 PostgreSQL，专门用来编辑**数据库拥有的怪物掉落表**：
`monster_loot_tables`（表头）+ `monster_loot_rules`（规则）。结构照 `tools/verify_monster_loot_migration.sql` 对齐。

---

## 编译成 EXE

```powershell
cd D:\Godswar-Reborn-main\tools\Godswar.LootTool
.\publish-loot-tool.ps1
```

产出 **`dist\Godswar.LootTool.exe`** —— **单文件、自包含**（约 50 MB），目标机器**不需要安装 .NET**，拷到哪都能双击运行。
脚本会自动把你当前的连接设置（`loot-tool.settings.json`）复制进发布目录，并对这个 EXE 跑一遍 `--selftest` 验证真能连库读写。

| 说明 | 值 |
| --- | --- |
| 目标平台 | `win-x64`（Windows 64 位） |
| 依赖 | 无（自带 .NET 10 + Windows Desktop 运行时） |
| 单文件 | 是（`PublishSingleFile` + 压缩） |
| 裁剪 | 否（WinForms 不能裁剪） |
| 设置文件 | 生成在 **EXE 同目录** `loot-tool.settings.json` |
| 自测报告 | 生成在 **EXE 同目录** `logs\selftest-*.txt` |

想只产出一个小体积 EXE（约 2–5 MB，但目标机器需装 .NET 10 Desktop Runtime）：

```powershell
.\publish-loot-tool.ps1 -Mode runtime
```

命令行参数（`--connection-string` / `--client-root` / `--selftest`）对 EXE 同样有效，也能用 `dist\Godswar.LootTool.exe --help` 查看。

---

## 启动

```powershell
cd D:\Godswar-Reborn-main\tools\Godswar.LootTool

.\start-loot-tool.ps1                                  # 构建并打开窗口（默认 D:\Godswar Origin）
.\start-loot-tool.ps1 -SelfTest                        # 只跑数据层自测，不开窗口
.\start-loot-tool.ps1 -ClientRoot 'C:\Godswar Origin'  # 换客户端目录
.\start-loot-tool.ps1 -ConnectionString 'Host=127.0.0.1;Port=5432;Database=godswar_local;Username=godswar;Password=godswar_dev_password'
```

也可以直接跑：

```powershell
dotnet run --project tools/Godswar.LootTool -c Release
```

命令行参数（会被记住，写入 `bin/.../loot-tool.settings.json`）：

| 参数 | 说明 |
| --- | --- |
| `--connection-string <串>` | 覆盖数据库连接串 |
| `--client-root <目录>` | 覆盖客户端根目录（用于中文名） |
| `--selftest` | 数据层自测 + 写入回环，不开窗口 |

界面里也有「连接串」「客户端目录」两个输入框，改完点「连接 / 刷新」即可，无需重启程序。

---

## 界面

**顶部连接区**（按参照工具的做法，分字段填写，不写连接串）：

| 字段 | 默认值 |
| --- | --- |
| 主机 | 127.0.0.1 |
| 端口 | 5432 |
| 数据库 | godswar_local |
| 用户名 | godswar |
| 密码 | godswar_dev_password |
| 客户端目录 | D:\Godswar Origin（用于中文名，可「浏览…」） |

按钮：

1. **连接数据库** —— 用上面填的信息连库，成功后在右侧显示「连接正常」，并自动读取一次。
2. **一键读取数据** —— 重新拉取怪物列表、物品目录、中文名；换库或换客户端目录后点它。
3. **浏览…** —— 选客户端根目录（中文名来源）。

所有字段都会被记住（`bin\...\loot-tool.settings.json`）。

**左侧怪物列表**：

- **`搜索怪物…`** 按钮 —— 弹窗按 **中文名 / 英文名 / template_key** 搜索，见下方「搜索怪物」。
- `显示所有` 按钮、`按怪物名查询 [___] [查询]`（输入即筛选）
- 筛选下拉：**全部 / 能刷出来的怪 / 未配置掉落 / 已配置掉落**
- 列表列：中文名 / 英文名 / `template_key` / 档位 / 区域 / 地图 / **刷怪点** / 掉落状态
  - **刷怪点为 0 时显示红色「0（不会掉落）」** —— 该怪没进入世界内容，配了也不会掉
  - 掉落按 `template_key` 绑定（`monster_templates` 是每个 source 一行，所以按 key 聚合）

### 搜索怪物

点 `搜索怪物…` 打开弹窗：

- 输入中文名 / 英文名 / key 即时筛选（例如输入「间谍」直接找到斯巴达间谍）
- 勾选 `只看会刷出来的怪` 可过滤掉永远不会掉的模板
- 结果按**刷怪点从多到少**排序，会掉的怪排最前
- 双击或点 `选择该怪物` → 主界面自动定位到该怪并载入它的掉落表（若被筛掉会自动恢复筛选）
- 底部提示「匹配 N 条，其中能刷出来 M 条」，刷怪点为红色 = 配了也不会生效

**右侧掉落编辑**：

- **掉落设置**：`启用该掉落表`、`单次最多掉落件数`（= `maximum_drops`）、当前规则数、`确认修改`（保存）
- **批量调整**：
  - `整体调整 [N] 倍` → `应用当前怪`（只改界面上的数值，需再点「确认修改」保存）／`应用所有怪`（**直接写库**，会二次确认）
  - `统一概率 [X] %` → `改当前怪`（只改界面）／`改所有怪`（**直接写库**，会二次确认）
- **规则表格**：`序号(loot_index)` / `物品ID` / `物品`（自动解析中文名）/ `概率%` / `最少` / `最多` / `启用`
- **按钮**：新增规则、删除选中规则、物品表…、确认修改、重新载入、删除整张表、自检
- 未保存改动有红点提示；**保存后出现橙色提示：必须重启游戏服务器才生效**

中文名来源（客户端目录）：

| 对象 | 来源 |
| --- | --- |
| 怪物 | `Localization\zh_cn\Monster\<区域>\Monster.ini`，段名 = `template_key`，取 `Name=`（该文件是 **UTF-16LE**，工具按 BOM 识别） |
| 物品 | `item_templates.name_key` → `Localization\zh_cn\Text\EquipName.dat`（UTF-8，`name_key<Tab>文本`） |

没有客户端目录时不影响使用，只是名称显示英文。

---

## 保存时会强制校验（服务端启动不变量）

服务端启动时 `MonsterLootContentSnapshot.Validate` 会拒绝下列数据，工具在写入前就拦住：

| 规则 | 说明 |
| --- | --- |
| `maximum_drops` 1–32 | 表头上限 |
| **规则条数 ≥ `maximum_drops`** | 违反会让**服务端启动直接失败** |
| 规则条数 ≥ 1 | 不想掉落就删整张表，不要留空表 |
| `loot_index` 0–31 且不重复 | 同时是掷骰输入与遍历顺序 |
| `chance_basis_points` 1–10000 | 界面按百分比输入，内部存万分之一 |
| 数量 1–255，且 `最多 ≥ 最少` | |
| `item_id` 必须存在于 `item_templates` | 外键；未知物品会在表格里以 ⚠ 标出 |

保存是**单事务**：先 upsert 表头与规则，再删除界面上已移除的序号。

---

## 关于「生效」

掉落内容由服务端在**启动时一次性读入内存**（`MonsterLootContentCatalog.Install`，全仓库没有热加载入口），
所以**改完必须重启游戏服务器**。本工具刻意**不碰 Docker**，只做提示；重启请自行执行：

```powershell
docker compose --profile legacy-raw restart server
```

---

## 自检（`--selftest` / 界面“自检”按钮）

- 连接、读怪物/物品目录、解析中文名的覆盖情况
- 打印现有掉落表全部内容（物品带中文名）
- **写入回环**：挑一个未配置掉落的怪，临时建表 → 读回比对 → 追加规则 → 删除规则 → 验证不变量拦截 → 清理还原
- 结构与一致性检查：规则数 < 上限的表、空表、停用的表/规则、未配置掉落的怪物数量

报告同时写到 `bin\Release\net10.0-windows\logs\selftest-*.txt`。

---

## 说明

- 目标框架 `net10.0-windows`（Windows 专用）。**故意不加入 `GodswarServer.sln`**，以免破坏 Linux/Docker 的解决方案构建。
- 依赖仅 `Npgsql 10.0.2`（与其它工具一致），无额外 UI 依赖。
- 默认连接串取自仓库根 `appsettings.json` 的 `storage.postgresConnectionString` 的主机/端口/账号，
  但**库名改成本地服务端实际在用的 `godswar_local`**。
- 掉落是**按 `template_key` 绑定**：同一个 key 出现在多张地图时共享同一张掉落表。想按地图区分，只能用不同的 key。
