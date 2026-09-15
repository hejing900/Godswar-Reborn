$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$patcher = Join-Path $PSScriptRoot 'PatchClientOnlineAwardLocalization.ps1'
$helper = Join-Path $PSScriptRoot (
    'client_patch_helpers\OnlineAwardLocalization.Core.ps1')
if (-not (Test-Path -LiteralPath $patcher -PathType Leaf) -or
    -not (Test-Path -LiteralPath $helper -PathType Leaf)) {
    throw 'Online Award localization patch files are incomplete.'
}
. $helper

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Assert-Equal($Expected, $Actual, [string]$Message) {
    if ($Expected -cne $Actual) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Write-FixtureText(
    [string]$Path,
    [string]$Text,
    [ValidateSet('Utf16LeBom', 'Utf8', 'Utf8Bom')]
    [string]$Encoding
) {
    $directory = Split-Path -Parent $Path
    [void](New-Item -ItemType Directory -Path $directory -Force)
    switch ($Encoding) {
        'Utf16LeBom' {
            [byte[]]$body = [Text.Encoding]::Unicode.GetBytes($Text)
            [byte[]]$data = [byte[]]::new($body.Length + 2)
            $data[0] = 0xFF
            $data[1] = 0xFE
            [Array]::Copy($body, 0, $data, 2, $body.Length)
        }
        'Utf8' {
            [byte[]]$data = [Text.UTF8Encoding]::new($false, $true).GetBytes($Text)
        }
        'Utf8Bom' {
            [byte[]]$body = [Text.UTF8Encoding]::new($false, $true).GetBytes($Text)
            [byte[]]$data = [byte[]]::new($body.Length + 3)
            $data[0] = 0xEF
            $data[1] = 0xBB
            $data[2] = 0xBF
            [Array]::Copy($body, 0, $data, 3, $body.Length)
        }
    }
    [IO.File]::WriteAllBytes($Path, $data)
}

function Get-FixtureBytes([string]$Path) {
    return [IO.File]::ReadAllBytes($Path)
}

function Assert-Throws([scriptblock]$Action, [string]$Pattern) {
    $threw = $false
    try { & $Action }
    catch {
        $threw = $true
        if ($_.Exception.Message -notmatch $Pattern) {
            throw "Unexpected error: $($_.Exception.Message)"
        }
    }
    if (-not $threw) { throw "Expected an error matching '$Pattern'." }
}

$tempParent = Get-OaFullPath ([IO.Path]::GetTempPath())
$fixtureRoot = Get-OaFullPath (Join-Path $tempParent (
    'reborn-online-award-fixture-' + [Guid]::NewGuid().ToString('N')))
if (-not (Test-OaPathWithin $fixtureRoot $tempParent) -or
    $fixtureRoot -ceq $tempParent) {
    throw 'Fixture root escaped the system temporary directory.'
}
$clientRoot = Join-Path $fixtureRoot 'Godswar Origin Fixture'
$backupRoot = Join-Path $fixtureRoot 'backups'

try {
    [void](New-Item -ItemType Directory -Path $clientRoot)
    [IO.File]::WriteAllBytes((Join-Path $clientRoot 'Origin.exe'), [byte[]]@(0x4D, 0x5A))
    $catalog = Get-OaTextCatalog
    $specifications = @(Get-OaFileSpecifications)
    $byRole = @{}
    foreach ($specification in $specifications) {
        $byRole[$specification.Role] = Join-Path $clientRoot $specification.RelativePath
    }

    $enNpc = -join @(
        "FixtureBefore`tuntouched`r`n",
        "Athens_132`t$($catalog.Original.EnDescription)`r`n",
        "Middle`tunchanged`r`n",
        "Sparta_132`t$($catalog.Original.EnDescription)`r`n",
        'FixtureAfter`tuntouched')
    Write-FixtureText $byRole.EnNpcDescription $enNpc 'Utf16LeBom'

    $zhNpc = -join @(
        "FixtureBefore`tuntouched`r`n",
        "Athens_132`t$($catalog.Original.ZhAthensDescription)`r`n",
        "Middle`tunchanged`r`n",
        "Sparta_132`t$($catalog.Original.ZhSpartaDescription)`r`n",
        "FixtureAfter`tuntouched`r`n")
    Write-FixtureText $byRole.ZhNpcDescription $zhNpc 'Utf16LeBom'

    $quoteCrLf = '"' + "`r`n"
    $enLua = -join @(
        'FixtureBefore = "untouched"', "`n",
        '-- first active block', "`r`n",
        'StayReward1 = "', $catalog.Original.StayReward1, $quoteCrLf,
        'StayReward2 = "Claim the Online Award"', "`r`n",
        'StayReward3 = "', $catalog.Original.StayReward3, $quoteCrLf,
        'StayReward4 = "', $catalog.Original.StayReward4First, $quoteCrLf,
        'StayReward5 = "', $catalog.Original.StayReward5First, $quoteCrLf,
        'StayReward6 = "Your inventory is full."', "`r`n",
        'StayReward7 = "The Event isn''t available at the moment."', "`r`n",
        '-- StayReward1 = "', $catalog.Original.StayReward1, $quoteCrLf,
        '-- second active block', "`r`n",
        'StayReward1 = "', $catalog.Original.StayReward1, $quoteCrLf,
        'StayReward2 = "Claim the Online Award"', "`r`n",
        'StayReward3 = "', $catalog.Original.StayReward3, $quoteCrLf,
        'StayReward4 = "', $catalog.Original.StayReward4Second, $quoteCrLf,
        'StayReward5 = "', $catalog.Original.StayReward5Second, $quoteCrLf,
        'StayReward6 = "Your inventory is full."', "`r`n",
        'StayReward7 = "The Event isn''t available at the moment."', "`r`n",
        'FixtureAfter = "untouched"', "`r`n")
    Write-FixtureText $byRole.EnLuaText $enLua 'Utf8'

    $zhLua = -join @(
        '-- fixture', "`r`n",
        'FixtureBefore = "untouched"', "`r`n",
        'FixtureAfter = "untouched"')
    Write-FixtureText $byRole.ZhLuaText $zhLua 'Utf8Bom'

    $beforeByPath = @{}
    foreach ($path in $byRole.Values) {
        $beforeByPath[$path] = Get-FixtureBytes $path
    }
    $beforeStates = @(Get-OnlineAwardClientStates $clientRoot)
    Assert-Equal 4 $beforeStates.Count 'Fixture should expose four patch files.'
    foreach ($state in $beforeStates) {
        Assert-Equal 'Original' $state.State "$($state.Role) initial state mismatch."
        Assert-True (
            $state.Sha256 -cne $state.PlannedSha256) (
            "$($state.Role) should have a distinct planned hash.")
    }

    $status = & $patcher -Mode Status -ClientRoot $clientRoot
    Assert-Equal 'Original' $status.State 'Status should report Original.'
    Assert-Equal $false $status.OriginRunning 'Fixture status should report Origin closed.'

    Assert-Throws {
        & $patcher -Mode Apply -ClientRoot $clientRoot `
            -BackupRoot $backupRoot -TestFailAfterFirstAtomicReplace `
            -Confirm:$false | Out-Null
    } 'Injected post-replace cleanup failure'
    foreach ($path in $byRole.Values) {
        [byte[]]$actual = Get-FixtureBytes $path
        Assert-True (
            (Test-OaBytesEqual $actual $beforeByPath[$path])) (
            "Failed Apply compensation did not restore exact bytes: $path")
    }
    $failedApplyStatus = & $patcher -Mode Status -ClientRoot $clientRoot
    Assert-Equal 'Original' $failedApplyStatus.State (
        'Injected Apply failure must leave the complete original state.')

    $apply = & $patcher -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-Equal 'Applied' $apply.State 'Apply should report Applied.'
    Assert-Equal $true $apply.Changed 'Apply should report a change.'
    Assert-True (
        (Test-Path -LiteralPath $apply.Receipt -PathType Leaf)) (
        'Apply should create a receipt.')
    $receiptPath = [string]$apply.Receipt

    foreach ($state in $beforeStates) {
        [byte[]]$actual = Get-FixtureBytes $state.Path
        Assert-True (
            (Test-OaBytesEqual $actual $state.PlannedData)) (
            "$($state.Role) did not match its exact byte plan.")
    }
    $afterStates = @(Get-OnlineAwardClientStates $clientRoot)
    foreach ($state in $afterStates) {
        Assert-Equal 'Applied' $state.State "$($state.Role) applied state mismatch."
    }

    $secondApply = & $patcher -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-Equal $false $secondApply.Changed 'A second apply must be idempotent.'
    Assert-Equal $null $secondApply.Receipt 'Idempotent apply must not invent a receipt.'

    $enLuaPath = $byRole.EnLuaText
    [byte[]]$validApplied = Get-FixtureBytes $enLuaPath
    $foreignText = [Text.UTF8Encoding]::new($false, $true).GetBytes(
        ("`r`n" + 'StayReward4 = "Foreign value"'))
    $targetText = [Text.UTF8Encoding]::new($false, $true).GetBytes(
        ("`r`n" + 'StayReward4 = "' + $catalog.En.StayReward4 + '"'))
    [byte[]]$foreign = Replace-OaBytes $validApplied $targetText $foreignText 2
    [IO.File]::WriteAllBytes($enLuaPath, $foreign)
    Assert-Throws {
        & $patcher -Mode Status -ClientRoot $clientRoot | Out-Null
    } 'foreign or partial English'
    [IO.File]::WriteAllBytes($enLuaPath, $validApplied)

    Assert-Throws {
        & $patcher -Mode Revert -ClientRoot $clientRoot `
            -ReceiptPath $receiptPath -TestFailAfterFirstAtomicReplace `
            -Confirm:$false | Out-Null
    } 'Injected post-replace cleanup failure'
    foreach ($state in $afterStates) {
        [byte[]]$actual = Get-FixtureBytes $state.Path
        Assert-True (
            (Test-OaBytesEqual $actual $state.PlannedData)) (
            "Failed Revert compensation did not restore exact bytes: $($state.Path)")
    }
    $failedRevertStatus = & $patcher -Mode Status -ClientRoot $clientRoot
    Assert-Equal 'Applied' $failedRevertStatus.State (
        'Injected Revert failure must leave the complete applied state.')

    $revert = & $patcher -Mode Revert -ClientRoot $clientRoot `
        -ReceiptPath $receiptPath -Confirm:$false
    Assert-Equal 'Original' $revert.State 'Revert should report Original.'
    Assert-Equal $true $revert.Changed 'Revert should report a change.'
    foreach ($path in $byRole.Values) {
        [byte[]]$actual = Get-FixtureBytes $path
        Assert-True (
            (Test-OaBytesEqual $actual $beforeByPath[$path])) (
            "Rollback did not restore exact bytes: $path")
    }

    $secondRevert = & $patcher -Mode Revert -ClientRoot $clientRoot `
        -ReceiptPath $receiptPath -Confirm:$false
    Assert-Equal $false $secondRevert.Changed 'A second revert must be idempotent.'

    [pscustomobject]@{
        Passed = $true
        Cases = @(
            'strict four-file original-state recognition',
            'exact byte-plan application with encoding preservation',
            'post-replace Apply and Revert failure compensation',
            'idempotent apply',
            'foreign-state rejection',
            'receipt-backed exact rollback',
            'idempotent revert')
    }
}
finally {
    if (Test-Path -LiteralPath $fixtureRoot) {
        $resolvedFixture = Get-OaFullPath $fixtureRoot
        if (-not (Test-OaPathWithin $resolvedFixture $tempParent) -or
            $resolvedFixture -ceq $tempParent) {
            throw 'Refusing unsafe fixture cleanup target.'
        }
        Remove-Item -LiteralPath $resolvedFixture -Recurse -Force
    }
}
