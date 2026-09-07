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

$relativePath = 'Localization\en_us\Settings\Sys\NPC.INI'
$aliasNames = @(
    'Athens_142_LS',
    'gwprivate_Athens_142_LS',
    'Sparta_142_LS',
    'gwprivate_Sparta_142_LS')

function Get-FullPath([string]$Path) {
    [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Get-Sha256([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        ([BitConverter]::ToString($algorithm.ComputeHash($Data))).Replace('-', '')
    }
    finally {
        $algorithm.Dispose()
    }
}

function Assert-ClientClosed {
    $running = @(
        Get-Process -Name GWPrivateServer, Origin -ErrorAction SilentlyContinue)
    if ($running.Count -ne 0) {
        throw "Close the game client before patching it (PID: $(
            ($running.Id | Sort-Object) -join ', '))."
    }
}

function Read-ClientIni([string]$Path) {
    [byte[]]$data = [IO.File]::ReadAllBytes($Path)
    if ($data.Length -lt 2 -or $data[0] -ne 0xFF -or $data[1] -ne 0xFE) {
        throw "NPC.INI must be UTF-16LE with a BOM: $Path"
    }
    if (($data.Length % 2) -ne 0) {
        throw "NPC.INI has a truncated UTF-16 code unit: $Path"
    }
    $text = [Text.Encoding]::Unicode.GetString($data, 2, $data.Length - 2)
    if ($text -match "(?<!`r)`n|`r(?!`n)") {
        throw "NPC.INI must use CRLF consistently: $Path"
    }
    [pscustomobject]@{
        Data = $data
        Text = $text
        Sha256 = Get-Sha256 $data
    }
}

function New-AliasBlock([string]$SectionName) {
    @(
        "[$SectionName]",
        'name             =Level Sealer',
        'sex              =1',
        'avatar_body      =2211',
        'avatar_boots     =2902',
        'avatar_gloves    =0',
        'avatar_hair      =0',
        'avatar_head      =0',
        'avatar_cap       =0',
        'avatar_circle    =0',
        'avatar_leggins   =0',
        'avatar_sleeves   =0',
        'avatar_twohand   =1802',
        'avatar_bow       =0',
        'avatar_mainhand  =0',
        'avatar_shield    =0',
        'avatar_assistant =0',
        'Range            =1.0f',
        'Shadow           =1.5f',
        'MeshName         =null',
        'TextureName      =null',
        'avatar_effect_body      =0',
        'avatar_effect_weapon      =0',
        'avatar_effect_mainweapon      =0',
        'avatar_effect_assistantweapon       =0') -join "`r`n"
}

function Get-State([string]$Text) {
    $sections = foreach ($aliasName in $aliasNames) {
        $pattern = '(?ms)^\[' + [regex]::Escape($aliasName) +
            '\]\r\n.*?(?=^\[|\z)'
        $matches = [regex]::Matches($Text, $pattern)
        $expected = New-AliasBlock $aliasName
        $actual = if ($matches.Count -eq 1) {
            $matches[0].Value.TrimEnd("`r", "`n")
        }
        else {
            $null
        }
        [pscustomobject]@{
            Section = $aliasName
            State = if ($matches.Count -eq 0) {
                'Absent'
            }
            elseif ($matches.Count -eq 1 -and $actual -ceq $expected) {
                'Applied'
            }
            else {
                'Foreign'
            }
        }
    }
    $distinct = @($sections.State | Sort-Object -Unique)
    $overall = if ($distinct.Count -eq 1 -and $distinct[0] -ceq 'Absent') {
        'Original'
    }
    elseif ($distinct.Count -eq 1 -and $distinct[0] -ceq 'Applied') {
        'Applied'
    }
    else {
        'Partial'
    }
    [pscustomobject]@{
        State = $overall
        Sections = @($sections)
    }
}

function Convert-ToUtf16LeBom([string]$Text) {
    [byte[]]$body = [Text.Encoding]::Unicode.GetBytes($Text)
    [byte[]]$data = [byte[]]::new($body.Length + 2)
    $data[0] = 0xFF
    $data[1] = 0xFE
    [Array]::Copy($body, 0, $data, 2, $body.Length)
    $data
}

function Write-Atomic([string]$Path, [byte[]]$Data) {
    $directory = Split-Path -Parent $Path
    $token = [Guid]::NewGuid().ToString('N')
    $temporary = Join-Path $directory ('.level-sealer-' + $token + '.tmp')
    $replacementBackup = Join-Path $directory (
        '.level-sealer-' + $token + '.bak')
    try {
        [IO.File]::WriteAllBytes($temporary, $Data)
        [IO.File]::Replace($temporary, $Path, $replacementBackup)
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
        if (Test-Path -LiteralPath $replacementBackup) {
            Remove-Item -LiteralPath $replacementBackup -Force
        }
    }
}

$clientRootPath = Get-FullPath $ClientRoot
$iniPath = Join-Path $clientRootPath $relativePath
if (-not (Test-Path -LiteralPath $iniPath -PathType Leaf)) {
    throw "NPC.INI was not found: $iniPath"
}
$snapshot = Read-ClientIni $iniPath
$state = Get-State $snapshot.Text

if ($Mode -ceq 'Status') {
    [pscustomobject]@{
        Mode = 'Status'
        State = $state.State
        ClientRoot = $clientRootPath
        Path = $iniPath
        Sha256 = $snapshot.Sha256
        Sections = $state.Sections
    }
    return
}

Assert-ClientClosed
if ($Mode -ceq 'Apply') {
    if ($state.State -ceq 'Applied') {
        [pscustomobject]@{ Mode = 'Apply'; State = 'Applied'; Changed = $false }
        return
    }
    if ($state.State -cne 'Original') {
        throw "Refusing to patch Level Sealer aliases in state '$($state.State)'."
    }
    $backupRootPath = Get-FullPath $BackupRoot
    if (-not (Test-Path -LiteralPath $backupRootPath -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $backupRootPath)
    }
    $backupDirectory = Join-Path $backupRootPath (
        'client-level-sealer-' +
        [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' +
        [Guid]::NewGuid().ToString('N').Substring(0, 8))
    [void](New-Item -ItemType Directory -Path $backupDirectory)
    $backupPath = Join-Path $backupDirectory 'NPC.INI'
    [IO.File]::WriteAllBytes($backupPath, $snapshot.Data)

    $patchedText = $snapshot.Text.TrimEnd("`r", "`n") + "`r`n"
    foreach ($aliasName in $aliasNames) {
        $patchedText += (New-AliasBlock $aliasName) + "`r`n"
    }
    [byte[]]$patchedData = Convert-ToUtf16LeBom $patchedText
    $afterSha256 = Get-Sha256 $patchedData
    if (-not $PSCmdlet.ShouldProcess(
            $iniPath,
            'Install resolvable Level Sealer NPC aliases')) {
        return
    }
    Write-Atomic $iniPath $patchedData

    $receiptPath = Join-Path $backupDirectory 'receipt.json'
    $receipt = [ordered]@{
        Schema = 2
        Patch = 'client-level-sealer-appearance'
        ClientRoot = $clientRootPath
        Path = $iniPath
        BackupPath = $backupPath
        BeforeSha256 = $snapshot.Sha256
        AfterSha256 = $afterSha256
    }
    [IO.File]::WriteAllText(
        $receiptPath,
        ($receipt | ConvertTo-Json) + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false))
    $after = Read-ClientIni $iniPath
    $afterState = Get-State $after.Text
    if ($after.Sha256 -cne $afterSha256 -or $afterState.State -cne 'Applied') {
        Write-Atomic $iniPath $snapshot.Data
        throw 'Level Sealer client alias patch failed readback validation.'
    }
    [pscustomobject]@{
        Mode = 'Apply'
        State = 'Applied'
        Changed = $true
        Receipt = $receiptPath
    }
    return
}

if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    throw 'Revert requires -ReceiptPath from Apply.'
}
$receipt = Get-Content -LiteralPath (Get-FullPath $ReceiptPath) -Raw |
    ConvertFrom-Json
if ($receipt.Schema -ne 2 -or
    $receipt.Patch -cne 'client-level-sealer-appearance' -or
    (Get-FullPath ([string]$receipt.ClientRoot)) -cne $clientRootPath -or
    [string]$receipt.Path -cne $iniPath -or
    $snapshot.Sha256 -cne [string]$receipt.AfterSha256) {
    throw 'Revert receipt does not match the current client state.'
}
[byte[]]$backup = [IO.File]::ReadAllBytes([string]$receipt.BackupPath)
if ((Get-Sha256 $backup) -cne [string]$receipt.BeforeSha256) {
    throw 'Level Sealer backup checksum is invalid.'
}
if ($PSCmdlet.ShouldProcess($iniPath, 'Restore original Level Sealer aliases')) {
    Write-Atomic $iniPath $backup
}
[pscustomobject]@{ Mode = 'Revert'; State = 'Original'; Changed = $true }
