[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$patcher = Join-Path $PSScriptRoot 'PatchClientWonderlandTitles.ps1'
$artifactRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'artifacts\wonderland-all-island-titles-20260910'
$fixtureRoot = Join-Path $artifactRoot ('synthetic-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($fixtureRoot) | Out-Null
$encoding = [Text.UnicodeEncoding]::new($false, $true, $true)
$ids = @(5155, 5114, 5156, 5115, 5157, 5116, 5117, 5118)
$names = @('Gatebreaker', 'Demonbreaker', 'Flamebreaker', 'Stonebreaker',
    "Marshal's Bane", 'Dragonbane', "Hydra's Bane", 'Wonderland Sovereign')
$passed = [Collections.Generic.List[string]]::new()

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "Wonderland title patch test failed: $Message" }
}
function Hash-Bytes([byte[]]$Bytes) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($Bytes)).Replace('-', '') }
    finally { $algorithm.Dispose() }
}
function Save-Text([string]$Path, [string]$Text) {
    [IO.File]::WriteAllBytes($Path, ($encoding.GetPreamble() + $encoding.GetBytes($Text)))
}
function Read-Text([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    Assert-True ($bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE -and $bytes.Length % 2 -eq 0) 'UTF-16LE BOM and byte alignment'
    return $encoding.GetString($bytes, 2, $bytes.Length - 2)
}
function New-Fixture([string]$Name) {
    $root = Join-Path $fixtureRoot $Name
    $files = [Collections.Generic.List[object]]::new()
    foreach ($locale in @('en_us', 'zh_cn')) {
        foreach ($file in @('DesigName.dat', 'DesigInfo.dat')) {
            $relative = "Localization\$locale\Text\$file"
            $path = Join-Path $root $relative
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
            $newLine = if ($locale -eq 'en_us') { "`r`n" } else { "`n" }
            $final = $file -eq 'DesigInfo.dat'
            $unicode = [string][char]0x6D77 + [char]0x795E + [char]::ConvertFromUtf32(0x1F30A)
            $rows = @("6000`tUnrelated $unicode", "5009`tPreserve Medusa",
                "5114`tLegacy island two", "5115`tLegacy island four", "5116`tLegacy island six",
                "5117`tLegacy island seven", "5118`tLegacy island eight", "5119`tHoly Star",
                "5120`tOrion the Magnificent", "5121`tLegendary Hero", "5132`tGaia's Envoy",
                "5152`tHeir of Perseus", "5153`tBane of the Three Sisters", "5154`tGorgon Breaker")
            $content = [string]::Join($newLine, $rows)
            if ($final) { $content += $newLine }
            Save-Text $path $content
            $files.Add([pscustomobject]@{ Relative = $relative; Path = $path; File = $file; Locale = $locale
                Before = [IO.File]::ReadAllBytes($path); OriginalRows = $rows; NewLine = $newLine; Final = $final })
        }
    }
    return [pscustomobject]@{ Root = $root; Files = $files }
}
function Get-Hashes($Fixture) {
    $result = @{}
    foreach ($file in $Fixture.Files) { $result[$file.Relative] = (Get-FileHash -LiteralPath $file.Path).Hash }
    return $result
}
function Assert-Hashes($Fixture, [hashtable]$Expected, [string]$Reason) {
    foreach ($file in $Fixture.Files) {
        Assert-True ((Get-FileHash -LiteralPath $file.Path).Hash -eq $Expected[$file.Relative]) "$Reason $($file.Relative)"
    }
}
function Assert-Rejected($Fixture, [string]$ExpectedError, [scriptblock]$Action) {
    $before = Get-Hashes $Fixture
    $failure = $null
    try { & $Action | Out-Null } catch { $failure = $_.Exception.Message }
    Assert-True ($null -ne $failure -and $failure -match $ExpectedError) "expected rejection '$ExpectedError', got '$failure'"
    Assert-Hashes $Fixture $before 'rejection preserves original bytes'
}
function Get-Backups($Fixture) {
    $path = Join-Path $Fixture.Root 'backups\wonderland-titles'
    if (Test-Path -LiteralPath $path) { Get-ChildItem -LiteralPath $path -Directory }
}
function Assert-Patched($Fixture, [string[]]$ExpectedNames) {
    foreach ($file in $Fixture.Files) {
        $expectedById = @{}
        for ($index = 0; $index -lt 8; $index++) {
            $value = if ($file.File -eq 'DesigName.dat') { $ExpectedNames[$index] } else {
                "Clear Wonderland island $($index + 1) with your admitted party. Unlocks the $($ExpectedNames[$index]) title. Select it in the title menu."
            }
            $expectedById[$ids[$index]] = "$($ids[$index])`t$value"
        }
        $expectedRows = @($file.OriginalRows | ForEach-Object {
            $id = [int]($_.Split("`t")[0])
            if ($expectedById.ContainsKey($id)) { $expectedById[$id] } else { $_ }
        }) + @($expectedById[5155], $expectedById[5156], $expectedById[5157])
        $expected = [string]::Join($file.NewLine, $expectedRows)
        if ($file.Final) { $expected += $file.NewLine }
        $actual = Read-Text $file.Path
        Assert-True ($actual -ceq $expected) "exact eight title mappings; only intended rows change in $($file.Relative)"
        $expectedBytes = $encoding.GetPreamble() + $encoding.GetBytes($expected)
        Assert-True ((Hash-Bytes ([IO.File]::ReadAllBytes($file.Path))) -eq (Hash-Bytes $expectedBytes)) 'Unicode, BOM, line endings and final newline preserved byte-for-byte'
    }
}

$fixture = New-Fixture 'upgrade'
$originalHashes = Get-Hashes $fixture
$preview = (& $patcher -ClientPath $fixture.Root -Preview | Out-String) | ConvertFrom-Json
Assert-True ($preview.Count -eq 4) 'preview covers two files in each locale'
foreach ($plan in $preview) {
    Assert-True (($plan.Rows.Id -join ',') -eq '5155,5114,5156,5115,5157,5116,5117,5118') 'explicit ID mapping is in island order'
    Assert-True (($plan.Rows.Island -join ',') -eq '1,2,3,4,5,6,7,8') 'preview includes all islands'
    Assert-True (@($plan.Rows | Where-Object { $null -eq $_.Before }).Count -eq 3) 'only three new rows append'
}
Assert-Hashes $fixture $originalHashes 'preview is read-only'
Assert-True (@(Get-Backups $fixture).Count -eq 0) 'preview creates no backups'
Assert-Rejected $fixture 'needs an update' { & $patcher -ClientPath $fixture.Root -ValidateOnly }
$passed.Add('read-only preview and pre-patch validation')

& $patcher -ClientPath $fixture.Root | Out-Null
Assert-Patched $fixture $names
$backups = @(Get-Backups $fixture)
Assert-True ($backups.Count -eq 1) 'one transactional backup set'
$manifest = Get-Content -LiteralPath (Join-Path $backups[0].FullName 'manifest.json') -Raw | ConvertFrom-Json
Assert-True ($manifest.Status -eq 'Verified' -and $manifest.Files.Count -eq 4) 'verified four-file manifest'
foreach ($file in $fixture.Files) {
    $backup = Join-Path $backups[0].FullName $file.Relative
    Assert-True ((Get-FileHash -LiteralPath $backup).Hash -eq (Hash-Bytes $file.Before)) 'backup retains exact pre-upgrade bytes'
    $record = @($manifest.Files | Where-Object { $_.Path -eq $file.Relative })[0]
    Assert-True ($record.BeforeSha256 -eq (Hash-Bytes $file.Before)) 'manifest before hash'
    Assert-True ($record.AfterSha256 -eq (Get-FileHash -LiteralPath $file.Path).Hash) 'manifest after hash'
}
$passed.Add('eight mappings, unrelated titles, Unicode, CRLF/LF, final newline and verified backups')
$patchedHashes = Get-Hashes $fixture
& $patcher -ClientPath $fixture.Root | Out-Null
& $patcher -ClientPath $fixture.Root -ValidateOnly | Out-Null
Assert-Hashes $fixture $patchedHashes 'repeat application is idempotent'
Assert-True (@(Get-Backups $fixture).Count -eq 1) 'idempotence creates no extra backups'
$passed.Add('idempotence and post-patch validation')

$customNames = @($names | ForEach-Object { 'Custom ' + $_ })
& $patcher -ClientPath $fixture.Root -TitleNames $customNames | Out-Null
Assert-Patched $fixture $customNames
& $patcher -ClientPath $fixture.Root -TitleNames $customNames -ValidateOnly | Out-Null
& $patcher -ClientPath $fixture.Root -TitleNames $names | Out-Null
Assert-Hashes $fixture $patchedHashes 'authored reserved IDs can be renamed and restored'
$passed.Add('paired title ownership allows repeatable custom names')

$single = New-Fixture 'one-locale'
$singleHashes = Get-Hashes $single
& $patcher -ClientPath $single.Root -Locales en_us | Out-Null
foreach ($file in $single.Files) {
    $changed = (Get-FileHash -LiteralPath $file.Path).Hash -ne $singleHashes[$file.Relative]
    Assert-True ($changed -eq ($file.Locale -eq 'en_us')) 'locale selection changes only requested files'
}
$passed.Add('selected locale isolation')

foreach ($scenario in @('duplicate-old', 'duplicate-new', 'occupied-new', 'partial-new', 'missing-old',
        'odd-bytes', 'invalid-surrogate', 'wrong-bom', 'mixed-lines', 'too-large')) {
    $bad = New-Fixture $scenario
    $last = $bad.Files[3]
    $text = Read-Text $last.Path
    switch ($scenario) {
        'duplicate-old' { Save-Text $last.Path ($text + "5114`tDuplicate`n") }
        'duplicate-new' { Save-Text $last.Path ($text + "5155`tDuplicate`n5155`tDuplicate`n") }
        'occupied-new' {
            Save-Text $last.Path ($text + "5155`tUnrelated achievement`n")
            $namePath = $bad.Files[2].Path
            Save-Text $namePath ((Read-Text $namePath) + "`n5155`tAnother title")
        }
        'partial-new' { Save-Text $last.Path ($text + "5155`tIncomplete pair`n") }
        'missing-old' { Save-Text $last.Path ([regex]::Replace($text, '(?m)^5114\t[^\r\n]*\n', '')) }
        'odd-bytes' { [IO.File]::WriteAllBytes($last.Path, ([IO.File]::ReadAllBytes($last.Path) + [byte]0x00)) }
        'invalid-surrogate' { [IO.File]::WriteAllBytes($last.Path, ([IO.File]::ReadAllBytes($last.Path) + [byte[]]@(0x00, 0xD8))) }
        'wrong-bom' { [IO.File]::WriteAllText($last.Path, $text, [Text.UTF8Encoding]::new($false)) }
        'mixed-lines' { Save-Text $last.Path ($text + "6100`tMixed`r`n") }
        'too-large' { Save-Text $last.Path ($text + ('x' * 10000)) }
    }
    Assert-Rejected $bad '.' { & $patcher -ClientPath $bad.Root }
    Assert-True (@(Get-Backups $bad).Count -eq 0) "$scenario is rejected before any writes"
    $passed.Add("fail-closed preflight: $scenario")
}

$rollback = New-Fixture 'rollback'
# A read-shared handle permits full preflight/backup but denies replacement of the
# fourth file, after the first three files have been replaced successfully.
$lock = [IO.File]::Open($rollback.Files[3].Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
try { Assert-Rejected $rollback 'Replace|used by another process|access' { & $patcher -ClientPath $rollback.Root } }
finally { $lock.Dispose() }
$rollbackBackups = @(Get-Backups $rollback)
Assert-True ($rollbackBackups.Count -eq 1) 'failed commit retains one backup set'
$rollbackManifest = Get-Content -LiteralPath (Join-Path $rollbackBackups[0].FullName 'manifest.json') -Raw | ConvertFrom-Json
Assert-True ($rollbackManifest.Status -eq 'RolledBack') 'partial write rolled back all previous files'
Assert-True (@(Get-ChildItem -LiteralPath $rollback.Root -Recurse -File | Where-Object {
    $_.Name.EndsWith('.stage') -or $_.Name.EndsWith('.original') }).Count -eq 0) 'staging files cleaned after rollback'
& $patcher -ClientPath $rollback.Root | Out-Null
Assert-Patched $rollback $names
$passed.Add('fourth-file failure rolls back exact bytes; retry succeeds')

$report = [ordered]@{ Passed = $passed.Count; Checks = @($passed); FixtureRoot = $fixtureRoot }
$json = $report | ConvertTo-Json -Depth 5
[IO.File]::WriteAllText((Join-Path $fixtureRoot 'result.json'), $json, [Text.UTF8Encoding]::new($false))
Write-Output $json
