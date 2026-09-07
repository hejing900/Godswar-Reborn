$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$curlyApostrophe = [char]0x2019
$emDash = [char]0x2014

$patcher = Join-Path $PSScriptRoot 'PatchClientLevelSealerDialogue.ps1'
if (-not (Test-Path -LiteralPath $patcher -PathType Leaf)) {
    throw "Level Sealer dialogue patcher was not found: $patcher"
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Assert-Equal($Expected, $Actual, [string]$Message) {
    if ($Expected -cne $Actual) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-Throws([scriptblock]$Action, [string]$Pattern, [string]$Message) {
    try {
        & $Action
    }
    catch {
        if ($_.Exception.Message -match $Pattern) {
            return
        }
        throw "$Message Unexpected error: $($_.Exception.Message)"
    }
    throw "$Message No error was raised."
}

function Write-Utf16LeBom([string]$Path, [string]$Text) {
    $directory = Split-Path -Parent $Path
    [void](New-Item -ItemType Directory -Path $directory -Force)
    [byte[]]$body = [Text.UnicodeEncoding]::new(
        $false,
        $false,
        $true).GetBytes($Text)
    [byte[]]$data = [byte[]]::new($body.Length + 2)
    $data[0] = 0xFF
    $data[1] = 0xFE
    [Array]::Copy($body, 0, $data, 2, $body.Length)
    [IO.File]::WriteAllBytes($Path, $data)
}

function Read-Utf16LeBom([string]$Path) {
    [byte[]]$data = [IO.File]::ReadAllBytes($Path)
    Assert-True (
        $data.Length -ge 2 -and
        $data[0] -eq 0xFF -and
        $data[1] -eq 0xFE) 'UTF-16LE BOM was not preserved.'
    return [Text.Encoding]::Unicode.GetString($data, 2, $data.Length - 2)
}

$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) (
    'reborn-level-sealer-dialogue-' + [Guid]::NewGuid().ToString('N'))
$clientRoot = Join-Path $fixtureRoot 'client'
$backupRoot = Join-Path $fixtureRoot 'backups'
$npcPath = Join-Path $clientRoot (
    'Localization\en_us\Text\NPCDescription.dat')
$luaPath = Join-Path $clientRoot (
    'Localization\en_us\UI\Base\LuaText.lua')

$athensOriginal =
    'Athens_142' + "`t" +
    "Ah, a bold adventurer! If you${curlyApostrophe}ve reached the Level 89, would you " +
    "like me to seal your level? Once sealed, you${curlyApostrophe}ll remain at 89 but " +
    "can still gain experience. This is useful for honing your skills " +
    "and earning rewards without leveling up further. Think carefully$emDash" +
    "once sealed, you${curlyApostrophe}ll be locked at this level until you choose to " +
    "unseal. If you${curlyApostrophe}re ready, let me know, and I${curlyApostrophe}ll take care of the rest."
$spartaOriginal =
    'Sparta_142' + "`t" +
    "Ah, a bold adventurer! I see you${curlyApostrophe}ve reached the Level 89. Would " +
    "you like me to seal your level? Once sealed, you${curlyApostrophe}ll remain at 89 " +
    "but can still gain experience. This is useful for honing your " +
    "skills and earning rewards without leveling up further. Think " +
    "carefully$emDash" + "once sealed, you${curlyApostrophe}ll be locked at this level until you " +
    "choose to unseal. If you${curlyApostrophe}re ready, let me know, and I${curlyApostrophe}ll take care " +
    "of the rest."
$luaOriginal = @'
Before = "untouched"
Seal1 = "Are you sure you want to Seal your level to 89? It will cost 10000 Gold."
Seal2 = "|cffFFFF00Seal my Level (10000 Gold)|cffffffff"
Seal3 = "|cffFFFF00Unseal my Level|cffffffff"
Seal4 = "You dont have the 10000 Gold required to Seal your Level."
Seal5 = "To Seal your level, you should be exactly at Level 89."
Seal6 = "Your level has been sealed to level 89. If you ever change your mind, come talk to me."
Seal7 = "Your level has been unsealed. You will continue leveling up once you meet the EXP requirements."
Seal8 = "Your level is not sealed."
Seal9 = "Your level has already been sealed."
After = "untouched"
'@

try {
    foreach ($protectedName in @(
            'B20H',
            'Godswar Origin B20H',
            'b20h-preview')) {
        $protectedRoot = Join-Path $fixtureRoot $protectedName
        Assert-Throws {
            & $patcher -Mode Status -ClientRoot $protectedRoot
        } 'protected B20H client tree' (
            "Protected client path was accepted: $protectedRoot")
    }

    [void](New-Item -ItemType Directory -Path $clientRoot)
    Write-Utf16LeBom $npcPath (-join @(
        "Athens_141`tFaction Crier stays untouched.`r`n",
        $athensOriginal, "`r`n",
        $spartaOriginal, "`r`n",
        "Sparta_143`tAfter stays untouched.`r`n"))
    $luaDirectory = Split-Path -Parent $luaPath
    [void](New-Item -ItemType Directory -Path $luaDirectory -Force)
    [IO.File]::WriteAllText(
        $luaPath,
        $luaOriginal.Replace("`n", "`r`n"),
        [Text.UTF8Encoding]::new($false))

    [byte[]]$npcBefore = [IO.File]::ReadAllBytes($npcPath)
    [byte[]]$luaBefore = [IO.File]::ReadAllBytes($luaPath)
    $status = & $patcher -Mode Status -ClientRoot $clientRoot
    Assert-Equal 'Original' $status.State 'Initial state mismatch.'

    $apply = & $patcher -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-Equal 'Applied' $apply.State 'Apply state mismatch.'
    Assert-Equal $true $apply.Changed 'Apply should report a change.'
    Assert-True (
        (Test-Path -LiteralPath $apply.Receipt -PathType Leaf)) (
        'Apply did not create a rollback receipt.')

    $npcAfter = Read-Utf16LeBom $npcPath
    Assert-True (
        $npcAfter.Contains("Athens_141`tFaction Crier stays untouched.")) (
        'The Faction Crier entry changed.')
    Assert-True (
        -not $npcAfter.Contains('Level 89') -and
        ([regex]::Matches(
            $npcAfter,
            'any player at any level can use this service\.')).Count -eq 2) (
        'Both local Level Sealer descriptions were not generalized.')

    [byte[]]$luaAppliedBytes = [IO.File]::ReadAllBytes($luaPath)
    [byte[]]$npcAppliedBytes = [IO.File]::ReadAllBytes($npcPath)
    Assert-True (
        -not ($luaAppliedBytes.Length -ge 3 -and
            $luaAppliedBytes[0] -eq 0xEF -and
            $luaAppliedBytes[1] -eq 0xBB -and
            $luaAppliedBytes[2] -eq 0xBF)) (
        'LuaText.lua unexpectedly gained a BOM.')
    $luaAfter = [Text.UTF8Encoding]::new(
        $false,
        $true).GetString($luaAppliedBytes)
    Assert-True (
        $luaAfter.Contains('*Seal my level for free') -and
        $luaAfter.Contains('*Unseal my level for 10,000 Bound Gold.')) (
        'The player-facing choices were not patched.')
    Assert-True (
        $luaAfter.Contains("Before = `"untouched`"") -and
        $luaAfter.Contains("After = `"untouched`"")) (
        'Non-target Lua text changed.')

    $secondApply = & $patcher -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-Equal $false $secondApply.Changed (
        'A second Apply should be idempotent.')

    $revert = & $patcher -Mode Revert -ClientRoot $clientRoot `
        -ReceiptPath $apply.Receipt -Confirm:$false
    Assert-Equal 'Original' $revert.State 'Revert state mismatch.'
    Assert-True (
        [Linq.Enumerable]::SequenceEqual(
            [IO.File]::ReadAllBytes($npcPath),
            $npcBefore)) 'NPCDescription rollback was not byte-exact.'
    Assert-True (
        [Linq.Enumerable]::SequenceEqual(
            [IO.File]::ReadAllBytes($luaPath),
            $luaBefore)) 'LuaText rollback was not byte-exact.'

    [IO.File]::WriteAllBytes($npcPath, $npcAppliedBytes)
    $mixedStatus = & $patcher -Mode Status -ClientRoot $clientRoot
    Assert-Equal 'Upgradable' $mixedStatus.State (
        'Mixed original/applied state was not recognized.')
    $mixedApply = & $patcher -Mode Apply -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Confirm:$false
    Assert-Equal 'Applied' $mixedApply.State (
        'Mixed-state apply did not converge to Applied.')
    $mixedRevert = & $patcher -Mode Revert -ClientRoot $clientRoot `
        -ReceiptPath $mixedApply.Receipt -Confirm:$false
    Assert-Equal 'Upgradable' $mixedRevert.State (
        'Mixed-state revert did not report the restored state.')
    Assert-True (
        [Linq.Enumerable]::SequenceEqual(
            [IO.File]::ReadAllBytes($npcPath),
            $npcAppliedBytes)) (
        'Mixed-state NPC rollback was not byte-exact.')
    Assert-True (
        [Linq.Enumerable]::SequenceEqual(
            [IO.File]::ReadAllBytes($luaPath),
            $luaBefore)) (
        'Mixed-state Lua rollback was not byte-exact.')

    [pscustomobject]@{
        Passed = $true
        Cases = @(
            'strict original-state recognition',
            'UTF-16LE BOM and UTF-8 no-BOM preservation',
            'local 142-only dialogue replacement',
            'external-capture economy wording',
            'protected B20H path-family rejection',
            'idempotent apply',
            'receipt-backed byte-exact rollback',
            'mixed-state rollback reporting')
    }
}
finally {
    if (Test-Path -LiteralPath $fixtureRoot) {
        $resolved = [IO.Path]::GetFullPath($fixtureRoot)
        $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $resolved.StartsWith(
                $temporaryRoot,
                [StringComparison]::OrdinalIgnoreCase) -or
            $resolved -ceq $temporaryRoot) {
            throw 'Refusing unsafe Level Sealer fixture cleanup target.'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
