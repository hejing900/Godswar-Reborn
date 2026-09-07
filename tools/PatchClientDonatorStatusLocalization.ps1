[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Status', 'Apply', 'Revert')]
    [string]$Mode = 'Status',
    [string]$ClientRoot = 'C:\Godswar Origin',
    [string]$BackupRoot = 'C:\Reborn\backups',
    [string]$ReceiptPath,
    [Parameter(DontShow = $true)]
    [switch]$TestFailAfterAtomicReplace
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$legacyPatchId = 'reborn.donator-status-localization.v1'
$previousPatchId = 'reborn.donator-status-localization.v2'
$patchId = 'reborn.donator-status-localization.v3'
$relativeStatusPath = 'Localization\en_us\Settings\Sys\Status.ini'
$strictUtf16 = [Text.UnicodeEncoding]::new($false, $false, $true)
$commonModulePath = Join-Path $PSScriptRoot `
    'ClientDonatorStatusLocalization.Common.psm1'
if (-not (Test-Path -LiteralPath $commonModulePath -PathType Leaf)) {
    throw "Donator status helper module was not found: $commonModulePath"
}
Import-Module -Name $commonModulePath -Force -ErrorAction Stop

function Assert-DsOriginClosed {
    if (@(Get-Process -Name Origin -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'Close Origin.exe before changing Donator status localization.'
    }
}

function Get-DsState([string]$Text) {
    $sections = Get-DsSections $Text
    $commonFoundation =
        -not $sections.ContainsKey(1505) -and
        $sections.ContainsKey(1504) -and
        $sections.ContainsKey(1390) -and
        $sections[1390].Normalized -ceq $script:mountSection
    $legacyFoundation = $commonFoundation -and
        $sections[1504].Normalized -ceq $script:legacyFactionSection
    $currentFoundation = $commonFoundation -and
        $sections[1504].Normalized -ceq $script:factionSection
    if ($legacyFoundation -and
         (Test-DsSectionSet $sections $script:originalSections @(1506, 1507))) {
        return [pscustomobject]@{ Name = 'Original'; Sections = $sections }
    }
    if ($legacyFoundation -and
        (Test-DsSectionSet $sections $script:appliedV1Sections @())) {
        return [pscustomobject]@{ Name = 'AppliedV1'; Sections = $sections }
    }
    if ($legacyFoundation -and
        (Test-DsSectionSet $sections $script:appliedSections @())) {
        return [pscustomobject]@{ Name = 'AppliedV2'; Sections = $sections }
    }
    if ($currentFoundation -and
        (Test-DsSectionSet $sections $script:appliedSections @())) {
        return [pscustomobject]@{ Name = 'AppliedV3'; Sections = $sections }
    }
    return [pscustomobject]@{ Name = 'Partial'; Sections = $sections }
}

function New-DsAppliedText([string]$Text) {
    $state = Get-DsState $Text
    if ($state.Name -notin @('Original', 'AppliedV1', 'AppliedV2')) {
        throw 'Only an exact original, Applied-v1, or Applied-v2 Donator status state can be planned.'
    }
    $planned = $Text
    $replacementIds = if ($state.Name -ceq 'Original') {
        @(1500, 1501, 1502, 1503, 1504)
    }
    elseif ($state.Name -ceq 'AppliedV1') {
        @(1504, 1507)
    }
    else {
        @(1504)
    }
    $replacements = @($replacementIds | ForEach-Object {
            $section = $state.Sections[$_]
            [pscustomobject]@{
                Id = $_
                Start = $section.Start
                Length = $section.Length
            }
        } | Sort-Object Start -Descending)
    foreach ($replacement in $replacements) {
        $value = if ($replacement.Id -eq 1504) {
            $script:factionSection + "`n`n"
        }
        else {
            $script:appliedSections[$replacement.Id] + "`n`n"
        }
        $planned = $planned.Remove(
            $replacement.Start,
            $replacement.Length).Insert(
                $replacement.Start,
                $value)
    }
    if ($state.Name -ceq 'Original') {
        $plannedSections = Get-DsSections $planned
        $insertAt = $plannedSections[1390].Start
        $addition =
            $script:appliedSections[1506] + "`n`n" +
            $script:appliedSections[1507] + "`n`n"
        $planned = $planned.Insert($insertAt, $addition)
    }
    if ((Get-DsState $planned).Name -cne 'AppliedV3') {
        throw 'Internal Donator status planning validation failed.'
    }
    return $planned
}

function Get-DsSnapshot([string]$Path) {
    Assert-DsOrdinaryFile $Path 'English Status.ini'
    [byte[]]$data = [IO.File]::ReadAllBytes($Path)
    if ($data.Length -lt 4 -or ($data.Length % 2) -ne 0 -or
        $data[0] -ne 0xFF -or $data[1] -ne 0xFE) {
        throw 'English Status.ini must be BOM-marked UTF-16LE.'
    }
    try {
        $text = $strictUtf16.GetString($data, 2, $data.Length - 2)
    }
    catch {
        throw "English Status.ini is not strict UTF-16LE: $($_.Exception.Message)"
    }
    $status = Get-DsState $text
    [byte[]]$planned = if (
        $status.Name -in @('Original', 'AppliedV1', 'AppliedV2')) {
        ConvertTo-DsUtf16Bytes (New-DsAppliedText $text)
    }
    else {
        $data
    }
    return [pscustomobject]@{
        Path = $Path
        Data = $data
        Text = $text
        State = $status.Name
        Length = $data.Length
        Sha256 = Get-DsSha256 $data
        PlannedData = $planned
        PlannedLength = $planned.Length
        PlannedSha256 = Get-DsSha256 $planned
    }
}

function Write-DsReceipt([string]$Path, [object]$Receipt) {
    $json = $Receipt | ConvertTo-Json -Depth 6
    [byte[]]$data = [Text.UTF8Encoding]::new($false).GetBytes(
        $json + [Environment]::NewLine)
    Write-DsAtomicBytes $Path $data
}

function New-DsResult([string]$ResultMode, [object]$Snapshot) {
    return [pscustomobject]@{
        Mode = $ResultMode
        State = $Snapshot.State
        ClientRoot = $script:clientRootPath
        RelativePath = $relativeStatusPath
        StatusPath = $Snapshot.Path
        OriginRunning =
            @(Get-Process -Name Origin -ErrorAction SilentlyContinue).Count -ne 0
        Length = $Snapshot.Length
        Sha256 = $Snapshot.Sha256
        PlannedLength = $Snapshot.PlannedLength
        PlannedSha256 = $Snapshot.PlannedSha256
        DonatorStatusIds = @(1500, 1501, 1502, 1503, 1506)
        BattlePassStatusId = 1507
    }
}

function Add-DsChangeResult(
    [object]$Result,
    [bool]$Changed,
    [AllowNull()][string]$Receipt
) {
    $Result | Add-Member Changed $Changed
    $Result | Add-Member Receipt $Receipt
    return $Result
}

$originalSections = @{}
$originalSections[1500] = New-DsStatusSection 1500 `
    'Bronze VIP EXP Bonus' 1008 1 '15' '0.05' `
    'Bronze VIP benefit: Increases fighter EXP gained by 5%.' '72,0'
$originalSections[1501] = New-DsStatusSection 1501 `
    'Silver VIP EXP Bonus' 1008 2 '15' '0.1' `
    'Silver VIP benefit: Increases fighter EXP gained by 10%.' '72,0'
$originalSections[1502] = New-DsStatusSection 1502 `
    'Gold VIP EXP Bonus' 1008 3 '15' '0.15' `
    'Gold VIP benefit: Increases fighter EXP gained by 15%.' '72,0'
$originalSections[1503] = New-DsStatusSection 1503 `
    'Platinum VIP EXP Bonus' 1008 4 '15' '0.2' `
    'Platinum VIP benefit: Increases fighter EXP gained by 20%.' '72,0'

$appliedSections = @{}
$appliedSections[1500] = New-DsStatusSection 1500 `
    'Kijin Patron' 1008 1 '15' '0.05' `
    'Kijin Patron benefit: Fighter EXP +5%, maximum HP +2%, and physical and magical attack +1%.' '72,0'
$appliedSections[1501] = New-DsStatusSection 1501 `
    'Oni Patron' 1008 2 '15' '0.1' `
    'Oni Patron benefit: Fighter EXP +10%, maximum HP +4%, and physical and magical attack +2%.' '72,0'
$appliedSections[1502] = New-DsStatusSection 1502 `
    'Demon Lord Seed' 1008 3 '15' '0.15' `
    'Demon Lord Seed benefit: Fighter EXP +15%, maximum HP +6%, and physical and magical attack +3%.' '72,0'
$appliedSections[1503] = New-DsStatusSection 1503 `
    'True Demon Lord' 1008 4 '15' '0.2' `
    'True Demon Lord benefit: Fighter EXP +20%, maximum HP +8%, and physical and magical attack +4%.' '72,0'
$appliedSections[1506] = New-DsStatusSection 1506 `
    'Octagram Patron' 1008 5 '15' '0.25' `
    'Octagram Patron benefit: Fighter EXP +25%, maximum HP +10%, and physical and magical attack +5%.' '72,0'
$appliedSections[1507] = New-DsStatusSection 1507 `
    'Premium Battle Pass' 1010 1 '15,32,34' '0.05,0.05,0.05' `
    'Premium Battle Pass benefit: Fighter, Talent, and pet EXP gained +5%.' '648,324'

$appliedV1Sections = @{}
foreach ($entry in $appliedSections.GetEnumerator()) {
    $appliedV1Sections[[int]$entry.Key] = [string]$entry.Value
}
$appliedV1Sections[1507] = $appliedV1Sections[1507].Replace(
    'Interval=0,0,0',
    'Interval=0')

$legacyFactionSection = @'
[1504]
Name=Faction Area EXP Bonus
Style=1
Kind=1009
Priority=1
Effect=15
Values=0.25
Interval=0
Time=43200
Note=Your faction controls this area. Fighter EXP gained in this area is increased by 25%.
IconPos=648,324
IconSize=36,36
EffectDisplay=-1
RideId=-1
Action=1
'@.TrimEnd([char]13, [char]10).Replace("`r`n", "`n")

$factionSection = @'
[1504]
Name=Faction Area EXP Bonus
Style=1
Kind=1009
Priority=1
Effect=15,32,34
Values=0.25,0.25,0.25
Interval=0,0,0
Time=43200
Note=Your faction controls this area. Fighter, Talent, and pet EXP gained in this area are increased by 25%.
IconPos=648,324
IconSize=36,36
EffectDisplay=-1
RideId=-1
Action=1
'@.TrimEnd([char]13, [char]10).Replace("`r`n", "`n")

$mountSection = @'
[1390]
Name=Travelling by Erebus Lion
Style=1
Kind=110
Priority=1
Effect=33
Values=1
Interval=0
Time=-1
Note=You are riding an Erebus Lion.
IconPos=360,0
IconSize=36,36
EffectDisplay=-1
RideId=117
Action=0
'@.TrimEnd([char]13, [char]10).Replace("`r`n", "`n")

$script:originalSections = $originalSections
$script:appliedSections = $appliedSections
$script:legacyFactionSection = $legacyFactionSection
$script:factionSection = $factionSection
$script:mountSection = $mountSection

$clientRootPath = Get-DsFullPath $ClientRoot
$script:clientRootPath = $clientRootPath
if ([IO.Path]::GetPathRoot($clientRootPath) -ceq $clientRootPath) {
    throw 'ClientRoot must not be a drive root.'
}
if ((Split-Path -Leaf $clientRootPath) -match '(?i)B20H') {
    throw 'The protected B20H client tree is outside this patch scope.'
}
if (-not (Test-Path -LiteralPath $clientRootPath -PathType Container)) {
    throw "ClientRoot was not found: $clientRootPath"
}
$clientRootItem = Get-Item -LiteralPath $clientRootPath -Force
if (($clientRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'ClientRoot must not be a reparse point.'
}
$originPath = Join-Path $clientRootPath 'Origin.exe'
Assert-DsOrdinaryFile $originPath 'Origin.exe'
$statusPath = Join-Path $clientRootPath $relativeStatusPath
$snapshot = Get-DsSnapshot $statusPath

if ($Mode -ceq 'Status') {
    New-DsResult 'Status' $snapshot
    return
}

if ($Mode -ceq 'Apply') {
    if ($snapshot.State -ceq 'Partial') {
        throw 'Refusing to apply over an unsupported or partial Donator status state.'
    }
    if ($snapshot.State -ceq 'AppliedV3') {
        Add-DsChangeResult (New-DsResult 'Apply' $snapshot) $false $null
        return
    }
    Assert-DsOriginClosed
    $backupRootPath = Get-DsFullPath $BackupRoot
    if (Test-DsPathWithin $backupRootPath $clientRootPath) {
        throw 'BackupRoot must be outside ClientRoot.'
    }
    if (-not $PSCmdlet.ShouldProcess(
            $statusPath,
            'Apply Donator and Battle Pass status localization')) {
        return
    }
    Assert-DsOriginClosed
    if (-not (Test-Path -LiteralPath $backupRootPath -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $backupRootPath)
    }
    $backupRootItem = Get-Item -LiteralPath $backupRootPath -Force
    if (($backupRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'BackupRoot must not be a reparse point.'
    }
    $backupDirectory = Join-Path $backupRootPath (
        'client-donator-status-' +
        [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' +
        [Guid]::NewGuid().ToString('N').Substring(0, 8))
    [void](New-Item -ItemType Directory -Path $backupDirectory)
    $backupPath = Join-Path $backupDirectory 'Status.ini'
    [IO.File]::WriteAllBytes($backupPath, $snapshot.Data)
    if ((Get-DsSha256 ([IO.File]::ReadAllBytes($backupPath))) -cne
        $snapshot.Sha256) {
        throw 'Donator localization backup verification failed.'
    }
    $receiptOutputPath = Join-Path $backupDirectory 'receipt.json'
    $receipt = [ordered]@{
        Schema = 3
        Patch = $patchId
        ClientRoot = $clientRootPath
        AppliedUtc = [DateTime]::UtcNow.ToString('O')
        BeforeState = $snapshot.State
        AfterState = 'AppliedV3'
        File = [ordered]@{
            RelativePath = $relativeStatusPath
            BackupPath = $backupPath
            BeforeLength = $snapshot.Length
            BeforeSha256 = $snapshot.Sha256
            AfterLength = $snapshot.PlannedLength
            AfterSha256 = $snapshot.PlannedSha256
        }
    }
    try {
        $liveHash = Get-DsSha256 ([IO.File]::ReadAllBytes($statusPath))
        if ($liveHash -cne $snapshot.Sha256) {
            throw 'English Status.ini changed after preflight.'
        }
        Assert-DsOriginClosed
        Write-DsAtomicBytes $statusPath $snapshot.PlannedData
        if ($TestFailAfterAtomicReplace) {
            throw 'Injected failure after Donator localization replacement.'
        }
        $after = Get-DsSnapshot $statusPath
        if ($after.State -cne 'AppliedV3' -or
            $after.Sha256 -cne $snapshot.PlannedSha256) {
            throw 'Post-apply Donator localization validation failed.'
        }
        Write-DsReceipt $receiptOutputPath $receipt
    }
    catch {
        $failure = $_
        Write-DsAtomicBytes $statusPath $snapshot.Data
        if ((Get-DsSha256 ([IO.File]::ReadAllBytes($statusPath))) -cne
            $snapshot.Sha256) {
            throw "Donator localization and rollback failed: $failure"
        }
        if (Test-Path -LiteralPath $receiptOutputPath) {
            Remove-Item -LiteralPath $receiptOutputPath -Force
        }
        throw $failure
    }
    Add-DsChangeResult (New-DsResult 'Apply' $after) $true $receiptOutputPath
    return
}

if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    throw 'Revert requires -ReceiptPath from the matching Apply operation.'
}
$receiptFullPath = Get-DsFullPath $ReceiptPath
if (Test-DsPathWithin $receiptFullPath $clientRootPath) {
    throw 'The rollback receipt must be outside ClientRoot.'
}
Assert-DsOrdinaryFile $receiptFullPath 'Rollback receipt'
try {
    $receiptData = Get-Content -LiteralPath $receiptFullPath -Raw |
        ConvertFrom-Json
}
catch {
    throw "Rollback receipt is invalid JSON: $($_.Exception.Message)"
}
$receiptPatch = [string]$receiptData.Patch
$isLegacyReceipt = $receiptData.Schema -eq 1 -and
    $receiptPatch -ceq $legacyPatchId
$isPreviousReceipt = $receiptData.Schema -eq 2 -and
    $receiptPatch -ceq $previousPatchId
$isCurrentReceipt = $receiptData.Schema -eq 3 -and
    $receiptPatch -ceq $patchId
if ((-not $isLegacyReceipt -and -not $isPreviousReceipt -and
        -not $isCurrentReceipt) -or
    (Get-DsFullPath ([string]$receiptData.ClientRoot)) -cne $clientRootPath -or
    [string]$receiptData.File.RelativePath -cne $relativeStatusPath) {
    throw 'Rollback receipt does not match this patch and client.'
}
$expectedBeforeState = if ($isLegacyReceipt) {
    'Original'
}
else {
    [string]$receiptData.BeforeState
}
$expectedAfterState = if ($isLegacyReceipt) {
    'AppliedV1'
}
else {
    [string]$receiptData.AfterState
}
$validTransition =
    ($isLegacyReceipt -and
        $expectedBeforeState -ceq 'Original' -and
        $expectedAfterState -ceq 'AppliedV1') -or
    ($isPreviousReceipt -and
        $expectedBeforeState -in @('Original', 'AppliedV1') -and
        $expectedAfterState -ceq 'AppliedV2') -or
    ($isCurrentReceipt -and
        $expectedBeforeState -in @('Original', 'AppliedV1', 'AppliedV2') -and
        $expectedAfterState -ceq 'AppliedV3')
if (-not $validTransition) {
    throw 'Rollback receipt contains an unsupported Donator patch transition.'
}
$receiptDirectory = Split-Path -Parent $receiptFullPath
$backupPath = Get-DsFullPath ([string]$receiptData.File.BackupPath)
if (-not (Test-DsPathWithin $backupPath $receiptDirectory) -or
    (Test-DsPathWithin $backupPath $clientRootPath)) {
    throw 'Rollback backup path is outside the receipt directory.'
}
Assert-DsOrdinaryFile $backupPath 'Rollback Status.ini backup'
[byte[]]$originalData = [IO.File]::ReadAllBytes($backupPath)
$beforeHash = [string]$receiptData.File.BeforeSha256
$afterHash = [string]$receiptData.File.AfterSha256
if ($originalData.Length -ne [int]$receiptData.File.BeforeLength -or
    (Get-DsSha256 $originalData) -cne $beforeHash) {
    throw 'Rollback Status.ini backup failed receipt verification.'
}
if ($snapshot.Sha256 -ceq $beforeHash -and
    $snapshot.Length -eq [int]$receiptData.File.BeforeLength) {
    Add-DsChangeResult (New-DsResult 'Revert' $snapshot) $false $receiptFullPath
    return
}
if ($snapshot.Sha256 -cne $afterHash -or
    $snapshot.Length -ne [int]$receiptData.File.AfterLength -or
    $snapshot.State -cne $expectedAfterState) {
    throw 'Refusing to revert a changed, partial, or unrelated Status.ini.'
}
Assert-DsOriginClosed
if (-not $PSCmdlet.ShouldProcess(
        $statusPath,
        'Restore the receipt-pinned English Status.ini')) {
    return
}
Assert-DsOriginClosed
try {
    Write-DsAtomicBytes $statusPath $originalData
    if ($TestFailAfterAtomicReplace) {
        throw 'Injected failure after Donator localization revert.'
    }
    $reverted = Get-DsSnapshot $statusPath
    if ($reverted.Sha256 -cne $beforeHash -or
        $reverted.State -cne $expectedBeforeState) {
        throw 'Post-revert Donator localization validation failed.'
    }
}
catch {
    $failure = $_
    Write-DsAtomicBytes $statusPath $snapshot.Data
    if ((Get-DsSha256 ([IO.File]::ReadAllBytes($statusPath))) -cne
        $afterHash) {
        throw "Donator localization revert and rollback failed: $failure"
    }
    throw $failure
}
Add-DsChangeResult (New-DsResult 'Revert' $reverted) $true $receiptFullPath
