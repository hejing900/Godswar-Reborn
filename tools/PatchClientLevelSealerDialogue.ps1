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

$patchName = 'client-level-sealer-dialogue'
$receiptSchema = 1
$curlyApostrophe = [char]0x2019
$emDash = [char]0x2014
$newDescription =
    "I can help you seal your level $emDash there are no restrictions; " +
    'any player at any level can use this service.'

$specifications = @(
    [pscustomobject]@{
        Role = 'NpcDescription'
        RelativePath = 'Localization\en_us\Text\NPCDescription.dat'
        Encoding = 'Utf16LeBom'
        BackupName = 'en_us-NPCDescription.dat'
        Targets = @(
            [pscustomobject]@{
                Key = 'Athens_142'
                Original = 'Athens_142' + "`t" +
                    "Ah, a bold adventurer! If you${curlyApostrophe}ve reached the Level 89, " +
                    "would you like me to seal your level? Once sealed, " +
                    "you${curlyApostrophe}ll remain at 89 but can still gain experience. " +
                    "This is useful for honing your skills and earning " +
                    "rewards without leveling up further. Think carefully$emDash" +
                    "once sealed, you${curlyApostrophe}ll be locked at this level until you " +
                    "choose to unseal. If you${curlyApostrophe}re ready, let me know, and " +
                    "I${curlyApostrophe}ll take care of the rest."
                Applied = 'Athens_142' + "`t" + $newDescription
            },
            [pscustomobject]@{
                Key = 'Sparta_142'
                Original = 'Sparta_142' + "`t" +
                    "Ah, a bold adventurer! I see you${curlyApostrophe}ve reached the Level " +
                    "89. Would you like me to seal your level? Once sealed, " +
                    "you${curlyApostrophe}ll remain at 89 but can still gain experience. " +
                    "This is useful for honing your skills and earning " +
                    "rewards without leveling up further. Think carefully$emDash" +
                    "once sealed, you${curlyApostrophe}ll be locked at this level until you " +
                    "choose to unseal. If you${curlyApostrophe}re ready, let me know, and " +
                    "I${curlyApostrophe}ll take care of the rest."
                Applied = 'Sparta_142' + "`t" + $newDescription
            })
    },
    [pscustomobject]@{
        Role = 'LuaText'
        RelativePath = 'Localization\en_us\UI\Base\LuaText.lua'
        Encoding = 'Utf8NoBom'
        BackupName = 'en_us-LuaText.lua'
        Targets = @(
            [pscustomobject]@{
                Key = 'Seal1'
                Original = 'Seal1 = "Are you sure you want to Seal your level to 89? It will cost 10000 Gold."'
                Applied = 'Seal1 = "' + $newDescription + '"'
            },
            [pscustomobject]@{
                Key = 'Seal2'
                Original = 'Seal2 = "|cffFFFF00Seal my Level (10000 Gold)|cffffffff"'
                Applied = 'Seal2 = "|cffFFFF00*Seal my level for free|cffffffff"'
            },
            [pscustomobject]@{
                Key = 'Seal3'
                Original = 'Seal3 = "|cffFFFF00Unseal my Level|cffffffff"'
                Applied = 'Seal3 = "|cffFFFF00*Unseal my level for 10,000 Bound Gold.|cffffffff"'
            },
            [pscustomobject]@{
                Key = 'Seal4'
                Original = 'Seal4 = "You dont have the 10000 Gold required to Seal your Level."'
                Applied = 'Seal4 = "You don''t have sufficient funds."'
            },
            [pscustomobject]@{
                Key = 'Seal5'
                Original = 'Seal5 = "To Seal your level, you should be exactly at Level 89."'
                Applied = 'Seal5 = "The request could not be completed. Please try again."'
            },
            [pscustomobject]@{
                Key = 'Seal6'
                Original = 'Seal6 = "Your level has been sealed to level 89. If you ever change your mind, come talk to me."'
                Applied = 'Seal6 = "Success! Your level has been sealed."'
            },
            [pscustomobject]@{
                Key = 'Seal7'
                Original = 'Seal7 = "Your level has been unsealed. You will continue leveling up once you meet the EXP requirements."'
                Applied = 'Seal7 = "Success! Your level has been unsealed."'
            },
            [pscustomobject]@{
                Key = 'Seal8'
                Original = 'Seal8 = "Your level is not sealed."'
                Applied = 'Seal8 = "Your level has already been unsealed."'
            },
            [pscustomobject]@{
                Key = 'Seal9'
                Original = 'Seal9 = "Your level has already been sealed."'
                Applied = 'Seal9 = "Your level has already been sealed."'
            })
    })

function Get-FullPath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.Equals($root, [StringComparison]::OrdinalIgnoreCase)) {
        return $root
    }
    return $fullPath.TrimEnd('\', '/')
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

function Get-Sha256([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $algorithm.ComputeHash($Data))).Replace('-', '')
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

function ConvertFrom-ExactBytes([byte[]]$Data, [string]$Encoding) {
    if ($Encoding -ceq 'Utf8NoBom') {
        if ($Data.Length -ge 3 -and
            $Data[0] -eq 0xEF -and
            $Data[1] -eq 0xBB -and
            $Data[2] -eq 0xBF) {
            throw 'LuaText.lua must remain UTF-8 without a BOM.'
        }
        return [Text.UTF8Encoding]::new($false, $true).GetString($Data)
    }

    if ($Data.Length -lt 2 -or
        $Data[0] -ne 0xFF -or
        $Data[1] -ne 0xFE -or
        ($Data.Length % 2) -ne 0) {
        throw 'NPCDescription.dat must remain UTF-16LE with a BOM.'
    }
    return [Text.UnicodeEncoding]::new(
        $false,
        $true,
        $true).GetString($Data, 2, $Data.Length - 2)
}

function ConvertTo-ExactBytes([string]$Text, [string]$Encoding) {
    if ($Encoding -ceq 'Utf8NoBom') {
        return [Text.UTF8Encoding]::new($false, $true).GetBytes($Text)
    }

    [byte[]]$body = [Text.UnicodeEncoding]::new(
        $false,
        $false,
        $true).GetBytes($Text)
    [byte[]]$data = [byte[]]::new($body.Length + 2)
    $data[0] = 0xFF
    $data[1] = 0xFE
    [Array]::Copy($body, 0, $data, 2, $body.Length)
    return $data
}

function Get-FilePlan([string]$Root, [object]$Specification) {
    $path = Join-Path $Root $Specification.RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Level Sealer localization file was not found: $path"
    }
    $item = Get-Item -LiteralPath $path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Level Sealer localization file must not be a reparse point: $path"
    }

    [byte[]]$data = [IO.File]::ReadAllBytes($path)
    $text = ConvertFrom-ExactBytes $data $Specification.Encoding
    $targetStates = [Collections.Generic.List[string]]::new()
    foreach ($target in $Specification.Targets) {
        $pattern = '(?m)^' + [regex]::Escape($target.Key) +
            '[^\r\n]*(?=\r?$)'
        $matches = [regex]::Matches($text, $pattern)
        if ($matches.Count -ne 1) {
            throw "Expected one $($target.Key) line in $path; found $($matches.Count)."
        }
        $actual = $matches[0].Value
        if ($target.Original -ceq $target.Applied) {
            if ($actual -cne $target.Original) {
                throw "Refusing foreign Level Sealer text for $($target.Key) in $path."
            }
            continue
        }
        if ($actual -ceq $target.Applied) {
            $targetStates.Add('Applied')
            continue
        }
        if ($actual -cne $target.Original) {
            throw "Refusing foreign Level Sealer text for $($target.Key) in $path."
        }
        $targetStates.Add('Original')
        $text = $text.Remove($matches[0].Index, $matches[0].Length).Insert(
            $matches[0].Index,
            $target.Applied)
    }
    [byte[]]$plannedData = ConvertTo-ExactBytes $text $Specification.Encoding
    $distinct = @($targetStates | Sort-Object -Unique)
    $state = if ($distinct.Count -eq 1) { $distinct[0] } else { 'Upgradable' }
    return [pscustomobject]@{
        Role = $Specification.Role
        RelativePath = $Specification.RelativePath
        BackupName = $Specification.BackupName
        Path = $path
        State = $state
        Data = $data
        PlannedData = $plannedData
        Sha256 = Get-Sha256 $data
        PlannedSha256 = Get-Sha256 $plannedData
    }
}

function Get-Plans([string]$Root) {
    return @($specifications | ForEach-Object { Get-FilePlan $Root $_ })
}

function Get-OverallState([object[]]$Plans) {
    $states = @($Plans.State | Sort-Object -Unique)
    if ($states.Count -eq 1) { return $states[0] }
    return 'Upgradable'
}

function New-Status([string]$ResultMode, [object[]]$Plans) {
    return [pscustomobject]@{
        Mode = $ResultMode
        State = Get-OverallState $Plans
        ClientRoot = $clientRootPath
        Files = @($Plans | ForEach-Object {
            [pscustomobject]@{
                Role = $_.Role
                RelativePath = $_.RelativePath
                State = $_.State
                Sha256 = $_.Sha256
                PlannedSha256 = $_.PlannedSha256
            }
        })
    }
}

function Write-AtomicExact([string]$Path, [byte[]]$Data) {
    $directory = Split-Path -Parent $Path
    $token = [Guid]::NewGuid().ToString('N')
    $temporary = Join-Path $directory ('.level-sealer-' + $token + '.tmp')
    try {
        [IO.File]::WriteAllBytes($temporary, $Data)
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Assert-ExactFile([string]$Path, [byte[]]$Expected) {
    [byte[]]$actual = [IO.File]::ReadAllBytes($Path)
    if (-not (Test-BytesEqual $actual $Expected)) {
        throw "Level Sealer localization readback failed: $Path"
    }
}

function Assert-ClientClosed {
    if (-not (Test-Path -LiteralPath (
            Join-Path $clientRootPath 'Origin.exe') -PathType Leaf)) {
        return
    }
    $running = @(Get-Process -Name Origin, GWPrivateServer `
        -ErrorAction SilentlyContinue)
    if ($running.Count -ne 0) {
        throw "Close the game client before patching it (PID: $(
            ($running.Id | Sort-Object) -join ', '))."
    }
}

$clientRootPath = Get-FullPath $ClientRoot
$rootPath = [IO.Path]::GetPathRoot($clientRootPath)
if ($clientRootPath.Equals(
        $rootPath,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'ClientRoot must not be a drive root.'
}
if ($clientRootPath -match '(?i)(?:^|[\\/])[^\\/]*B20H[^\\/]*(?:[\\/]|$)') {
    throw 'The protected B20H client tree is outside this patch scope.'
}
if (-not (Test-Path -LiteralPath $clientRootPath -PathType Container)) {
    throw "ClientRoot was not found: $clientRootPath"
}
$rootItem = Get-Item -LiteralPath $clientRootPath -Force
if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "ClientRoot must not be a reparse point: $clientRootPath"
}

$plans = @(Get-Plans $clientRootPath)
if ($Mode -ceq 'Status') {
    New-Status 'Status' $plans
    return
}

Assert-ClientClosed
if ($Mode -ceq 'Apply') {
    if ((Get-OverallState $plans) -ceq 'Applied') {
        $result = New-Status 'Apply' $plans
        $result | Add-Member Changed $false
        $result | Add-Member Receipt $null
        return $result
    }

    $backupRootPath = Get-FullPath $BackupRoot
    if (Test-PathWithin $backupRootPath $clientRootPath) {
        throw 'BackupRoot must be outside ClientRoot.'
    }
    if (-not $PSCmdlet.ShouldProcess(
        $clientRootPath,
        'Patch the two Level Sealer localization files')) {
        return
    }
    if (-not (Test-Path -LiteralPath $backupRootPath -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $backupRootPath)
    }
    $backupRootItem = Get-Item -LiteralPath $backupRootPath -Force
    if (($backupRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "BackupRoot must not be a reparse point: $backupRootPath"
    }
    $backupDirectory = Join-Path $backupRootPath (
        "$patchName-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))-" +
        [Guid]::NewGuid().ToString('N').Substring(0, 8))
    [void](New-Item -ItemType Directory -Path $backupDirectory)

    $receiptFiles = [Collections.Generic.List[object]]::new()
    foreach ($plan in $plans) {
        $backupPath = Join-Path $backupDirectory $plan.BackupName
        [IO.File]::WriteAllBytes($backupPath, $plan.Data)
        Assert-ExactFile $backupPath $plan.Data
        $receiptFiles.Add([ordered]@{
            Role = $plan.Role
            RelativePath = $plan.RelativePath
            BackupPath = $backupPath
            BeforeSha256 = $plan.Sha256
            AfterSha256 = $plan.PlannedSha256
        })
    }

    $written = [Collections.Generic.List[object]]::new()
    try {
        foreach ($plan in $plans) {
            Assert-ClientClosed
            Assert-ExactFile $plan.Path $plan.Data
            if (-not (Test-BytesEqual $plan.Data $plan.PlannedData)) {
                Write-AtomicExact $plan.Path $plan.PlannedData
                $written.Add($plan)
            }
            Assert-ExactFile $plan.Path $plan.PlannedData
        }
    }
    catch {
        $failure = $_
        for ($index = $written.Count - 1; $index -ge 0; $index--) {
            Write-AtomicExact $written[$index].Path $written[$index].Data
        }
        throw $failure
    }

    $receiptOutputPath = Join-Path $backupDirectory 'receipt.json'
    $receipt = [ordered]@{
        Schema = $receiptSchema
        Patch = $patchName
        ClientRoot = $clientRootPath
        AppliedUtc = [DateTime]::UtcNow.ToString('O')
        Files = $receiptFiles.ToArray()
    }
    [IO.File]::WriteAllText(
        $receiptOutputPath,
        ($receipt | ConvertTo-Json -Depth 6) + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false))
    $after = @(Get-Plans $clientRootPath)
    if ((Get-OverallState $after) -cne 'Applied') {
        throw 'Level Sealer localization post-apply validation failed.'
    }
    $result = New-Status 'Apply' $after
    $result | Add-Member Changed $true
    $result | Add-Member Receipt $receiptOutputPath
    return $result
}

if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    throw 'Revert requires -ReceiptPath from the matching Apply operation.'
}
$receiptFullPath = Get-FullPath $ReceiptPath
if (-not (Test-Path -LiteralPath $receiptFullPath -PathType Leaf)) {
    throw "Receipt was not found: $receiptFullPath"
}
$receipt = Get-Content -LiteralPath $receiptFullPath -Raw | ConvertFrom-Json
if ($receipt.Schema -ne $receiptSchema -or
    $receipt.Patch -cne $patchName -or
    (Get-FullPath ([string]$receipt.ClientRoot)) -cne $clientRootPath -or
    @($receipt.Files).Count -ne $plans.Count) {
    throw 'Receipt does not match this client and patch schema.'
}

$receiptDirectory = Split-Path -Parent $receiptFullPath
$currentByPath = @{}
$originalByPath = @{}
foreach ($plan in $plans) {
    $entry = @($receipt.Files | Where-Object {
        $_.RelativePath -ceq $plan.RelativePath
    })
    if ($entry.Count -ne 1 -or
        $plan.Sha256 -cne [string]$entry[0].AfterSha256) {
        throw 'Installed files do not match the receipt after-state.'
    }
    $backupPath = Get-FullPath ([string]$entry[0].BackupPath)
    if (-not (Test-PathWithin $backupPath $receiptDirectory) -or `
        (Test-PathWithin $backupPath $clientRootPath) -or `
        -not (Test-Path -LiteralPath $backupPath -PathType Leaf)) {
        throw "Receipt backup is unsafe or missing: $backupPath"
    }
    [byte[]]$original = [IO.File]::ReadAllBytes($backupPath)
    if ((Get-Sha256 $original) -cne [string]$entry[0].BeforeSha256) {
        throw "Receipt backup checksum is invalid: $backupPath"
    }
    $currentByPath[$plan.Path] = $plan.Data
    $originalByPath[$plan.Path] = $original
}

if (-not $PSCmdlet.ShouldProcess(
    $clientRootPath,
    'Restore both Level Sealer localization backups')) {
    return
}
$restored = [Collections.Generic.List[string]]::new()
try {
    foreach ($plan in $plans) {
        Assert-ClientClosed
        Assert-ExactFile $plan.Path $currentByPath[$plan.Path]
        Write-AtomicExact $plan.Path $originalByPath[$plan.Path]
        $restored.Add($plan.Path)
        Assert-ExactFile $plan.Path $originalByPath[$plan.Path]
    }
}
catch {
    $failure = $_
    for ($index = $restored.Count - 1; $index -ge 0; $index--) {
        Write-AtomicExact $restored[$index] $currentByPath[$restored[$index]]
    }
    throw $failure
}
$afterRevert = @(Get-Plans $clientRootPath)
$result = New-Status 'Revert' $afterRevert
$result | Add-Member Changed $true
$result | Add-Member Receipt $receiptFullPath
return $result
