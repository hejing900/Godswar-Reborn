[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-DsTest([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw "Donator status patch test failed: $Message"
    }
}

function Get-DsTestSha256([byte[]]$Data) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString(
            $sha.ComputeHash($Data)).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}

function ConvertTo-DsTestUtf16([string]$Text) {
    $encoding = [Text.UnicodeEncoding]::new($false, $false, $true)
    [byte[]]$body = $encoding.GetBytes($Text)
    [byte[]]$data = [byte[]]::new($body.Length + 2)
    $data[0] = 0xFF
    $data[1] = 0xFE
    [Array]::Copy($body, 0, $data, 2, $body.Length)
    return $data
}

function Get-DsTestText([string]$Path) {
    [byte[]]$data = [IO.File]::ReadAllBytes($Path)
    Assert-DsTest (
        $data.Length -ge 2 -and $data[0] -eq 0xFF -and $data[1] -eq 0xFE) `
        'Status.ini lost its UTF-16LE BOM'
    return [Text.UnicodeEncoding]::new($false, $false, $true).GetString(
        $data,
        2,
        $data.Length - 2)
}

$patchPath = Join-Path $PSScriptRoot 'PatchClientDonatorStatusLocalization.ps1'
if (-not (Test-Path -LiteralPath $patchPath -PathType Leaf)) {
    throw "Patch script was not found: $patchPath"
}

$fixture = @'
;
[10]
Name=Fixture
Style=1
Kind=1
Priority=1
Effect=1
Values=1
Interval=0
Time=-1
Note=Fixture
IconPos=0,0
IconSize=36,36
EffectDisplay=-1
RideId=-1
Action=0

[1500]
Name=Bronze VIP EXP Bonus
Style=1
Kind=1008
Priority=1
Effect=15
Values=0.05
Interval=0
Time=-1
Note=Bronze VIP benefit: Increases fighter EXP gained by 5%.
IconPos=72,0
IconSize=36,36
EffectDisplay=-1
RideId=-1
Action=1

[1501]
Name=Silver VIP EXP Bonus
Style=1
Kind=1008
Priority=2
Effect=15
Values=0.1
Interval=0
Time=-1
Note=Silver VIP benefit: Increases fighter EXP gained by 10%.
IconPos=72,0
IconSize=36,36
EffectDisplay=-1
RideId=-1
Action=1

[1502]
Name=Gold VIP EXP Bonus
Style=1
Kind=1008
Priority=3
Effect=15
Values=0.15
Interval=0
Time=-1
Note=Gold VIP benefit: Increases fighter EXP gained by 15%.
IconPos=72,0
IconSize=36,36
EffectDisplay=-1
RideId=-1
Action=1

[1503]
Name=Platinum VIP EXP Bonus
Style=1
Kind=1008
Priority=4
Effect=15
Values=0.2
Interval=0
Time=-1
Note=Platinum VIP benefit: Increases fighter EXP gained by 20%.
IconPos=72,0
IconSize=36,36
EffectDisplay=-1
RideId=-1
Action=1

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
'@.TrimStart([char]13, [char]10).Replace("`r`n", "`n") + "`n"

$testRoot = Join-Path ([IO.Path]::GetTempPath()) (
    'reborn-donator-status-' + [Guid]::NewGuid().ToString('N'))
$clientRoot = Join-Path $testRoot 'client'
$statusDirectory = Join-Path $clientRoot 'Localization\en_us\Settings\Sys'
$backupRoot = Join-Path $testRoot 'backups'
$statusPath = Join-Path $statusDirectory 'Status.ini'

try {
    [void](New-Item -ItemType Directory -Path $statusDirectory -Force)
    [IO.File]::WriteAllBytes(
        (Join-Path $clientRoot 'Origin.exe'),
        [byte[]]@(0x4D, 0x5A))
    [byte[]]$originalData = ConvertTo-DsTestUtf16 $fixture
    [IO.File]::WriteAllBytes($statusPath, $originalData)
    $originalHash = Get-DsTestSha256 $originalData

    $status = & $patchPath -Mode Status -ClientRoot $clientRoot `
        -BackupRoot $backupRoot
    Assert-DsTest ($status.State -ceq 'Original') 'fixture was not Original'
    Assert-DsTest ($status.Sha256 -ceq $originalHash) 'source hash drifted'

    $apply = & $patchPath -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-DsTest ($apply.Changed -and $apply.State -ceq 'AppliedV3') `
        'Apply did not report an AppliedV3 mutation'
    Assert-DsTest (Test-Path -LiteralPath $apply.Receipt -PathType Leaf) `
        'Apply receipt is missing'
    $appliedHash = $apply.Sha256
    [byte[]]$appliedData = [IO.File]::ReadAllBytes($statusPath)
    $appliedText = Get-DsTestText $statusPath
    foreach ($expected in @(
            '[1500]', 'Name=Kijin Patron',
            '[1501]', 'Name=Oni Patron',
            '[1502]', 'Name=Demon Lord Seed',
            '[1503]', 'Name=True Demon Lord',
            '[1506]', 'Name=Octagram Patron',
            '[1507]', 'Name=Premium Battle Pass',
            'Effect=15,32,34', 'Values=0.05,0.05,0.05',
            'Interval=0,0,0',
            'Values=0.25,0.25,0.25',
            'Fighter, Talent, and pet EXP gained in this area')) {
        Assert-DsTest $appliedText.Contains($expected) "missing $expected"
    }
    Assert-DsTest (
        ([regex]::Matches(
            $appliedText,
            '(?m)^Effect=15,32,34\r?$')).Count -eq 2) `
        'faction and Battle Pass do not both advertise all EXP channels'
    Assert-DsTest (-not $appliedText.Contains('[1505]')) `
        'historical Erebus status ID 1505 was reused'
    Assert-DsTest (
        ([regex]::Matches($appliedText, '(?m)^\[1504\]\r?$')).Count -eq 1) `
        'faction status 1504 was duplicated'

    $secondApply = & $patchPath -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-DsTest (-not $secondApply.Changed) 'Apply was not idempotent'
    Assert-DsTest ($secondApply.Sha256 -ceq $appliedHash) `
        'idempotent Apply changed Status.ini'

    $revert = & $patchPath -Mode Revert -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -ReceiptPath $apply.Receipt -Confirm:$false
    Assert-DsTest ($revert.Changed -and $revert.State -ceq 'Original') `
        'Revert did not restore Original'
    Assert-DsTest (
        (Get-DsTestSha256 ([IO.File]::ReadAllBytes($statusPath))) -ceq
        $originalHash) 'Revert was not byte-exact'

    $secondRevert = & $patchPath -Mode Revert -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -ReceiptPath $apply.Receipt -Confirm:$false
    Assert-DsTest (-not $secondRevert.Changed) 'Revert was not idempotent'

    Assert-DsTest ((Get-DsTestText $statusPath) -ceq $fixture) `
        'Original fixture changed before the v1-upgrade scenario'
    $v2Faction = @'
Effect=15
Values=0.25
Interval=0
Time=43200
Note=Your faction controls this area. Fighter EXP gained in this area is increased by 25%.
'@.Replace("`r`n", "`n").TrimEnd([char]10)
    $v3Faction = @'
Effect=15,32,34
Values=0.25,0.25,0.25
Interval=0,0,0
Time=43200
Note=Your faction controls this area. Fighter, Talent, and pet EXP gained in this area are increased by 25%.
'@.Replace("`r`n", "`n").TrimEnd([char]10)
    $v1BattlePass = @'
Effect=15,32,34
Values=0.05,0.05,0.05
Interval=0
'@.Replace("`r`n", "`n").TrimEnd([char]10)
    $v2BattlePass = @'
Effect=15,32,34
Values=0.05,0.05,0.05
Interval=0,0,0
'@.Replace("`r`n", "`n").TrimEnd([char]10)
    $v2Text = $appliedText.Replace($v3Faction, $v2Faction)
    Assert-DsTest ($v2Text -cne $appliedText) `
        'failed to construct the AppliedV2 fixture'
    [byte[]]$v2Data = ConvertTo-DsTestUtf16 $v2Text
    $v2Hash = Get-DsTestSha256 $v2Data
    $v1Text = $v2Text.Replace(
        $v2BattlePass,
        $v1BattlePass)
    [byte[]]$v1Data = ConvertTo-DsTestUtf16 $v1Text
    [IO.File]::WriteAllBytes($statusPath, $v1Data)
    $v1Hash = Get-DsTestSha256 $v1Data
    $v1Status = & $patchPath -Mode Status -ClientRoot $clientRoot `
        -BackupRoot $backupRoot
    Assert-DsTest ($v1Status.State -ceq 'AppliedV1') `
        'legacy applied fixture was not recognized as AppliedV1'

    $upgrade = & $patchPath -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-DsTest ($upgrade.Changed -and $upgrade.State -ceq 'AppliedV3') `
        'AppliedV1 was not upgraded to AppliedV3'
    Assert-DsTest (
        (Get-DsTestText $statusPath).Contains($v3Faction)) `
        'AppliedV1 upgrade did not install the three-channel faction status'
    $upgradeRevert = & $patchPath -Mode Revert -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -ReceiptPath $upgrade.Receipt -Confirm:$false
    Assert-DsTest (
        $upgradeRevert.Changed -and $upgradeRevert.State -ceq 'AppliedV1') `
        'upgrade rollback did not restore AppliedV1'
    Assert-DsTest (
        (Get-DsTestSha256 ([IO.File]::ReadAllBytes($statusPath))) -ceq
        $v1Hash) 'upgrade rollback was not byte-exact'
    $secondUpgradeRevert = & $patchPath -Mode Revert `
        -ClientRoot $clientRoot -BackupRoot $backupRoot `
        -ReceiptPath $upgrade.Receipt -Confirm:$false
    Assert-DsTest (-not $secondUpgradeRevert.Changed) `
        'upgrade rollback was not idempotent'

    [IO.File]::WriteAllBytes($statusPath, $v2Data)
    $v2Status = & $patchPath -Mode Status -ClientRoot $clientRoot `
        -BackupRoot $backupRoot
    Assert-DsTest ($v2Status.State -ceq 'AppliedV2') `
        'previous applied fixture was not recognized as AppliedV2'
    $v2Upgrade = & $patchPath -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-DsTest ($v2Upgrade.Changed -and $v2Upgrade.State -ceq 'AppliedV3') `
        'AppliedV2 was not upgraded to AppliedV3'
    $v2UpgradeRevert = & $patchPath -Mode Revert -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -ReceiptPath $v2Upgrade.Receipt `
        -Confirm:$false
    Assert-DsTest (
        $v2UpgradeRevert.Changed -and
        $v2UpgradeRevert.State -ceq 'AppliedV2') `
        'AppliedV2 upgrade rollback did not restore AppliedV2'
    Assert-DsTest (
        (Get-DsTestSha256 ([IO.File]::ReadAllBytes($statusPath))) -ceq
        $v2Hash) 'AppliedV2 upgrade rollback was not byte-exact'

    [IO.File]::WriteAllBytes($statusPath, $v1Data)

    $legacyReceiptDirectory = Join-Path $backupRoot 'legacy-v1-receipt'
    [void](New-Item -ItemType Directory -Path $legacyReceiptDirectory -Force)
    $legacyBackupPath = Join-Path $legacyReceiptDirectory 'Status.ini'
    $legacyReceiptPath = Join-Path $legacyReceiptDirectory 'receipt.json'
    [IO.File]::WriteAllBytes($legacyBackupPath, $originalData)
    $legacyReceipt = [ordered]@{
        Schema = 1
        Patch = 'reborn.donator-status-localization.v1'
        ClientRoot = [IO.Path]::GetFullPath($clientRoot)
        AppliedUtc = [DateTime]::UtcNow.ToString('O')
        File = [ordered]@{
            RelativePath = 'Localization\en_us\Settings\Sys\Status.ini'
            BackupPath = $legacyBackupPath
            BeforeLength = $originalData.Length
            BeforeSha256 = $originalHash
            AfterLength = $v1Data.Length
            AfterSha256 = $v1Hash
        }
    }
    [IO.File]::WriteAllText(
        $legacyReceiptPath,
        ($legacyReceipt | ConvertTo-Json -Depth 6),
        [Text.UTF8Encoding]::new($false))
    $legacyRevert = & $patchPath -Mode Revert -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -ReceiptPath $legacyReceiptPath `
        -Confirm:$false
    Assert-DsTest (
        $legacyRevert.Changed -and $legacyRevert.State -ceq 'Original') `
        'legacy v1 receipt did not restore Original'
    Assert-DsTest (
        (Get-DsTestSha256 ([IO.File]::ReadAllBytes($statusPath))) -ceq
        $originalHash) 'legacy v1 receipt rollback was not byte-exact'

    $previousReceiptDirectory = Join-Path $backupRoot 'previous-v2-receipt'
    [void](New-Item -ItemType Directory -Path $previousReceiptDirectory -Force)
    $previousBackupPath = Join-Path $previousReceiptDirectory 'Status.ini'
    $previousReceiptPath = Join-Path $previousReceiptDirectory 'receipt.json'
    [IO.File]::WriteAllBytes($previousBackupPath, $originalData)
    $previousReceipt = [ordered]@{
        Schema = 2
        Patch = 'reborn.donator-status-localization.v2'
        ClientRoot = [IO.Path]::GetFullPath($clientRoot)
        AppliedUtc = [DateTime]::UtcNow.ToString('O')
        BeforeState = 'Original'
        AfterState = 'AppliedV2'
        File = [ordered]@{
            RelativePath = 'Localization\en_us\Settings\Sys\Status.ini'
            BackupPath = $previousBackupPath
            BeforeLength = $originalData.Length
            BeforeSha256 = $originalHash
            AfterLength = $v2Data.Length
            AfterSha256 = $v2Hash
        }
    }
    [IO.File]::WriteAllText(
        $previousReceiptPath,
        ($previousReceipt | ConvertTo-Json -Depth 6),
        [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllBytes($statusPath, $v2Data)
    $previousRevert = & $patchPath -Mode Revert -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -ReceiptPath $previousReceiptPath `
        -Confirm:$false
    Assert-DsTest (
        $previousRevert.Changed -and
        $previousRevert.State -ceq 'Original') `
        'previous v2 receipt did not restore Original'
    Assert-DsTest (
        (Get-DsTestSha256 ([IO.File]::ReadAllBytes($statusPath))) -ceq
        $originalHash) 'previous v2 receipt rollback was not byte-exact'

    $injected = $false
    try {
        & $patchPath -Mode Apply -ClientRoot $clientRoot `
            -BackupRoot $backupRoot -Confirm:$false `
            -TestFailAfterAtomicReplace | Out-Null
    }
    catch {
        $injected = $_.Exception.Message -match 'Injected failure'
    }
    Assert-DsTest $injected 'injected Apply failure did not surface'
    Assert-DsTest (
        (Get-DsTestSha256 ([IO.File]::ReadAllBytes($statusPath))) -ceq
        $originalHash) 'failed Apply did not roll back byte-exactly'

    $applyForGuards = & $patchPath -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    $changedText = (Get-DsTestText $statusPath).Replace(
        'Name=Oni Patron',
        'Name=Changed Oni Patron')
    [IO.File]::WriteAllBytes(
        $statusPath,
        (ConvertTo-DsTestUtf16 $changedText))
    $partial = & $patchPath -Mode Status -ClientRoot $clientRoot `
        -BackupRoot $backupRoot
    Assert-DsTest ($partial.State -ceq 'Partial') `
        'changed target section was not Partial'
    $partialRejected = $false
    try {
        & $patchPath -Mode Apply -ClientRoot $clientRoot `
            -BackupRoot $backupRoot -Confirm:$false | Out-Null
    }
    catch {
        $partialRejected = $_.Exception.Message -match 'partial'
    }
    Assert-DsTest $partialRejected 'Apply accepted a partial state'

    [IO.File]::WriteAllBytes($statusPath, $appliedData)
    & $patchPath -Mode Revert -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -ReceiptPath $applyForGuards.Receipt `
        -Confirm:$false | Out-Null
    $legacyMount = $fixture.Replace('[1390]', '[1505]')
    [IO.File]::WriteAllBytes(
        $statusPath,
        (ConvertTo-DsTestUtf16 $legacyMount))
    $legacyStatus = & $patchPath -Mode Status -ClientRoot $clientRoot `
        -BackupRoot $backupRoot
    Assert-DsTest ($legacyStatus.State -ceq 'Partial') `
        'historical status 1505 was not rejected'

    'PASS: guarded Donator/Battle Pass Status.ini apply/revert'
}
finally {
    $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTestRoot.StartsWith(
            $tempRoot,
            [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedTestRoot).StartsWith(
            'reborn-donator-status-',
            [StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force `
            -ErrorAction SilentlyContinue
    }
}
