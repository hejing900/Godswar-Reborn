$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$strictUtf16 = [Text.UnicodeEncoding]::new($false, $false, $true)

function Get-DsFullPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'A required path is empty.'
    }
    return [IO.Path]::GetFullPath($Path)
}

function Test-DsPathWithin([string]$Candidate, [string]$Parent) {
    $candidatePath = Get-DsFullPath $Candidate
    $parentPath = (Get-DsFullPath $Parent).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar)
    if ([string]::Equals(
            $candidatePath,
            $parentPath,
            [StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    $prefix = $parentPath + [IO.Path]::DirectorySeparatorChar
    return $candidatePath.StartsWith(
        $prefix,
        [StringComparison]::OrdinalIgnoreCase)
}

function Get-DsSha256([byte[]]$Data) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString(
            $sha.ComputeHash($Data)).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}

function Assert-DsOrdinaryFile([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label was not found: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "$Label must not be a reparse point: $Path"
    }
}

function New-DsStatusSection(
    [int]$Id,
    [string]$Name,
    [int]$Kind,
    [int]$Priority,
    [string]$Effect,
    [string]$Values,
    [string]$Note,
    [string]$IconPos
) {
    [string[]]$effects = $Effect.Split(',')
    [string[]]$valuesList = $Values.Split(',')
    if ($effects.Count -eq 0 -or
        $effects.Count -ne $valuesList.Count -or
        @($effects | Where-Object {
            [string]::IsNullOrWhiteSpace($_)
        }).Count -ne 0 -or
        @($valuesList | Where-Object {
            [string]::IsNullOrWhiteSpace($_)
        }).Count -ne 0) {
        throw "Status [$Id] must define one non-empty value per effect."
    }
    $intervals = (@('0') * $effects.Count) -join ','
    return @(
        "[$Id]",
        "Name=$Name",
        'Style=1',
        "Kind=$Kind",
        "Priority=$Priority",
        "Effect=$Effect",
        "Values=$Values",
        "Interval=$intervals",
        'Time=-1',
        "Note=$Note",
        "IconPos=$IconPos",
        'IconSize=36,36',
        'EffectDisplay=-1',
        'RideId=-1',
        'Action=1') -join "`n"
}

function Get-DsSections([string]$Text) {
    $headers = [regex]::Matches($Text, '(?m)^\[(?<id>\d+)\]\r?$')
    if ($headers.Count -eq 0) {
        throw 'Status.ini contains no numeric status sections.'
    }
    $sections = @{}
    for ($index = 0; $index -lt $headers.Count; $index++) {
        $header = $headers[$index]
        $id = [int]::Parse(
            $header.Groups['id'].Value,
            [Globalization.CultureInfo]::InvariantCulture)
        if ($sections.ContainsKey($id)) {
            throw "Status.ini contains duplicate section [$id]."
        }
        $start = $header.Index
        $end = if ($index + 1 -lt $headers.Count) {
            $headers[$index + 1].Index
        }
        else {
            $Text.Length
        }
        $raw = $Text.Substring($start, $end - $start)
        $sections[$id] = [pscustomobject]@{
            Id = $id
            Start = $start
            Length = $end - $start
            Raw = $raw
            Normalized = $raw.Replace("`r`n", "`n").TrimEnd(
                [char]13,
                [char]10)
        }
    }
    return $sections
}

function Test-DsSectionSet(
    [hashtable]$Sections,
    [hashtable]$Expected,
    [int[]]$Absent
) {
    foreach ($entry in $Expected.GetEnumerator()) {
        $id = [int]$entry.Key
        if (-not $Sections.ContainsKey($id) -or
            $Sections[$id].Normalized -cne [string]$entry.Value) {
            return $false
        }
    }
    foreach ($id in $Absent) {
        if ($Sections.ContainsKey($id)) {
            return $false
        }
    }
    return $true
}

function ConvertTo-DsUtf16Bytes([string]$Text) {
    [byte[]]$body = $strictUtf16.GetBytes($Text)
    [byte[]]$output = [byte[]]::new($body.Length + 2)
    $output[0] = 0xFF
    $output[1] = 0xFE
    [Array]::Copy($body, 0, $output, 2, $body.Length)
    return $output
}

function Write-DsAtomicBytes([string]$Path, [byte[]]$Data) {
    $stage = "$Path.$([Guid]::NewGuid().ToString('N')).stage"
    $replaceBackup =
        "$Path.$([Guid]::NewGuid().ToString('N')).replace-backup"
    try {
        [IO.File]::WriteAllBytes($stage, $Data)
        if ((Get-DsSha256 ([IO.File]::ReadAllBytes($stage))) -cne
            (Get-DsSha256 $Data)) {
            throw 'Staged Donator localization failed verification.'
        }
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            [IO.File]::Replace($stage, $Path, $replaceBackup, $true)
        }
        else {
            [IO.File]::Move($stage, $Path)
        }
    }
    finally {
        if (Test-Path -LiteralPath $stage) {
            Remove-Item -LiteralPath $stage -Force
        }
        if (Test-Path -LiteralPath $replaceBackup) {
            Remove-Item -LiteralPath $replaceBackup -Force
        }
    }
}

Export-ModuleMember -Function @(
    'Get-DsFullPath',
    'Test-DsPathWithin',
    'Get-DsSha256',
    'Assert-DsOrdinaryFile',
    'New-DsStatusSection',
    'Get-DsSections',
    'Test-DsSectionSet',
    'ConvertTo-DsUtf16Bytes',
    'Write-DsAtomicBytes')
