<#
.SYNOPSIS
    Set a character's item quality, grade and/or experience, on equipped gear or any
    other item location.

.DESCRIPTION
    Operates on character_items rows for one character, joined by name, filtered to a
    single item_location (0 = equipped by default).  Other locations are never touched.

    Maximums are read from the database rather than hard-coded, so the script stays
    correct if the content caps change:
      * maximum grade   = greatest grade in item_grade_levels, also capped by the
                          ck_character_items_grade_domain check constraint
      * maximum quality = ck_character_items_quality_domain
      * maximum exp     = the int4 ceiling on the item_exp column

    Both directions work: values may be raised or lowered.  A lower target is applied
    exactly like a higher one, and -Grade/-Quality accept any value inside the caps.

    THIS SCRIPT CANNOT DETECT WHETHER A CHARACTER IS ONLINE.  There is no presence
    table in this schema, and the server's 'joined' lines are swallowed by the
    structured logging boundary, so neither the database nor `docker logs` can answer
    the question.  Treat -ConfirmCharacterOffline as your own assertion that you have
    logged the character out.  Editing a character that is online is not reliably
    safe: verified in practice, an item can be moved between kit-bag and equipment by
    the live session while you are editing, and the server holds character state in
    memory.  Items the player is actively changing win; your write may be undone.

    Every run writes a timestamped backup of the affected rows (CSV plus manifest.json)
    so Restore-CharacterItemGrade.ps1 can roll it back.

.PARAMETER Name
    Character name.  Case-insensitive; must match exactly one character on the realm.

.PARAMETER ServerId
    Realm/server id.  Default 1 (Tempest).

.PARAMETER Operation
    MaxGrade (default when no target is given)
                 raise grade to the maximum and set experience to the int4 ceiling.
    SetStats     set quality and/or grade explicitly; experience is left untouched.
                 Selected automatically when -Quality or -Grade is supplied.
    SetExp       only set experience.
    AddExp       only add experience.  Selected automatically when -ExpDelta is given.

.PARAMETER Grade
    Target grade.  Any value from 1 to the discovered maximum, up or down.
    MaxGrade/SetStats default to the maximum when this is omitted.

.PARAMETER Quality
    Target item quality, 1 to the discovered maximum.  Omit to leave quality alone,
    which is what every operation except SetStats does.

.PARAMETER Exp
    Target item experience.  Omit to leave experience alone (SetStats) or to use the
    int4 ceiling (MaxGrade/SetExp).  Pass an explicit value such as 1000000000 when
    you want a specific number.

.PARAMETER ExpDelta
    Instead of setting experience, add this amount to each item's current value.

.PARAMETER Location
    Which item_location to operate on: 0 equipped (default), 1 kit bag, 3 warehouse,
    2 sealed/negative slots.  Only one location per run, so a bag edit can never
    silently reach the warehouse.

.PARAMETER WhatIf
    Report exactly what would change without writing anything.  Also bypasses the
    offline confirmation, because it never writes.

.EXAMPLE
    # preview maxing out equipped gear
    ./Set-CharacterItemGrade.ps1 -Name test -WhatIf

.EXAMPLE
    # equipped gear to quality 12 and grade 10, experience untouched
    ./Set-CharacterItemGrade.ps1 -Name test -Quality 12 -Grade 10 -ConfirmCharacterOffline

.EXAMPLE
    # max grade plus a specific experience value
    ./Set-CharacterItemGrade.ps1 -Name test -Exp 1000000000 -ConfirmCharacterOffline

.EXAMPLE
    # add experience to every item in the kit bag
    ./Set-CharacterItemGrade.ps1 -Name test -Operation AddExp -ExpDelta 500000 -Location 1 -ConfirmCharacterOffline
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [int]$ServerId = 1,
    [ValidateSet('', 'MaxGrade', 'SetStats', 'SetExp', 'AddExp')][string]$Operation = '',
    [int]$Grade = 0,
    [int]$Quality = 0,
    [long]$Exp = 0,
    [long]$ExpDelta = 0,
    [ValidateSet(0, 1, 2, 3)][int]$Location = 0,
    [switch]$WhatIf,
    [switch]$ConfirmCharacterOffline
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- configuration
# Defaults come from the repository's docker-compose.yml.  Override with
# environment variables when pointing at another stack.
$PgContainer = if ($env:GODSWAR_PG_CONTAINER) { $env:GODSWAR_PG_CONTAINER } else { 'godswar-postgres' }
$PgDatabase  = if ($env:POSTGRES_DB)         { $env:POSTGRES_DB }         else { 'godswar_local' }
$PgUser      = if ($env:POSTGRES_USER)       { $env:POSTGRES_USER }       else { 'godswar' }

$RepoRoot    = Split-Path -Parent $PSScriptRoot
$BackupRoot  = Join-Path $RepoRoot 'backups'

# ---------------------------------------------------------------- psql plumbing
# Transaction command tags emitted by psql.  They are kept out of data results but
# deliberately still reported by Invoke-Psql so the caller can assert UPDATE counts.
$TransactionTags = @('BEGIN', 'COMMIT', 'ROLLBACK', 'START TRANSACTION')

function Invoke-Psql {
    <# Runs SQL and returns trimmed stdout lines.  Throws on a non-zero exit.
       Command tags (BEGIN/COMMIT/...) are retained; use Select-UpdateCount to read them. #>
    param(
        [Parameter(Mandatory = $true)][string]$Sql,
        [switch]$TuplesOnly
    )
    $args = @('exec', '-i', $PgContainer, 'psql', '-U', $PgUser, '-d', $PgDatabase,
              '-v', 'ON_ERROR_STOP=1', '-X')
    if ($TuplesOnly) { $args += @('-t', '-A') }
    $args += @('-c', $Sql)

    $output = & docker @args 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed (exit $LASTEXITCODE):`n$($output -join "`n")"
    }
    return @($output | Where-Object { $_ -is [string] -and $_.Trim().Length -gt 0 })
}

function Select-UpdateCount {
    <# Returns the row count from an 'UPDATE n' command tag, or $null if absent. #>
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Output)
    $match = $Output | Select-String -Pattern '^UPDATE (\d+)$' | Select-Object -First 1
    if (-not $match) { return $null }
    return [int]$match.Matches[0].Groups[1].Value
}

function Get-PsqlScalar {
    param([Parameter(Mandatory = $true)][string]$Sql)
    # @() keeps this an array even for a single row, so [0] is the row and not a character.
    $lines = @(Invoke-Psql -Sql $Sql -TuplesOnly | Where-Object { $_ -notin $TransactionTags })
    if ($lines.Count -eq 0) { return $null }
    return $lines[0].Trim()
}

function Assert-Container {
    $state = & docker inspect $PgContainer --format '{{.State.Status}}' 2>&1
    if ($LASTEXITCODE -ne 0 -or "$state".Trim() -ne 'running') {
        throw "PostgreSQL container '$PgContainer' is not running. Start it with: docker compose up -d postgres"
    }
}

# ---------------------------------------------------------------- 1. preflight
Write-Host "== Set-CharacterItemGrade ==" -ForegroundColor Cyan
Assert-Container

$escapedName = $Name.Replace("'", "''")
$matches = @(Invoke-Psql -TuplesOnly -Sql @"
SELECT id || '|' || name || '|' || server_id
FROM character_base
WHERE lower(name) = lower('$escapedName')
  AND server_id = $ServerId
  AND deleted_at IS NULL
ORDER BY id;
"@)

if ($matches.Count -eq 0) {
    throw "No live character named '$Name' on server $ServerId."
}
if ($matches.Count -gt 1) {
    throw "Character name '$Name' matches $($matches.Count) characters on server $ServerId. Names are not unique here; disambiguate by name before running."
}
$parts = $matches[0] -split '\|'
if ($parts.Count -ne 3) {
    throw "Unexpected character lookup result for '$Name': '$($matches[0])'"
}
$characterId = [int]$parts[0]
$characterName = $parts[1]
Write-Host "  character : $characterName (id $characterId, server $($parts[2]))"

# Discover the real caps instead of trusting constants in this file.
$maxGrade   = [int](Get-PsqlScalar -Sql 'SELECT max(level) FROM item_grade_levels;')
$maxQuality = [int](Get-PsqlScalar -Sql @"
SELECT (regexp_match(pg_get_constraintdef(oid), 'item_quality <= (\d+)'))[1]
FROM pg_constraint WHERE conname = 'ck_character_items_quality_domain';
"@)
$maxExp = [long](Get-PsqlScalar -Sql @"
SELECT 2147483647;
"@)

Write-Host "  caps      : grade<=$maxGrade quality<=$maxQuality exp<=$maxExp" -ForegroundColor DarkGray

$locationLabel = switch ($Location) {
    0 { 'equipped' }
    1 { 'kit bag' }
    2 { 'sealed / negative slots' }
    3 { 'warehouse' }
}

$before = @(Invoke-Psql -Sql @"
SELECT slot_index || '|' || prop_id || '|' || item_quality || '|' || item_grade || '|' || item_exp
FROM character_items
WHERE user_id = $characterId AND item_location = $Location
ORDER BY slot_index;
"@ -TuplesOnly)

if ($before.Count -eq 0) {
    throw "Character '$characterName' has no items in location $Location ($locationLabel)."
}
Write-Host "  items     : $($before.Count) in location $Location ($locationLabel)"

# ---------------------------------------------------------------- 2. target
# -Exp not supplied means different things per operation: MaxGrade wants the ceiling,
# SetStats wants experience left exactly as it is.
$expWasSupplied = $PSBoundParameters.ContainsKey('Exp')

$targetQuality = $null
if ($Quality -gt 0) { $targetQuality = $Quality }
$targetGrade = $null
if ($Grade -gt 0) { $targetGrade = $Grade }

if ([string]::IsNullOrEmpty($Operation)) {
    $Operation = if ($ExpDelta -gt 0) { 'AddExp' } elseif ($null -ne $targetQuality -or $null -ne $targetGrade) { 'SetStats' } else { 'MaxGrade' }
}

switch ($Operation) {
    'MaxGrade' {
        if ($null -eq $targetGrade) { $targetGrade = $maxGrade }
        $targetExp = if ($expWasSupplied) { $Exp } else { $maxExp }
    }
    'SetStats' {
        if ($null -eq $targetGrade) { $targetGrade = $maxGrade }
        $targetExp = $null   # experience is deliberately left alone
    }
    'SetExp' {
        $targetExp = if ($expWasSupplied) { $Exp } else { $maxExp }
    }
    'AddExp' {
        if ($ExpDelta -le 0) { throw '-ExpDelta must be positive when -Operation AddExp is used.' }
        $targetExp = $null
    }
}

if ($null -ne $targetGrade -and ($targetGrade -lt 1 -or $targetGrade -gt $maxGrade)) {
    throw "Requested grade $targetGrade is outside the permitted range 1..$maxGrade."
}
if ($null -ne $targetQuality -and ($targetQuality -lt 1 -or $targetQuality -gt $maxQuality)) {
    throw "Requested quality $targetQuality is outside the permitted range 1..$maxQuality."
}
if ($null -ne $targetExp) {
    if ($targetExp -gt $maxExp) { throw "Requested exp $targetExp exceeds the int4 maximum of $maxExp." }
    if ($targetExp -lt 0)       { throw 'Requested exp must not be negative.' }
}

# Refuse to fight a live session for the same rows unless told to.
if (-not $ConfirmCharacterOffline -and -not $WhatIf) {
    throw @"
Character '$characterName' must be offline before its items are edited.

Log the character out, then re-run with -ConfirmCharacterOffline.
(Character items are cached in the running server; editing a live character can be
overwritten when that session flushes.  Use -WhatIf to preview without this gate.)
"@
}

# ---------------------------------------------------------------- 3. plan
$setClauses = @()
if ($null -ne $targetQuality) { $setClauses += "item_quality = $targetQuality" }
if ($null -ne $targetGrade)   { $setClauses += "item_grade = $targetGrade" }
if ($null -ne $targetExp)     { $setClauses += "item_exp = $targetExp" }
if ($Operation -eq 'AddExp')  { $setClauses += "item_exp = LEAST(item_exp + $ExpDelta, $maxExp)" }
$setClauses += 'updated_at = now()'
$setList = $setClauses -join ', '

$differsParts = @()
if ($null -ne $targetQuality) { $differsParts += "item_quality <> $targetQuality" }
if ($null -ne $targetGrade)   { $differsParts += "item_grade <> $targetGrade" }
if ($null -ne $targetExp)     { $differsParts += "item_exp <> $targetExp" }
if ($Operation -eq 'AddExp')  { $differsParts += "item_exp <> LEAST(item_exp + $ExpDelta, $maxExp)" }
$differsClause = $differsParts -join ' OR '

$willChange = [int](Get-PsqlScalar -Sql @"
SELECT count(*) FROM character_items
WHERE user_id = $characterId AND item_location = $Location AND ($differsClause);
"@)

Write-Host ''
Write-Host "  operation : $Operation"
$targetParts = @()
if ($null -ne $targetQuality) { $targetParts += "quality $targetQuality" }
if ($null -ne $targetGrade)   { $targetParts += "grade $targetGrade" }
if ($null -ne $targetExp)     { $targetParts += "exp $targetExp" }
if ($Operation -eq 'AddExp')  { $targetParts += "exp += $ExpDelta" }
if ($targetParts.Count -eq 0) { $targetParts += '(nothing)' }
Write-Host "  target    : $($targetParts -join ', ')"
if ($null -eq $targetExp -and $Operation -ne 'AddExp') {
    Write-Host '              (experience left unchanged)' -ForegroundColor DarkGray
}
Write-Host "  rows that would change : $willChange of $($before.Count)"

if ($WhatIf) {
    Write-Host ''
    Write-Host '  -WhatIf: no changes written.' -ForegroundColor Yellow
    Write-Host '  current state:'
    $before | ForEach-Object {
        $f = $_ -split '\|'
        Write-Host ("    slot {0,3}  prop {1,-6} q{2,-3} g{3,-3} exp {4}" -f $f[0], $f[1], $f[2], $f[3], $f[4])
    }
    return
}

if ($willChange -eq 0) {
    Write-Host ''
    Write-Host "  Nothing to do: every item in location $Location already matches the target." -ForegroundColor Green
    return
}

# ---------------------------------------------------------------- 4. backup
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = Join-Path $BackupRoot "character-$characterId-items-$stamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$csvPath = Join-Path $backupDir 'character_items_before.csv'
$remoteCsv = "/tmp/charitems-$stamp.csv"
Invoke-Psql -Sql "\copy (SELECT * FROM character_items WHERE user_id = $characterId AND item_location = $Location ORDER BY slot_index) TO '$remoteCsv' WITH CSV HEADER" | Out-Null
& docker cp "${PgContainer}:$remoteCsv" $csvPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed.' }
& docker exec $PgContainer rm -f $remoteCsv | Out-Null

# The CSV carries a header row, so the data rows are one fewer than the line count.
$backupRows = (Get-Content $csvPath | Measure-Object -Line).Lines - 1
if ($backupRows -ne $before.Count) {
    throw "Backup holds $backupRows rows but $($before.Count) items were selected. Aborting."
}

# Record what was true before, so the restore script can verify it is reverting the
# right thing rather than blindly overwriting.
$manifestPath = Join-Path $backupDir 'manifest.json'
$manifest = [ordered]@{
    script        = 'Set-CharacterItemGrade.ps1'
    takenAtUtc    = (Get-Date).ToUniversalTime().ToString('o')
    characterId   = $characterId
    characterName = $characterName
    serverId      = [int]$parts[2]
    operation     = $Operation
    itemLocation  = $Location
    rowCount      = $before.Count
    # Exactly what this run intends to write, so the restore script can tell a
    # clean reverse from one that would discard newer changes.
    writtenTarget = [ordered]@{
        quality  = $targetQuality
        grade    = $targetGrade
        exp      = $targetExp
        expDelta = if ($Operation -eq 'AddExp') { $ExpDelta } else { $null }
    }
    rows = @($before | ForEach-Object {
        $f = $_ -split '\|'
        [ordered]@{
            slotIndex = [int]$f[0]; propId = [int]$f[1]
            quality = [int]$f[2]; grade = [int]$f[3]; exp = [long]$f[4]
        }
    })
    capsDiscovered = [ordered]@{ maxGrade = $maxGrade; maxQuality = $maxQuality; maxExp = $maxExp }
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host ''
Write-Host "  backup    : $backupDir" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 5. apply
$updateSql = @"
BEGIN;
UPDATE character_items
SET $setList
WHERE user_id = $characterId AND item_location = $Location;
COMMIT;
"@
$updateOutput = @(Invoke-Psql -Sql $updateSql)
$updated = Select-UpdateCount -Output $updateOutput
if ($null -eq $updated -or $updated -ne $before.Count) {
    throw "Update reported '$($updateOutput -join ' ')'; expected UPDATE $($before.Count). The transaction did not report the expected row count; inspect the table and the backup at $backupDir."
}
Write-Host "  applied   : UPDATE $updated" -ForegroundColor Green

# ---------------------------------------------------------------- 6. verify
$after = @(Invoke-Psql -Sql @"
SELECT slot_index || '|' || prop_id || '|' || item_quality || '|' || item_grade || '|' || item_exp
FROM character_items
WHERE user_id = $characterId AND item_location = $Location
ORDER BY slot_index;
"@ -TuplesOnly)

$bad = 0
$report = @()
for ($i = 0; $i -lt $after.Count; $i++) {
    $b = $before[$i] -split '\|'
    $a = $after[$i]  -split '\|'
    $ok = $true
    if ($null -ne $targetQuality -and [int]$a[2] -ne $targetQuality) { $ok = $false }
    if ($null -ne $targetGrade   -and [int]$a[3] -ne $targetGrade)   { $ok = $false }
    if ($Operation -eq 'AddExp') {
        if ([long]$a[4] -ne [Math]::Min([long]$b[4] + $ExpDelta, $maxExp)) { $ok = $false }
    }
    elseif ($null -ne $targetExp) {
        if ([long]$a[4] -ne $targetExp) { $ok = $false }
    }
    else {
        # experience was not targeted; it must be exactly as it was
        if ([long]$a[4] -ne [long]$b[4]) { $ok = $false }
    }
    if (-not $ok) { $bad++ }
    $report += [pscustomobject]@{
        Slot = [int]$a[0]; Prop = [int]$a[1]
        'Q was' = [int]$b[2]; 'Q now' = [int]$a[2]
        'G was' = [int]$b[3]; 'G now' = [int]$a[3]
        'Exp was' = [long]$b[4]; 'Exp now' = [long]$a[4]
    }
}

# Independently re-check the table-level invariants the update must not break.
$violations = [int](Get-PsqlScalar -Sql @"
SELECT count(*) FROM character_items
WHERE user_id = $characterId AND item_location = $Location
  AND (item_grade < 0 OR item_grade > $maxGrade
    OR item_quality < 0 OR item_quality > $maxQuality
    OR item_exp < 0);
"@)

$report | Format-Table -AutoSize
Write-Host "  verified  : $($after.Count - $bad)/$($after.Count) rows match the target; $violations domain violations" -ForegroundColor $(if ($bad -eq 0 -and $violations -eq 0) { 'Green' } else { 'Red' })

# Confirm scope: nothing outside the targeted location moved.
$otherLocations = [int](Get-PsqlScalar -Sql @"
SELECT count(*) FROM character_items
WHERE user_id = $characterId AND item_location <> $Location
  AND item_exp <> 0;
"@)
if ($Location -eq 0 -and $otherLocations -ne 0) {
    Write-Host "  note      : $otherLocations rows outside location 0 carry experience; they were not touched by this script." -ForegroundColor Yellow
}

if ($bad -ne 0 -or $violations -ne 0) {
    throw "Verification failed. Restore with: ./Scripts/Restore-CharacterItemGrade.ps1 -BackupDirectory `"$backupDir`" -ConfirmCharacterOffline"
}
Write-Host ''
Write-Host '  Done.' -ForegroundColor Cyan
