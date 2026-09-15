[CmdletBinding()]
param()

# Logical-clone mutation/replay coverage. The live authority is read-only and
# fingerprinted before and after the disposable database test.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$postgresContainer = 'godswar-dev-postgres'
$databaseUser = 'godswar'
$suffix = [Guid]::NewGuid().ToString('N').Substring(0, 10)
$database = "godswar_faction_nameplates_$suffix"
$databasePattern = '^godswar_faction_nameplates_[a-f0-9]{10}$'
if ($database -notmatch $databasePattern) {
    throw 'Disposable database name generation failed.'
}

. (Join-Path $PSScriptRoot `
    'GrantLocalDevelopmentFactionCrierNameplates.Guards.ps1')
$null = Initialize-NameplateGrantEnvironment $postgresContainer `
    'godswar-dev-tempest-openworld-01' 'godswar-dev-redis-coordination'

function Invoke-NameplateTestSql(
    [string]$TargetDatabase,
    [string]$Sql
) {
    $output = $Sql | & docker exec -i $postgresContainer `
        psql -X -q -A -t -v ON_ERROR_STOP=1 `
        -U $databaseUser -d $TargetDatabase 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Disposable Nameplate SQL failed:`n$($output -join "`n")"
    }
    @($output | ForEach-Object { $_.ToString() })
}

function Invoke-NameplateAdminSql([string]$Sql) {
    $null = Invoke-NameplateTestSql 'postgres' $Sql
}

function Get-NameplateLiveFingerprint {
    $sql = @'
BEGIN READ ONLY;
SELECT 'LIVE|' || encode(sha256(convert_to(jsonb_build_object(
 'account',(SELECT to_jsonb(a) FROM accounts a WHERE id=13),
 'character',(SELECT to_jsonb(c) FROM character_base c WHERE id=2),
 'items',COALESCE((SELECT jsonb_agg(to_jsonb(i)
   ORDER BY i.item_location,i.slot_index,i.id)
   FROM character_items i WHERE i.user_id=2),'[]'::jsonb),
 'receipt',COALESCE((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id)
   FROM command_audit a
   WHERE a.command_family='faction_crier_nameplate_test_kit'
     AND a.principal_key='13' AND a.aggregate_key='character:2'),
   '[]'::jsonb),
 'itemAudits',COALESCE((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id)
   FROM character_item_audit a
   WHERE a.source='localdev-faction-crier-nameplate-test-kit-v1'
     AND a.user_id=2),'[]'::jsonb)
)::text,'UTF8')),'hex');
COMMIT;
'@
    $lines = Invoke-NameplateTestSql 'godswar' $sql
    $line = $lines | Where-Object {
        $_.StartsWith('LIVE|', [StringComparison]::Ordinal)
    } | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($line)) {
        throw 'Live Nameplate fingerprint returned no marker.'
    }
    $line.Substring(5)
}

function Assert-TenEach($Counts) {
    foreach ($itemId in 3820..3825) {
        $property = $Counts.PSObject.Properties[$itemId.ToString()]
        if ($null -eq $property -or [int]$property.Value -ne 10) {
            throw "Nameplate $itemId did not reconcile to ten."
        }
    }
}

$liveBefore = Get-NameplateLiveFingerprint
$created = $false
try {
    Invoke-NameplateAdminSql "CREATE DATABASE $database;"
    $created = $true
    $copyCommand =
        "pg_dump --no-owner --no-privileges -U $databaseUser godswar" +
        " | psql -X -q -v ON_ERROR_STOP=1 -U $databaseUser -d $database"
    $copyOutput = & docker exec $postgresContainer sh -c $copyCommand 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Nameplate logical clone failed:`n$($copyOutput -join "`n")"
    }

    $tool = Join-Path $PSScriptRoot `
        'GrantLocalDevelopmentFactionCrierNameplates.ps1'
    $ready = & $tool -Mode Status -Database $database -DisposableTest
    if ($ready.Status -ne 'Ready' -or -not $ready.ContentValid -or
        -not $ready.CatalogReviewed -or -not $ready.IdentityReady -or
        -not $ready.SourceReady -or $ready.PostReady -or
        $ready.CurrentInventoryRevision -ne 742 -or
        $ready.CurrentBagRows -ne 2 -or $ready.CurrentBagUnits -ne 95 -or
        $ready.MissingUnits -ne 59 -or $ready.RequiredSlots -ne 5) {
        throw 'Disposable clone did not preserve the ready Nameplate state.'
    }
    $preservedHash = $ready.PreservedItemsSha256
    $characterHash = $ready.NonInventoryCharacterSha256

    $null = & $tool -Mode Apply -Database $database `
        -DisposableTest -WhatIf
    $afterWhatIf = & $tool -Mode Status -Database $database -DisposableTest
    if ($afterWhatIf.Status -ne 'Ready' -or
        $afterWhatIf.CurrentInventoryRevision -ne 742) {
        throw 'WhatIf changed the disposable Nameplate authority.'
    }

    $applied = & $tool -Mode Apply -Database $database `
        -DisposableTest -Confirm:$false
    if ($applied.status -ne 'Applied' -or -not $applied.changed -or
        $applied.auditId -le 0 -or $applied.mutationCount -ne 6 -or
        $applied.itemAuditCount -ne 6 -or
        $applied.inventoryRevisionBefore -ne 742 -or
        $applied.inventoryRevisionAfter -ne 743) {
        throw 'Disposable Nameplate fixture did not commit exactly.'
    }
    $verified = & $tool -Mode Status -Database $database -DisposableTest
    Assert-TenEach $verified.CurrentNameplateCounts
    if ($verified.Status -ne 'Applied' -or -not $verified.PostReady -or
        $verified.ReceiptAuditId -ne $applied.auditId -or
        $verified.LinkedItemAuditCount -ne 6 -or
        $verified.CurrentBagRows -ne 7 -or
        $verified.CurrentBagUnits -ne 154 -or
        $verified.CurrentInventoryRevision -ne 743 -or
        $verified.PreservedItemsSha256 -cne $preservedHash -or
        $verified.NonInventoryCharacterSha256 -cne $characterHash) {
        throw 'Disposable Nameplate read-back or preservation failed.'
    }

    $repeat = & $tool -Mode Apply -Database $database `
        -DisposableTest -Confirm:$false
    if ($repeat.Status -ne 'Applied' -or
        $repeat.ReceiptAuditId -ne $applied.auditId -or
        -not $repeat.PostReady) {
        throw 'Immediate Nameplate replay was not idempotent.'
    }

    $null = Invoke-NameplateTestSql $database @'
BEGIN;
UPDATE character_items SET stack=9,updated_at=now()
WHERE user_id=2 AND prop_id=3820 AND item_location=1 AND stack=10;
UPDATE character_base SET inventory_revision=inventory_revision+1
WHERE id=2 AND account_id=13 AND inventory_revision=743;
COMMIT;
'@
    $afterConsumption = & $tool -Mode Apply -Database $database `
        -DisposableTest -Confirm:$false
    if ($afterConsumption.Status -ne 'Applied' -or
        $afterConsumption.ReceiptAuditId -ne $applied.auditId -or
        $afterConsumption.PostReady) {
        throw 'Permanent receipt did not prevent a Nameplate re-grant.'
    }
    $rows = Invoke-NameplateTestSql $database @'
BEGIN READ ONLY;
SELECT stack FROM character_items
WHERE user_id=2 AND prop_id=3820 AND item_location=1;
SELECT count(*) FROM command_audit
WHERE command_family='faction_crier_nameplate_test_kit'
  AND principal_key='13' AND aggregate_key='character:2';
SELECT count(*) FROM character_item_audit
WHERE source='localdev-faction-crier-nameplate-test-kit-v1'
  AND user_id=2;
COMMIT;
'@
    if (@($rows) -join ',' -ne '9,1,6') {
        throw 'Consumed replay changed the grant or audit cardinality.'
    }

    [pscustomobject]@{
        Status = 'Passed'
        Database = $database
        InventoryRevisionBefore = 742
        InventoryRevisionAfterGrant = 743
        NameplateTarget = '3820..3825 x10 each'
        PreservedBagItem = '10104 x94 @ slot 24'
        ItemAuditCount = 6
        CommandAuditId = $applied.auditId
        ReplayAfterConsumption = 'AppliedWithoutRegrant'
    }
}
finally {
    if ($created) {
        if ($database -notmatch $databasePattern) {
            throw 'Refusing to drop an unvalidated disposable database.'
        }
        Invoke-NameplateAdminSql "DROP DATABASE $database;"
    }
    $liveAfter = Get-NameplateLiveFingerprint
    if ($liveAfter -cne $liveBefore) {
        throw 'The disposable test detected a live-database state change.'
    }
}
