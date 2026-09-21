[CmdletBinding()]
param(
    [string]$FixtureExe = 'C:\Godswar Origin\Origin.exe',
    [string]$ReportPath = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'client_patch_helpers\PetSpecies46.Binary.ps1')
$patcher = Join-Path $PSScriptRoot 'PatchClientPetSpecies46.ps1'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$artifactRoot = [IO.Path]::GetFullPath((Join-Path $repo 'artifacts'))
$testRoot = Join-Path $artifactRoot ('pet-species46-test-' + [guid]::NewGuid().ToString('N'))
$client = Join-Path $testRoot 'Origin.exe'
$backups = Join-Path $testRoot 'backups'
$script:checks = 0

function Assert-True([bool]$Condition, [string]$Label) {
    if (-not $Condition) { throw "Assertion failed: $Label" }
    $script:checks++
}

function Assert-Rejected([scriptblock]$Action, [string]$Label) {
    $rejected = $false
    try { $null = & $Action } catch { $rejected = $true }
    Assert-True $rejected $Label
}

function Test-TailAccepted(
    [byte[]]$Image, [int]$Length, [int]$Species, [int]$Bound,
    [int]$Sex = 0, [int]$ReservedAppearance = 0, [int]$ReservedGender = 0
) {
    if ($Length -eq 68) { return $true }
    if ($Length -notin @(72, 76)) { return $false }
    $packedOffset = if ($Length -eq 72) { 0x5C38B6 } else { 0x5C343F }
    $speciesOffset = if ($Length -eq 72) { 0x5C38C1 } else { 0x5C344A }
    $maximumPacked = [BitConverter]::ToUInt32($Image, $packedOffset)
    $maximumSpecies = $Image[$speciesOffset]
    [uint32]$packed = [uint32]$Species -bor ([uint32]$Bound -shl 8) -bor
        ([uint32]$ReservedAppearance -shl 16)
    [uint32]$gender = [uint32]$Sex -bor ([uint32]$ReservedGender -shl 8)
    return $packed -le $maximumPacked -and $Species -ne 0 -and
        $Species -le $maximumSpecies -and ($Length -eq 72 -or $gender -le 1)
}

try {
    $fixtureHash = (Get-FileHash -LiteralPath $FixtureExe -Algorithm SHA256).Hash
    [IO.Directory]::CreateDirectory($testRoot) | Out-Null
    Copy-Item -LiteralPath $FixtureExe -Destination $client
    $status = & $patcher -ClientExe $client -Mode Status
    if ($status.Status -eq 'Patched') {
        $null = & $patcher -ClientExe $client -Mode Revert -BackupRoot $backups
    }
    [byte[]]$source = [IO.File]::ReadAllBytes($client)
    $definition = Get-BloodfangPetNativeDefinition
    $ready = & $patcher -ClientExe $client -Mode Status
    Assert-True ($ready.Status -eq 'Ready to apply' -and $ready.MaximumSpecies -eq 45) 'source status'
    Assert-True ($ready.Hash -ceq $definition.SourceHash) 'pinned predecessor hash'
    Assert-True ($ready.ProgressionPacketLength -eq 68 -and
        $ready.AppearancePacketLength -eq 72 -and $ready.GenderPacketLength -eq 76) 'packet lengths retained'
    $applied = & $patcher -ClientExe $client -Mode Apply -BackupRoot $backups
    Assert-True ($applied.Status -eq 'Patched' -and $applied.MaximumSpecies -eq 46) 'apply status'
    Assert-True ($applied.Hash -ceq $definition.PatchedHash -and $applied.ChangedBytes -eq 4) 'exact target and mutation count'
    [byte[]]$patched = [IO.File]::ReadAllBytes($client)
    Assert-True ($patched.Length -eq $source.Length) 'image length unchanged'
    [byte[]]$restored = $patched.Clone()
    foreach ($change in $definition.Changes) {
        Assert-True ($source[$change.Offset] -eq 45 -and $patched[$change.Offset] -eq 46) $change.Label
        $restored[$change.Offset] = 45
    }
    Assert-True ([Linq.Enumerable]::SequenceEqual($source, $restored)) 'only four allowed bytes changed'
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $applied.Backup 'Origin.exe') -Algorithm SHA256).Hash -ceq
        $definition.SourceHash) 'verified predecessor backup'
    $manifest = Get-Content -LiteralPath (Join-Path $applied.Backup 'manifest.json') -Raw | ConvertFrom-Json
    Assert-True ($manifest.BeforeSha256 -ceq $definition.SourceHash -and
        $manifest.AfterSha256 -ceq $definition.PatchedHash -and $manifest.ChangedOffsets.Count -eq 4) 'backup manifest evidence'
    foreach ($length in @(72, 76)) {
        foreach ($species in 1..46) {
            foreach ($bound in 0..1) {
                foreach ($sex in 0..1) {
                    Assert-True (Test-TailAccepted $patched $length $species $bound $sex) `
                        "valid length $length species $species bound $bound sex $sex"
                }
            }
        }
        foreach ($bound in 0..1) {
            Assert-True (-not (Test-TailAccepted $source $length 46 $bound)) `
                "predecessor rejects Bloodfang at length $length bound $bound"
        }
        foreach ($invalid in @(@(0, 0, 0, 0, 0), @(47, 0, 0, 0, 0),
                @(255, 1, 0, 0, 0), @(46, 2, 0, 0, 0), @(46, 1, 0, 1, 0),
                @(46, 1, 0, 65535, 0))) {
            Assert-True (-not (Test-TailAccepted $patched $length @invalid)) `
                "invalid appearance tail length $length values $($invalid -join '/')"
        }
    }
    foreach ($invalid in @(@(46, 1, 2, 0, 0), @(46, 1, 255, 0, 0),
            @(46, 1, 0, 0, 1), @(46, 1, 0, 0, 65535))) {
        Assert-True (-not (Test-TailAccepted $patched 76 @invalid)) 'invalid sex/reserved gender tail'
    }
    foreach ($length in @(0, 67, 69, 71, 73, 75, 77, 255, 324)) {
        Assert-True (-not (Test-TailAccepted $patched $length 46 1 1)) "malformed packet length $length"
    }
    Assert-True (Test-TailAccepted $patched 68 0 0) '68-byte progression still skips appearance fields'
    $again = & $patcher -ClientExe $client -Mode Apply -BackupRoot $backups
    Assert-True ($again.Status -eq 'Already patched' -and $again.ChangedBytes -eq 0) 'idempotent apply'
    foreach ($mask in 1..14) {
        [byte[]]$partial = $source.Clone()
        for ($index = 0; $index -lt 4; $index++) {
            if (($mask -band (1 -shl $index)) -ne 0) { $partial[$definition.Changes[$index].Offset] = 46 }
        }
        Assert-Rejected { Get-BloodfangPetNativeState $partial } "partial native state $mask rejected"
    }
    [byte[]]$foreign = $source.Clone()
    $foreign[0x1000] = $foreign[0x1000] -bxor 1
    [IO.File]::WriteAllBytes($client, $foreign)
    $foreignHash = Get-BloodfangBytesHash $foreign
    Assert-Rejected { & $patcher -ClientExe $client -Mode Apply -BackupRoot $backups } 'foreign composite rejected'
    Assert-True ((Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash -ceq $foreignHash) 'rejected input remains untouched'
    [byte[]]$badPe = $source.Clone()
    $badPe[0] = 0
    Assert-Rejected { Get-BloodfangPetNativeState $badPe } 'malformed PE rejected'
    Assert-Rejected { Get-BloodfangPetNativeState ([byte[]]::new(100)) } 'wrong executable length rejected'
    [IO.File]::WriteAllBytes($client, $patched)
    $reverted = & $patcher -ClientExe $client -Mode Revert -BackupRoot $backups
    Assert-True ($reverted.Status -eq 'Reverted' -and $reverted.Hash -ceq $definition.SourceHash) 'exact revert hash'
    Assert-True ([Linq.Enumerable]::SequenceEqual($source, [IO.File]::ReadAllBytes($client))) 'byte-exact predecessor restored'
    $again = & $patcher -ClientExe $client -Mode Revert -BackupRoot $backups
    Assert-True ($again.Status -eq 'Already reverted') 'idempotent revert'
    Assert-True ((Get-FileHash -LiteralPath $FixtureExe -Algorithm SHA256).Hash -ceq $fixtureHash) 'installed fixture remained unchanged'
    $result = [ordered]@{
        Status = 'Passed'; Assertions = $script:checks
        SourceHash = $definition.SourceHash; PatchedHash = $definition.PatchedHash
        ChangedBytes = 4; ClientExeWritten = $false
    }
    if ($ReportPath) {
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($ReportPath),
            ($result | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    }
    [pscustomobject]$result
}
finally {
    if (Test-Path -LiteralPath $testRoot -PathType Container) {
        $resolvedTest = [IO.Path]::GetFullPath($testRoot)
        $expectedPrefix = $artifactRoot.TrimEnd('\') + '\pet-species46-test-'
        if (-not $resolvedTest.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to remove a test directory outside its intended artifact workspace.'
        }
        Remove-Item -LiteralPath $resolvedTest -Recurse -Force
    }
}
