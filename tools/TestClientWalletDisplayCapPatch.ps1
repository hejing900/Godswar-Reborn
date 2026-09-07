param([string]$FixtureExe = 'C:\Godswar Origin\Origin.exe')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$patcher = Join-Path $PSScriptRoot 'PatchClientWalletDisplayCap.ps1'
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "reborn-wallet-cap-test-$([Guid]::NewGuid().ToString('N'))")
$temporaryRoot = [IO.Path]::GetFullPath($temporaryRoot)
$systemTemporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$patchOffsets = @(0x1765D8, 0x1765F9, 0x176634, 0x17663F, 0x176660, 0x176681)
$unrelatedOffsets = @(0x21C82A, 0x21C831, 0x21CBB5)
[byte[]]$stockLimit = [BitConverter]::GetBytes([int]99999999)
[byte[]]$fullLimit = [BitConverter]::GetBytes([int]::MaxValue)

if (-not $temporaryRoot.StartsWith(
    $systemTemporaryRoot,
    [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Fixture path escaped the system temporary directory.'
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Test-BytesAt(
    [byte[]]$Data,
    [int]$Offset,
    [byte[]]$Expected
) {
    if ($Offset -lt 0 -or $Offset + $Expected.Length -gt $Data.Length) {
        return $false
    }
    for ($index = 0; $index -lt $Expected.Length; $index++) {
        if ($Data[$Offset + $index] -ne $Expected[$index]) {
            return $false
        }
    }
    return $true
}

function Test-BytesEqual([byte[]]$Left, [byte[]]$Right) {
    if ($Left.Length -ne $Right.Length) { return $false }
    for ($index = 0; $index -lt $Left.Length; $index++) {
        if ($Left[$index] -ne $Right[$index]) { return $false }
    }
    return $true
}

function Copy-BytesAt([byte[]]$Source, [byte[]]$Target, [int]$Offset) {
    [Array]::Copy($Source, 0, $Target, $Offset, $Source.Length)
}

try {
    $fixturePath = [IO.Path]::GetFullPath($FixtureExe)
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        throw "Origin fixture was not found: $fixturePath"
    }
    [byte[]]$fixture = [IO.File]::ReadAllBytes($fixturePath)
    Assert-True ($fixture.Length -gt 0x21CBB9) 'Origin fixture is too short.'
    Assert-True ($fixture[0] -eq 0x4D -and $fixture[1] -eq 0x5A) `
        'Origin fixture lacks an MZ header.'
    foreach ($offset in $patchOffsets) {
        Assert-True (
            (Test-BytesAt $fixture $offset $stockLimit) -or
            (Test-BytesAt $fixture $offset $fullLimit)) `
            "Fixture wallet immediate 0x$('{0:X}' -f $offset) is unsupported."
        Copy-BytesAt $stockLimit $fixture $offset
    }
    foreach ($offset in $unrelatedOffsets) {
        Assert-True (Test-BytesAt $fixture $offset $stockLimit) `
            "Fixture unrelated immediate 0x$('{0:X}' -f $offset) changed."
    }

    $client = Join-Path $temporaryRoot 'client'
    $backups = Join-Path $temporaryRoot 'backups'
    [IO.Directory]::CreateDirectory($client) | Out-Null
    $clientExe = Join-Path $client 'Origin.exe'
    [IO.File]::WriteAllBytes($clientExe, $fixture)
    [byte[]]$stockFixture = [byte[]]$fixture.Clone()

    $status = & $patcher -Mode Status -ClientRoot $client -BackupRoot $backups
    Assert-True ($status.State -ceq 'Stock') 'Initial state was not Stock.'
    Assert-True ($status.DisplayMaximum -eq 99999999) `
        'Initial display maximum was wrong.'

    $unsafeBackupRejected = $false
    try {
        & $patcher -Mode Apply -ClientRoot $client -BackupRoot $client `
            -Confirm:$false | Out-Null
    }
    catch {
        $unsafeBackupRejected = $_.Exception.Message -like `
            '*BackupRoot must be outside ClientRoot*'
    }
    Assert-True $unsafeBackupRejected 'Client-root backup placement was accepted.'

    $applied = & $patcher -Mode Apply -ClientRoot $client `
        -BackupRoot $backups -Confirm:$false
    Assert-True ($applied.Changed -and $applied.State -ceq 'Applied') `
        'Apply failed.'
    Assert-True ($applied.DisplayMaximum -eq [int]::MaxValue) `
        'Applied display maximum was wrong.'
    Assert-True (Test-Path -LiteralPath $applied.Backup -PathType Leaf) `
        'External backup is missing.'
    Assert-True (Test-Path -LiteralPath $applied.Receipt -PathType Leaf) `
        'Receipt is missing.'

    [byte[]]$patchedFixture = [IO.File]::ReadAllBytes($clientExe)
    foreach ($offset in $patchOffsets) {
        Assert-True (Test-BytesAt $patchedFixture $offset $fullLimit) `
            "Wallet site 0x$('{0:X}' -f $offset) was not patched."
    }
    foreach ($offset in $unrelatedOffsets) {
        Assert-True (Test-BytesAt $patchedFixture $offset $stockLimit) `
            "Unrelated site 0x$('{0:X}' -f $offset) was mutated."
    }
    for ($offset = 0; $offset -lt $stockFixture.Length; $offset++) {
        if ($stockFixture[$offset] -eq $patchedFixture[$offset]) { continue }
        $allowed = @($patchOffsets | Where-Object {
            $offset -ge $_ -and $offset -lt $_ + 4
        }).Count -ne 0
        Assert-True $allowed `
            "Unexpected fixture mutation at 0x$('{0:X}' -f $offset)."
    }

    $noOp = & $patcher -Mode Apply -ClientRoot $client `
        -BackupRoot $backups -Confirm:$false
    Assert-True (-not $noOp.Changed) 'Second Apply was not idempotent.'

    [byte[]]$partial = [byte[]]$patchedFixture.Clone()
    Copy-BytesAt $stockLimit $partial $patchOffsets[0]
    [IO.File]::WriteAllBytes($clientExe, $partial)
    $partialStatus = & $patcher -Mode Status -ClientRoot $client `
        -BackupRoot $backups
    Assert-True ($partialStatus.State -ceq 'Partial') `
        'Partial patch was not reported.'
    $partialApplyRejected = $false
    try {
        & $patcher -Mode Apply -ClientRoot $client -BackupRoot $backups `
            -Confirm:$false | Out-Null
    }
    catch {
        $partialApplyRejected = $_.Exception.Message -like `
            '*partial wallet-display patch*'
    }
    Assert-True $partialApplyRejected 'Partial patch was accepted.'

    [IO.File]::WriteAllBytes($clientExe, $patchedFixture)
    [byte[]]$foreign = [byte[]]$patchedFixture.Clone()
    Copy-BytesAt ([byte[]](0, 0, 0, 0)) $foreign $patchOffsets[0]
    [IO.File]::WriteAllBytes($clientExe, $foreign)
    $foreignRejected = $false
    try {
        & $patcher -Mode Status -ClientRoot $client -BackupRoot $backups | Out-Null
    }
    catch {
        $foreignRejected = $_.Exception.Message -like `
            '*Unsupported wallet cap bytes*'
    }
    Assert-True $foreignRejected 'Foreign wallet bytes were accepted.'

    [IO.File]::WriteAllBytes($clientExe, $patchedFixture)
    $reverted = & $patcher -Mode Revert -ClientRoot $client `
        -BackupRoot $backups -ReceiptPath $applied.Receipt -Confirm:$false
    Assert-True ($reverted.Changed -and $reverted.State -ceq 'Stock') `
        'Revert failed.'
    Assert-True (Test-BytesEqual ([IO.File]::ReadAllBytes($clientExe)) $stockFixture) `
        'Revert did not restore the fixture byte-for-byte.'
    $revertNoOp = & $patcher -Mode Revert -ClientRoot $client `
        -BackupRoot $backups -ReceiptPath $applied.Receipt -Confirm:$false
    Assert-True (-not $revertNoOp.Changed) 'Second Revert was not idempotent.'

    [pscustomobject]@{
        Result = 'Pass'
        SixWalletSitesPatched = $true
        ThreeUnrelatedSitesPreserved = $true
        ByteExactRevert = $true
        PartialAndForeignStatesRejected = $true
        ExternalBackupAndReceiptVerified = $true
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
