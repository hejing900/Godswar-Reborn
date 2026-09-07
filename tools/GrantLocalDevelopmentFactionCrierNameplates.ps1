[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [ValidateSet('Status', 'Apply')]
    [string]$Mode = 'Status',

    [ValidatePattern('^godswar(?:_faction_nameplates_[a-f0-9]{10})?$')]
    [string]$Database = 'godswar',

    [switch]$DisposableTest
)

# One-purpose offline local-development fixture for account 13 / character 2.
# It reconciles bound Nameplates I-VI to exactly ten each without touching any
# unrelated item or character field. Status is always read-only.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$postgresContainer = 'godswar-dev-postgres'
$serverContainer = 'godswar-dev-tempest-openworld-01'
$redisContainer = 'godswar-dev-redis-coordination'
$databaseUser = 'godswar'
$operationText =
    'localdev|faction-crier-nameplate-test-kit|account:13|character:2|v1'
$requestText = $operationText +
    '|realm:1|items:3820-3825|target-each:10|binding:1|stack-cap:99' +
    '|item-release:AC11E2A725B0450B93D9C71F021F2D95B19EB4204ACC8E36B54CFEF1F8B9A063'

. (Join-Path $PSScriptRoot `
    'GrantLocalDevelopmentFactionCrierNameplates.Guards.ps1')
. (Join-Path $PSScriptRoot `
    'GrantLocalDevelopmentFactionCrierNameplates.Sql.Common.ps1')
. (Join-Path $PSScriptRoot `
    'GrantLocalDevelopmentFactionCrierNameplates.Sql.Status.ps1')
. (Join-Path $PSScriptRoot `
    'GrantLocalDevelopmentFactionCrierNameplates.Sql.Apply.ps1')

if ($DisposableTest) {
    if ($Database -notmatch '^godswar_faction_nameplates_[a-f0-9]{10}$') {
        throw 'Disposable tests require the faction-nameplates DB prefix.'
    }
}
elseif ($Database -cne 'godswar') {
    throw 'The real fixture can target only the godswar database.'
}

function Invoke-NameplateGrantPsql([string]$Sql, [string]$Marker) {
    $output = $Sql | & docker exec -i $postgresContainer `
        psql -X -q -A -t -v ON_ERROR_STOP=1 `
        -U $databaseUser -d $Database 2>&1
    $exitCode = $LASTEXITCODE
    $lines = @($output | ForEach-Object { $_.ToString() })
    if ($exitCode -ne 0) {
        throw "Nameplate fixture failed and rolled back:`n$($lines -join "`n")"
    }
    $receipt = $lines | Where-Object {
        $_.StartsWith($Marker, [StringComparison]::Ordinal)
    } | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($receipt)) {
        throw 'The database returned no Nameplate fixture receipt.'
    }
    $receipt.Substring($Marker.Length) | ConvertFrom-Json
}

function Test-NameplateGrantCatalogSource {
    $path = Join-Path $PSScriptRoot `
        '..\src\Godswar.Server\Infrastructure\Items\FactionCrierNameplateItemContentBaseline.cs'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
    $source = Get-Content -Raw -LiteralPath $path
    $required = @(
        'public const int FirstItemId = 3820;'
        'public const int LastItemId = 3825;'
        'public const short MaximumStack = 99;'
        '["BindType"] = "1"'
        '("216,936", 1)'
        '("396,936", 6)'
    )
    foreach ($value in $required) {
        if ($source.IndexOf($value, [StringComparison]::Ordinal) -lt 0) {
            return $false
        }
    }
    return $true
}

function Test-NameplateCounts($Counts) {
    if ($null -eq $Counts) { return $false }
    foreach ($itemId in 3820..3825) {
        $property = $Counts.PSObject.Properties[$itemId.ToString()]
        if ($null -eq $property -or [int]$property.Value -ne 10) {
            return $false
        }
    }
    return $true
}

$environment = Initialize-NameplateGrantEnvironment `
    $postgresContainer $serverContainer $redisContainer
$serverRunning = [bool]$environment.Server.State.Running
$originRunning = Test-NameplateGrantOriginRunning
$redisKeyCount = if ($DisposableTest) {
    0
}
else {
    Get-NameplateGrantRedisKeyCount $redisContainer
}
$catalogReviewed = Test-NameplateGrantCatalogSource
$operationHex = Get-NameplateGrantSha256Hex $operationText
$requestHashHex = Get-NameplateGrantSha256Hex $requestText
$status = Invoke-NameplateGrantPsql `
    (Get-NameplateGrantStatusSql $operationHex $requestHashHex) `
    'FACTION_NAMEPLATE_STATUS|'

if ($status.receiptCount -gt 1 -or
    ($status.receiptCount -eq 1 -and -not $status.receiptValid)) {
    throw 'The permanent Nameplate receipt or item-audit chain is invalid.'
}
$sourceReady = $catalogReviewed -and [bool]$status.sourceReady
$offline = -not $serverRunning -and -not $originRunning -and
    $redisKeyCount -eq 0
$state = if ($status.receiptCount -eq 1) {
    'Applied'
}
elseif (-not $sourceReady) {
    'Refused'
}
elseif ($DisposableTest -or $offline) {
    'Ready'
}
else {
    'AwaitingOffline'
}
$summary = [pscustomobject]@{
    Status = $state
    Database = $Database
    AccountId = 13
    CharacterId = 2
    CharacterName = 'test2'
    RealmId = 1
    ItemIds = @(3820..3825)
    TargetQuantityEach = 10
    CurrentNameplateCounts = $status.nameplateCounts
    CurrentInventoryRevision = $status.inventoryRevision
    CurrentBagRows = $status.bagRows
    CurrentBagUnits = $status.bagUnits
    EmptyBagSlots = $status.emptySlots
    MissingUnits = $status.missingUnits
    RequiredSlots = $status.requiredSlots
    PublishedItemRevision = $status.publishedItemRevision
    ContentValid = $status.contentValid
    CatalogReviewed = $catalogReviewed
    IdentityReady = $status.identityReady
    SourceReady = $sourceReady
    PostReady = $status.postReady
    PreservedItemsSha256 = $status.preservedItemsSha256
    NameplateItemsSha256 = $status.nameplateItemsSha256
    NonInventoryCharacterSha256 =
        $status.nonInventoryCharacterSha256
    AccountSha256 = $status.accountSha256
    ReceiptAuditId = $status.receiptAuditId
    LinkedItemAuditCount = $status.linkedItemAuditCount
    ServerRunning = $serverRunning
    OriginRunning = $originRunning
    RedisPlayerLoginKeyCount = $redisKeyCount
    OperationIdSha256 = $operationHex.ToUpperInvariant()
    RequestHashSha256 = $requestHashHex.ToUpperInvariant()
}
if ($Mode -eq 'Status' -or $state -eq 'Applied') { return $summary }
if ($state -ne 'Ready') {
    throw 'Exact content, inventory capacity, or offline guards are not ready.'
}
if (-not $DisposableTest) {
    Assert-NameplateGrantOffline `
        $environment $serverContainer $redisContainer
}
if (-not $PSCmdlet.ShouldProcess(
        'isolated-development account 13 / character 2',
        'Reconcile bound Nameplates I-VI to exactly ten each')) {
    return
}
if (-not $DisposableTest) {
    Assert-NameplateGrantOffline `
        $environment $serverContainer $redisContainer
}

$result = Invoke-NameplateGrantPsql `
    (Get-NameplateGrantApplySql $operationHex $requestHashHex) `
    'FACTION_NAMEPLATE_RESULT|'
$verified = Invoke-NameplateGrantPsql `
    (Get-NameplateGrantStatusSql $operationHex $requestHashHex) `
    'FACTION_NAMEPLATE_STATUS|'
if ($result.status -ne 'Applied' -or $result.auditId -le 0 -or
    $result.itemAuditCount -ne $result.mutationCount -or
    $verified.receiptCount -ne 1 -or -not $verified.receiptValid -or
    -not $verified.postReady -or
    $verified.receiptAuditId -ne $result.auditId -or
    -not (Test-NameplateCounts $verified.nameplateCounts)) {
    throw 'The committed Nameplate fixture failed read-back verification.'
}
$result
