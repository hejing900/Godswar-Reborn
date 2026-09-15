[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Status', 'Apply', 'Verify')]
    [string]$Mode = 'Status',
    [string]$ClientRoot = 'C:\Godswar Origin',
    [string]$BackupDirectory,
    [string]$ReceiptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$relativePath = 'Localization\en_us\UI\Base\LuaText.lua'
$targetPath = [IO.Path]::GetFullPath((Join-Path $ClientRoot $relativePath))
$utf8 = [Text.UTF8Encoding]::new($false, $true)

function Get-BytesSha256([byte[]]$Bytes) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash($Bytes)).Replace('-', '')
    }
    finally { $algorithm.Dispose() }
}

function Read-AtlantisLevelState([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing Lua localization file: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "The Lua localization file must be a regular file: $Path"
    }
    [byte[]]$bytes = [IO.File]::ReadAllBytes($Path)
    # The audited installed and repository resources use UTF-8. Strict
    # decoding rejects unknown encodings rather than silently converting them.
    $text = $utf8.GetString($bytes)
    if ($text.IndexOf([char]0) -ge 0) {
        throw "Unsupported LuaText.lua encoding: $Path"
    }
    $keys = [regex]::Matches($text, '(?m)^[ \t]*NF_L0_R208[ \t]*=')
    $assignments = [regex]::Matches($text,
        '(?m)^[ \t]*NF_L0_R208[ \t]*=[ \t]*"(?<value>[^"\r\n]*)"[ \t]*\r?$')
    if ($keys.Count -ne 1 -or $assignments.Count -ne 1) {
        throw 'Expected exactly one ordinary NF_L0_R208 string assignment.'
    }
    $value = $assignments[0].Groups['value']
    $old = [regex]::Matches($value.Value, '\|cff39D8B8Level 90-140\|cFFFFFFFF')
    $new = [regex]::Matches($value.Value, '\|cff39D8B8Level 90\+\|cFFFFFFFF')
    if (($old.Count + $new.Count) -ne 1) {
        throw 'NF_L0_R208 has an unknown or duplicate Atlantis level fragment.'
    }

    [byte[]]$planned = $bytes
    $byteOffset = $null
    if ($old.Count -eq 1) {
        $characterOffset = $value.Index + $old[0].Index + '|cff39D8B8Level '.Length
        $byteOffset = $utf8.GetByteCount($text.Substring(0, $characterOffset))
        [byte[]]$replacement = [Text.Encoding]::ASCII.GetBytes('90+')
        $planned = [byte[]]::new($bytes.Length - 3)
        [Array]::Copy($bytes, 0, $planned, 0, $byteOffset)
        [Array]::Copy($replacement, 0, $planned, $byteOffset, $replacement.Length)
        [Array]::Copy($bytes, $byteOffset + 6, $planned, $byteOffset + 3,
            $bytes.Length - $byteOffset - 6)
    }
    return [pscustomobject]@{
        State = if ($old.Count -eq 1) { 'NeedsPatch' } else { 'Applied' }
        Bytes = $bytes
        Sha256 = Get-BytesSha256 $bytes
        PlannedBytes = $planned
        PlannedSha256 = Get-BytesSha256 $planned
        ByteOffset = $byteOffset
        Encoding = if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and
            $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { 'Utf8Bom' } else { 'Utf8NoBom' }
    }
}

function Assert-ReceiptMatches([string]$Path, [object]$Current) {
    $receipt = [IO.File]::ReadAllText([IO.Path]::GetFullPath($Path), $utf8) |
        ConvertFrom-Json
    if ($receipt.Schema -ne 1 -or $receipt.Token -cne 'NF_L0_R208' -or
        -not $receipt.TargetPath.Equals($targetPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The receipt does not identify this Atlantis localization patch.'
    }
    $original = Read-AtlantisLevelState $receipt.BackupPath
    if ($original.State -ne 'NeedsPatch' -or
        $original.Sha256 -cne $receipt.BeforeSha256 -or
        $original.PlannedSha256 -cne $receipt.AfterSha256 -or
        $Current.Sha256 -cne $original.PlannedSha256) {
        throw 'The installed file is not the exact one-fragment change from its backup.'
    }
}

$before = Read-AtlantisLevelState $targetPath
$writtenReceipt = $null
if ($Mode -eq 'Verify' -and $before.State -ne 'Applied') {
    throw 'NF_L0_R208 still contains the Atlantis upper level cap.'
}
if ($Mode -eq 'Apply' -and $before.State -eq 'NeedsPatch' -and
    $PSCmdlet.ShouldProcess($targetPath, 'Replace only NF_L0_R208 90-140 with 90+')) {
    if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
        $BackupDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'artifacts\atlantis-level90plus-20260908'
    }
    $BackupDirectory = [IO.Path]::GetFullPath($BackupDirectory)
    [void][IO.Directory]::CreateDirectory($BackupDirectory)
    $backupPath = Join-Path $BackupDirectory ($before.Sha256 + '-LuaText.lua.before')
    if (Test-Path -LiteralPath $backupPath) {
        if ((Get-BytesSha256 ([IO.File]::ReadAllBytes($backupPath))) -cne $before.Sha256) {
            throw "Existing backup contents do not match: $backupPath"
        }
    }
    else { [IO.File]::WriteAllBytes($backupPath, $before.Bytes) }
    if ((Get-BytesSha256 ([IO.File]::ReadAllBytes($backupPath))) -cne $before.Sha256) {
        throw 'The exact original localization backup could not be verified.'
    }

    $temporaryPath = $targetPath + '.atlantis-' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllBytes($temporaryPath, $before.PlannedBytes)
        if ((Get-BytesSha256 ([IO.File]::ReadAllBytes($targetPath))) -cne $before.Sha256) {
            throw 'LuaText.lua changed after preparation; no replacement was applied.'
        }
        [IO.File]::Replace($temporaryPath, $targetPath,
            [System.Management.Automation.Language.NullString]::Value)
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
    $after = Read-AtlantisLevelState $targetPath
    if ($after.State -ne 'Applied' -or $after.Sha256 -cne $before.PlannedSha256) {
        throw "The written localization failed verification. Exact backup: $backupPath"
    }
    $writtenReceipt = Join-Path $BackupDirectory ($before.Sha256 + '-receipt.json')
    $receipt = [ordered]@{
        Schema = 1
        Token = 'NF_L0_R208'
        TargetPath = $targetPath
        BackupPath = $backupPath
        BeforeSha256 = $before.Sha256
        AfterSha256 = $after.Sha256
        BeforeBytes = $before.Bytes.Length
        AfterBytes = $after.Bytes.Length
        ReplacedByteOffset = $before.ByteOffset
        BeforeFragment = '90-140'
        AfterFragment = '90+'
        Encoding = $before.Encoding
        AppliedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
    }
    [IO.File]::WriteAllText($writtenReceipt, ($receipt | ConvertTo-Json) + "`n", $utf8)
    Assert-ReceiptMatches $writtenReceipt $after
}

$current = Read-AtlantisLevelState $targetPath
if (-not [string]::IsNullOrWhiteSpace($ReceiptPath)) {
    Assert-ReceiptMatches $ReceiptPath $current
}
[pscustomobject]@{
    Mode = $Mode
    State = $current.State
    Path = $targetPath
    Bytes = $current.Bytes.Length
    Sha256 = $current.Sha256
    Encoding = $current.Encoding
    ReceiptPath = $writtenReceipt
} | ConvertTo-Json
