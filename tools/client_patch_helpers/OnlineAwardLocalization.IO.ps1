$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-OaOriginClosed {
    try {
        $processes = @(Get-Process -Name Origin -ErrorAction SilentlyContinue)
    }
    catch {
        throw "Could not prove that Origin.exe is closed: $($_.Exception.Message)"
    }
    if ($processes.Count -ne 0) {
        $ids = ($processes.Id | Sort-Object) -join ', '
        throw "Close Origin.exe before changing client localization (PID: $ids)."
    }
}

function Write-OaAtomicExact(
    [string]$Path,
    [byte[]]$Data,
    [switch]$TestFailAfterReplace
) {
    $directory = Split-Path -Parent $Path
    $token = [Guid]::NewGuid().ToString('N')
    $temporary = Join-Path $directory ".reborn-online-award-$token.tmp"
    $replaceBackup = Join-Path $directory ".reborn-online-award-$token.bak"
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
        if ($null -ne $stream) { $stream.Dispose() }
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
        if (Test-Path -LiteralPath $replaceBackup) {
            Remove-Item -LiteralPath $replaceBackup -Force
        }
    }
    if ($TestFailAfterReplace) {
        throw 'Injected post-replace cleanup failure.'
    }
}

function Assert-OaExactFile([string]$Path, [byte[]]$Expected) {
    [byte[]]$actual = [IO.File]::ReadAllBytes($Path)
    if (-not (Test-OaBytesEqual $actual $Expected)) {
        throw "Exact byte readback failed: $Path"
    }
}

function Assert-OaLiveFilesExact(
    [object[]]$States,
    [hashtable]$ExpectedByPath
) {
    foreach ($state in $States) {
        $path = [string]$state.Path
        if (-not $ExpectedByPath.ContainsKey($path) -or
            -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Client file changed after validation: $path"
        }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Client file became a reparse point after validation: $path"
        }

        [byte[]]$expected = $ExpectedByPath[$path]
        [byte[]]$actual = [IO.File]::ReadAllBytes($path)
        if ($actual.Length -ne $expected.Length -or
            (Get-OaSha256 $actual) -cne (Get-OaSha256 $expected) -or
            -not (Test-OaBytesEqual $actual $expected)) {
            throw "Client file changed after validation: $path"
        }
    }
}

function Restore-OaWrittenFiles([object[]]$Written, [hashtable]$BytesByPath) {
    for ($index = $Written.Count - 1; $index -ge 0; $index--) {
        $path = [string]$Written[$index]
        Write-OaAtomicExact $path $BytesByPath[$path]
        Assert-OaExactFile $path $BytesByPath[$path]
    }
}
