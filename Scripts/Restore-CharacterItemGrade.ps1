<#
.SYNOPSIS
    Restore item grade and experience from a Set-CharacterItemGrade.ps1 backup.

.DESCRIPTION
    Reverses a Set-CharacterItemGrade.ps1 run using the manifest.json written beside
    the backup.  Only item_grade, item_exp and updated_at are restored; every other
    column is left exactly as it is now, so unrelated edits made since the backup are
    not clobbered.

    Before touching anything the script checks that each item still holds the value the
    forward run wrote.  If an item no longer does, the database has moved on and the
    script refuses rather than silently discarding that change.  Pass -Force to restore
    anyway.

    -WhatIf reports what would be restored without writing.

.PARAMETER BackupDirectory
    A backups/character-<id>-items-<timestamp> directory produced by Set-CharacterItemGrade.ps1.

.PARAMETER Force
    Restore even when an item's current value differs from what the forward run wrote.

.EXAMPLE
    ./Restore-CharacterItemGrade.ps1 -BackupDirectory ../backups/character-2-items-20260918-232235 -WhatIf

.EXAMPLE
    ./Restore-CharacterItemGrade.ps1 -BackupDirectory ../backups/character-2-items-20260918-232235 -ConfirmCharacterOffline
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BackupDirectory,
    [switch]$Force,
    [switch]$WhatIf,
    [switch]$ConfirmCharacterOffline
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$PgContainer = if ($env:GODSWAR_PG_CONTAINER) { $env:GODSWAR_PG_CONTAINER } else { 'godswar-postgres' }
$PgDatabase  = if ($env:POSTGRES_DB)         { $env:POSTGRES_DB }         else { 'godswar_local' }
$PgUser      = if ($env:POSTGRES_USER)       { $env:POSTGRES_USER }       else { 'godswar' }

$TransactionTags = @('BEGIN', 'COMMIT', 'ROLLBACK', 'START TRANSACTION')

function Invoke-Psql {
    param([Parameter(Mandatory = $true)][string]$Sql, [switch]$TuplesOnly)
    $a = @('exec', '-i', $PgContainer, 'psql', '-U', $PgUser, '-d', $PgDatabase,
           '-v', 'ON_ERROR_STOP=1', '-X')
    if ($TuplesOnly) { $a += @('-t', '-A') }
    $a += @('-c', $Sql)
    $output = & docker @a 2>&1
    if ($LASTEXITCODE -ne 0) { throw "psql failed (exit $LASTEXITCODE):`n$($output -join "`n")" }
    return @($output | Where-Object { $_ -is [string] -and $_.Trim().Length -gt 0 })
}

function Select-UpdateCount {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Output)
    $match = $Output | Select-String -Pattern '^UPDATE (\d+)$' | Select-Object -First 1
    if (-not $match) { return $null }
    return [int]$match.Matches[0].Groups[1].Value
}

function Get-PsqlScalar {
    param([Parameter(Mandatory = $true)][string]$Sql)
    # @() keeps this an array even for a single row, so [0] is the row and not a character.
    $l = @(Invoke-Psql -Sql $Sql -TuplesOnly | Where-Object { $_ -notin $TransactionTags })
    if ($l.Count -eq 0) { return $null }
    return $l[0].Trim()
}

Write-Host '== Restore-CharacterItemGrade ==' -ForegroundColor Cyan

if (-not (Test-Path $BackupDirectory)) { throw "Backup directory not found: $BackupDirectory" }
$BackupDirectory = (Resolve-Path $BackupDirectory).Path

$manifestPath = Join-Path $BackupDirectory 'manifest.json'
$csvPath      = Join-Path $BackupDirectory 'character_items_before.csv'
if (-not (Test-Path $manifestPath)) { throw "manifest.json is missing from $BackupDirectory" }
if (-not (Test-Path $csvPath))      { throw "character_items_before.csv is missing from $BackupDirectory" }

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$characterId = [int]$manifest.characterId
# Backups from before the location parameter always targeted equipped items.
$location = if ($null -ne $manifest.itemLocation) { [int]$manifest.itemLocation } else { 0 }
Write-Host "  character : $($manifest.characterName) (id $characterId, server $($manifest.serverId))"
Write-Host "  taken     : $($manifest.takenAtUtc)  operation=$($manifest.operation)  location=$location  rows=$($manifest.rowCount)" -ForegroundColor DarkGray

$state = & docker inspect $PgContainer --format '{{.State.Status}}' 2>&1
if ($LASTEXITCODE -ne 0 -or "$state".Trim() -ne 'running') {
    throw "PostgreSQL container '$PgContainer' is not running."
}

if (-not $ConfirmCharacterOffline -and -not $WhatIf) {
    throw @"
Character '$($manifest.characterName)' must be offline before its items are restored.

Log the character out and re-run with -ConfirmCharacterOffline (or use -WhatIf to preview).
"@
}

# Divergence check.  Every item is matched by its slot within the backed-up location,
# then compared against what the forward run wrote.
$rows = @(Invoke-Psql -TuplesOnly -Sql @"
SELECT id || '|' || slot_index || '|' || item_quality || '|' || item_grade || '|' || item_exp
FROM character_items
WHERE user_id = $characterId AND item_location = $location
ORDER BY slot_index;
"@)

if ($rows.Count -eq 0) { throw "Character $characterId has no items in location $location; nothing to restore." }

$currentBySlot = @{}
foreach ($r in $rows) {
    $f = $r -split '\|'
    $currentBySlot[[int]$f[1]] = [pscustomobject]@{
        Id = [long]$f[0]; Quality = [int]$f[2]; Grade = [int]$f[3]; Exp = [long]$f[4]
    }
}

$target = $manifest.writtenTarget
$diverged = @()
foreach ($m in $manifest.rows) {
    $slot = [int]$m.slotIndex
    if (-not $currentBySlot.ContainsKey($slot)) {
        $diverged += "slot ${slot}: no longer present on the character"
        continue
    }
    $current = $currentBySlot[$slot]
    if ($null -ne $target.quality -and $current.Quality -ne [int]$target.quality) {
        $diverged += "slot ${slot}: quality is $($current.Quality), the forward run wrote $($target.quality)"
    }
    elseif ($null -ne $target.grade -and $current.Grade -ne [int]$target.grade) {
        $diverged += "slot ${slot}: grade is $($current.Grade), the forward run wrote $($target.grade)"
    }
    elseif ($null -ne $target.exp -and $current.Exp -ne [long]$target.exp) {
        $diverged += "slot ${slot}: exp is $($current.Exp), the forward run wrote $($target.exp)"
    }
    elseif ($null -ne $target.expDelta) {
        $expected = [Math]::Min([long]$m.exp + [long]$target.expDelta, [long]$manifest.capsDiscovered.maxExp)
        if ($current.Exp -ne $expected) {
            $diverged += "slot ${slot}: exp is $($current.Exp), the forward run wrote $expected"
        }
    }
}

if ($diverged.Count -gt 0 -and -not $Force) {
    Write-Host ''
    $diverged | ForEach-Object { Write-Host "  diverged: $_" -ForegroundColor Yellow }
    throw @"
The database no longer matches what the forward run wrote, so restoring would discard
those newer changes.  Re-run with -Force only if that is what you want.
"@
}

Write-Host "  items     : $($rows.Count)"
if ($WhatIf) {
    Write-Host ''
    Write-Host '  -WhatIf: would restore these rows from the backup:' -ForegroundColor Yellow
    $manifest.rows | ForEach-Object {
        Write-Host ("    slot {0,3}  quality -> {1,-3}  grade -> {2,-3}  exp -> {3}" -f $_.slotIndex, $_.quality, $_.grade, $_.exp)
    }
    return
}

# Restore straight from the manifest.  The manifest is the authoritative record of
# what the forward run replaced, which avoids a second, redundant parse of the CSV.
# (\copy is a psql meta-command and cannot be embedded in a -c script, so the CSV is
# kept purely as human-readable evidence.)
$values = ($manifest.rows | ForEach-Object {
    "({0}, {1}, {2}, {3})" -f [int]$_.slotIndex, [int]$_.quality, [int]$_.grade, [long]$_.exp
}) -join ",`n    "

$sql = @"
BEGIN;
UPDATE character_items AS ci
SET item_quality = v.quality,
    item_grade   = v.grade,
    item_exp     = v.exp,
    updated_at   = now()
FROM (VALUES
    $values
) AS v(slot_index, quality, grade, exp)
WHERE ci.user_id = $characterId
  AND ci.item_location = $location
  AND ci.slot_index = v.slot_index;
COMMIT;
"@

$output = @(Invoke-Psql -Sql $sql)
$updated = Select-UpdateCount -Output $output
if ($null -eq $updated) {
    throw "Restore did not report an UPDATE row count. Output: $($output -join ' | ')"
}
Write-Host "  restored  : UPDATE $updated" -ForegroundColor Green

# Verify against the manifest.
$after = @(Invoke-Psql -TuplesOnly -Sql @"
SELECT slot_index || '|' || item_quality || '|' || item_grade || '|' || item_exp
FROM character_items
WHERE user_id = $characterId AND item_location = $location ORDER BY slot_index;
"@)
$afterBySlot = @{}
foreach ($r in $after) { $f = $r -split '\|'; $afterBySlot[[int]$f[0]] = $f }

$bad = 0
foreach ($m in $manifest.rows) {
    $a = $afterBySlot[[int]$m.slotIndex]
    if (-not $a -or
        [int]$a[1] -ne [int]$m.quality -or
        [int]$a[2] -ne [int]$m.grade -or
        [long]$a[3] -ne [long]$m.exp) {
        $bad++
    }
}
Write-Host "  verified  : $($manifest.rows.Count - $bad)/$($manifest.rows.Count) rows match the backup" -ForegroundColor $(if ($bad -eq 0) { 'Green' } else { 'Red' })
if ($bad -ne 0) { throw 'Restore verification failed; inspect the table and the backup.' }
Write-Host ''
Write-Host '  Done.' -ForegroundColor Cyan
