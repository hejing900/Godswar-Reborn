$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$patcher = Join-Path $PSScriptRoot 'PatchClientTalentPointGainNotification.ps1'
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "reborn-talent-note-test-$([Guid]::NewGuid().ToString('N'))")
$temporaryRoot = [IO.Path]::GetFullPath($temporaryRoot)
$systemTemporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
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
if (-not $temporaryRoot.StartsWith(
    $systemTemporaryRoot,
    [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Fixture path escaped the system temporary directory.'
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Test-BytesEqual([byte[]]$Left, [byte[]]$Right) {
    if ($Left.Length -ne $Right.Length) { return $false }
    for ($index = 0; $index -lt $Left.Length; $index++) {
        if ($Left[$index] -ne $Right[$index]) { return $false }
    }
    return $true
}

function New-Utf16Table([string]$Path, [string[]]$Rows) {
    $text = ($Rows -join "`r`n") + "`r`n"
    [byte[]]$payload = [Text.Encoding]::Unicode.GetBytes($text)
    [byte[]]$data = [byte[]]::new($payload.Length + 2)
    $data[0] = 0xFF
    $data[1] = 0xFE
    [Array]::Copy($payload, 0, $data, 2, $payload.Length)
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    [IO.File]::WriteAllBytes($Path, $data)
}

try {
    $actualPointCodePoints = @($chineseTalentPoints.ToCharArray() | ForEach-Object { [int]$_ })
    $expectedPointCodePoints = @(0x5929, 0x8D4B, 0x70B9, 0x6570, 0xFF1A)
    Assert-True ($actualPointCodePoints.Count -eq $expectedPointCodePoints.Count) `
        'Chinese target codepoint count changed.'
    for ($index = 0; $index -lt $expectedPointCodePoints.Count; $index++) {
        Assert-True ($actualPointCodePoints[$index] -eq $expectedPointCodePoints[$index]) `
            "Chinese target codepoint $index changed."
    }
    $client = Join-Path $temporaryRoot 'client'
    $backups = Join-Path $temporaryRoot 'backups'
    [IO.Directory]::CreateDirectory($client) | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $client 'Origin.exe'), [byte[]](0x4D, 0x5A))
    $english = Join-Path $client 'Localization\en_us\Text\Message.dat'
    $chinese = Join-Path $client 'Localization\zh_cn\Text\Message.dat'
    New-Utf16Table $english @(
        "Header`tValue",
        "Attr_Note_4`tTalent Exp:",
        "Tail`tValue")
    New-Utf16Table $chinese @(
        "Header`tValue",
        "Attr_Note_4`t$chineseTalentExperience",
        "Tail`tValue")
    [byte[]]$englishBefore = [IO.File]::ReadAllBytes($english)
    [byte[]]$chineseBefore = [IO.File]::ReadAllBytes($chinese)

    $status = & $patcher -Mode Status -ClientRoot $client -BackupRoot $backups
    Assert-True ($status.State -ceq 'Absent') 'Initial state was not Absent.'
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
    $applied = & $patcher -Mode Apply -ClientRoot $client -BackupRoot $backups -Confirm:$false
    Assert-True ($applied.Changed -and $applied.State -ceq 'Applied') 'Apply failed.'
    Assert-True (Test-Path -LiteralPath $applied.Receipt -PathType Leaf) 'Receipt missing.'

    $englishText = [Text.Encoding]::Unicode.GetString(
        [IO.File]::ReadAllBytes($english), 2, (Get-Item $english).Length - 2)
    $chineseText = [Text.Encoding]::Unicode.GetString(
        [IO.File]::ReadAllBytes($chinese), 2, (Get-Item $chinese).Length - 2)
    Assert-True ($englishText.Contains("Attr_Note_5`t Talent Points:`r`n")) 'English row missing.'
    Assert-True ($chineseText.Contains(
        "Attr_Note_5`t$chineseTalentPoints`r`n")) 'Chinese row missing.'
    Assert-True ($englishText -notmatch "(?<!`r)`n|`r(?!`n)") 'English EOL changed.'
    Assert-True ($chineseText -notmatch "(?<!`r)`n|`r(?!`n)") 'Chinese EOL changed.'

    $noOp = & $patcher -Mode Apply -ClientRoot $client -BackupRoot $backups -Confirm:$false
    Assert-True (-not $noOp.Changed) 'Second Apply was not idempotent.'
    $reverted = & $patcher -Mode Revert -ClientRoot $client `
        -BackupRoot $backups -ReceiptPath $applied.Receipt -Confirm:$false
    Assert-True ($reverted.Changed -and $reverted.State -ceq 'Absent') 'Revert failed.'
    Assert-True (Test-BytesEqual ([IO.File]::ReadAllBytes($english)) $englishBefore) `
        'English was not restored byte-for-byte.'
    Assert-True (Test-BytesEqual ([IO.File]::ReadAllBytes($chinese)) $chineseBefore) `
        'Chinese was not restored byte-for-byte.'
    $revertNoOp = & $patcher -Mode Revert -ClientRoot $client `
        -BackupRoot $backups -ReceiptPath $applied.Receipt -Confirm:$false
    Assert-True (-not $revertNoOp.Changed) 'Second Revert was not idempotent.'

    New-Utf16Table $english @(
        "Attr_Note_4`tTalent Exp:",
        "Attr_Note_5`tWrong")
    $foreignRejected = $false
    try {
        & $patcher -Mode Status -ClientRoot $client -BackupRoot $backups | Out-Null
    }
    catch {
        $foreignRejected = $_.Exception.Message -like '*unsupported value*'
    }
    Assert-True $foreignRejected 'Foreign Attr_Note_5 value was accepted.'

    [pscustomobject]@{
        Result = 'Pass'
        ApplyAndRevert = $true
        ByteExactRestore = $true
        UnsafeBackupRejected = $true
        ForeignValueRejected = $true
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
