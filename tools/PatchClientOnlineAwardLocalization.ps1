[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Status', 'Apply', 'Revert')]
    [string]$Mode = 'Status',
    [string]$ClientRoot = 'C:\Godswar Origin',
    [string]$BackupRoot = 'C:\Reborn\backups',
    [string]$ReceiptPath,
    [Parameter(DontShow = $true)]
    [switch]$TestFailAfterFirstAtomicReplace
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$helperPaths = @(
    'client_patch_helpers\OnlineAwardLocalization.Core.ps1',
    'client_patch_helpers\OnlineAwardLocalization.IO.ps1')
foreach ($relativeHelperPath in $helperPaths) {
    $helperPath = Join-Path $PSScriptRoot $relativeHelperPath
    if (-not (Test-Path -LiteralPath $helperPath -PathType Leaf)) {
        throw "Online Award localization helper was not found: $helperPath"
    }
    . $helperPath
}

$patchName = 'client-online-award-localization'
$receiptSchema = 1
$clientRootPath = Get-OaFullPath $ClientRoot

if ([IO.Path]::GetPathRoot($clientRootPath) -ceq $clientRootPath) {
    throw 'ClientRoot must not be a drive root.'
}
if ((Split-Path -Leaf $clientRootPath) -match '(?i)B20H') {
    throw 'The protected B20H client tree is outside this patch scope.'
}
$originPath = Join-Path $clientRootPath 'Origin.exe'
if (-not (Test-Path -LiteralPath $originPath -PathType Leaf)) {
    throw "Origin.exe was not found under ClientRoot: $clientRootPath"
}
$originItem = Get-Item -LiteralPath $originPath -Force
if (($originItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Origin.exe must not be a reparse point: $originPath"
}

function Get-OverallState([object[]]$States) {
    $distinct = @($States.State | Sort-Object -Unique)
    if ($distinct.Count -eq 1) { return $distinct[0] }
    return 'Partial'
}

function New-StatusResult([string]$ResultMode, [object[]]$States) {
    $catalog = Get-OaTextCatalog
    return [pscustomobject]@{
        Mode = $ResultMode
        State = Get-OverallState $States
        ClientRoot = $clientRootPath
        OriginRunning = @(
            Get-Process -Name Origin -ErrorAction SilentlyContinue).Count -ne 0
        Files = @($States | ForEach-Object {
            [pscustomobject]@{
                Role = $_.Role
                Locale = $_.Locale
                RelativePath = $_.RelativePath
                State = $_.State
                BeforeLength = $_.Length
                BeforeSha256 = $_.Sha256
                PlannedLength = $_.PlannedLength
                PlannedSha256 = $_.PlannedSha256
            }
        })
        Copy = [pscustomobject]@{
            EnDescription = $catalog.En.Description
            EnStayReward1 = $catalog.En.StayReward1
            EnStayReward2 = $catalog.En.StayReward2
            EnStayReward3 = $catalog.En.StayReward3
            EnStayReward4 = $catalog.En.StayReward4
            EnStayReward5 = $catalog.En.StayReward5
            EnStayReward6 = $catalog.En.StayReward6
            EnStayReward7 = $catalog.En.StayReward7
            ZhDescription = $catalog.Zh.Description
            ZhStayReward1 = $catalog.Zh.StayReward1
            ZhStayReward2 = $catalog.Zh.StayReward2
            ZhStayReward3 = $catalog.Zh.StayReward3
            ZhStayReward4 = $catalog.Zh.StayReward4
            ZhStayReward5 = $catalog.Zh.StayReward5
            ZhStayReward6 = $catalog.Zh.StayReward6
            ZhStayReward7 = $catalog.Zh.StayReward7
        }
    }
}

function Add-ChangeResult(
    [object]$Result,
    [bool]$Changed,
    [AllowNull()]$Receipt
) {
    $Result | Add-Member -NotePropertyName Changed -NotePropertyValue $Changed
    $Result | Add-Member -NotePropertyName Receipt -NotePropertyValue $Receipt
    return $Result
}

$states = @(Get-OnlineAwardClientStates $clientRootPath)
if ($Mode -ceq 'Status') {
    New-StatusResult 'Status' $states
    return
}

Assert-OaOriginClosed

if ($Mode -ceq 'Apply') {
    $overall = Get-OverallState $states
    if ($overall -ceq 'Partial') {
        throw 'Refusing to apply over a partial Online Award localization state.'
    }
    if ($overall -ceq 'Applied') {
        Add-ChangeResult (New-StatusResult 'Apply' $states) $false $null
        return
    }

    $backupRootPath = Get-OaFullPath $BackupRoot
    if (Test-OaPathWithin $backupRootPath $clientRootPath) {
        throw 'BackupRoot must be outside ClientRoot.'
    }
    if (-not $PSCmdlet.ShouldProcess(
        $clientRootPath,
        'Apply Online Award localization to four client files')) {
        return
    }
    Assert-OaOriginClosed

    if (-not (Test-Path -LiteralPath $backupRootPath -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $backupRootPath)
    }
    $backupRootItem = Get-Item -LiteralPath $backupRootPath -Force
    if (($backupRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "BackupRoot must not be a reparse point: $backupRootPath"
    }
    $backupDirectory = Join-Path $backupRootPath (
        "$patchName-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))-" +
        [Guid]::NewGuid().ToString('N').Substring(0, 8))
    [void](New-Item -ItemType Directory -Path $backupDirectory)

    $originalByPath = @{}
    $plannedByPath = @{}
    $receiptFiles = [Collections.Generic.List[object]]::new()
    foreach ($state in $states) {
        $originalByPath[$state.Path] = $state.Data
        $plannedByPath[$state.Path] = $state.PlannedData
        $backupPath = Join-Path $backupDirectory $state.BackupName
        [IO.File]::WriteAllBytes($backupPath, $state.Data)
        Assert-OaExactFile $backupPath $state.Data
        $receiptFiles.Add([ordered]@{
            Role = $state.Role
            Locale = $state.Locale
            RelativePath = $state.RelativePath
            BackupPath = $backupPath
            BeforeLength = $state.Length
            BeforeSha256 = $state.Sha256
            AfterLength = $state.PlannedLength
            AfterSha256 = $state.PlannedSha256
        })
    }

    $receiptOutputPath = Join-Path $backupDirectory 'receipt.json'
    $receipt = [ordered]@{
        Schema = $receiptSchema
        Patch = $patchName
        ClientRoot = $clientRootPath
        AppliedUtc = [DateTime]::UtcNow.ToString('O')
        Files = $receiptFiles.ToArray()
    }
    $written = [Collections.Generic.List[string]]::new()
    try {
        Assert-OaLiveFilesExact $states $originalByPath
        foreach ($state in $states) {
            Assert-OaOriginClosed
            Assert-OaLiveFilesExact @($state) $originalByPath
            $injectFailure =
                $TestFailAfterFirstAtomicReplace -and $written.Count -eq 0
            $written.Add($state.Path)
            Write-OaAtomicExact `
                $state.Path `
                $plannedByPath[$state.Path] `
                -TestFailAfterReplace:$injectFailure
            Assert-OaExactFile $state.Path $plannedByPath[$state.Path]
        }
        $json = $receipt | ConvertTo-Json -Depth 8
        [IO.File]::WriteAllText(
            $receiptOutputPath,
            $json + [Environment]::NewLine,
            [Text.UTF8Encoding]::new($false))
        if (-not (Test-Path -LiteralPath $receiptOutputPath -PathType Leaf)) {
            throw 'Receipt readback failed.'
        }
    }
    catch {
        $failure = $_
        Restore-OaWrittenFiles $written.ToArray() $originalByPath
        throw $failure
    }

    try {
        $afterStates = @(Get-OnlineAwardClientStates $clientRootPath)
        if (@($afterStates.State | Where-Object { $_ -cne 'Applied' }).Count -ne 0) {
            throw 'Post-apply Online Award localization validation failed.'
        }
    }
    catch {
        $failure = $_
        Restore-OaWrittenFiles $written.ToArray() $originalByPath
        if (Test-Path -LiteralPath $receiptOutputPath) {
            Remove-Item -LiteralPath $receiptOutputPath -Force
        }
        throw $failure
    }
    Add-ChangeResult (
        New-StatusResult 'Apply' $afterStates) $true $receiptOutputPath
    return
}

if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    throw 'Revert requires -ReceiptPath from the matching Apply operation.'
}
$receiptFullPath = Get-OaFullPath $ReceiptPath
if (Test-OaPathWithin $receiptFullPath $clientRootPath) {
    throw 'The rollback receipt must be outside ClientRoot.'
}
if (-not (Test-Path -LiteralPath $receiptFullPath -PathType Leaf)) {
    throw "Receipt was not found: $receiptFullPath"
}
$receiptItem = Get-Item -LiteralPath $receiptFullPath -Force
if (($receiptItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Receipt must not be a reparse point: $receiptFullPath"
}
$receiptDirectory = Split-Path -Parent $receiptFullPath
$receiptData = Get-Content -LiteralPath $receiptFullPath -Raw | ConvertFrom-Json
$specifications = @(Get-OaFileSpecifications)
if ($receiptData.Schema -ne $receiptSchema -or
    $receiptData.Patch -cne $patchName -or
    (Get-OaFullPath ([string]$receiptData.ClientRoot)) -cne $clientRootPath -or
    @($receiptData.Files).Count -ne $specifications.Count) {
    throw 'Receipt does not match this client and patch schema.'
}

$receiptByRelativePath = @{}
foreach ($entry in @($receiptData.Files)) {
    $relative = [string]$entry.RelativePath
    if ($receiptByRelativePath.ContainsKey($relative)) {
        throw "Receipt contains a duplicate file entry: $relative"
    }
    $receiptByRelativePath[$relative] = $entry
}
$currentByPath = @{}
$originalByPath = @{}
$allBefore = $true
$allAfter = $true
foreach ($state in $states) {
    if (-not $receiptByRelativePath.ContainsKey($state.RelativePath)) {
        throw "Receipt omitted $($state.RelativePath)."
    }
    $entry = $receiptByRelativePath[$state.RelativePath]
    if ([string]$entry.Role -cne $state.Role -or
        [string]$entry.Locale -cne $state.Locale) {
        throw "Receipt identity mismatch for $($state.RelativePath)."
    }
    [byte[]]$current = [IO.File]::ReadAllBytes($state.Path)
    $currentByPath[$state.Path] = $current
    $currentHash = Get-OaSha256 $current
    if ($current.Length -ne [int]$entry.BeforeLength -or
        $currentHash -cne [string]$entry.BeforeSha256) { $allBefore = $false }
    if ($current.Length -ne [int]$entry.AfterLength -or
        $currentHash -cne [string]$entry.AfterSha256) { $allAfter = $false }

    $backupPath = Get-OaFullPath ([string]$entry.BackupPath)
    if (-not (Test-OaPathWithin $backupPath $receiptDirectory) -or
        (Test-OaPathWithin $backupPath $clientRootPath) -or
        -not (Test-Path -LiteralPath $backupPath -PathType Leaf)) {
        throw "Receipt backup is unsafe or missing: $backupPath"
    }
    $backupItem = Get-Item -LiteralPath $backupPath -Force
    if (($backupItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Receipt backup must not be a reparse point: $backupPath"
    }
    [byte[]]$original = [IO.File]::ReadAllBytes($backupPath)
    if ($original.Length -ne [int]$entry.BeforeLength -or
        (Get-OaSha256 $original) -cne [string]$entry.BeforeSha256) {
        throw "Receipt backup verification failed: $backupPath"
    }
    $originalByPath[$state.Path] = $original
}

if ($allBefore) {
    Add-ChangeResult (
        New-StatusResult 'Revert' $states) $false $receiptFullPath
    return
}
if (-not $allAfter) {
    throw 'Refusing to revert because installed files do not match the receipt after-state.'
}
if (-not $PSCmdlet.ShouldProcess(
    $clientRootPath,
    'Restore all four Online Award localization backups')) {
    return
}
Assert-OaOriginClosed
$written = [Collections.Generic.List[string]]::new()
try {
    Assert-OaLiveFilesExact $states $currentByPath
    foreach ($state in $states) {
        Assert-OaOriginClosed
        Assert-OaLiveFilesExact @($state) $currentByPath
        $injectFailure =
            $TestFailAfterFirstAtomicReplace -and $written.Count -eq 0
        $written.Add($state.Path)
        Write-OaAtomicExact `
            $state.Path `
            $originalByPath[$state.Path] `
            -TestFailAfterReplace:$injectFailure
        Assert-OaExactFile $state.Path $originalByPath[$state.Path]
    }
}
catch {
    $failure = $_
    Restore-OaWrittenFiles $written.ToArray() $currentByPath
    throw $failure
}
try {
    $revertedStates = @(Get-OnlineAwardClientStates $clientRootPath)
    if (@($revertedStates.State | Where-Object { $_ -cne 'Original' }).Count -ne 0) {
        throw 'Post-revert Online Award localization validation failed.'
    }
}
catch {
    $failure = $_
    Restore-OaWrittenFiles $written.ToArray() $currentByPath
    throw $failure
}
Add-ChangeResult (
    New-StatusResult 'Revert' $revertedStates) $true $receiptFullPath
