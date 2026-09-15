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

$patchName = 'client-talent-point-gain-notification'
$receiptSchema = 1
$messageRelativePaths = [ordered]@{
    en_us = 'Localization\en_us\Text\Message.dat'
    zh_cn = 'Localization\zh_cn\Text\Message.dat'
}
$chineseTalentExperience = -join @(
    [char]0x5929,
    [char]0x8D4B,
    [char]0x7ECF,
    [char]0x9A8C,
    [char]0xFF1A)
$chineseTalentPoints = -join @(
    [char]0x5929,
    [char]0x8D4B,
    [char]0x70B9,
    [char]0x6570,
    [char]0xFF1A)
$anchorRows = [ordered]@{
    en_us = "Attr_Note_4`tTalent Exp:"
    zh_cn = "Attr_Note_4`t$chineseTalentExperience"
}
$targetRows = [ordered]@{
    en_us = "Attr_Note_5`t Talent Points:"
    zh_cn = "Attr_Note_5`t$chineseTalentPoints"
}

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

function Get-BytesSha256([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $hash = $algorithm.ComputeHash($Data)
        return ([BitConverter]::ToString($hash)).Replace('-', '')
    }
    finally {
        $algorithm.Dispose()
    }
}

function Test-BytesEqual([byte[]]$Left, [byte[]]$Right) {
    if ($Left.Length -ne $Right.Length) { return $false }
    for ($index = 0; $index -lt $Left.Length; $index++) {
        if ($Left[$index] -ne $Right[$index]) { return $false }
    }
    return $true
}

function Find-ByteSequence(
    [byte[]]$Haystack,
    [byte[]]$Needle
) {
    $matches = [Collections.Generic.List[int]]::new()
    for ($offset = 0; $offset -le $Haystack.Length - $Needle.Length; $offset++) {
        $matched = $true
        for ($index = 0; $index -lt $Needle.Length; $index++) {
            if ($Haystack[$offset + $index] -ne $Needle[$index]) {
                $matched = $false
                break
            }
        }
        if ($matched) {
            $matches.Add($offset)
        }
    }
    return $matches.ToArray()
}

function Assert-OriginClosed {
    try {
        $originProcesses = @(Get-Process -Name Origin -ErrorAction SilentlyContinue)
    }
    catch {
        throw "Could not prove that Origin.exe is closed: $($_.Exception.Message)"
    }
    if ($originProcesses.Count -ne 0) {
        $ids = ($originProcesses.Id | Sort-Object) -join ', '
        throw "Close Origin.exe before changing client localization (PID: $ids)."
    }
}

function Assert-RegularClientFile([string]$Path, [string]$Root) {
    if (-not (Test-PathWithin $Path $Root)) {
        throw "Client file escaped ClientRoot: $Path"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Client localization file was not found: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Client localization file must not be a reparse point: $Path"
    }
}

function Read-MessageTableState(
    [string]$Locale,
    [string]$Path,
    [string]$RelativePath,
    [string]$AnchorRow,
    [string]$TargetRow
) {
    [byte[]]$data = [IO.File]::ReadAllBytes($Path)
    if ($data.Length -lt 2 -or $data[0] -ne 0xFF -or $data[1] -ne 0xFE) {
        throw "Message.dat must be UTF-16LE with a BOM: $Path"
    }
    if (($data.Length % 2) -ne 0) {
        throw "Message.dat has a truncated UTF-16 code unit: $Path"
    }

    $text = [Text.Encoding]::Unicode.GetString($data, 2, $data.Length - 2)
    if ($text -match "(?<!`r)`n|`r(?!`n)") {
        throw "Message.dat must use CRLF consistently: $Path"
    }
    [byte[]]$roundTrip = [byte[]]::new($data.Length)
    $roundTrip[0] = 0xFF
    $roundTrip[1] = 0xFE
    [byte[]]$encodedText = [Text.Encoding]::Unicode.GetBytes($text)
    [Array]::Copy($encodedText, 0, $roundTrip, 2, $encodedText.Length)
    if (-not (Test-BytesEqual $roundTrip $data)) {
        throw "Message.dat is not canonical UTF-16LE: $Path"
    }

    $lines = $text.Split(
        [string[]]@("`r`n"),
        [StringSplitOptions]::None)
    $anchorCount = @($lines | Where-Object { $_ -ceq $AnchorRow }).Count
    if ($anchorCount -ne 1) {
        throw "Expected exactly one '$AnchorRow' row in $Path; found $anchorCount."
    }
    $targetKey = "Attr_Note_5`t"
    $targetKeyRows = @($lines | Where-Object {
        $_.StartsWith($targetKey, [StringComparison]::Ordinal)
    })
    if ($targetKeyRows.Count -gt 1) {
        throw "Attr_Note_5 occurs $($targetKeyRows.Count) times in $Path."
    }
    if ($targetKeyRows.Count -eq 1 -and $targetKeyRows[0] -cne $TargetRow) {
        throw "Attr_Note_5 has an unsupported value in $Path."
    }

    return [pscustomobject]@{
        Locale = $Locale
        RelativePath = $RelativePath
        Path = $Path
        State = if ($targetKeyRows.Count -eq 1) { 'Applied' } else { 'Absent' }
        Length = $data.Length
        Sha256 = Get-BytesSha256 $data
        Data = $data
        AnchorRow = $AnchorRow
        TargetRow = $TargetRow
    }
}

function Get-ClientStates([string]$Root) {
    $states = [Collections.Generic.List[object]]::new()
    foreach ($locale in $messageRelativePaths.Keys) {
        $relative = $messageRelativePaths[$locale]
        $path = Join-Path $Root $relative
        Assert-RegularClientFile $path $Root
        $states.Add((Read-MessageTableState `
            $locale $path $relative $anchorRows[$locale] $targetRows[$locale]))
    }
    return $states.ToArray()
}

function New-PatchedMessageBytes([object]$State) {
    [byte[]]$anchor = [Text.Encoding]::Unicode.GetBytes(
        $State.AnchorRow + "`r`n")
    [byte[]]$addition = [Text.Encoding]::Unicode.GetBytes(
        $State.TargetRow + "`r`n")
    $matches = @(Find-ByteSequence $State.Data $anchor)
    if ($matches.Count -ne 1) {
        throw "The UTF-16 anchor is not byte-unique in $($State.Path)."
    }
    $insertAt = $matches[0] + $anchor.Length
    [byte[]]$updated = [byte[]]::new($State.Data.Length + $addition.Length)
    [Array]::Copy($State.Data, 0, $updated, 0, $insertAt)
    [Array]::Copy($addition, 0, $updated, $insertAt, $addition.Length)
    [Array]::Copy(
        $State.Data,
        $insertAt,
        $updated,
        $insertAt + $addition.Length,
        $State.Data.Length - $insertAt)
    return $updated
}

function Write-AtomicExact([string]$Path, [byte[]]$Data) {
    $directory = Split-Path -Parent $Path
    $temporary = Join-Path $directory (
        ".reborn-talent-note-$([Guid]::NewGuid().ToString('N')).tmp")
    $replaceBackup = Join-Path $directory (
        ".reborn-talent-note-$([Guid]::NewGuid().ToString('N')).bak")
    $stream = $null
    try {
        $stream = [IO.FileStream]::new(
            $temporary,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None,
            4096,
            [IO.FileOptions]::WriteThrough)
        $stream.Write($Data, 0, $Data.Length)
        $stream.Flush($true)
        $stream.Dispose()
        $stream = $null
        [IO.File]::Replace($temporary, $Path, $replaceBackup, $true)
    }
    finally {
        if ($null -ne $stream) {
            $stream.Dispose()
        }
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
        throw "Exact readback failed: $Path"
    }
}

function Restore-WrittenFiles([object[]]$Written, [hashtable]$OriginalByPath) {
    for ($index = $Written.Count - 1; $index -ge 0; $index--) {
        $path = [string]$Written[$index]
        Write-AtomicExact $path $OriginalByPath[$path]
        Assert-ExactFile $path $OriginalByPath[$path]
    }
}

function New-StatusResult([object[]]$States) {
    $distinct = @($States.State | Sort-Object -Unique)
    $overall = if ($distinct.Count -eq 1) { $distinct[0] } else { 'Partial' }
    return [pscustomobject]@{
        Mode = 'Status'
        State = $overall
        ClientRoot = $clientRootPath
        OriginRunning = @(Get-Process -Name Origin -ErrorAction SilentlyContinue).Count -ne 0
        Files = @($States | ForEach-Object {
            [pscustomobject]@{
                Locale = $_.Locale
                RelativePath = $_.RelativePath
                State = $_.State
                Length = $_.Length
                Sha256 = $_.Sha256
                TargetRow = $_.TargetRow
            }
        })
    }
}

$clientRootPath = Get-FullPath $ClientRoot
if ([IO.Path]::GetPathRoot($clientRootPath) -ceq $clientRootPath) {
    throw 'ClientRoot must not be a drive root.'
}
if ((Split-Path -Leaf $clientRootPath) -match '(?i)B20H') {
    throw 'The protected B20H client tree is outside this patch scope.'
}
if (-not (Test-Path -LiteralPath (Join-Path $clientRootPath 'Origin.exe') -PathType Leaf)) {
    throw "Origin.exe was not found under ClientRoot: $clientRootPath"
}

$states = @(Get-ClientStates $clientRootPath)
if ($Mode -ceq 'Status') {
    New-StatusResult $states
    return
}

Assert-OriginClosed

if ($Mode -ceq 'Apply') {
    $distinct = @($states.State | Sort-Object -Unique)
    if ($distinct.Count -ne 1) {
        throw 'Refusing to apply over a partial locale state.'
    }
    if ($distinct[0] -ceq 'Applied') {
        $result = New-StatusResult $states
        $result.Mode = 'Apply'
        $result | Add-Member -NotePropertyName Changed -NotePropertyValue $false
        $result | Add-Member -NotePropertyName Receipt -NotePropertyValue $null
        $result
        return
    }

    $backupRootPath = Get-FullPath $BackupRoot
    if (Test-PathWithin $backupRootPath $clientRootPath) {
        throw 'BackupRoot must be outside ClientRoot.'
    }
    if (-not $PSCmdlet.ShouldProcess($clientRootPath, 'Add localized Talent Point gain note')) {
        return
    }
    Assert-OriginClosed

    $backupDirectory = Join-Path $backupRootPath (
        "$patchName-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))-$([Guid]::NewGuid().ToString('N').Substring(0, 8))")
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    $originalByPath = @{}
    $updatedByPath = @{}
    $receiptFiles = [Collections.Generic.List[object]]::new()
    foreach ($state in $states) {
        $originalByPath[$state.Path] = $state.Data
        [byte[]]$updated = New-PatchedMessageBytes $state
        $updatedByPath[$state.Path] = $updated
        $backupPath = Join-Path $backupDirectory "$($state.Locale)-Message.dat"
        [IO.File]::WriteAllBytes($backupPath, $state.Data)
        Assert-ExactFile $backupPath $state.Data
        $receiptFiles.Add([ordered]@{
            Locale = $state.Locale
            RelativePath = $state.RelativePath
            BackupPath = $backupPath
            BeforeLength = $state.Data.Length
            BeforeSha256 = Get-BytesSha256 $state.Data
            AfterLength = $updated.Length
            AfterSha256 = Get-BytesSha256 $updated
        })
    }

    $written = [Collections.Generic.List[string]]::new()
    $receipt = [ordered]@{
        Schema = $receiptSchema
        Patch = $patchName
        ClientRoot = $clientRootPath
        AppliedUtc = [DateTime]::UtcNow.ToString('O')
        Files = $receiptFiles.ToArray()
    }
    $receiptOutputPath = Join-Path $backupDirectory 'receipt.json'
    try {
        foreach ($state in $states) {
            Assert-OriginClosed
            Write-AtomicExact $state.Path $updatedByPath[$state.Path]
            $written.Add($state.Path)
            Assert-ExactFile $state.Path $updatedByPath[$state.Path]
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
        Restore-WrittenFiles $written.ToArray() $originalByPath
        throw $failure
    }

    try {
        $afterStates = @(Get-ClientStates $clientRootPath)
        if (@($afterStates.State | Where-Object { $_ -cne 'Applied' }).Count -ne 0) {
            throw 'Post-apply locale validation failed.'
        }
    }
    catch {
        $failure = $_
        Restore-WrittenFiles $written.ToArray() $originalByPath
        if (Test-Path -LiteralPath $receiptOutputPath) {
            Remove-Item -LiteralPath $receiptOutputPath -Force
        }
        throw $failure
    }
    $result = New-StatusResult $afterStates
    $result.Mode = 'Apply'
    $result | Add-Member -NotePropertyName Changed -NotePropertyValue $true
    $result | Add-Member -NotePropertyName Receipt -NotePropertyValue $receiptOutputPath
    $result
    return
}

if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    throw 'Revert requires -ReceiptPath from the matching Apply operation.'
}
$receiptFullPath = Get-FullPath $ReceiptPath
if (-not (Test-Path -LiteralPath $receiptFullPath -PathType Leaf)) {
    throw "Receipt was not found: $receiptFullPath"
}
$receiptData = Get-Content -LiteralPath $receiptFullPath -Raw | ConvertFrom-Json
if ($receiptData.Schema -ne $receiptSchema -or
    $receiptData.Patch -cne $patchName -or
    (Get-FullPath ([string]$receiptData.ClientRoot)) -cne $clientRootPath -or
    @($receiptData.Files).Count -ne $states.Count) {
    throw 'Receipt does not match this client and patch schema.'
}

$currentByPath = @{}
$originalByPath = @{}
$receiptByRelativePath = @{}
foreach ($entry in @($receiptData.Files)) {
    $receiptByRelativePath[[string]$entry.RelativePath] = $entry
}
$allBefore = $true
$allAfter = $true
foreach ($state in $states) {
    if (-not $receiptByRelativePath.ContainsKey($state.RelativePath)) {
        throw "Receipt omitted $($state.RelativePath)."
    }
    $entry = $receiptByRelativePath[$state.RelativePath]
    if ([string]$entry.Locale -cne $state.Locale) {
        throw "Receipt locale mismatch for $($state.RelativePath)."
    }
    [byte[]]$current = [IO.File]::ReadAllBytes($state.Path)
    $currentByPath[$state.Path] = $current
    $currentHash = Get-BytesSha256 $current
    if ($currentHash -cne [string]$entry.BeforeSha256) { $allBefore = $false }
    if ($currentHash -cne [string]$entry.AfterSha256) { $allAfter = $false }

    $backupPath = Get-FullPath ([string]$entry.BackupPath)
    if ((Test-PathWithin $backupPath $clientRootPath) -or
        -not (Test-Path -LiteralPath $backupPath -PathType Leaf)) {
        throw "Receipt backup is unsafe or missing: $backupPath"
    }
    [byte[]]$original = [IO.File]::ReadAllBytes($backupPath)
    if ($original.Length -ne [int]$entry.BeforeLength -or
        (Get-BytesSha256 $original) -cne [string]$entry.BeforeSha256) {
        throw "Receipt backup verification failed: $backupPath"
    }
    $originalByPath[$state.Path] = $original
}

if ($allBefore) {
    $result = New-StatusResult $states
    $result.Mode = 'Revert'
    $result | Add-Member -NotePropertyName Changed -NotePropertyValue $false
    $result | Add-Member -NotePropertyName Receipt -NotePropertyValue $receiptFullPath
    $result
    return
}
if (-not $allAfter) {
    throw 'Refusing to revert because installed files do not match the receipt after-state.'
}
if (-not $PSCmdlet.ShouldProcess($clientRootPath, 'Restore localized Message.dat backups')) {
    return
}
Assert-OriginClosed
$written = [Collections.Generic.List[string]]::new()
try {
    foreach ($state in $states) {
        Assert-OriginClosed
        Write-AtomicExact $state.Path $originalByPath[$state.Path]
        $written.Add($state.Path)
        Assert-ExactFile $state.Path $originalByPath[$state.Path]
    }
}
catch {
    $failure = $_
    Restore-WrittenFiles $written.ToArray() $currentByPath
    throw $failure
}
try {
    $revertedStates = @(Get-ClientStates $clientRootPath)
    if (@($revertedStates.State | Where-Object { $_ -cne 'Absent' }).Count -ne 0) {
        throw 'Post-revert locale validation failed.'
    }
}
catch {
    $failure = $_
    Restore-WrittenFiles $written.ToArray() $currentByPath
    throw $failure
}
$result = New-StatusResult $revertedStates
$result.Mode = 'Revert'
$result | Add-Member -NotePropertyName Changed -NotePropertyValue $true
$result | Add-Member -NotePropertyName Receipt -NotePropertyValue $receiptFullPath
$result
