[CmdletBinding()]
param(
    [ValidateSet('Status', 'Apply', 'Revert')]
    [string]$Mode = 'Status',
    [string]$ClientExe = 'C:\Godswar Origin\Origin.exe',
    [string]$BackupRoot = (Join-Path $PSScriptRoot '..\backups')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'client_patch_helpers\PetSpecies46.Binary.ps1')

function Assert-BloodfangClientClosed([string]$Path) {
    foreach ($process in @(Get-Process Origin -ErrorAction SilentlyContinue)) {
        try {
            try { $processPath = $process.Path } catch { $processPath = $null }
            if (-not $processPath -or [string]::Equals(
                [IO.Path]::GetFullPath($processPath), $Path,
                [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Close Origin.exe before applying or reverting species-46 support.'
            }
        }
        finally { $process.Dispose() }
    }
}

if (-not (Test-Path -LiteralPath $ClientExe -PathType Leaf)) { throw "Client executable not found: $ClientExe" }
$resolved = [IO.Path]::GetFullPath($ClientExe)
[byte[]]$before = [IO.File]::ReadAllBytes($resolved)
$state = Get-BloodfangPetNativeState $before
if ($Mode -eq 'Status') {
    [pscustomobject]@{
        Mode = $Mode
        Status = $(if ($state.Patched) { 'Patched' } else { 'Ready to apply' })
        MaximumSpecies = $state.MaximumSpecies
        ProgressionPacketLength = 68
        AppearancePacketLength = 72
        GenderPacketLength = 76
        Hash = $state.Hash
    }
    return
}

$wantPatched = $Mode -eq 'Apply'
if ($wantPatched -eq $state.Patched) {
    [pscustomobject]@{
        Mode = $Mode
        Status = $(if ($wantPatched) { 'Already patched' } else { 'Already reverted' })
        MaximumSpecies = $state.MaximumSpecies
        ChangedBytes = 0
        Hash = $state.Hash
    }
    return
}
Assert-BloodfangClientClosed $resolved
[byte[]]$after = New-BloodfangPetNativeBytes $before $wantPatched
$target = Get-BloodfangPetNativeState $after
$backupDirectory = Join-Path ([IO.Path]::GetFullPath($BackupRoot)) (
    'client-pet-species46-' + $Mode.ToLowerInvariant() + '-' +
    (Get-Date -Format 'yyyyMMdd-HHmmssfff') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
[IO.Directory]::CreateDirectory($backupDirectory) | Out-Null
$backup = Join-Path $backupDirectory 'Origin.exe'
[IO.File]::WriteAllBytes($backup, $before)
if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -cne $state.Hash) {
    throw 'Species-46 backup failed exact SHA-256 verification.'
}
$manifest = [ordered]@{
    Patch = 'PetSpecies46'; Mode = $Mode; ClientExe = $resolved
    BeforeSha256 = $state.Hash; AfterSha256 = $target.Hash
    BeforeMaximumSpecies = $state.MaximumSpecies; AfterMaximumSpecies = $target.MaximumSpecies
    ChangedOffsets = @((Get-BloodfangPetNativeDefinition).Changes | ForEach-Object { '0x' + $_.Offset.ToString('X') })
    Backup = $backup; CreatedUtc = [DateTime]::UtcNow.ToString('O')
}
[IO.File]::WriteAllText((Join-Path $backupDirectory 'manifest.json'),
    ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
$stage = "$resolved.$([guid]::NewGuid().ToString('N')).species46-stage"
$replaced = $false
try {
    [IO.File]::WriteAllBytes($stage, $after)
    if ((Get-FileHash -LiteralPath $stage -Algorithm SHA256).Hash -cne $target.Hash) {
        throw 'Staged species-46 executable failed exact hash verification.'
    }
    Assert-BloodfangClientClosed $resolved
    if ((Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash -cne $state.Hash) {
        throw 'Origin.exe changed since preflight; refusing to overwrite it.'
    }
    # PowerShell 5 converts ordinary $null to an empty string for this overload.
    [IO.File]::Replace($stage, $resolved, [NullString]::Value)
    $replaced = $true
    $readback = Get-BloodfangPetNativeState ([IO.File]::ReadAllBytes($resolved))
    if ($readback.Hash -cne $target.Hash) { throw 'Species-46 installed readback differs.' }
}
catch {
    $failure = $_
    if ($replaced) {
        [IO.File]::Copy($backup, $resolved, $true)
        if ((Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash -cne $state.Hash) {
            throw "Species-46 installation and rollback failed: $failure"
        }
        throw "Species-46 installation failed; exact predecessor restored: $failure"
    }
    throw $failure
}
finally {
    if (Test-Path -LiteralPath $stage -PathType Leaf) { Remove-Item -LiteralPath $stage -Force }
}
[pscustomobject]@{
    Mode = $Mode
    Status = $(if ($wantPatched) { 'Patched' } else { 'Reverted' })
    MaximumSpecies = $target.MaximumSpecies
    ChangedBytes = 4
    Backup = $backupDirectory
    Hash = $target.Hash
}
