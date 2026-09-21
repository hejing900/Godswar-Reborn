[CmdletBinding()]
param([string]$ClientRoot = 'C:\Godswar Origin')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'PatchClientCharacterSpeedStats.Binary.ps1')
$profile = Get-CharacterStatsBinaryProfile
$title = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot (
    'client_patch_helpers\TitleBracketColorNative.json')) | ConvertFrom-Json
$path = Join-Path $ClientRoot 'Origin.exe'
[byte[]]$original = [IO.File]::ReadAllBytes($path)
Assert-CharacterStatsBinaryCompatible $original $profile
[byte[]]$installed = $original.Clone()
$cave = [byte[]]::new($title.cave_length)
Copy-RebornBytes (Convert-RebornHexBytes $title.code_hex) $cave 0
Copy-RebornBytes $cave $installed $profile.CaveOffset
Copy-RebornBytes (Convert-RebornHexBytes $title.entry_hex) $installed (
    [Convert]::ToInt32($title.entry_offset, 16))
Copy-RebornBytes (Convert-RebornHexBytes $title.width_hex) $installed (
    [Convert]::ToInt32($title.width_offset, 16))
if ((Get-CharacterStatsBinaryState $installed $profile) -ne 'Original') {
    throw 'Complete title owner should retain the original native speed path.'
}
Restore-CharacterStatsOriginalBinary $installed $profile
if (-not (Test-CharacterStatsTitleColorOwner $installed $profile)) {
    throw 'Speed restoration erased the complete title formatter.'
}
foreach ($offset in @(0x5C3F20, 0x20921, 0x21BD5, 0x21185, 0x1B5B97)) {
    [byte[]]$partial = $installed.Clone()
    $partial[$offset] = $partial[$offset] -bxor 1
    $rejected = $false
    try { Restore-CharacterStatsOriginalBinary $partial $profile }
    catch { $rejected = $true }
    if (-not $rejected) { throw "Partial title owner at $offset was accepted." }
    if ($partial[$offset] -ne ($installed[$offset] -bxor 1)) {
        throw 'Rejected restoration modified the foreign bytes.'
    }
}
[byte[]]$empty = $installed.Clone()
Copy-RebornBytes $profile.EmptyCave $empty $profile.CaveOffset
$rejected = $false
try { Restore-CharacterStatsOriginalBinary $empty $profile }
catch { $rejected = $true }
if (-not $rejected) { throw 'An active title entry pointing at an empty cave was accepted.' }

# A genuine predecessor retains its old migration path.
[byte[]]$legacy = $original.Clone()
Copy-RebornBytes (Convert-RebornHexBytes (
    'E9CA24FEFFCCCCCCCCCCCCCCCCCCCC')) $legacy 0x20921
Copy-RebornBytes (Convert-RebornHexBytes (
    '89F180BFA20900007C7465EB66CCCC')) $legacy 0x21BD1
Copy-RebornBytes $profile.LegacyHook $legacy $profile.HookOffset
Copy-RebornBytes $profile.LegacyCave $legacy $profile.CaveOffset
if ((Get-CharacterStatsBinaryState $legacy $profile) -ne 'LegacyPatched') {
    throw 'Historical speed state was not recognized.'
}
Restore-CharacterStatsOriginalBinary $legacy $profile
if ((Get-CharacterStatsBinaryState $legacy $profile) -ne 'Original' -or
    -not (Test-RebornBytes $legacy $profile.CaveOffset $profile.EmptyCave)) {
    throw 'Historical speed restoration did not clear its own old cave.'
}
if (-not (Test-RebornBytes ([IO.File]::ReadAllBytes($path)) 0 $original)) {
    throw 'The fixture changed the installed client.'
}
'PASS title-color cave ownership, exact preservation, six partial-state rejections and historical speed migration.'
