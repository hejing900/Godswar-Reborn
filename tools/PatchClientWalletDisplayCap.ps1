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

$patchName = 'client-wallet-display-int32'
$receiptSchema = 1
$originRelativePath = 'Origin.exe'
[byte[]]$stockLimit = [BitConverter]::GetBytes([int]99999999)
[byte[]]$fullLimit = [BitConverter]::GetBytes([int]::MaxValue)
$patchSites = @(
    [pscustomobject]@{
        Label = 'SilverCompare'; Offset = 0x1765D8
        Prefix = '8B81CC0200003D'; Suffix = '6A0A8D4C2450517D'
    },
    [pscustomobject]@{
        Label = 'SilverFallback'; Offset = 0x1765F9
        Prefix = '83182400008B3068'; Suffix = '81C684000000E80C'
    },
    [pscustomobject]@{
        Label = 'GoldCompare'; Offset = 0x176634
        Prefix = '5081C6840000003D'; Suffix = '527D0350EB0568'
    },
    [pscustomobject]@{
        Label = 'GoldFallback'; Offset = 0x17663F
        Prefix = '527D0350EB0568'; Suffix = 'E8CC4D24008B8B1C'
    },
    [pscustomobject]@{
        Label = 'BindingGoldCompare'; Offset = 0x176660
        Prefix = '8B81DC0200003D'; Suffix = '6A0A8D4C2450517D'
    },
    [pscustomobject]@{
        Label = 'BindingGoldFallback'; Offset = 0x176681
        Prefix = '83202400008B3068'; Suffix = '81C684000000E884'
    }
)
$unrelatedStockSites = @(
    [pscustomobject]@{ Label = 'NumericEntryInitialValue'; Offset = 0x21C82A },
    [pscustomobject]@{ Label = 'NumericEntryInitialText'; Offset = 0x21C831 },
    [pscustomobject]@{ Label = 'NumericEntryClamp'; Offset = 0x21CBB5 }
)

function Get-FullPath([string]$Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Test-PathWithin([string]$Candidate, [string]$Parent) {
    $candidatePath = Get-FullPath $Candidate
    $parentPath = Get-FullPath $Parent
    return $candidatePath.Equals(
            $parentPath,
            [StringComparison]::OrdinalIgnoreCase) -or
        $candidatePath.StartsWith(
            $parentPath + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)
}

function Convert-HexBytes([string]$Hex) {
    $compact = $Hex -replace '[^0-9A-Fa-f]', ''
    if (($compact.Length % 2) -ne 0) {
        throw 'Malformed wallet-display guard bytes.'
    }
    [byte[]]$result = for ($index = 0; $index -lt $compact.Length;
        $index += 2) {
        [Convert]::ToByte($compact.Substring($index, 2), 16)
    }
    return ,$result
}

function Get-BytesSha256([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $algorithm.ComputeHash($Data))).Replace('-', '')
    }
    finally {
        $algorithm.Dispose()
    }
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

function Copy-BytesAt(
    [byte[]]$Source,
    [byte[]]$Destination,
    [int]$Offset
) {
    [Array]::Copy($Source, 0, $Destination, $Offset, $Source.Length)
}

function Assert-OriginClosed {
    try {
        $processes = @(Get-Process -Name Origin -ErrorAction SilentlyContinue)
    }
    catch {
        throw "Could not prove that Origin.exe is closed: $($_.Exception.Message)"
    }
    if ($processes.Count -ne 0) {
        $ids = ($processes.Id | Sort-Object) -join ', '
        throw "Close Origin.exe before changing the client (PID: $ids)."
    }
}

function Assert-RegularFile([string]$Path, [string]$ExpectedRoot) {
    if (-not (Test-PathWithin $Path $ExpectedRoot)) {
        throw "Client file escaped ClientRoot: $Path"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Client executable was not found: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Client executable must not be a reparse point: $Path"
    }
}

function Read-OriginState([string]$Path) {
    [byte[]]$data = [IO.File]::ReadAllBytes($Path)
    if ($data.Length -lt 2 -or $data[0] -ne 0x4D -or $data[1] -ne 0x5A) {
        throw "Origin.exe does not have an MZ header: $Path"
    }

    $siteStates = [Collections.Generic.List[object]]::new()
    foreach ($site in $patchSites) {
        [byte[]]$prefix = Convert-HexBytes $site.Prefix
        [byte[]]$suffix = Convert-HexBytes $site.Suffix
        if (-not (Test-BytesAt $data ($site.Offset - $prefix.Length) $prefix) -or
            -not (Test-BytesAt $data ($site.Offset + 4) $suffix)) {
            throw "Unsupported Origin.exe context at $($site.Label) " +
                "(0x$('{0:X}' -f $site.Offset))."
        }
        $state = if (Test-BytesAt $data $site.Offset $stockLimit) {
            'Stock'
        }
        elseif (Test-BytesAt $data $site.Offset $fullLimit) {
            'Applied'
        }
        else {
            throw "Unsupported wallet cap bytes at $($site.Label) " +
                "(0x$('{0:X}' -f $site.Offset))."
        }
        $siteStates.Add([pscustomobject]@{
            Label = $site.Label
            Offset = '0x{0:X}' -f $site.Offset
            State = $state
        })
    }

    foreach ($site in $unrelatedStockSites) {
        if (-not (Test-BytesAt $data $site.Offset $stockLimit)) {
            throw "Unrelated 99,999,999 immediate changed at $($site.Label) " +
                "(0x$('{0:X}' -f $site.Offset)); refusing wallet patch scope."
        }
    }

    $distinct = @($siteStates.State | Sort-Object -Unique)
    $state = if ($distinct.Count -eq 1) { $distinct[0] } else { 'Partial' }
    return [pscustomobject]@{
        Path = $Path
        State = $state
        Length = $data.Length
        Sha256 = Get-BytesSha256 $data
        Data = $data
        Sites = $siteStates.ToArray()
    }
}

function New-PatchedBytes([byte[]]$Source) {
    [byte[]]$updated = [byte[]]$Source.Clone()
    foreach ($site in $patchSites) {
        Copy-BytesAt $fullLimit $updated $site.Offset
    }
    return $updated
}

function Assert-OnlyPatchSitesChanged(
    [byte[]]$Before,
    [byte[]]$After
) {
    if ($Before.Length -ne $After.Length) {
        throw 'Wallet patch changed the Origin.exe length.'
    }
    for ($offset = 0; $offset -lt $Before.Length; $offset++) {
        if ($Before[$offset] -eq $After[$offset]) { continue }
        $insidePatchSite = $false
        foreach ($site in $patchSites) {
            if ($offset -ge $site.Offset -and $offset -lt $site.Offset + 4) {
                $insidePatchSite = $true
                break
            }
        }
        if (-not $insidePatchSite) {
            throw "Wallet patch mutated unexpected file offset " +
                "0x$('{0:X}' -f $offset)."
        }
    }
}

function Write-AtomicExact([string]$Path, [byte[]]$Data) {
    $directory = Split-Path -Parent $Path
    $temporary = Join-Path $directory (
        ".reborn-wallet-cap-$([Guid]::NewGuid().ToString('N')).tmp")
    $replaceBackup = Join-Path $directory (
        ".reborn-wallet-cap-$([Guid]::NewGuid().ToString('N')).bak")
    $stream = $null
    try {
        $stream = [IO.FileStream]::new(
            $temporary,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None,
            65536,
            [IO.FileOptions]::WriteThrough)
        $stream.Write($Data, 0, $Data.Length)
        $stream.Flush($true)
        $stream.Dispose()
        $stream = $null
        [IO.File]::Replace($temporary, $Path, $replaceBackup, $true)
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
        if (Test-Path -LiteralPath $replaceBackup) {
            Remove-Item -LiteralPath $replaceBackup -Force
        }
    }
}

function Assert-ExactFile([string]$Path, [byte[]]$Expected) {
    [byte[]]$actual = [IO.File]::ReadAllBytes($Path)
    if (-not (Test-BytesEqual $actual $Expected)) {
        throw "Exact file readback failed: $Path"
    }
}

function New-StatusResult([object]$State, [string]$ResultMode) {
    return [pscustomobject]@{
        Mode = $ResultMode
        State = $State.State
        ClientRoot = $clientRootPath
        OriginPath = $State.Path
        OriginRunning = @(Get-Process -Name Origin -ErrorAction SilentlyContinue).Count -ne 0
        Length = $State.Length
        Sha256 = $State.Sha256
        DisplayMaximum = if ($State.State -ceq 'Applied') {
            [int]::MaxValue
        } elseif ($State.State -ceq 'Stock') {
            99999999
        } else {
            $null
        }
        Sites = $State.Sites
        PreservedUnrelatedOffsets = @($unrelatedStockSites | ForEach-Object {
            '0x{0:X}' -f $_.Offset
        })
    }
}

$clientRootPath = Get-FullPath $ClientRoot
if ([IO.Path]::GetPathRoot($clientRootPath) -ceq $clientRootPath) {
    throw 'ClientRoot must not be a drive root.'
}
if ($clientRootPath -match '(?i)(^|[\\/])B20H([\\/]|$)') {
    throw 'The protected B20H client tree is outside this patch scope.'
}
$originPath = Join-Path $clientRootPath $originRelativePath
Assert-RegularFile $originPath $clientRootPath
$state = Read-OriginState $originPath

if ($Mode -ceq 'Status') {
    New-StatusResult $state 'Status'
    return
}

Assert-OriginClosed
$backupRootPath = Get-FullPath $BackupRoot
if ([IO.Path]::GetPathRoot($backupRootPath) -ceq $backupRootPath) {
    throw 'BackupRoot must not be a drive root.'
}
if (Test-PathWithin $backupRootPath $clientRootPath) {
    throw 'BackupRoot must be outside ClientRoot.'
}

if ($Mode -ceq 'Apply') {
    if ($state.State -ceq 'Partial') {
        throw 'Refusing to apply over a partial wallet-display patch.'
    }
    if ($state.State -ceq 'Applied') {
        $result = New-StatusResult $state 'Apply'
        $result | Add-Member -NotePropertyName Changed -NotePropertyValue $false
        $result | Add-Member -NotePropertyName Receipt -NotePropertyValue $null
        $result
        return
    }
    if (-not $PSCmdlet.ShouldProcess(
        $originPath,
        'Lift six wallet display immediates to Int32 maximum')) {
        return
    }
    Assert-OriginClosed

    [byte[]]$updated = New-PatchedBytes $state.Data
    Assert-OnlyPatchSitesChanged $state.Data $updated
    $updatedHash = Get-BytesSha256 $updated
    $backupDirectory = Join-Path $backupRootPath (
        "$patchName-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))-" +
        "$([Guid]::NewGuid().ToString('N').Substring(0, 8))")
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    $backupPath = Join-Path $backupDirectory 'Origin.exe.before'
    $receiptOutputPath = Join-Path $backupDirectory 'receipt.json'
    [IO.File]::WriteAllBytes($backupPath, $state.Data)
    Assert-ExactFile $backupPath $state.Data

    $receipt = [ordered]@{
        Schema = $receiptSchema
        Patch = $patchName
        ClientRoot = $clientRootPath
        RelativePath = $originRelativePath
        AppliedUtc = [DateTime]::UtcNow.ToString('O')
        BackupPath = $backupPath
        BeforeLength = $state.Length
        BeforeSha256 = $state.Sha256
        AfterLength = $updated.Length
        AfterSha256 = $updatedHash
        PatchOffsets = @($patchSites | ForEach-Object { '0x{0:X}' -f $_.Offset })
        PreservedUnrelatedOffsets = @($unrelatedStockSites | ForEach-Object {
            '0x{0:X}' -f $_.Offset
        })
        StockDisplayMaximum = 99999999
        PatchedDisplayMaximum = [int]::MaxValue
    }

    $installed = $false
    try {
        Assert-OriginClosed
        Write-AtomicExact $originPath $updated
        $installed = $true
        Assert-ExactFile $originPath $updated
        $afterState = Read-OriginState $originPath
        if ($afterState.State -cne 'Applied' -or
            $afterState.Sha256 -cne $updatedHash) {
            throw 'Post-apply wallet-display validation failed.'
        }
        $json = $receipt | ConvertTo-Json -Depth 6
        [IO.File]::WriteAllText(
            $receiptOutputPath,
            $json + [Environment]::NewLine,
            [Text.UTF8Encoding]::new($false))
        if (-not (Test-Path -LiteralPath $receiptOutputPath -PathType Leaf)) {
            throw 'Wallet patch receipt readback failed.'
        }
    }
    catch {
        $failure = $_
        if ($installed) {
            Write-AtomicExact $originPath $state.Data
            Assert-ExactFile $originPath $state.Data
        }
        if (Test-Path -LiteralPath $receiptOutputPath) {
            Remove-Item -LiteralPath $receiptOutputPath -Force
        }
        throw $failure
    }

    $result = New-StatusResult $afterState 'Apply'
    $result | Add-Member -NotePropertyName Changed -NotePropertyValue $true
    $result | Add-Member -NotePropertyName Receipt -NotePropertyValue $receiptOutputPath
    $result | Add-Member -NotePropertyName Backup -NotePropertyValue $backupPath
    $result
    return
}

if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    throw 'Revert requires -ReceiptPath from the matching Apply operation.'
}
$receiptFullPath = Get-FullPath $ReceiptPath
if (-not (Test-PathWithin $receiptFullPath $backupRootPath) -or
    -not (Test-Path -LiteralPath $receiptFullPath -PathType Leaf)) {
    throw "Receipt must exist under BackupRoot: $receiptFullPath"
}
$receiptData = Get-Content -LiteralPath $receiptFullPath -Raw | ConvertFrom-Json
if ($receiptData.Schema -ne $receiptSchema -or
    $receiptData.Patch -cne $patchName -or
    -not (Get-FullPath ([string]$receiptData.ClientRoot)).Equals(
        $clientRootPath,
        [StringComparison]::OrdinalIgnoreCase) -or
    [string]$receiptData.RelativePath -cne $originRelativePath) {
    throw 'Receipt does not match this client and wallet patch schema.'
}

$backupPath = Get-FullPath ([string]$receiptData.BackupPath)
if (-not (Test-PathWithin $backupPath $backupRootPath) -or
    (Test-PathWithin $backupPath $clientRootPath) -or
    -not (Test-Path -LiteralPath $backupPath -PathType Leaf)) {
    throw "Receipt backup is unsafe or missing: $backupPath"
}
[byte[]]$original = [IO.File]::ReadAllBytes($backupPath)
if ($original.Length -ne [int]$receiptData.BeforeLength -or
    (Get-BytesSha256 $original) -cne [string]$receiptData.BeforeSha256) {
    throw "Receipt backup verification failed: $backupPath"
}

$currentHash = $state.Sha256
if ($currentHash -ceq [string]$receiptData.BeforeSha256) {
    $result = New-StatusResult $state 'Revert'
    $result | Add-Member -NotePropertyName Changed -NotePropertyValue $false
    $result | Add-Member -NotePropertyName Receipt -NotePropertyValue $receiptFullPath
    $result
    return
}
if ($currentHash -cne [string]$receiptData.AfterSha256 -or
    $state.State -cne 'Applied') {
    throw 'Refusing to revert because Origin.exe does not match the receipt after-state.'
}
if (-not $PSCmdlet.ShouldProcess($originPath, 'Restore verified Origin.exe backup')) {
    return
}
Assert-OriginClosed
[byte[]]$current = $state.Data
try {
    Write-AtomicExact $originPath $original
    Assert-ExactFile $originPath $original
    $revertedState = Read-OriginState $originPath
    if ($revertedState.State -cne 'Stock' -or
        $revertedState.Sha256 -cne [string]$receiptData.BeforeSha256) {
        throw 'Post-revert wallet-display validation failed.'
    }
}
catch {
    $failure = $_
    Write-AtomicExact $originPath $current
    Assert-ExactFile $originPath $current
    throw $failure
}
$result = New-StatusResult $revertedState 'Revert'
$result | Add-Member -NotePropertyName Changed -NotePropertyValue $true
$result | Add-Member -NotePropertyName Receipt -NotePropertyValue $receiptFullPath
$result
