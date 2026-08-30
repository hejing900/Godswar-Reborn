[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [ValidateSet('Status', 'Apply')]
    [string]$Mode = 'Status',

    [ValidatePattern('^godswar(?:_outbox_repair_[a-f0-9]{10})?$')]
    [string]$Database = 'godswar',

    [switch]$DisposableTest
)

# Exact v317 replay only.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$postgresContainer = 'godswar-dev-postgres'
$tempestContainer = 'godswar-dev-tempest-openworld-01'
$dwargonContainer = 'godswar-dev-dwargon-openworld-01'
$redisContainer = 'godswar-dev-redis-coordination'
$databaseUser = 'godswar'
$eventId = 'b6753826-ebcd-4c40-91e3-e856b27621cb'
$sparseMigrationChecksum =
    '6186E1DB0FCFEEC40A7593AE60E05D468F0A45E40556EC2FFAFA7055CC41075F'
$claimPlanMigrationChecksum =
    '232F53D0C36BEDF4DCC729F486ADE852FFE7E17880F21FAA91D16161D6524030'
$operationText =
    'localdev|outbox-poison-replay|pet_durable_v1|character:2|v317|v1'
$requestText = $operationText +
    '|attempts:8->0|poison:consumer_failure_max_attempts->pending' +
    '|payload:a0f41b055090797377f86874e7b1c57d0ed943a0e565ea2b6c6876136b6aafb6'

. (Join-Path $PSScriptRoot `
    'RepairLocalDevelopmentPetRebirthExperience.Guards.ps1')

if ($DisposableTest) {
    if ($Database -notmatch '^godswar_outbox_repair_[a-f0-9]{10}$') {
        throw 'Disposable outbox-repair database required.'
    }
}
elseif ($Database -ne 'godswar') {
    throw 'The real repair requires the godswar database.'
}

function Invoke-OutboxRepairPsql([string]$Sql, [string]$Marker) {
    $output = $Sql | & docker exec -i $postgresContainer `
        psql -X -q -A -t -v ON_ERROR_STOP=1 `
        -U $databaseUser -d $Database 2>&1
    $exitCode = $LASTEXITCODE
    $lines = @($output | ForEach-Object { $_.ToString() })
    if ($exitCode -ne 0) {
        throw "Outbox poison repair failed and rolled back:`n$($lines -join "`n")"
    }
    $receipt = $lines | Where-Object {
        $_.StartsWith($Marker, [StringComparison]::Ordinal)
    } | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($receipt)) {
        throw 'The database returned no outbox repair receipt.'
    }
    $receipt.Substring($Marker.Length) | ConvertFrom-Json
}

function Get-ExpectedPayloadSql {
    @"
jsonb_build_object(
 'repairVersion',1,
 'source','offline_isolated_localdevelopment_outbox_repair',
 'eventRowId',6774,
 'eventId','$eventId',
 'commandInboxId',6719,
 'consumerKey','pet_durable_v1',
 'aggregateType','character_pet_value',
 'aggregateKey','character:2',
 'aggregateVersion',317,
 'eventType','pet.basic_savvy_reset',
 'contractVersion',2,
 'createdAtUtc','2026-08-11T14:41:57.319068Z',
 'poisonedAtUtc','2026-08-11T14:43:23.374761Z',
 'poisonReason','consumer_failure_max_attempts',
 'attemptCountBefore',8,
 'attemptCountAfter',0,
 'maximumAttempts',8,
 'payloadSha256',
   'a0f41b055090797377f86874e7b1c57d0ed943a0e565ea2b6c6876136b6aafb6',
 'action','requeue_for_current_contract_validation')
"@
}

function Get-StatusSql([string]$OperationHex, [string]$RequestHex) {
    $expectedPayload = Get-ExpectedPayloadSql
    @"
BEGIN READ ONLY;
WITH target AS (
 SELECT event.*,
   encode(sha256(convert_to(event.payload::text,'UTF8')),'hex') payload_sha
 FROM public.outbox_events event
 WHERE event.event_id='$eventId'::uuid
), position AS (
 SELECT * FROM public.outbox_consumer_positions
 WHERE consumer_key='pet_durable_v1'
   AND aggregate_type='character_pet_value'
   AND aggregate_key='character:2'
), receipt AS (
 SELECT audit.* FROM public.command_audit audit
 WHERE audit.principal_type='developer'
   AND audit.principal_key='13'
   AND audit.aggregate_type='character_pet_value'
   AND audit.aggregate_key='character:2'
   AND audit.command_family='outbox_poison_replay_repair'
   AND audit.operation_id=decode('$OperationHex','hex')
), facts AS (
 SELECT
   (SELECT count(*) FROM target) target_count,
   COALESCE((SELECT event.id=6774
      AND event.command_inbox_id=6719
      AND event.consumer_key='pet_durable_v1'
      AND event.aggregate_type='character_pet_value'
      AND event.aggregate_key='character:2'
      AND event.aggregate_version=317
      AND event.event_type='pet.basic_savvy_reset'
      AND event.contract_version=2
      AND event.ordering_policy='strict'
      AND event.attempt_count=8 AND event.max_attempts=8
      AND event.delivered_at IS NULL
      AND event.poisoned_at=
        '2026-08-11 14:43:23.374761+00'::timestamptz
      AND event.poison_reason='consumer_failure_max_attempts'
      AND event.created_at=
        '2026-08-11 14:41:57.319068+00'::timestamptz
      AND event.payload_sha=
        'a0f41b055090797377f86874e7b1c57d0ed943a0e565ea2b6c6876136b6aafb6'
      AND event.lease_token IS NULL FROM target event),false) source_ready,
   COALESCE((SELECT event.poisoned_at IS NULL
      AND event.poison_reason IS NULL
      AND event.lease_token IS NULL
      AND (event.delivered_at IS NOT NULL OR event.attempt_count<8)
      FROM target event),false) post_ready,
   (SELECT count(*) FROM receipt) receipt_count,
   COALESCE((SELECT bool_and(
      audit.request_hash=decode('$RequestHex','hex')
      AND audit.outcome_code='repaired'
      AND audit.retention_policy='permanent'
      AND audit.detail_payload=$expectedPayload) FROM receipt audit),false)
      receipt_valid,
   (SELECT min(id) FROM receipt) receipt_audit_id,
   COALESCE((SELECT current_version FROM position),-1) current_version,
   EXISTS (SELECT 1 FROM public.schema_migrations
      WHERE migration_id='20260830_122_outbox_ordered_sparse')
      sparse_migration_applied,
   EXISTS (SELECT 1 FROM public.schema_migrations
      WHERE migration_id='20260830_122_outbox_ordered_sparse'
        AND checksum='$sparseMigrationChecksum')
      sparse_migration_valid,
   EXISTS (SELECT 1 FROM public.schema_migrations
      WHERE migration_id='20260830_123_outbox_claim_candidate_index'
        AND checksum='$claimPlanMigrationChecksum')
      claim_plan_migration_valid,
   (SELECT count(*)=124 AND max(migration_id)=
      '20260830_123_outbox_claim_candidate_index'
    FROM public.schema_migrations) catalog_tail_valid,
   (SELECT count(*) FROM public.outbox_events
      WHERE consumer_key IN ('inventory_projection_v1',
        'progression_reward_projection_v1')
        AND ordering_policy<>'ordered_sparse') sparse_event_mismatches,
   (SELECT count(*) FROM public.outbox_consumer_positions
      WHERE consumer_key IN ('inventory_projection_v1',
        'progression_reward_projection_v1')
        AND ordering_policy<>'ordered_sparse') sparse_position_mismatches,
   (SELECT count(*) FROM pg_constraint
      WHERE conrelid IN ('public.outbox_events'::regclass,
        'public.outbox_consumer_positions'::regclass)
        AND conname IN ('ck_outbox_events_sparse_consumer_policy',
          'ck_outbox_positions_sparse_consumer_policy')
        AND convalidated) sparse_constraint_count,
   ((to_regclass('public.ix_outbox_events_claimable_stream') IS NOT NULL)::int
     + (to_regclass(
       'public.ix_outbox_events_ordered_stream_version') IS NOT NULL)::int)
      claim_index_count,
   (SELECT count(*) FROM pg_trigger
      WHERE tgrelid IN ('public.outbox_events'::regclass,
        'public.outbox_consumer_positions'::regclass)
        AND tgname IN ('trg_outbox_events_guard',
          'trg_outbox_events_lease_consistency',
          'trg_outbox_consumer_positions_guard',
          'trg_outbox_positions_lease_consistency')
        AND tgenabled='O') guard_count,
   (SELECT count(*) FROM pg_trigger
      WHERE tgrelid='public.command_audit'::regclass
        AND tgname='trg_command_audit_immutable'
        AND tgenabled='O') audit_guard_count
)
SELECT 'OUTBOX_POISON_REPAIR_STATUS|' || jsonb_build_object(
 'targetCount',target_count,'sourceReady',source_ready,
 'postReady',post_ready,'receiptCount',receipt_count,
 'receiptValid',receipt_valid,'receiptAuditId',receipt_audit_id,
 'currentVersion',current_version,
 'sparseMigrationApplied',sparse_migration_applied,
 'sparseMigrationValid',sparse_migration_valid,
 'claimPlanMigrationValid',claim_plan_migration_valid,
 'catalogTailValid',catalog_tail_valid,
 'sparseEventMismatches',sparse_event_mismatches,
 'sparsePositionMismatches',sparse_position_mismatches,
 'sparseConstraintCount',sparse_constraint_count,
 'claimIndexCount',claim_index_count,
 'guardCount',guard_count,
 'auditGuardCount',audit_guard_count)::text
FROM facts;
COMMIT;
"@
}

function Get-ApplySql([string]$OperationHex, [string]$RequestHex) {
    $expectedPayload = Get-ExpectedPayloadSql
    @"
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
SELECT pg_advisory_xact_lock(5138414028200206917);
LOCK TABLE public.command_audit IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.outbox_events IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.outbox_consumer_positions IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.schema_migrations IN SHARE MODE;
DO `$validate_repair`$
BEGIN
 IF current_setting('session_replication_role')<>'origin' THEN
   RAISE EXCEPTION 'Outbox repair requires active triggers.';
 END IF;
 IF (SELECT count(*) FROM pg_trigger
      WHERE tgrelid IN ('public.outbox_events'::regclass,
        'public.outbox_consumer_positions'::regclass)
        AND tgname IN ('trg_outbox_events_guard',
          'trg_outbox_events_lease_consistency',
          'trg_outbox_consumer_positions_guard',
          'trg_outbox_positions_lease_consistency')
        AND tgenabled='O')<>4 THEN
   RAISE EXCEPTION 'Required outbox mutation guards are not enabled.';
 END IF;
 IF (SELECT count(*) FROM pg_trigger
      WHERE tgrelid='public.command_audit'::regclass
        AND tgname='trg_command_audit_immutable'
        AND tgenabled='O')<>1 THEN
   RAISE EXCEPTION 'The immutable command-audit guard is not enabled.';
 END IF;
 IF (SELECT count(*) FROM public.schema_migrations)<>124
 OR (SELECT max(migration_id) FROM public.schema_migrations)<>
      '20260830_123_outbox_claim_candidate_index'
 OR NOT EXISTS (SELECT 1 FROM public.schema_migrations
      WHERE migration_id='20260830_122_outbox_ordered_sparse'
        AND checksum='$sparseMigrationChecksum')
 OR NOT EXISTS (SELECT 1 FROM public.schema_migrations
      WHERE migration_id='20260830_123_outbox_claim_candidate_index'
        AND checksum='$claimPlanMigrationChecksum') THEN
   RAISE EXCEPTION 'Required ordered-sparse migrations are not current.';
 END IF;
 IF EXISTS (SELECT 1 FROM public.outbox_events
      WHERE consumer_key IN ('inventory_projection_v1',
        'progression_reward_projection_v1')
        AND ordering_policy<>'ordered_sparse')
 OR EXISTS (SELECT 1 FROM public.outbox_consumer_positions
      WHERE consumer_key IN ('inventory_projection_v1',
        'progression_reward_projection_v1')
        AND ordering_policy<>'ordered_sparse')
 OR (SELECT count(*) FROM pg_constraint
      WHERE conrelid IN ('public.outbox_events'::regclass,
        'public.outbox_consumer_positions'::regclass)
        AND conname IN ('ck_outbox_events_sparse_consumer_policy',
          'ck_outbox_positions_sparse_consumer_policy')
        AND convalidated)<>2
 OR to_regclass('public.ix_outbox_events_claimable_stream') IS NULL
 OR to_regclass(
      'public.ix_outbox_events_ordered_stream_version') IS NULL THEN
   RAISE EXCEPTION 'Ordered-sparse schema postconditions are incomplete.';
 END IF;
 IF EXISTS (SELECT 1 FROM public.command_audit
   WHERE command_family='outbox_poison_replay_repair'
     AND operation_id=decode('$OperationHex','hex')) THEN
   RAISE EXCEPTION 'A repair receipt already exists; use Status.';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM public.outbox_consumer_positions
   WHERE consumer_key='pet_durable_v1'
     AND aggregate_type='character_pet_value'
     AND aggregate_key='character:2' AND ordering_policy='strict'
     AND current_version=316 AND inflight_event_id IS NULL) THEN
   RAISE EXCEPTION 'The pet durable checkpoint is not idle at v316.';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM public.outbox_events event
   WHERE event.id=6774 AND event.event_id='$eventId'::uuid
     AND event.command_inbox_id=6719
     AND event.consumer_key='pet_durable_v1'
     AND event.aggregate_type='character_pet_value'
     AND event.aggregate_key='character:2'
     AND event.aggregate_version=317
     AND event.event_type='pet.basic_savvy_reset'
     AND event.contract_version=2 AND event.ordering_policy='strict'
     AND event.attempt_count=8 AND event.max_attempts=8
     AND event.delivered_at IS NULL
     AND event.poisoned_at=
       '2026-08-11 14:43:23.374761+00'::timestamptz
     AND event.poison_reason='consumer_failure_max_attempts'
     AND event.created_at=
       '2026-08-11 14:41:57.319068+00'::timestamptz
     AND event.lease_token IS NULL
     AND encode(sha256(convert_to(event.payload::text,'UTF8')),'hex')=
       'a0f41b055090797377f86874e7b1c57d0ed943a0e565ea2b6c6876136b6aafb6')
 THEN
   RAISE EXCEPTION 'The exact poisoned event authority changed.';
 END IF;
END
`$validate_repair`$;

ALTER TABLE public.outbox_events
 DISABLE TRIGGER trg_outbox_events_guard;

UPDATE public.outbox_events
SET attempt_count=0,available_at=clock_timestamp(),
    lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
    poisoned_at=NULL,poison_reason=NULL,
    state_changed_at=clock_timestamp()
WHERE id=6774 AND event_id='$eventId'::uuid
  AND attempt_count=8
  AND poisoned_at=
    '2026-08-11 14:43:23.374761+00'::timestamptz
  AND poison_reason='consumer_failure_max_attempts';

SET CONSTRAINTS ALL IMMEDIATE;

ALTER TABLE public.outbox_events
 ENABLE TRIGGER trg_outbox_events_guard;

DO `$record_repair`$
DECLARE
 v_audit_id bigint;
BEGIN
 IF (SELECT count(*) FROM pg_trigger
      WHERE tgrelid='public.outbox_events'::regclass
        AND tgname IN ('trg_outbox_events_guard',
          'trg_outbox_events_lease_consistency')
        AND tgenabled='O')<>2
 OR (SELECT count(*) FROM pg_trigger
      WHERE tgrelid='public.command_audit'::regclass
        AND tgname='trg_command_audit_immutable'
        AND tgenabled='O')<>1 THEN
   RAISE EXCEPTION 'Repair guards were not restored before audit.';
 END IF;

 IF NOT EXISTS (SELECT 1 FROM public.outbox_events
   WHERE id=6774 AND event_id='$eventId'::uuid
     AND attempt_count=0 AND delivered_at IS NULL
     AND poisoned_at IS NULL AND poison_reason IS NULL
     AND lease_token IS NULL) THEN
   RAISE EXCEPTION 'The poison row was not reset exactly once.';
 END IF;

 INSERT INTO public.command_audit(
   principal_type,principal_key,aggregate_type,aggregate_key,
   command_family,operation_id,request_hash,outcome_code,
   detail_payload,retention_policy)
 VALUES('developer','13','character_pet_value','character:2',
   'outbox_poison_replay_repair',decode('$OperationHex','hex'),
   decode('$RequestHex','hex'),'repaired',$expectedPayload,'permanent')
 RETURNING id INTO v_audit_id;

 IF NOT EXISTS (SELECT 1 FROM public.outbox_events
   WHERE id=6774 AND event_id='$eventId'::uuid
     AND attempt_count=0 AND delivered_at IS NULL
     AND poisoned_at IS NULL AND poison_reason IS NULL
     AND lease_token IS NULL)
 OR NOT EXISTS (SELECT 1 FROM public.command_audit
   WHERE id=v_audit_id AND request_hash=decode('$RequestHex','hex')
     AND detail_payload=$expectedPayload AND outcome_code='repaired'
     AND retention_policy='permanent') THEN
   RAISE EXCEPTION 'Poison replay repair readback failed.';
 END IF;
END
`$record_repair`$;
COMMIT;
SELECT 'OUTBOX_POISON_REPAIR_RESULT|' || jsonb_build_object(
 'status','Applied','changed',true,'eventId','$eventId',
 'aggregateVersion',317,'attemptCountBefore',8,'attemptCountAfter',0,
 'poisonEvidencePreserved',true)::text;
"@
}

$environment = Initialize-RebirthRepairEnvironment `
    $postgresContainer $tempestContainer $redisContainer
$dwargon = Get-RepairContainer $dwargonContainer
Assert-RepairContainer $dwargon $dwargonContainer ''
if (-not (@($dwargon.Config.Env) -contains
        'GODSWAR_RUNTIME_PROFILE=LocalDevelopment')) {
    throw "Server container '$dwargonContainer' is not LocalDevelopment."
}
$originRunning = Test-OriginRunning
$redisKeyCount = Get-RebirthRepairRedisKeyCount $redisContainer
$operationHex = Get-RepairSha256Hex $operationText
$requestHex = Get-RepairSha256Hex $requestText
$status = Invoke-OutboxRepairPsql `
    (Get-StatusSql $operationHex $requestHex) `
    'OUTBOX_POISON_REPAIR_STATUS|'

if ($status.targetCount -ne 1 -or $status.receiptCount -gt 1 -or
    ($status.receiptCount -eq 1 -and
     (-not $status.receiptValid -or -not $status.postReady)) -or
    $status.guardCount -ne 4 -or $status.auditGuardCount -ne 1) {
    throw 'The poisoned event, permanent receipt, or outbox guards are inconsistent.'
}
$sparseReady = $status.sparseMigrationApplied -and
    $status.sparseMigrationValid -and
    $status.claimPlanMigrationValid -and
    $status.catalogTailValid -and
    $status.sparseEventMismatches -eq 0 -and
    $status.sparsePositionMismatches -eq 0 -and
    $status.sparseConstraintCount -eq 2 -and
    $status.claimIndexCount -eq 2
if ($status.receiptCount -eq 1 -and -not $sparseReady) {
    throw 'An applied repair no longer has its ordered-sparse schema invariants.'
}
$serversOffline = -not [bool]$environment.Server.State.Running -and
    -not [bool]$dwargon.State.Running
$offline = $serversOffline -and -not $originRunning -and
    $redisKeyCount -eq 0
$state = if ($status.receiptCount -eq 1) { 'Applied' }
    elseif (-not $status.sourceReady -or -not $sparseReady) { 'Refused' }
    elseif ($DisposableTest -or $offline) { 'Ready' }
    else { 'AwaitingOffline' }
$summary = [pscustomobject]@{
    Status = $state
    Database = $Database
    EventId = $eventId
    AggregateVersion = 317
    CurrentVersion = $status.currentVersion
    SourceReady = $status.sourceReady
    PostReady = $status.postReady
    ReceiptAuditId = $status.receiptAuditId
    SparseMigrationApplied = $status.sparseMigrationApplied
    SparseMigrationChecksumValid = $status.sparseMigrationValid
    ClaimPlanMigrationChecksumValid = $status.claimPlanMigrationValid
    CatalogTailValid = $status.catalogTailValid
    SparseEventMismatches = $status.sparseEventMismatches
    SparsePositionMismatches = $status.sparsePositionMismatches
    SparseConstraintCount = $status.sparseConstraintCount
    ClaimPlanIndexCount = $status.claimIndexCount
    CommandAuditGuardCount = $status.auditGuardCount
    TempestRunning = [bool]$environment.Server.State.Running
    DwargonRunning = [bool]$dwargon.State.Running
    OriginRunning = $originRunning
    RedisPlayerLoginKeyCount = $redisKeyCount
    PoisonEvidencePreserved = $status.receiptCount -eq 1
}
if ($Mode -eq 'Status' -or $state -eq 'Applied') { return $summary }
if ($state -ne 'Ready') {
    throw 'The exact poison source or every offline fence is not ready.'
}
if (-not $PSCmdlet.ShouldProcess(
        'pet_durable_v1 character:2 revision 317',
        'Requeue exact poison with permanent immutable audit')) {
    return
}
if (-not $DisposableTest) {
    $latestTempest = Get-RepairContainer $tempestContainer
    $latestDwargon = Get-RepairContainer $dwargonContainer
    if ($latestTempest.State.Running -or $latestDwargon.State.Running -or
        (Test-OriginRunning) -or
        (Get-RebirthRepairRedisKeyCount $redisContainer) -ne 0) {
        throw 'An offline fence changed immediately before repair.'
    }
}
$result = Invoke-OutboxRepairPsql `
    (Get-ApplySql $operationHex $requestHex) `
    'OUTBOX_POISON_REPAIR_RESULT|'
$verified = Invoke-OutboxRepairPsql `
    (Get-StatusSql $operationHex $requestHex) `
    'OUTBOX_POISON_REPAIR_STATUS|'
if ($result.status -ne 'Applied' -or -not $result.changed -or
    -not $result.poisonEvidencePreserved -or
    $verified.receiptCount -ne 1 -or -not $verified.receiptValid -or
    -not $verified.postReady -or -not $verified.sparseMigrationValid -or
    -not $verified.claimPlanMigrationValid -or
    -not $verified.catalogTailValid) {
    throw 'Committed outbox poison repair failed exact readback verification.'
}
$result
