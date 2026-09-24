# 宠物打工（Pet Work）协议逆向取证报告

生成方式：静态分析 `D:\Godswar Origin\Origin.exe`（未修改任何仓库源文件；分析脚本放在
`%TEMP%\re_pw.py`，只读加载 PE / MAP）。

**标签约定（本报告严格区分）**

| 标签 | 含义 |
|---|---|
| 【原文·客户端二进制】 | 直接从 `Origin.exe` 机器码/disasm 读出的常量、字符串引用、比较与运算（附原始反汇编片段） |
| 【原文·配置/文本】 | 客户端安装目录下的 XML / lua / dat 文本 |
| 【实测】 | 已有真实抓包或真实游戏内观测（本报告不新造实测；引用仓库既有记录时会标明出处） |
| 【推断·未证实】 | 由上述证据推出的结论，尚未被独立验证 |

---

## 0. 地址换算前提（必须显式说明）

PE 节表（实测 dump）：

```
num_sections 4  magic 0x10b  ImageBase 0x400000  SizeOfImage 0x11de000
.text   va=0x001000 vsize=0x51aedc rawptr=0x001000 rawsize=0x51b000
.rdata  va=0x51c000 vsize=0x0a8000 rawptr=0x51c000 rawsize=0x0a8000
.data   va=0x5c4000 vsize=0xbf6920 rawptr=0x5c4000 rawsize=0x077000
.rsrc   va=0x11bb000 vsize=0x02266c rawptr=0x63b000 rawsize=0x023000
file size 0x65e000
```

- `.text` / `.rdata` / `.data`（初始化部分）三节的 `rawptr == va`，因此对这三节：
  **file_offset == RVA，VA = 0x400000 + file_offset**（本报告所有 VA 均据此换算）。
- `.rsrc` 不满足（va=0x11bb000, rawptr=0x63b000），本报告不涉及。
- **MAP 文件的地址对本 exe 不可信**：不止 ±2 字节。例：map 里
  `?loadPetWorkInfo@CPetResourceManager@@IAEXXZ 005d5ea0`（RVA 0x1D5EA0），
  但真正引用 `/Settings/Sys/Pet_Job.xml` 的代码在 **VA 0x6AA130（RVA 0x2AA130）**；
  map 的 `?updateText@CPetWorkUI@@IAEXXZ 00653c70`（RVA 0x253C70），
  而真正的 `CPetWorkUI::init` 在 **VA 0x5C7EE0**、`updateText` 在 **VA 0x5C8730**。
  两者相差约 0xD0000 量级 ⇒ **本报告一律用「字符串 xref + 函数序言扫描」定位函数，不采信 map 地址**
  （map 仅用于确认"该类存在这些方法"与符号名）。

定位到并确认序言（`push -1; push <handler>; mov eax,fs:[0]…` 或 `55 8B EC`）的函数：

| VA | 判定 | 依据 |
|---|---|---|
| 0x5C7EE0 | `CPetWorkUI::init` | 先 push `/UI/XML/PetWork.xml` + `PetWorkWin`，再依次按 ID 取 10 个控件 |
| 0x5C80D0 (推测 `onWorkTypeChange`) | 含 851006/851007 控件 ID | 【推断·未证实】（未逐条读完） |
| 0x5C84D0 (推测 `onPayTypeChange`) | 含 851004 控件 ID | 【推断·未证实】（未逐条读完） |
| 0x5C8730 | **`CPetWorkUI::updateText`（本地预算刷新）** | 由 `init` 尾部 `push esi; call 0x5C8730` 调用；读 `this+0x1C`(付款方式)、`this+0x30`(时长)，写 851001/851002/851003 |
| 0x5C8DF0 | **`CPetWorkUI::doWork`（点确定后走这里）** | 校验 `this+0x1C`/`this+0x30`，报错键 `PetWorkNoPayType`/`PetWorkNoTime`，构造 `PetWorkQuery` |
| 0x5C92B0 | 消息分派器包装 | 取 `[this+0x34]→+0x68` 消息对象，`[obj+6]` 与 **10291 / 10294** 比较 |
| 0x5C93C0 | **S2C 10291 处理（打工状态/结果）** | 读消息 +4/+8/+0xa/+0xc/+0xe，渲染到 PetWork 窗口 |
| 0x5C9960 | 10294 处理 + 开窗重置 + 调 Lua `PetWork_onStateChange(n)` | 重置 `this+0x1C=0`、`this+0x30=0`，全部复选框取消，三行文本清空，拼接并执行 `PetWork_onStateChange(` + `0/1` + `)` |
| 0x6AA130 | **`loadPetWorkInfo`（Pet_Job.xml 解析）** | 引用 `/Settings/Sys/Pet_Job.xml`、`CostBase`、`GainBase`、`MoneyGain`、`BijouGain`、`Money`、`Bijou` |

---

## 1. 结论速览

| 问题 | 结论 | 强度 |
|---|---|---|
| Q1 C2S opcode | **未知（未取证）**。`doWork` 内部没有任何 wire opcode 常量；它走「资源查询 + 命令对象」两级间接 | — |
| Q1 取消是否同 opcode | **未知（未取证）**（但客户端存在独立的 'can abort' 状态与中止查询键，见 §4） | — |
| Q2 S2C 状态包 opcode | **10291**（客户端自己拿收到的消息 id 与 10291 比），另有 **10294** 走开窗/重置分支 | 【原文·客户端二进制】 |
| Q2 剩余时间编码 | 消息内 **u16**（payload 偏移 +0xa），直接数字格式化显示；单位（秒/分）**未知（未取证）** | 【原文·客户端二进制】（偏移） |
| Q3 10237 记录里的打工字段 | **未知（未取证）**（本次未取证到 10237 记录解析代码） | — |
| Q4 谁算奖励 | **两边都有**：本地预览（updateText）用 Pet_Job.xml 自己算并显示；服务器开工状态包（10291）另带 开支/经验/专长 数值直接显示 | 【原文·客户端二进制】 |
| Q5 公式 | 见 §5：`Money`/`Bijou` 是 **float**，`CostBase` 是 **int 向量**，`GainBase` 是 **float 向量**，`MoneyGain`/`BijouGain` 是 **两个 int**（`"%d,%d"`） | 【原文·客户端二进制】 |
| Q5 早期中止 20% | 文本原文（PETW_X0_19）确认；**20% 作用在哪一项未取证** | 【原文·配置/文本】 |
| Q6 门槛 | `Addiction_petwork`（防沉迷）、`PetWorkNoPayType`、`PetWorkNoTime`、玩家状态==4 的门 | 【原文·客户端二进制】+【原文·配置/文本】 |

---

## 2. Pet_Job.xml 解析（`loadPetWorkInfo`，VA 0x6AA130 起）

### 2.1 关键格式串（.rdata 原文 dump）

```
0x9510D0  b'%d,%d\x00'        # <<< MoneyGain / BijouGain 用的格式串
0x95a5a0  "Pet"               # <Config> 的父节点名
0x960c20  "CostBase"
0x960c2c  "GainBase"
0x960b78  "Lv"                # 每行 PlayerLv{n} 的 Lv 属性名
0x9512d0  "Money"
0x95394c  "Bijou"
0x960c38  "MoneyGain"
0x960c44  "BijouGain"
0x960c04  "/Settings/Sys/Pet_Job.xml"
```

⇒ **`MoneyGain="55360,6"` / `BijouGain="138400,10"` 各是两个整数**（`%d,%d`）。
【原文·客户端二进制 / .rdata 原始字节实测】

### 2.2 Config：CostBase 存成 int 向量，GainBase 存成 float 向量

CostBase 循环（VA 0x6AA41C 起；每段都是 `atof` → `0x7C0210`(浮点转整/取整) → 存入容器）：

```
006AA41C  be200c9600        mov  esi, 0x960c20        ; "CostBase"
006AA499  50                push eax                  ; 属性字符串
006AA49A  e8f5061100        call 0x7bab94             ; atof
006AA49F  83c404            add  esp, 4
006AA4A2  e8695d1100        call 0x7c0210             ; float -> int（__ftol 系列）
006AA4B4  e8b78ad9ff        call 0x442f70             ; push_back(int)
...
006AA51F  ... 0x7bab94 (atof)      ; 循环结束后再补最后一个元素
006AA531  call 0x7c0210
006AA543  call 0x442f70
```

GainBase 循环（VA 0x6AA54C 起；**没有** 0x7C0210 转换，直接存 float）：

```
006AA54C  be2c0c9600        mov  esi, 0x960c2c        ; "GainBase"
006AA5B8  50                push eax
006AA5B9  e8d6051100        call 0x7bab94             ; atof
006AA5BE  d95c241c          fstp dword ptr [esp+0x1c] ; <<< 保持 float
006AA5CE  e8dd8bd9ff        call 0x4431b0             ; push_back(float)
...
006AA645  call 0x7bab94
006AA64A  d95c241c          fstp dword ptr [esp+0x1c]
006AA65A  call 0x4431b0
```

⇒ `Time="3600,10800,28800,86400"` / `CostBase="1,3,8,24"` / `GainBase="1,3.5,10,32"` 中的
`CostBase` = 整数数组、`GainBase` = 浮点数组（因为 3.5 必须保留小数）。
**本次未取到客户端读取 `Time` 属性的代码**（只看到 CostBase/GainBase 两个属性名被查），
`Time` 是否被客户端使用 = **未知（未取证）**。

### 2.3 每行 `PlayerLv{n}` 的属性

```
006AA6B8  b9780b9600        mov  ecx, 0x960b78   ; "Lv"  -> 拼出子节点名
006AA6BF  e8ac31f9ff        call 0x63d870
006AA6C7  be d0129500       mov  esi, 0x9512d0   ; "Money"
006AA6E0  e8af041100        call 0x7bab94        ; atof
006AA6E5  d95c242c          fstp dword ptr [esp+0x2c]   ; Money  -> float
006AA6EC  be 4c399500       mov  esi, 0x95394c   ; "Bijou"
006AA705  e8 8a041100       call 0x7bab94        ; atof
006AA70A  d95c2430          fstp dword ptr [esp+0x30]   ; Bijou  -> float
006AA711  be 380c9600       mov  esi, 0x960c38   ; "MoneyGain"
006AA76F  68d0109500        push 0x9510d0        ; "%d,%d"
006AA775  e89e021100        call 0x7baa18        ; sscanf
006AA77D  be 440c9600       mov  esi, 0x960c44   ; "BijouGain"
006AA7DA  68d0109500        push 0x9510d0        ; "%d,%d"
006AA7E0  e833021100        call 0x7baa18        ; sscanf
006AA831  e8ca340000        call 0x6add00        ; map<level, PetWorkGainInfo>::insert
```

**字段类型结论（强，直接来自指令）**：

| XML 属性 | 解析方式 | 类型 |
|---|---|---|
| `Lv` | 子节点名 `PlayerLv{n}` | 用作 map 的键（**玩家等级**，见 §5.4） |
| `Money` | `atof` + `fstp dword` | **float** |
| `Bijou` | `atof` + `fstp dword` | **float** |
| `MoneyGain="a,b"` | `sscanf("%d,%d")` | **两个 int** |
| `BijouGain="a,b"` | `sscanf("%d,%d")` | **两个 int** |

### 2.4 `PetWorkGainInfo` 结构体布局

打包段原文（0x6AA7E5–0x6AA831，紧接 BijouGain 的 sscanf 之后）：

```
006AA7E5  8b4c2438        mov  ecx, dword ptr [esp+0x38]
006AA7E9  8b54243c        mov  edx, dword ptr [esp+0x3c]
006AA7ED  8b44242c        mov  eax, dword ptr [esp+0x2c]
006AA7F1  8b5c246c        mov  ebx, dword ptr [esp+0x6c]
006AA7F5  894c2454        mov  dword ptr [esp+0x54], ecx
006AA7F9  8b4c2444        mov  ecx, dword ptr [esp+0x44]
006AA7FD  89542458        mov  dword ptr [esp+0x58], edx
006AA801  8b542448        mov  edx, dword ptr [esp+0x48]
006AA805  89442450        mov  dword ptr [esp+0x50], eax
006AA809  8b442440        mov  eax, dword ptr [esp+0x40]
006AA80D  83c410          add  esp, 0x10
006AA810  894c2450        mov  dword ptr [esp+0x50], ecx
006AA814  8d4c2440        lea  ecx, [esp+0x40]
006AA818  89542454        mov  dword ptr [esp+0x54], edx
006AA81C  8944244c        mov  dword ptr [esp+0x4c], eax
006AA820  8b44243c        mov  eax, dword ptr [esp+0x3c]
006AA824  51              push ecx
006AA825  8d9424e8000000  lea  edx, [esp+0xe8]
006AA82C  52              push edx
006AA82D  89442460        mov  dword ptr [esp+0x60], eax
006AA831  e8ca340000      call 0x6add00
```

**结论与诚实边界**

- 结构体至少含 **2 个 float（Money、Bijou）+ 4 个 int（MoneyGain 两个、BijouGain 两个）= 24 字节**。
  这是【原文·客户端二进制】级别的（类型来自 §2.3 的 atof/sscanf 指令）。
- **每个字段的精确字节偏移：未知（未取证）**。原因：上式里 `[esp+0x2c]/[esp+0x30]/[esp+0x34]/
  [esp+0x38]/[esp+0x3c]/[esp+0x40]` 的 esp 基准在 `call 0x7baa18`（cdecl sscanf，参数由调用者清理，
  清理由 0x6AA80D 的 `add esp,0x10` 完成）前后不同步，逐字节换算无法在本次预算内闭合。
  因此**不给出结构体偏移数字**，只给字段集合与类型。
- **两个第 2 整数（6 / 10）的语义**：见 §5.3，与"获得专长点数"对应（推断，但有强锚点）。

---

## 3. C2S 请求（Q1）

### 3.1 `doWork`（VA 0x5C8DF0）里**没有** wire opcode

`doWork` 的实际流程（原文节选）：

```
005C8E2C  mov  eax, [edi+0x1c]      ; this+0x1C = 付款方式（0=未选）
005C8E2F  test eax, eax
005C8E31  jne  0x5c8e63
005C8E39  push 0x95be30             ; "PetWorkNoPayType"
...
005C8E63  mov  ecx, [edi+0x30]      ; this+0x30 = 时长档位（0=未选）
005C8E66  test ecx, ecx
005C8E70  push 0x95be44             ; "PetWorkNoTime"
...
005C8E9A  push ecx
005C8E9B  push eax
005C8E9C  lea  eax, [esp+0x54]
005C8EA0  push eax
005C8EA1  push ecx
005C8EA2  call 0x49e8c0             ; ChaSingleInstance getter（返回 eax=单例）
005C8EA7  add  esp, 4
005C8EAA  call 0x6aa8b0             ; 另一个单例 getter（CPetResourceManager 一侧）
005C8EAF  push 0x95be54             ; "PetWorkQuery"
...
005C8FE4  mov  edi, [edi+0x1c]      ; 付款方式
005C8FE7  sub  edi, 1
005C8FEA  je   0x5c907d             ; ==1 -> "Silver" 分支
005C8FF0  sub  edi, 1
005C8FF3  jne  0x5c910f             ; !=2 -> 直接收尾
005C8FF9  push 0x953854             ; "Gold"
...
005C910F  call 0x596d40             ; 命令/通知单例
005C9125  mov  dword ptr [eax+0x34], 0x26    ; 命令号 0x26
005C9133  mov  eax, 3
005C9138  call 0x5968c0             ; 带 int 参数执行/发送
...
005C9159  mov  edx, esi
005C915B  call 0x596de0             ; 带字符串参数（"PetWorkQuery…"）
```

**没有出现任何 10237…10330 范围的立即数**（对该函数所在区间 0x5C7000–0x5CC000 做的
全量 u16/u32 常量扫描里，落在本函数内的唯一 10239 命中位于 0x5C8E7D，而该地址落在
`e8 ff 27 e6 ff`（`call rel32`）的位移字节内 ⇒ **误命中**，非真实常量）。

⇒ **`doWork` 的实际发包 opcode 未知（未取证）**。已确定的是它：
1. 校验 `this+0x1C`（付款方式）与 `this+0x30`（时长档位），二者为 0 时本地报错（不发包）；
2. 用 `0x6AA8B0` 单例 + `PetWorkQuery` 键 + `Gold`/`Silver` 字符串构造一个"查询"文本/结构；
3. 交给 `sub_5C9240`；
4. 最后触发命令单例 `[0x596D40]+0x34 = 0x26`（int 参数 3）与 `sub_596DE0`（字符串参数）。

### 3.2 付款方式取值（**已确证**，两端一致）

```
doWork:   this+0x1C == 1 -> "Silver" 分支;  == 2 -> "Gold" 分支;  0 -> PetWorkNoPayType
10291 处理: movzx eax, byte ptr [esi+0xe] ; sub eax,1 ; je Silver(851005=1,851004=0)
                                         ; sub eax,1 ; jne skip  ; ==2 -> Gold(851004=1,851005=0)
```

【原文·客户端二进制】⇒ **1 = 银两(Silver)，2 = 金币(Gold)，0 = 未选择**。
（XML：`851004` = `Gold` 复选框、`851005` = `Silver` 复选框。）

### 3.3 "取消/中止"是不是同一个包

- Lua（`PetWorkProc.lua`，zh_cn 与 en_us 两份内容**完全相同**）：`state 1` 时
  `opBtn:SetText(PETW_X0_15)`（= 中止打工），说明**同一个按钮**在两种状态下复用；
- 客户端存在独立字符串 `PetStopWorkQueryCheck`（VA 0x95BEE4）与
  `PetWork_onStateChange(state)`，说明中止路径另有查询键。

⇒ 中止是否复用同一 opcode、还是另有一个 opcode：**未知（未取证）**。

---

## 4. S2C 状态报文（Q2）

### 4.1 opcode 判定过程（原文）

消息分派包装（VA 0x5C92B0）：

```
005C92BF  cmp  byte ptr [eax+0x10d], 0     ; 窗口可见性门
005C92C6  je   0x5c92f7
005C92C8  mov  eax, [edx+0x34]             ; 当前命令/消息对象
005C92CB  mov  eax, [eax+0x68]
005C92CE  test eax, eax
005C92D0  je   0x5c92f7
005C92D2  movzx ecx, word ptr [eax+6]      ; 收到的消息 id (u16)
005C92D6  sub  ecx, 0x2833                 ; 0x2833 = 10291
005C92DC  je   0x5c92ee                    ; 10291 -> 0x5C93C0
005C92DE  sub  ecx, 3
005C92E1  jne  0x5c92f7                    ; 其它 -> 丢弃
005C92E3  mov  ecx, edx
005C92E5  call 0x5c9960                    ; 10294 -> 开窗重置/调 Lua
005C92EE  lea  ecx, [eax+4]
005C92F1  push edx                         ; 参数 = CPetWorkUI this
005C92F2  call 0x5c93c0
```

### 4.2 payload 布局（**偏移来自指令，方向明确**）

处理函数 VA 0x5C93C0，以 `esi` = 报文子对象指针（= 上面 `eax+4`）：

| 偏移 | 宽度 | 读它的指令 | 用途 | 强度 |
|---:|---|---|---|---|
| +0x0 | u16 | （分派器用 `[eax+6]` 即本偏移+2 之外的 id，见上） | 头字段（推测长度/序号） | 【推断·未证实】 |
| +0x2 | u16 | `movzx ecx, word ptr [eax+6]`（相对本指针即 +2） | **消息 id = 10291 / 10294** | 【原文·客户端二进制】 |
| +0x4 | u32 | `005C96EF mov eax,[esp+0x38]; 005C96F4 mov ecx,[eax+4]` → 与键 `PlayerExpValue` 一起格式化，SetText 到元素 851002（获得经验） | **获得经验** | 【原文·客户端二进制】 |
| +0x8 | **u16** | `005C97E1 movzx eax, word ptr [esi+8]` → 键 `PlayerSkillPoint`，SetText 到 851003（获得专长） | **获得专长点数** | 【原文·客户端二进制】 |
| +0xa | u16 | `005C9452 movzx ecx, word ptr [esi+0xa]` → 键 `PetWorkRemainTime` → SetText 到元素 851011（剩余时间值） | **剩余时间** | 【原文·客户端二进制】 |
| +0xc | u16 | `005C95A2 movzx edx, word ptr [esi+0xc]` → `sub_535D00` 数字格式化 → SetText 到 851001（预计开支值） | **预计开支** | 【原文·客户端二进制】 |
| +0xe | u8 | `005C95B1 movzx eax, byte ptr [esi+0xe]` → 1=Silver/2=Gold，并打勾对应复选框 | **付款方式** | 【原文·客户端二进制】 |

原文节选：

```
005C9419  lea  eax, [esp+0x54]
005C941E  call 0x4e4360
005C9425  push 0x95be94                  ; "PetWorkRemainTime"
005C943E  call 0x42e800                  ; 构造 key
005C9452  movzx ecx, word ptr [esi+0xa]  ; <<< 剩余时间 u16
005C945C  call 0x535d00                  ; 数值 -> 文本
...
005C94F6  mov  ecx, [ebp+4]              ; 窗口对象
005C9500  push 0xcfc43                   ; 851011 = 剩余时间值元素
005C9505  call [edx+0x4c]                ; GetChildByID
005C9527  call [edx+0x84]                ; SetText
...
005C95A2  movzx edx, word ptr [esi+0xc]  ; <<< 预计开支 u16
005C95AC  call 0x535d00
005C9641  mov  ecx, [ebp+8]              ; 851001 = 预计开支值
005C964D  call eax                       ; SetText
...
005C96DD  push 0x95be0c                  ; "PlayerExpValue"
005C96EF  mov  eax, [esp+0x38]
005C96F4  mov  ecx, [eax+4]              ; <<< 获得经验（消息 +4）
005C96FD  call 0x535e60
005C9730  mov  ecx, [ebp+0xc]            ; 851002 = 获得经验值
...
005C97CB  push 0x95be1c                  ; "PlayerSkillPoint"
005C97E1  movzx eax, word ptr [esi+8]    ; <<< 获得专长（消息 +8）
005C97EC  call 0x535d00
```

**剩余时间编码：是报文里的一个 u16 计数值本身（不是绝对时间戳）**——客户端只是把这个数
交给数字→文本转换器直接显示。【原文·客户端二进制】；但**单位是秒/分/小时 = 未知（未取证）**
（没有任何 ×60、除 60 或与本地时钟比较的指令出现在这段显示代码里）。

### 4.3 10294 与 Lua 状态回调

VA 0x5C9960（10294 分支）：把 `this+0x1C`、`this+0x30` 清零，取消全部复选框，把
851011/851012/851013 文本清成 0x95951C 处的空串，然后拼字符串并执行 Lua：

```
005C9A4F  push 1
005C9A51  push 0xcfc43            ; 851011
005C9A6B  ... SetText(0x95951c)   ; 清空
005C9A85  push 1
005C9A87  push 0xcfc44            ; 851012
005C9AAA  push 1
005C9AAC  push 0xcfc45            ; 851013
005C9B07  push 0x95becc           ; "PetWork_onStateChange("
005C9B14  call 0x428290           ; 拼接
005C9B1C  cmp  byte ptr [esp+0x14], 0
005C9B23  push 1                  ; -> "(1)"
005C9B2C  push edi                ; edi=0 -> "(0)"
005C9B32  call 0x49f680
005C9B3B  push 0x959e60           ; ")"
005C9B49  call 0x74b890           ; 脚本引擎执行
005C9B7E  call eax                ; Execute(script_string)
```

`[esp+0x14]` 的来源：

```
005C9994  call 0x4a12c0            ; 取本地玩家/自身对象
005C9999  cmp  dword ptr [eax+0x34], 4
005C99A0  sete al                  ; al = (player_state == 4)
```

⇒ Lua 的 `state` 参数 = **1 当本地玩家对象 `+0x34` 字段等于 4，否则 0**。
字段语义（"4" 代表什么状态）**未知（未取证）**；注意这与 Lua 注释
（state 1 = 可以中止打工）一致 ⇒ 该字段很可能表示"正在打工"。【推断·未证实】

---

## 5. 奖励/开支算术（Q4 + Q5）

### 5.1 客户端**会**用 Pet_Job.xml 自己算（本地预览）

`CPetWorkUI::updateText`（VA 0x5C8730，由 `init` 调用）原文开头：

```
005C875D  mov  ebp, [esp+0x1dc]     ; ebp = CPetWorkUI*
005C8764  mov  eax, [ebp+0x30]      ; 时长档位
005C8767  mov  ecx, [ebp+0x1c]      ; 付款方式
005C876A  push eax
005C876B  push ecx
005C876C  lea  edx, [esp+0x8c]      ; 结果结构体（by-value 返回）缓冲
005C8773  push edx
005C8774  push ecx
005C8775  call 0x49e8c0             ; 单例 getter
005C877A  add  esp, 4
005C877D  call 0x6aa8b0             ; CPetResourceManager 侧单例 getter
...
005C8798  mov  eax, [ebp+0x1c]
005C879B  sub  eax, 1
005C879E  je   0x5c8abf             ; ==1 (Silver) 分支
005C87A4  sub  eax, 1
005C87A7  je   0x5c87e4             ; ==2 (Gold) 分支
005C87A9  ...                       ; ==0：三行文本全部清空(0x95951c)，返回
```

- **预计开支（851001）**：两个分支各自 `fld dword ptr [esp+0x88]`（Gold，0x5C87F5）/
  `fld dword ptr [esp+0x84]`（Silver，0x5C8AD0），然后
  `push "Gold"/"Silver"` + `call 0x536120`（float→文本）→ `SetText([ebp+8])`。
  ⇒ **开支是浮点数**，且金币/银两取自两个**相邻的 float 字段**（相隔 4 字节）。
  【原文·客户端二进制】。**精确结构体偏移未取证**（esp 基准在 by-value 返回缓冲的
  push/add 序列中无法闭合）；由字段相邻性可**推断**为 `{float Money; float Bijou}` 的
  +0 / +4，其中 Silver 读 +0、Gold 读 +4。【推断·未证实】
- **获得经验（851002）**：键 `PlayerExpValue`（0x95BE0C），值取自栈上结构体字段
  （`005C891B mov eax,[esp+0x98]` → `005C892C call 0x4e4200`）→ `SetText([ebp+0xc])`。
- **获得专长（851003）**：键 `PlayerSkillPoint`（0x95BE1C），值取自另一字段
  （`005C8A33 mov eax,[esp+0x9c]`）→ `SetText([ebp+0x10])`。

⇒ **Q4 答案：客户端自己会算并显示（预览行），数据源就是 `Pet_Job.xml`（经资源管理器单例）；
同时服务器在 10291 里也会把 开支/经验/专长 直接发过来供"已开工"状态显示（§4.2）。
两个路径用的 UI 元素与文本键完全相同。**

### 5.2 各字段如何参与（可与锚点同时成立的公式）

元素映射（【原文·配置/文本】PetWork.xml + 【原文·客户端二进制】init）：
`851001`=预计开支值、`851002`=获得经验值、`851003`=获得专长值、`851011`=剩余时间值、
`851004`=金币、`851005`=银两、`851006..851009`=1/3/8/24 小时。

```
h = 时长档位 0..3        （851006..851009 顺序 → CostBase/GainBase 的下标 0..3）
p = 付款方式 1=银两(Money 通道) / 2=金币(Bijou 通道)

开支      = (p==2 ? Bijou : Money) * CostBase[h]          # 浮点结果，直接显示
获得经验  = (p==2 ? BijouGain.1 : MoneyGain.1) * GainBase[h]
获得专长  = (p==2 ? BijouGain.2 : MoneyGain.2) * GainBase[h]
```

**锚点校验（运营方给的真实数值）**：玩家等级 140、金币通道、1 小时 →
`h=0` ⇒ `CostBase[0]=1`、`GainBase[0]=1`；表内 `Bijou="119"`、`BijouGain="138400,10"`：

```
开支 = 119 * 1      = 119      ✔ 与"119 金币"一致
经验 = 138400 * 1   = 138400   ✔ 与"138400 经验"一致
专长 = 10 * 1       = 10       ✔ 与"10 点专长"一致
```

⇒ 公式在 h=0 处与真实数值**完全吻合**；`GainBase[1]=3.5` 这类小数说明
**经验/专长侧确实要乘 GainBase（浮点）**。【推断·未证实（只有 h=0 被真实数值锚定）】
- `CostBase` 为 int 数组（§2.2 `__ftol` 转换）⇒ 开支 = float × int。
- **未能取到 `getGainInfo` 本体**（map 符号 `?getGainInfo@CPetResourceManager@@QAE?AUPetWorkGainInfo@@HH@Z`
  的 map 地址 0x5D3BC0 已证实不可用；本次在 `updateText`/`doWork` 里看到的是
  **被内联/内嵌的等价计算块**，没有独立的 call 目标可读）。
  因此"第 2 整数是否参与乘法"**未取证**——它要么与第 1 个整数同乘 `GainBase[h]`，
  要么是"额外/固定"项；两种写法在 h=0 时都得 10，无法区分。

### 5.3 `MoneyGain="55360,6"` 的第 2 个数是什么

- 【原文·客户端二进制】它是 `%d` 整数（§2.1），且与第 1 个整数一起被塞进同一个
  `PetWorkGainInfo`（§2.4）。
- 【原文·客户端二进制】10291 状态包分别携带 **经验(u32@+4)** 与 **专长点数(u16@+8)**，
  显示行分别是 PETW_X0_4"获得经验" / PETW_X0_5"获得专长"。
- 【原文·配置/文本】`BijouGain="138400,10"` 与真实数值"138400 经验 + 10 专长"一一对应。

⇒ 第 2 个数 = **专长点数（技能点 / specialty）**，与第 1 个数（经验）同属一次打工的收获。
【推断·未证实（三条证据同向，但缺直接锚定 h≠0 的实测）】
它**不是**等级区间索引、也**不是**上限：解析代码里两个 `%d` 被写进同一结果结构，
没有任何"与等级表比较/取 min/max"的指令出现在解析路径里。【原文·客户端二进制（否定性证据）】

### 5.4 表是按**玩家等级**索引

```
006AA6B8  mov  ecx, 0x960b78   ; "Lv"
006AA6BF  call 0x63d870        ; 用循环变量拼子节点名
（循环体在 006AA6B0..006AA845，遍历 <Job> 的所有子节点）
006AA831  call 0x6add00        ; insert(level, PetWorkGainInfo)
```

- `<Job>` 下的每行是 `PlayerLv{n}`，解析用的属性名是 `Lv`，键来自行内的 `Lv` 值
  （1..140），而不是宠物对象/宠物等级。【原文·客户端二进制 + 原文·配置/文本】
- 宠物对象数据**完全没有出现在这段解析里**：没有任何"读宠物等级/资质"的调用。
  `updateText` 传给资源查询的只有 `this+0x1C`(付款) 与 `this+0x30`(时长)。
  ⇒ **公式里不含宠物等级/宠物资质**（客户端侧如此）。【原文·客户端二进制】
  注：**玩家等级的来源**（本地玩家等级从哪个字段取）出现在被我截断的
  `0x5C8730` 之前/之内的部分未逐条确认 ⇒ 该细节【未取证】。

### 5.5 早期中止 = 20%

- 【原文·配置/文本】`Base\text.lua` 的 `PETW_X0_19`：
  "你已派遣宠物外出打工，时间结束后宠物自动返回。临时中止宠物打工，未完成的时间仅能获得20％的收益，且不退还打工开支，请谨慎选择！"
- 【原文·配置/文本】`PetWorkProc.lua`：`state==1` 时按钮文本变为 `PETW_X0_15`（中止打工），
  且把 `851014` 文案换成 `PETW_X0_19`。
- **20% 具体乘在哪一项（经验？专长？两者？是否向下取整？）：未知（未取证）**。
  客户端里没有找到 0.2 / 20 的常量参与这段计算（本次未对全镜像做 0.2f 常量扫描）。

---

## 6. 其它门槛（Q6）

| 门槛 | 证据 | 强度 |
|---|---|---|
| 防沉迷 | 字符串 `Addiction_petwork` @ VA 0x95BDF8（就在 PetWork 一组字符串中）；`Message.dat` 文本为「未通过防沉迷验证，无法使用宠物打工功能。」 | 【原文】字符串位置已实测；**引用它的代码位置未取证** |
| 必须选付款方式 | `PetWorkNoPayType` @ 0x95BE30，`doWork` 里 `this+0x1C==0` 即走该分支 | 【原文·客户端二进制】 |
| 必须选时长 | `PetWorkNoTime` @ 0x95BE44，`doWork` 里 `this+0x30==0` 即走该分支 | 【原文·客户端二进制】 |
| 玩家状态门 | `cmp dword ptr [eax+0x34], 4`（0x5C9999）与 `jne 0x5c9900`（0x5C9413）：不满足时 10291 分支直接返回 | 【原文·客户端二进制】；语义未取证 |
| 窗口可见性门 | `005C92BF cmp byte ptr [eax+0x10d], 0` | 【原文·客户端二进制】 |
| 中止查询键 | 字符串 `PetStopWorkQueryCheck` @ 0x95BEE4 | 【原文】字符串已实测；引用点未取证 |
| 宠物天赋"打工" | `Message_Pet.dat` `Genius3=打工`；道具 `Pet10112` 授予 | 【原文·配置/文本】 |
| 一次只能一只 / 打工时不能召唤别的宠物 | **未知（未取证）**（客户端侧未见对应分支；需服务端/抓包证据） | — |

---

## 7. 明确未取证清单（不要当成已知）

1. **C2S 打工请求的 opcode 与 payload 布局**（含取消/中止是否为独立 opcode）。
   已排除：不在 `doWork` 的常量里；`doWork` 走 `sub_5C9240` + 命令单例(`[0x596D40]+0x34=0x26`)。
   下一步建议：在 `sub_5C9240` / `0x5968C0` / `0x596DE0` 内追 opcode 写入点，或对 `[0x1576154]`
   客户端的 send 函数下断。
2. **10291 剩余时间的单位**，以及 +0xa / +0xc 两个 u16 的确切语义（我只确证了它们分别被显示到
   "剩余时间"和"预计开支"两行）。
3. **`PetWorkGainInfo` 每个字段的精确偏移**（类型与字段集合已确证）。
4. **90/`getGainInfo` 本体的指令级公式**（当前公式是"由类型+锚点反推"的推断）。
5. **早期中止 20% 的适用项与取整规则**。
6. **10237 记录内是否有打工状态/剩余时间字段**（本次未取证到 10237 记录解析代码；
   仓库既有文档把 10237 记为"8 字节头 + N×0xA8 记录"，但那是**实测**结论，非本次客户端取证）。
7. **10294 的语义**（是"结束/返回"还是"取消结果"）——只确证它触发开窗重置与
   `PetWork_onStateChange(0|1)`。
8. `Time="3600,10800,28800,86400"` 是否被客户端读取（只确证 CostBase/GainBase 两个属性名被查）。

---

## 8. 原始反汇编摘录索引

| 主题 | VA 区间 |
|---|---|
| Pet_Job.xml 解析（CostBase/GainBase/每行属性/打包） | 0x6AA130–0x6AA895（本报告引用 0x6AA41C–0x6AA831） |
| `CPetWorkUI::init` | 0x5C7EE0–0x5C80D0 |
| `CPetWorkUI::updateText` | 0x5C8730–0x5C8ABF+ |
| `CPetWorkUI::doWork` | 0x5C8DF0–0x5C91F0 |
| 消息分派（10291/10294 比较） | 0x5C92B0–0x5C92FA |
| 10291 处理（payload +4/+8/+0xa/+0xc/+0xe） | 0x5C93C0–0x5C9890+ |
| 10294 处理 + Lua 回调 | 0x5C9960–0x5C9BEB |
| 调度表（低位 opcode 10001–10199） | 字节表 0x4EE900（199 项）、dword 表 0x4EE82C（53 项）、分派点 0x4EA861(`sub eax,0x2711`) |

> 说明：本报告所有反汇编均为 capstone 现场反汇编输出，未做人工改写；
> 提到"未取证"的地方就是本次没有读到能支撑结论的指令。
