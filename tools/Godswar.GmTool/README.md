# Godswar GM 工具（Godswar.GmTool）

直连 PostgreSQL 的本地 GM 工具，浏览器界面：

1. **按角色名查询角色**，查看角色各项属性（战斗属性、基础数据、装备、背包、技能、宠物、天赋加成）。
2. **检索全部物品**（ID / 英文名 / name_key / 中文名），选中后**发放给指定角色**。

---

## 启动

推荐用启动脚本（会以**独立进程**运行，退出终端/关闭页面都不影响它）：

```powershell
cd D:\Godswar-Reborn-main\tools\Godswar.GmTool

.\start-gm-tool.ps1                      # 跟随仓库 appsettings.json 的数据库
.\start-gm-tool.ps1 -Database godswar_test      # 换库
.\start-gm-tool.ps1 -Url 'http://0.0.0.0:8090'  # 换监听地址（默认 127.0.0.1:8090）
.\start-gm-tool.ps1 -Rebuild -Foreground        # 重新构建 + 前台运行（调试用）

.\stop-gm-tool.ps1                       # 停止（只结束监听 8090 的那个进程）
```

脚本会把输出写到 `logs\gm-tool.out.log` / `gm-tool.err.log`。

也可以直接跑：

```powershell
$env:GODSWAR_GM_POSTGRES_CONNECTION_STRING='Host=127.0.0.1;Port=5432;Database=godswar;Username=godswar;Password=godswar_dev_password'
$env:GODSWAR_GM_CLIENT_ROOT='D:\Godswar Origin'          # 可选：用于中文名检索
dotnet run --project tools/Godswar.GmTool -c Release
```

然后打开 <http://127.0.0.1:8090>。

也支持命令行参数：`--connection-string <...>`、`--client-root <...>`、`--urls http://127.0.0.1:8090`。

### 连接串解析顺序

1. `-ConnectionString` 参数 / `--connection-string`
2. 环境变量 `GODSWAR_GM_POSTGRES_CONNECTION_STRING`
3. 环境变量 `GODSWAR_POSTGRES_CONNECTION_STRING`（与游戏服务器同名变量）
4. 本工具 `appsettings.json` 的 `postgresConnectionString`
5. **仓库根 `appsettings.json` 的 `storage.postgresConnectionString`** ← 换服务器时改这里，工具会自动跟随（按属性名递归查找，层级变了也能找到）
6. `-Host/-Port/-Database/-User/-Password` 组合

---

## 运维

### 页面关掉 / 终端关掉会怎样

| 操作 | 工具是否还在跑 |
| --- | --- |
| 关闭浏览器标签页 | **还在跑**。重新打开 <http://127.0.0.1:8090> 即可 |
| 关闭启动它的终端 | **还在跑**（`start-gm-tool.ps1` 用独立进程方式启动，父进程退出后它自行存活） |
| 重启机器 / 注销 | 不在了，重新执行 `start-gm-tool.ps1` 即可 |
| 工具进程崩溃/被杀 | 服务不可用；页面红字会提示"工具服务未响应"，重启即可 |

工具本身**无状态**：所有数据都在数据库里，随时重启随时接着用。
浏览器里记的「接口地址」存在 localStorage，重启工具不用重设。

### 换服务器 / 换数据库

| 场景 | 做法 |
| --- | --- |
| 游戏服务器换成连另一个库 | 改**仓库根 `appsettings.json`** 的 `storage.postgresConnectionString`，然后 `.\stop-gm-tool.ps1` + `.\start-gm-tool.ps1`（默认就会读它） |
| 只想临时查另一个库 | `.\start-gm-tool.ps1 -Database <库名>` 或 `-ConnectionString '<完整连接串>'` |
| 同时想看两个库 | 用不同端口起两个实例：`.\start-gm-tool.ps1 -Database a -Url http://127.0.0.1:8090` 和 `.\start-gm-tool.ps1 -Database b -Url http://127.0.0.1:8091`；页面右上角「接口」切换 |
| 游戏服务器重新部署/重启 | 工具**不受影响**（独立连接）。服务器完成内容发布后，工具下次检索就是新的物品目录，无需重启 |
| 服务器跑了新的数据库迁移 | 一般不用动；若改了 `character_stat_summary` 等视图/列名，重新 `.\start-gm-tool.ps1 -Rebuild` |
| 工具在另一台机器上 | 工具端 `-Url http://0.0.0.0:8090`，页面右上角「接口」填 `http://<那台机器IP>:8090` |

> ⚠ 用 `-Url http://0.0.0.0:8090` 会把一个**能写数据库**的工具暴露到网络上，
> 仅限可信内网；对外网开放请自行加反向代理 + 认证。

### 开机自启（可选）

```powershell
$action  = New-ScheduledTaskAction -Execute 'pwsh.exe' `
  -Argument '-NoProfile -File "D:\Godswar-Reborn-main\tools\Godswar.GmTool\start-gm-tool.ps1"'
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName 'GodswarGmTool' -Action $action -Trigger $trigger -RunLevel Highest
# 取消： Unregister-ScheduledTask -TaskName 'GodswarGmTool' -Confirm:$false
```

---

## ⚠ 一致性风险（必读）

本工具**直接写数据库**，不会通知正在运行的游戏服务器。

- 目标角色**在线**时：服务器内存里保存着该角色的背包状态，下次存档会**覆盖**本次发放。
- 目标角色**离线**时：直连写库是安全的，角色下次登录即可看到。

因此 `/api/grant` **强制要求** `confirmOffline: true`；界面上必须勾选「我确认目标角色已下线」。
未勾选时接口返回 `409`，并附上账号的 `login_status` / 最后登录登出时间供判断。

> 注意：`accounts.login_status` 在服务器异常退出后可能是**过期值**，不要只依赖它；
> 最稳妥的做法是确认该账号当前没有游戏连接。

**建议流程**：让角色下线 → 在工具里查询确认 → 发放 → 让角色重新登录。

---

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/status` | 连接信息、角色数、物品行数、当前发布修订 |
| GET | `/api/characters?name=&limit=` | 按角色名模糊查询（留空列出全部） |
| GET | `/api/characters/{id}` | 角色详情：`character` / `stats` / `talents` / `equipment` / `bag` / `skills` / `pets` |
| GET | `/api/items?q=&kind=&limit=` | 物品检索：纯数字按 ID 精确匹配，否则按 英文名/name_key/中文名 模糊匹配 |
| GET | `/api/items/kinds` | 全部物品类型 |
| POST | `/api/grant` | 发放物品 |

### POST /api/grant

```json
{
  "characterId": 3,
  "itemId": 3820,
  "quantity": 150,
  "confirmOffline": true,
  "dryRun": false,
  "note": "补偿发放"
}
```

- `dryRun: true` → 只返回落位方案，**不写库**。
- 返回 `placements`：每个槽位的 `before` / `after` / `added` / `newRow`。

**发放规则**

- 目标位置固定为背包（`item_location = 1`），槽位范围 `0..95`（96 格，24 格/页）。
- 堆叠上限取自物品 `stats->>'Overlap'`；先填满已有未满堆叠，再占用新的空闲槽位（不会重复规划同一槽位）。
- 绑定状态：物品 `stats` 含 `BindType` 时写入 `bound = 1`，否则 `0`。
- 品质/星级固定 `1`（与 `SetEquippedWeapon.ps1` 的既有做法一致）。
- 整个发放是**单个事务**；任何一步失败都回滚，不会留下半个物品。
- 每次写入都会往 `character_item_audit` 记一行：`source='gm-tool'`，
  `action='gm-grant-insert' | 'gm-grant-stack'`，
  `old_item = {"note":..., "previousStack":..., "grantedStack":...}`。
- 背包满时返回 `400`，消息说明未写入任何数据。
- 若落位槽位超出已解锁背包页（`bag_num × 24`），返回里会带
  `slotsBeyondUnlockedPages`，界面给出「客户端可能看不到」的提醒。

---

## 说明

- 物品检索的**权威来源**是 `item_templates`（外键目标）与当前发布修订
  `item_template_content_definitions` 的并集；发放时要求物品存在于
  `item_templates`，否则返回明确错误（提示先让服务器完成一次内容发布）。
- 服务端的 `display_name` 是英文；中文名通过读取客户端
  `Localization/zh_cn/Text/EquipName.dat` 补充（`localizedName` 字段）。
  未配置客户端目录时该功能自动关闭，其余功能不受影响。
- 角色属性直接取服务端自己的视图 `character_stat_summary` /
  `character_talent_stat_summary`，与游戏内数值口径一致。
