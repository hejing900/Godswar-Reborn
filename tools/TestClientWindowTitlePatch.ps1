[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$patcher = Join-Path $PSScriptRoot 'PatchClientWindowTitle.ps1'
if ((Get-Item -LiteralPath $patcher).Length -ge 20KB) {
    throw 'PatchClientWindowTitle.ps1 exceeds the repository 20KB limit.'
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Write-Fixture {
    param(
        [string]$Root,
        [string]$Locale,
        [string]$Title,
        [string]$Area
    )

    $path = Join-Path $Root "Localization\$Locale\Text\Message.dat"
    [IO.Directory]::CreateDirectory(
        [IO.Path]::GetDirectoryName($path)) | Out-Null
    $text = "//{vUI_`t`r`n" +
        "LogoText`tUnrelated brand text`r`n" +
        "AppTitle`t$Title`r`n" +
        "AreaTitle11`t$Area`r`n" +
        "AreaTitle12`t$Area`r`n" +
        "AreaTitle13`t[Facebook]`r`n" +
        "Tail`tunchanged`r`n"
    [IO.File]::WriteAllText(
        $path,
        $text,
        [Text.UnicodeEncoding]::new($false, $true, $true))
    return $path
}

function Write-OriginFixture {
    param(
        [string]$Root,
        [switch]$UnknownFormat,
        [switch]$LegacyPatched
    )

    $path = Join-Path $Root 'Origin.exe'
    [IO.Directory]::CreateDirectory($Root) | Out-Null
    $formatOffset = 0x554FCC
    $suffixOffset = 0x557904
    $sharedOperand = [BitConverter]::GetBytes([uint32]0x00954FCC)
    $sharedCallOperands = @(
        0x0D8047,
        0x17EB07,
        0x1CEEA4,
        0x1E487F,
        0x1E743E)
    $bytes = [byte[]]::new($suffixOffset + 16)
    $bytes[0] = 0x4D
    $bytes[1] = 0x5A
    [Array]::Copy(
        [Text.Encoding]::ASCII.GetBytes("AppTitle`0"),
        0,
        $bytes,
        0x554F78,
        9)
    [Array]::Copy(
        [Text.Encoding]::Unicode.GetBytes("%s`0"),
        0,
        $bytes,
        0x551528,
        6)
    foreach ($operandOffset in $sharedCallOperands) {
        $bytes[$operandOffset - 1] = 0x68
        [Array]::Copy(
            $sharedOperand, 0, $bytes, $operandOffset, 4)
    }
    $formatText = if ($UnknownFormat) {
        "?s ?s`0"
    }
    elseif ($LegacyPatched) {
        "%s`0`0`0`0"
    }
    else {
        "%s %s`0"
    }
    $format = [Text.Encoding]::Unicode.GetBytes($formatText)
    [Array]::Copy($format, 0, $bytes, $formatOffset, $format.Length)
    $suffix = [Text.Encoding]::Unicode.GetBytes(" - `0")
    [Array]::Copy($suffix, 0, $bytes, $suffixOffset, $suffix.Length)
    [IO.File]::WriteAllBytes($path, $bytes)
    return $path
}

function Get-Hash {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-BytesHash {
    param([byte[]]$Bytes)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $algorithm.ComputeHash($Bytes))).Replace('-', '')
    }
    finally {
        $algorithm.Dispose()
    }
}

$testRoot = Join-Path ([IO.Path]::GetTempPath()) (
    'reborn-window-title-' + [Guid]::NewGuid().ToString('N'))
$clientRoot = Join-Path $testRoot 'client'
$backupRoot = Join-Path $testRoot 'backups'
[IO.Directory]::CreateDirectory($clientRoot) | Out-Null
$chinesePristineTitle = -join @(
    [char]0x795E,
    [char]0x6218,
    [char]0x8D77,
    [char]0x6E90)
$chineseArea = '[' + [char]0x7F8E + [char]0x56FD + ']'

try {
    $en = Write-Fixture $clientRoot 'en_us' 'Godswar Origin' '[USA]'
    $zh = Write-Fixture `
        $clientRoot 'zh_cn' $chinesePristineTitle $chineseArea
    $origin = Write-OriginFixture $clientRoot
    $originalEnHash = Get-Hash $en
    $originalZhHash = Get-Hash $zh
    $originalOriginHash = Get-Hash $origin

    $status = & $patcher -Mode Status -ClientRoot $clientRoot
    Assert-True ($status.State -ceq 'Pristine') `
        'Pristine status was not recognized.'
    Assert-True ($status.LoginTitle -ceq 'Godswar Origin [USA]' -and
        $status.Executable.State -ceq 'Pristine') `
        'Pristine title composition was not recognized.'

    $applied = & $patcher -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -AllowMutation
    Assert-True ($applied.State -ceq 'Patched') `
        'Apply did not produce the patched state.'
    Assert-True ($applied.LoginTitle -ceq 'Godswar Reborn' -and
        $applied.RealmTitleTemplate -ceq
            'Godswar Reborn - <realm>') `
        'Apply did not remove the region while preserving the realm suffix.'
    Assert-True (-not [string]::IsNullOrWhiteSpace(
            $applied.BackupDirectory)) `
        'Apply did not report its verified backup directory.'

    foreach ($path in @($en, $zh)) {
        $bytes = [IO.File]::ReadAllBytes($path)
        Assert-True ($bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) `
            "$path lost its UTF-16LE BOM."
        $text = [Text.Encoding]::Unicode.GetString(
            $bytes, 2, $bytes.Length - 2)
        Assert-True ($text -match '(?m)^AppTitle\tGodswar Reborn\r$') `
            "$path did not receive the target AppTitle."
        Assert-True ($text -match '(?m)^LogoText\tUnrelated brand text\r$') `
            "$path changed an unrelated localization record."
        Assert-True ($text -match '(?m)^AreaTitle13\t\[Facebook\]\r$') `
            "$path changed the region-title contract."
    }
    Assert-True ((Get-Content -LiteralPath $en -Encoding Unicode -Raw) -match
            '(?m)^AreaTitle11\t\[USA\]\r$') `
        'Apply changed the USA region suffix.'
    Assert-True ((Get-Content -LiteralPath $zh -Encoding Unicode -Raw) -match
            "(?m)^AreaTitle11\t$([regex]::Escape($chineseArea))\r`$") `
        'Apply changed the Chinese region suffix.'
    $originBytes = [IO.File]::ReadAllBytes($origin)
    $sharedFormat = [Text.Encoding]::Unicode.GetBytes("%s %s`0")
    $sharedOperand = [BitConverter]::GetBytes([uint32]0x00954FCC)
    $baseOnlyOperand = [BitConverter]::GetBytes([uint32]0x00951528)
    $dynamicSuffix = [Text.Encoding]::Unicode.GetBytes(" - `0")
    $actualSharedFormat = $originBytes[
        0x554FCC..(0x554FCC + $sharedFormat.Length - 1)]
    $actualTitleOperand = $originBytes[
        0x0D8047..(0x0D8047 + $baseOnlyOperand.Length - 1)]
    $actualDynamicSuffix = $originBytes[
        0x557904..(0x557904 + $dynamicSuffix.Length - 1)]
    Assert-True ($null -eq (Compare-Object `
            $sharedFormat $actualSharedFormat)) `
        'Apply changed the shared two-string format.'
    Assert-True ($null -eq (Compare-Object `
            $baseOnlyOperand $actualTitleOperand)) `
        'Apply did not redirect only the title caller.'
    foreach ($operandOffset in @(0x17EB07, 0x1CEEA4, 0x1E487F, 0x1E743E)) {
        $actualOperand = $originBytes[
            $operandOffset..($operandOffset + $sharedOperand.Length - 1)]
        Assert-True ($null -eq (Compare-Object `
                $sharedOperand $actualOperand)) `
            "Apply redirected shared consumer 0x$($operandOffset.ToString('X'))."
    }
    Assert-True ($null -eq (Compare-Object `
            $dynamicSuffix $actualDynamicSuffix)) `
        'Apply changed the native dynamic realm separator.'

    $second = & $patcher -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -AllowMutation
    Assert-True ($second.State -ceq 'Patched' -and
        [string]::IsNullOrWhiteSpace($second.BackupDirectory)) `
        'An idempotent Apply unexpectedly created another backup.'

    $rolledBack = & $patcher -Mode Rollback -ClientRoot $clientRoot `
        -RollbackFrom $applied.BackupDirectory -AllowMutation
    Assert-True ($rolledBack.State -ceq 'Pristine') `
        'Rollback did not restore the pristine state.'
    Assert-True ((Get-Hash $en) -ceq $originalEnHash -and
        (Get-Hash $zh) -ceq $originalZhHash -and
        (Get-Hash $origin) -ceq $originalOriginHash) `
        'Rollback did not restore the exact original bytes.'

    $legacyRoot = Join-Path $testRoot 'legacy-client'
    $null = Write-Fixture $legacyRoot 'en_us' 'Godswar Reborn' '[USA]'
    $null = Write-Fixture `
        $legacyRoot 'zh_cn' 'Godswar Reborn' $chineseArea
    $legacyOrigin = Write-OriginFixture $legacyRoot -LegacyPatched
    $legacyHash = Get-Hash $legacyOrigin
    $legacyBytes = [IO.File]::ReadAllBytes($legacyOrigin)
    $legacyStatus = & $patcher -Mode Status -ClientRoot $legacyRoot
    Assert-True ($legacyStatus.State -ceq 'LegacyPatched' -and
        $legacyStatus.Executable.State -ceq 'LegacyPatched') `
        'The shared-literal legacy patch was not recognized.'
    $migrated = & $patcher -Mode Apply -ClientRoot $legacyRoot `
        -BackupRoot $backupRoot -AllowMutation
    Assert-True ($migrated.State -ceq 'Patched') `
        'Apply did not migrate the shared-literal legacy patch.'
    $legacyBackupOrigin = Join-Path $migrated.BackupDirectory 'Origin.exe'
    $legacyManifest = Get-Content -LiteralPath (
        Join-Path $migrated.BackupDirectory 'manifest.json') `
        -Encoding UTF8 -Raw | ConvertFrom-Json
    Assert-True ($legacyManifest.contractVersion -eq 3 -and
        (Get-Hash $legacyBackupOrigin) -ceq $legacyHash) `
        'Legacy migration did not retain a verified version-3 backup.'
    $migratedBytes = [IO.File]::ReadAllBytes($legacyOrigin)
    $expectedMigratedBytes = [byte[]]$legacyBytes.Clone()
    [Array]::Copy(
        $sharedFormat, 0, $expectedMigratedBytes, 0x554FCC, 12)
    [Array]::Copy(
        $baseOnlyOperand, 0, $expectedMigratedBytes, 0x0D8047, 4)
    $migratedShared = $migratedBytes[
        0x554FCC..(0x554FCC + $sharedFormat.Length - 1)]
    $migratedTitle = $migratedBytes[
        0x0D8047..(0x0D8047 + $baseOnlyOperand.Length - 1)]
    Assert-True ($null -eq (Compare-Object `
            $sharedFormat $migratedShared) -and
        $null -eq (Compare-Object $baseOnlyOperand $migratedTitle)) `
        'Legacy migration did not install the caller-specific contract.'
    Assert-True ((Get-BytesHash $migratedBytes) -ceq
        (Get-BytesHash $expectedMigratedBytes)) `
        'Legacy migration changed bytes outside the two reviewed ranges.'
    $legacyRollback = & $patcher -Mode Rollback -ClientRoot $legacyRoot `
        -RollbackFrom $migrated.BackupDirectory -AllowMutation
    Assert-True ($legacyRollback.State -ceq 'LegacyPatched' -and
        (Get-Hash $legacyOrigin) -ceq $legacyHash) `
        'Version-3 rollback did not restore the exact legacy executable.'

    $unknownRoot = Join-Path $testRoot 'unknown-client'
    $unknownEn = Write-Fixture $unknownRoot 'en_us' 'Unexpected Fork' '[USA]'
    $null = Write-Fixture `
        $unknownRoot 'zh_cn' $chinesePristineTitle $chineseArea
    $null = Write-OriginFixture $unknownRoot
    $unknownHash = Get-Hash $unknownEn
    $failedClosed = $false
    try {
        $null = & $patcher -Mode Apply -ClientRoot $unknownRoot `
            -BackupRoot $backupRoot -AllowMutation
    }
    catch {
        $failedClosed = $_.Exception.Message -like '*unknown*'
    }
    Assert-True $failedClosed 'Unknown AppTitle did not fail closed.'
    Assert-True ((Get-Hash $unknownEn) -ceq $unknownHash) `
        'Failed Apply changed the unknown fixture.'

    $unknownBinaryRoot = Join-Path $testRoot 'unknown-binary-client'
    $null = Write-Fixture `
        $unknownBinaryRoot 'en_us' 'Godswar Origin' '[USA]'
    $null = Write-Fixture `
        $unknownBinaryRoot 'zh_cn' $chinesePristineTitle $chineseArea
    $unknownOrigin = Write-OriginFixture $unknownBinaryRoot -UnknownFormat
    $unknownOriginHash = Get-Hash $unknownOrigin
    $binaryFailedClosed = $false
    try {
        $null = & $patcher -Mode Apply -ClientRoot $unknownBinaryRoot `
            -BackupRoot $backupRoot -AllowMutation
    }
    catch {
        $binaryFailedClosed = $_.Exception.Message -like '*unknown*'
    }
    Assert-True $binaryFailedClosed `
        'Unknown Origin.exe title format did not fail closed.'
    Assert-True ((Get-Hash $unknownOrigin) -ceq $unknownOriginHash) `
        'Failed Apply changed the unknown Origin.exe fixture.'

    'Client window-title patch checks passed.'
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
