[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Status', 'Apply', 'Revert')]
    [string]$Mode = 'Status',
    [string]$ClientRoot = 'C:\Godswar Origin',
    [string]$BackupRoot = 'C:\Reborn\backups',
    [string]$ReceiptPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# External Arena capture, 2026-09-07. Both appearances use stock assets.
$actors = @(
    [pscustomobject]@{
        Key = 'Arena_006'
        Template = 'Arena_006_AirDrop'
        Source = 'Arena_002_Male18'
        Name = 'Airdrop Merchant'
        Description = 'I offer the best airdrop for the community.'
    },
    [pscustomobject]@{
        Key = 'DuelArena_001'
        Template = 'DuelArena_001_Male3'
        Source = 'Athens_025_Male6'
        Name = '[Warehouse] Akou'
        Description = 'After the logistics are developed, I will suggest they form a |cffF14187Federal Trade Bank|cffffffff. Thus,the |cffF14187Atticas Alliance in Athens will become stronger.'
    })
$relativePaths = @(
    'Localization\en_us\Settings\Sys\NPC.INI',
    'Localization\en_us\Text\NpcName.dat',
    'Localization\en_us\Text\NPCDescription.dat')
$clientRootPath = [IO.Path]::GetFullPath($ClientRoot).TrimEnd('\', '/')
$unicode = [Text.UnicodeEncoding]::new($false, $true, $true)

function Get-Sha256([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        ([BitConverter]::ToString($algorithm.ComputeHash($Data))).Replace('-', '')
    }
    finally { $algorithm.Dispose() }
}

function Get-ClientProcessImagePath($Process) {
    if (-not [string]::IsNullOrWhiteSpace($Process.Path)) { return $Process.Path }
    # Querying the image path needs fewer process rights than MainModule;
    # this also works for clients launched with elevated privileges.
    if (-not ('Reborn.DuelArenaProcessPath' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
namespace Reborn {
    public static class DuelArenaProcessPath {
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint access, bool inherit, int id);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool QueryFullProcessImageName(IntPtr process, uint flags, StringBuilder path, ref int length);
        [DllImport("kernel32.dll")]
        private static extern bool CloseHandle(IntPtr handle);
        public static string Read(int id) {
            var process = OpenProcess(0x1000, false, id);
            if (process == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                var path = new StringBuilder(32768);
                var length = path.Capacity;
                if (!QueryFullProcessImageName(process, 0, path, ref length))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                return path.ToString();
            }
            finally { CloseHandle(process); }
        }
    }
}
'@
    }
    [Reborn.DuelArenaProcessPath]::Read($Process.Id)
}

function Assert-ClientClosed {
    $targetPrefix = $clientRootPath + [IO.Path]::DirectorySeparatorChar
    $running = @(foreach ($process in @(Get-Process -Name GWPrivateServer, Origin, GWOriginSV -ErrorAction SilentlyContinue)) {
        try { $imagePath = Get-ClientProcessImagePath $process }
        catch {
            if ($process.HasExited) { continue }
            throw "Could not identify the executable path for client PID $($process.Id): $($_.Exception.Message)"
        }
        if ([IO.Path]::GetFullPath($imagePath).StartsWith($targetPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            $process
        }
    })
    if ($running.Count -ne 0) {
        throw "Close the game client in '$clientRootPath' before patching it (PID: $(($running.Id | Sort-Object) -join ', '))."
    }
}

function Read-Snapshot([string]$RelativePath) {
    $path = Join-Path $clientRootPath $RelativePath
    [byte[]]$data = [IO.File]::ReadAllBytes($path)
    if ($data.Length -lt 2 -or $data[0] -ne 0xFF -or $data[1] -ne 0xFE -or $data.Length % 2 -ne 0) {
        throw "Expected a complete UTF-16LE file with BOM: $path"
    }
    [pscustomobject]@{
        RelativePath = $RelativePath
        Path = $path
        Data = $data
        Text = $unicode.GetString($data, 2, $data.Length - 2)
        BeforeSha256 = Get-Sha256 $data
    }
}

function Get-SectionMatches([string]$Text, [string]$Name) {
    $pattern = '(?ms)^\[' + [regex]::Escape($Name) + '\]\r?\n.*?(?=^\[|\z)'
    @([regex]::Matches($Text, $pattern))
}

function New-Plan($Snapshot) {
    $blocks = [Collections.Generic.List[string]]::new()
    foreach ($actor in $actors) {
        if ($Snapshot.RelativePath -ceq $relativePaths[0]) {
            $source = @(Get-SectionMatches $Snapshot.Text $actor.Source)
            if ($source.Count -ne 1) { throw "Expected one stock template '$($actor.Source)'." }
            $expected = $source[0].Value.TrimEnd("`r", "`n")
            $expected = $expected.Replace('[' + $actor.Source + ']', '[' + $actor.Template + ']')
            $namePattern = '(?m)^name[ \t]*=[^\r\n]*'
            if ([regex]::Matches($expected, $namePattern).Count -ne 1) {
                throw "Expected one name in stock template '$($actor.Source)'."
            }
            $expected = [regex]::Replace($expected, $namePattern, 'name             =' + $actor.Name)
            $found = @(Get-SectionMatches $Snapshot.Text $actor.Template)
        }
        else {
            $value = if ($Snapshot.RelativePath -ceq $relativePaths[1]) { $actor.Name } else { $actor.Description }
            $expected = $actor.Key + "`t" + $value
            $found = @([regex]::Matches($Snapshot.Text, '(?m)^' + [regex]::Escape($actor.Key) + '\t[^\r\n]*'))
        }
        if ($found.Count -gt 1 -or ($found.Count -eq 1 -and $found[0].Value.TrimEnd("`r", "`n") -cne $expected)) {
            throw "Conflicting existing Arena entry '$($actor.Key)' in '$($Snapshot.Path)'; no files changed."
        }
        if ($found.Count -eq 0) { $blocks.Add($expected) }
    }
    $suffix = ''
    if ($blocks.Count -gt 0) {
        if (-not $Snapshot.Text.EndsWith("`n")) { $suffix = "`r`n" }
        $suffix += ($blocks -join "`r`n") + "`r`n"
    }
    [byte[]]$append = $unicode.GetBytes($suffix)
    [byte[]]$after = [byte[]]::new($Snapshot.Data.Length + $append.Length)
    [Array]::Copy($Snapshot.Data, 0, $after, 0, $Snapshot.Data.Length)
    [Array]::Copy($append, 0, $after, $Snapshot.Data.Length, $append.Length)
    $Snapshot | Add-Member -NotePropertyName After -NotePropertyValue $after
    $Snapshot | Add-Member -NotePropertyName AfterSha256 -NotePropertyValue (Get-Sha256 $after)
    $Snapshot | Add-Member -NotePropertyName AddedEntries -NotePropertyValue $blocks.Count
    $Snapshot
}

function Write-Atomic([string]$Path, [byte[]]$Data) {
    $temporary = Join-Path (Split-Path -Parent $Path) ('.duel-arena-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $replacementBackup = $temporary + '.bak'
    try {
        [IO.File]::WriteAllBytes($temporary, $Data)
        [IO.File]::Replace($temporary, $Path, $replacementBackup)
        if ((Get-Sha256 ([IO.File]::ReadAllBytes($Path))) -cne (Get-Sha256 $Data)) {
            throw "Duel Arena patch readback mismatch: $Path"
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
        if (Test-Path -LiteralPath $replacementBackup) { Remove-Item -LiteralPath $replacementBackup -Force }
    }
}

if ($Mode -ceq 'Revert') {
    if ([string]::IsNullOrWhiteSpace($ReceiptPath)) { throw 'Revert requires -ReceiptPath from Apply.' }
    $receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
    if ($receipt.Schema -ne 1 -or $receipt.Patch -cne 'client-duel-arena-npc-aliases' -or $receipt.ClientRoot -cne $clientRootPath) {
        throw 'Receipt does not match this Duel Arena client patch.'
    }
    $restores = @(foreach ($file in $receipt.Files) {
        if ($file.RelativePath -cnotin $relativePaths) { throw 'Unexpected path in Arena patch receipt.' }
        $snapshot = Read-Snapshot $file.RelativePath
        [byte[]]$backup = [IO.File]::ReadAllBytes($file.BackupPath)
        if ($snapshot.BeforeSha256 -cne $file.AfterSha256 -or (Get-Sha256 $backup) -cne $file.BeforeSha256) {
            throw "Current file or backup changed; refusing restore: $($snapshot.Path)"
        }
        [pscustomobject]@{ Path = $snapshot.Path; Backup = $backup }
    })
    Assert-ClientClosed
    if ($PSCmdlet.ShouldProcess($clientRootPath, 'Restore the backed-up Duel Arena NPC catalogs')) {
        foreach ($restore in $restores) { Write-Atomic $restore.Path $restore.Backup }
        [pscustomobject]@{ Mode = $Mode; Changed = $true; State = 'Restored' }
    }
    return
}

$plans = @($relativePaths | ForEach-Object { New-Plan (Read-Snapshot $_) })
$changes = @($plans | Where-Object { $_.AddedEntries -gt 0 })
if ($Mode -ceq 'Status' -or $changes.Count -eq 0) {
    [pscustomobject]@{
        Mode = $Mode
        ClientRoot = $clientRootPath
        State = if ($changes.Count -eq 0) { 'Applied' } else { 'NeedsAliases' }
        Changed = $false
        Files = @($plans | Select-Object RelativePath, AddedEntries, BeforeSha256)
    }
    return
}

Assert-ClientClosed
if (-not $PSCmdlet.ShouldProcess($clientRootPath, 'Append captured Duel Arena NPC aliases and text')) { return }
$backupDirectory = Join-Path ([IO.Path]::GetFullPath($BackupRoot)) (
    'client-duel-arena-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
[void](New-Item -ItemType Directory -Path $backupDirectory)
$files = @(foreach ($plan in $changes) {
    $backupPath = Join-Path $backupDirectory ([IO.Path]::GetFileName($plan.Path))
    [IO.File]::WriteAllBytes($backupPath, $plan.Data)
    [pscustomobject]@{
        RelativePath = $plan.RelativePath
        BackupPath = $backupPath
        BeforeSha256 = $plan.BeforeSha256
        AfterSha256 = $plan.AfterSha256
    }
})
$written = [Collections.Generic.List[object]]::new()
try {
    foreach ($plan in $changes) {
        if ((Get-Sha256 ([IO.File]::ReadAllBytes($plan.Path))) -cne $plan.BeforeSha256) {
            throw "Client catalog changed after inspection: $($plan.Path)"
        }
        $written.Add($plan)
        Write-Atomic $plan.Path $plan.After
    }
}
catch {
    foreach ($plan in $written) { Write-Atomic $plan.Path $plan.Data }
    throw
}
$receiptPath = Join-Path $backupDirectory 'receipt.json'
$receipt = [ordered]@{
    Schema = 1
    Patch = 'client-duel-arena-npc-aliases'
    ClientRoot = $clientRootPath
    Files = $files
}
[IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 4) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
[pscustomobject]@{ Mode = $Mode; Changed = $true; State = 'Applied'; Receipt = $receiptPath }
