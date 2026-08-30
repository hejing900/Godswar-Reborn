[CmdletBinding()]
param()

# Proves migration 122 and the poison replay against a logical backup. The
# live godswar database is fingerprinted before/after and is never mutated.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$postgresContainer = 'godswar-dev-postgres'
$databaseUser = 'godswar'
$suffix = [Guid]::NewGuid().ToString('N').Substring(0, 10)
$database = "godswar_outbox_repair_$suffix"
$databasePattern = '^godswar_outbox_repair_[a-f0-9]{10}$'
$proxy = "godswar-outbox-repair-proxy-$suffix"
$created = $false
$proxyStarted = $false
$previousConnection = $env:GODSWAR_OUTBOX_REPAIR_TEST_CONNECTION_STRING
$previousPhase = $env:GODSWAR_OUTBOX_REPAIR_TEST_PHASE

if ($database -notmatch $databasePattern) {
    throw 'Disposable database name generation failed.'
}

function Invoke-OutboxTestSql([string]$Target, [string]$Sql) {
    $output = $Sql | & docker exec -i $postgresContainer `
        psql -X -q -A -t -v ON_ERROR_STOP=1 `
        -U $databaseUser -d $Target 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Disposable outbox SQL failed:`n$($output -join "`n")"
    }
    @($output | ForEach-Object { $_.ToString() })
}

function Invoke-OutboxAdminSql([string]$Sql) {
    $null = Invoke-OutboxTestSql 'postgres' $Sql
}

function Get-LiveFingerprint {
    $sql = @'
BEGIN READ ONLY;
SELECT 'LIVE|' || encode(sha256(convert_to(jsonb_build_object(
 'events',COALESCE((SELECT jsonb_agg(to_jsonb(event) ORDER BY event.id)
   FROM public.outbox_events event
   WHERE (event.consumer_key,event.aggregate_key) IN (
    ('inventory_projection_v1','character:2:inventory'),
    ('inventory_projection_v1','character:7005:inventory'),
    ('progression_reward_projection_v1','character:2:progression'),
    ('pet_durable_v1','character:2'))),'[]'::jsonb),
 'positions',COALESCE((SELECT jsonb_agg(to_jsonb(position)
     ORDER BY position.consumer_key,position.aggregate_key)
   FROM public.outbox_consumer_positions position
   WHERE (position.consumer_key,position.aggregate_key) IN (
    ('inventory_projection_v1','character:2:inventory'),
    ('inventory_projection_v1','character:7005:inventory'),
    ('progression_reward_projection_v1','character:2:progression'),
    ('pet_durable_v1','character:2'))),'[]'::jsonb),
 'repairAudit',COALESCE((SELECT jsonb_agg(to_jsonb(audit) ORDER BY audit.id)
   FROM public.command_audit audit
   WHERE audit.command_family='outbox_poison_replay_repair'),'[]'::jsonb),
 'migrationCount',(SELECT count(*) FROM public.schema_migrations),
 'lastMigration',(SELECT max(migration_id) FROM public.schema_migrations)
)::text,'UTF8')),'hex');
COMMIT;
'@
    $line = Invoke-OutboxTestSql 'godswar' $sql | Where-Object {
        $_.StartsWith('LIVE|', [StringComparison]::Ordinal)
    } | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($line)) {
        throw 'Live outbox fingerprint query returned no marker.'
    }
    $line.Substring(5)
}

$liveBefore = Get-LiveFingerprint
try {
    Invoke-OutboxAdminSql "CREATE DATABASE $database;"
    $created = $true
    $copyCommand =
        "pg_dump --no-owner --no-privileges -U $databaseUser godswar" +
        " | psql -X -q -v ON_ERROR_STOP=1 -U $databaseUser -d $database"
    $copyOutput = & docker exec $postgresContainer sh -c $copyCommand 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Logical backup restore failed:`n$($copyOutput -join "`n")"
    }

    $proxyId = & docker run -d --rm --name $proxy `
        --network reborn_dev_runtime -p '127.0.0.1::5432' `
        alpine:3.22 nc -lk -p 5432 -e nc `
        $postgresContainer 5432 2>&1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($proxyId)) {
        throw "Could not start disposable PostgreSQL proxy: $proxyId"
    }
    $proxyStarted = $true
    $published = (& docker port $proxy '5432/tcp' 2>&1).ToString().Trim()
    if ($LASTEXITCODE -ne 0 -or
        $published -notmatch '^127\.0\.0\.1:(\d{1,5})$') {
        throw "Unexpected disposable proxy endpoint '$published'."
    }
    $port = [int]$Matches[1]
    if ($port -lt 1 -or $port -gt 65535) {
        throw 'Disposable proxy port is invalid.'
    }

    $passwordPath = Join-Path $PSScriptRoot `
        '..\artifacts\development-stack\postgres.password'
    $password = (Get-Content -Raw -LiteralPath $passwordPath).Trim()
    if ($password -notmatch '^[a-f0-9]{64}$') {
        throw 'The isolated PostgreSQL secret is malformed.'
    }
    try {
        $env:GODSWAR_OUTBOX_REPAIR_TEST_CONNECTION_STRING =
            "Host=127.0.0.1;Port=$port;Database=$database;" +
            "Username=$databaseUser;Password=$password;Timeout=10;" +
            'Command Timeout=60;Pooling=true;Maximum Pool Size=8;' +
            'SSL Mode=Disable;GSS Encryption Mode=Disable'
        $env:GODSWAR_OUTBOX_REPAIR_TEST_PHASE = 'prepare'
        & dotnet run --project `
            (Join-Path $PSScriptRoot `
                '..\tests\Godswar.Server.ProtocolChecks') `
            --no-restore -- `
            'historical outbox ordered-sparse repair'
        if ($LASTEXITCODE -ne 0) {
            throw 'Historical outbox preparation check failed.'
        }

        $repairTool = Join-Path $PSScriptRoot `
            'RepairLocalDevelopmentOutboxPoison.ps1'
        $ready = & $repairTool -Mode Status -Database $database `
            -DisposableTest
        if ($ready.Status -ne 'Ready' -or -not $ready.SourceReady -or
            $ready.CurrentVersion -ne 316 -or $ready.ReceiptAuditId -or
            -not $ready.SparseMigrationApplied -or
            -not $ready.SparseMigrationChecksumValid -or
            -not $ready.ClaimPlanMigrationChecksumValid -or
            -not $ready.CatalogTailValid -or
            $ready.SparseEventMismatches -ne 0 -or
            $ready.SparsePositionMismatches -ne 0 -or
            $ready.SparseConstraintCount -ne 2 -or
            $ready.ClaimPlanIndexCount -ne 2) {
            throw 'Migrated backup did not preserve the exact poison source.'
        }
        $applied = & $repairTool -Mode Apply -Database $database `
            -DisposableTest -Confirm:$false
        if ($applied.status -ne 'Applied' -or -not $applied.changed -or
            -not $applied.poisonEvidencePreserved) {
            throw 'Disposable poison repair did not commit exactly once.'
        }
        $repeat = & $repairTool -Mode Apply -Database $database `
            -DisposableTest -Confirm:$false
        if ($repeat.Status -ne 'Applied' -or -not $repeat.PostReady -or
            -not $repeat.PoisonEvidencePreserved) {
            throw 'Disposable poison repair replay was not idempotent.'
        }

        $env:GODSWAR_OUTBOX_REPAIR_TEST_PHASE = 'verify'
        & dotnet run --project `
            (Join-Path $PSScriptRoot `
                '..\tests\Godswar.Server.ProtocolChecks') `
            --no-restore -- `
            'historical outbox ordered-sparse repair'
        if ($LASTEXITCODE -ne 0) {
            throw 'Historical outbox delivery verification failed.'
        }
    }
    finally {
        $password = $null
        $env:GODSWAR_OUTBOX_REPAIR_TEST_CONNECTION_STRING =
            $previousConnection
        $env:GODSWAR_OUTBOX_REPAIR_TEST_PHASE = $previousPhase
    }

    $verified = Invoke-OutboxTestSql $database @'
BEGIN READ ONLY;
SELECT concat_ws('|',
 (SELECT count(*) FROM outbox_events
  WHERE consumer_key IN ('inventory_projection_v1',
    'progression_reward_projection_v1','pet_durable_v1')
    AND delivered_at IS NULL),
 (SELECT count(*) FROM outbox_events
  WHERE consumer_key IN ('inventory_projection_v1',
    'progression_reward_projection_v1','pet_durable_v1')
    AND poisoned_at IS NOT NULL),
 (SELECT count(*) FROM command_audit
  WHERE command_family='outbox_poison_replay_repair'),
 (SELECT count(*) FROM schema_migrations
  WHERE migration_id='20260830_122_outbox_ordered_sparse'),
 (SELECT count(*) FROM schema_migrations
  WHERE migration_id='20260830_123_outbox_claim_candidate_index'));
COMMIT;
'@
    if (@($verified)[0] -cne '0|0|1|1|1') {
        throw "Disposable final state was unexpected: $($verified -join ',')"
    }

    [pscustomobject]@{
        Status = 'Passed'
        Database = $database
        HistoricalRowsValidated = 2215
        InventoryCharacter2Position = 738
        InventoryCharacter7005Position = 75
        ProgressionCharacter2Position = 32
        PetCharacter2Position = 1742
        PoisonV2Decoded = $true
        PoisonEvidenceAudited = $true
        Replay = 'Idempotent'
        LiveDatabaseUnchanged = $true
    }
}
finally {
    $env:GODSWAR_OUTBOX_REPAIR_TEST_CONNECTION_STRING = $previousConnection
    $env:GODSWAR_OUTBOX_REPAIR_TEST_PHASE = $previousPhase
    if ($proxyStarted) {
        $null = & docker stop $proxy 2>&1
    }
    if ($created) {
        if ($database -notmatch $databasePattern) {
            throw 'Refusing to drop an unvalidated disposable database.'
        }
        Invoke-OutboxAdminSql (
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity " +
            "WHERE datname='$database' AND pid<>pg_backend_pid();")
        Invoke-OutboxAdminSql "DROP DATABASE $database;"
    }
    $liveAfter = Get-LiveFingerprint
    if ($liveAfter -cne $liveBefore) {
        throw 'Disposable repair testing changed the live godswar database.'
    }
}
