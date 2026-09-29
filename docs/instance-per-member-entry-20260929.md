# 副本逐人入场 + 按副本结算改造 — 2026-09-29

目标：所有队伍副本统一成港湾那套入场流程；奖励从"报名冻结名单"改成"按副本最终进度算一份、
发给结算时仍在副本内的角色"。计分、怪物、掉落、每日上限、客户端不变。

## 已完成并部署

### 阶段 1 — 进度面板发给每个成员

- 美杜莎：`GameSessionRegistry.MedusaRunUi.cs`
  - 新增 `_medusaMemberUi`（键 `(WorldInstanceId, ClientSession)`）与 `TryRegisterMedusaMemberUi`。
  - 成员面板在**场景就绪后**发布 `Sync + 成员名单 + FightInfo(剩余秒数, 当前分数)`；新成员第一次收到的是完整快照。
  - `TryRegisterMedusaMemberUi` 由 `GameClientHandler.MedusaInvitation.cs` 在成员入场后调用。
  - 领导权与"结束副本"权限完全不变：`_medusaLeaderUi` 仍是唯一授权来源。
- 亚特兰蒂斯/飘渺的面板成员判定本来就是"在场"（`IsCurrentAtlantisMember` / `IsCurrentWonderlandMember`），
  且新会话首次发布即完整快照，故无需改动。

### 阶段 2 — 亚特兰蒂斯/飘渺改用逐人进入窗口

- `InstanceCallerProtocol.UsesPerMemberEntryWindow(kind)`：港湾、亚特兰蒂斯、飘渺为 true。
- `GameSessionRegistry.HarborAttackEntry.cs` 泛化为 `MemberEntryWindow`/`MemberEntryJoin`：
  窗口记录 `Kind`，并在队长提交时由 `BindMemberEntryRun(leader, instance, map, x, z)` 绑定目标副本。
- 队长提交只带"已确认"的成员（`ConfirmedMemberEntryMembers`），未确认者走既有释放路径（不扣次数）。
- 队长未入场 → `CloseMemberEntryWindowsAsync` 关闭全队窗口；队长入场 →
  窗口保留，之后点"进入"的成员各自领次数后直接进入正在运行的副本（`JoinCommittedMemberEntryRunAsync`）。
- 绑定点从港湾运行内部移到统一激活点：`GameClientHandler.InstanceEntryActivation.cs`。

### 验证

- 全量协议检查 **456 通过 / 22 失败**，与改造前逐项一致，无新增失败。
- 两处旧断言按新行为更新：
  - `InstanceCallerHandlerChecks.PartyEntry.cs`：美杜莎"计时器只发队长" → "发给队长与每个成员"。
  - 亚特兰蒂斯入场测试辅助函数（`OpalPolicy.EnterAtlantisAsync`、`OpalConsent` 的组队入口）：
    补上"成员在队长提交前确认窗口"这一步。
- 镜像 `sha256:de25dd65e2d8a42e6685dde819a27803ba16f63885db14cb542d0be37e25985b`，
  回滚镜像 `reborn-server:before-per-member-entry-20260929`。

## 未完成（下一阶段）

### 阶段 2.3 — 飘渺"后加入者"：已支持（方案 C，2026-09-29）

实机日志证明队员的点击帧完全正确，但入场被拒：

```
[instance-entry] 10217 character=12e1 scene=227 invitation=0 response=1 owned-window=1
[harbor] member join deferred character=12e1 instance=d4985886380449d7ad01b3ee3e5c9982
```

根因：飘渺在队长入场那一刻按当时人数封盘，未进场的角色被 `MayEnterWonderlandMap` 挡在门外，
而 `run.Participants` 与怪物计划都在 `TryFinalizeWonderlandAdmissions` 里一次性生成
（`WonderlandMonsterPlan.Create(island, entrants.Length, camp)`）。

按运营决定采用**运行中加人**，怪物数值一行不动：

1. `WonderlandRunRuntime._party` 改为可写 + 新增 `TryAddLateParticipant`
   —— 只扩参与名单（岛屿传送、友方战斗表现、区域目标筛选），**`_plans` 与已发布怪物保持不变**。
2. `MapInstance.Wonderland.MonsterRuntime` 新增 `TryAddParticipant`：把后加入者补进攻击者白名单
   （该名单同时把守"伤害是否计入"与目标筛选）。
3. `MapInstance.Wonderland.Admissions.cs` 新增 `TryAppendWonderlandParticipant`：同时扩运行名单、
   怪物攻击者名单与 `_wonderlandFinalizedIds`。
4. `GameSessionRegistry.WonderlandRun.cs` 新增 `TryAdmitWonderlandLateEntrant`：
   要求已封盘且该角色在副本外 → 先经世界属主追加名单 → 成功后写入 `Entrants`（传送门据此放行）。
5. `GameClientHandler.HarborAttackEntry.cs`：成员入场前对飘渺调用它；失败则释放其当日次数。

**效果**：队长先入场，队员随后点"进入"也能进去，并能正常使用岛屿传送、正常对怪物造成伤害；
已生成的怪物数量与血量维持队长入场时的数值（不重算）。

### 队员"进入窗口"的真实客户端验证（2026-09-29，已澄清）

一度怀疑"队员点击没反应"是承载封包选错。实测**推翻了该怀疑**：装上诊断日志后抓到队员客户端的回帧

```
[instance-entry] 10217 character=12e1 scene=227 invitation=0 response=1 owned-window=1
```

即队员客户端确实会弹出窗口、并按正确形状回帧（场景 227、邀请号 0、接受 1），
服务端也认出这属于他的窗口。所以 10222 + 10216 这对封包**可以**用于队员；
当时的失败纯粹是飘渺"封盘后不放人"，已由上面的阶段 2.3 修复。

诊断日志（`[instance-entry] 10217 …`）已在实机验证通过后**移除**。

### 阶段 3 — 三个副本的奖励都改为"按在场结算"

统一规则（三处一致）：

| 维度 | 规则 |
|---|---|
| 奖励值/档次 | **不变**：仍是副本自己的结果（亚特兰蒂斯按报名队伍分类、飘渺按岛屿进度、美杜莎按难度） |
| 发给谁 | **结算那一刻还在副本内的角色**（`WorldReady` + 所有权有效 + 实例匹配）；**掉线=不在场=不发** |
| 后加入者 | 持有自己的入场次数记录，**在场即享有** |
| 提前离开者 | 不享有 |
| 结算次数 | 以 `world_instance_id` 为幂等键，**每次进本独立结算**，一次运行只发一次 |

| 副本 | 改动 |
|---|---|
| 亚特兰蒂斯 | `MapInstance.AtlantisCompletionRewards.FreezeAtlantisCompletionMembers`：收件人从"在场 ∩ 报名集"改为"在场"；`AdmittedMembers` 仍是报名队伍（档次与持久化校验锚点）；契约放松"收件人必须属于报名队伍"；请求新增 `AdmissionReservationIds`（记录本次运行的全部入场 reservation） |
| 飘渺 | `WonderlandTitleRequest` 去掉"收件人必须是报名成员"的包含校验；收件人原本就取自 `SnapshotWonderlandMembersLocked`（在场）且后加入者已写入 `Entrants` |
| 美杜莎 | `SettleMedusaCompletionRewardAsync`：奖励名单从 `egress.AdmittedCharacterIds`（冻结）改为 `egress.Members`（在场）；**出口名单不动**，该送回家的人照旧送回；无人在场则不结算 |

对应断言按新语义更新：亚特兰蒂斯奖励契约新增"后加入者按在场享有奖励"的正向断言并移除"非报名成员必被拒"；
`InstanceCallerHandlerChecks.AtlantisCompletionRewards` 的"保留报名队伍分类 + 仅在场者领取"两条**无需改动即通过**（正是新规则的期望）。

### 阶段 4 — 收尾

- 临时诊断日志已删除。
- 全量协议检查 **456 通过 / 22 失败**，与改造前逐项一致，**无新增失败**。
  （期间 `B18C2 语义网关真实套接字集成` 偶发失败一次，重跑即通过，与本改造无关。）

### 阶段 3（原始设计记录，保留供追溯）

**结论**：我复用"队长那对封包"（10222 `RepetitionQueueState` + 10216 `RepetitionNotice`，
`PacketBuilder.InstanceEntry.cs`）给队员弹窗，是**选错了承载**。队长能用是因为窗口由他自己的
NPC 对话触发；非队长会话对这对封包的反应（是否弹窗、回帧形状）在真实客户端上未经验证。

**真实客户端上唯一验证过的"队员确认后各自入场"机制是美杜莎的邀请**：

| 环节 | 美杜莎（已验证） | 我新加的（不生效） |
|---|---|---|
| 弹窗封包 | 10224 `RepetitionInvitation`（带**邀请号**） | 10216 `RepetitionNotice`（邀请号固定 0） |
| 回帧 | 10217 带该邀请号 → `TryReadMedusaInvitationResponse` | 10217 邀请号为 0 |
| 过期 | `MonitorMedusaInvitationTimeoutAsync` 逐个邀请计时 | 客户端自身 60 秒 |
| 入场 | `AdmitInvitedMedusaMemberAsync`：各自领次数 → 传送 → 注册面板 | `JoinCommittedMemberEntryRunAsync`（同语义） |

**修复方向**：把队员入场统一到**邀请机制**上——即把美杜莎那条链路
（`PrepareMedusaMemberInvitations` / `TryBeginMedusaInvitation` / `PublishMedusaInvitationNoticeAsync`
/ 超时监控 / `AdmitInvitedMedusaMemberAsync`）抽成面向"队伍副本"的通用版本，
亚特兰蒂斯/飘渺/港湾的队员都走它。这样：

- 弹窗是客户端认识的原生确认框（带团长名字），点了才进；
- 不点 → 邀请超时 → 次数不扣（沿用 `ReleaseLegacyInstanceDailyEntryMembersAsync`）；
- 每次进本各自领次数（与阶段 3 的"结算时在场"规则天然一致）。

**当前状态**：诊断日志已上线（任何 16 字节 10217 都会打印
`[instance-entry] 10217 character=… scene=… invitation=… response=… owned-window=…`）。
抓到真实回帧后即可确认是"客户端不回帧"还是"回帧字段不同"，再据此实现通用邀请链路。

## 阶段 3 — 奖励按结算时在场快照

现状（三处都把"报名名单"当发放依据）：

1. 亚特兰蒂斯 `MapInstance.AtlantisCompletionRewards.cs:45 FreezeAtlantisCompletionMembers`
   - `admitted` = `_atlantisRewardAdmissions`（报名准入集）→ 写进请求的 `AdmittedCharacterIds`
   - `eligible` = **在场**角色 ∩ `_atlantisRewardAdmissions` → 真正的收件人
   - 结论：收件人已经是"在场"，但被报名集**求交**，后加入者被排除。
2. 飘渺 `GameSessionRegistry.WonderlandRun.cs:134`
   - `admitted = OriginalMembers.Where(Entrants.Contains)` → 称号/通关按报名名单。
3. 美杜莎 `MedusaTitleAwardContracts` / `MedusaCompletionRewardPolicy` 同类冻结快照。

落库校验把这份名单当成契约（`PostgresAtlantisCompletionRewardStore.Reads.cs`）：

- `AdmissionMatchesAsync`：`legacy_instance_daily_entries` 中该 reservation 的已入场行
  必须与请求名单**逐个、按序、数量完全相等**。
- `ReadExistingAsync`：持久化数组必须与请求数组完全相等，否则 `RequestConflict`。
- `ReadMembersAsync`：成员行必须与 `FrozenMembers` 数量与顺序完全相等。

因此"后加入者"今天放不进去：他有入场记录，但记录挂在**他自己的 reservation** 下，
而校验只看队长的那个 reservation。

改动设计：

1. `AtlantisCompletionRewardRequest` 增加"本次运行用到的全部 reservation 集合"。
   - 队长的 reservation 在 `ConfigureAtlantisRewardAdmission` 已知；
   - 后加入者由成员入场路径带来（`RecordLegacyInstanceAdmissionsAsync(reservationId, [charId])`
     → 需要新增 `RecordAtlantisLateAdmissionReservation`），在 `MapInstance` 上累积。
2. `FreezeAtlantisCompletionMembers`：`eligible` 改为"结算时在场且属于本次运行"
   （去掉与报名集的交集；仍要求 `WorldInstanceId == run` 且所有权有效、`WorldReady`——
   这正是"掉线不算在场"），并让 `admitted` 与 `eligible` 使用同一份角色集合。
3. `PostgresAtlantisCompletionRewardStore.AdmissionMatchesAsync`：改为
   "请求中每个角色，都能在上述 reservation 集合之一里找到已入场行"。
4. 飘渺/美杜莎按同一模式改：收件人 = 结算时在场者；落库校验用"这些人都属于本次运行"。
5. 幂等与"每次进本独立结算"不变：仍以 `world_instance_id` 为唯一键，一次运行只结算一次。

风险：奖励是已上线功能，必须逐副本上线、逐条改断言（`AtlantisCompletionReward*`、
`WonderlandTitle*`、`MedusaTitle*` 相关检查），并保留数据库备份与回滚镜像。
