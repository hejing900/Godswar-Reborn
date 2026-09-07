[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$patchPath = Join-Path $PSScriptRoot 'PatchClientGearPalette.ps1'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) (
    'reborn-gear-palette-test-' + [guid]::NewGuid().ToString('N')
)
$clientRoot = Join-Path $testRoot 'client'
$backupRoot = Join-Path $testRoot 'backups'
$gb2312 = [Text.Encoding]::GetEncoding(936)
$utf8Bom = [Text.UTF8Encoding]::new($true)
$elementalNames = @(
    'ELEMENT_FIRE_COLOR',
    'ELEMENT_WATER_COLOR',
    'ELEMENT_LIGHTNING_COLOR',
    'ELEMENT_EARTH_COLOR',
    'ELEMENT_WIND_COLOR',
    'ELEMENT_LIGHT_COLOR',
    'ELEMENT_DARK_COLOR'
)
$expectedQualityColors = [ordered]@{
    5 = 'QUALITY_Q05={r=255,g=153,b=0,a=255}'
    11 = 'QUALITY_Q11={r=255,g=240,b=176,a=255}'
    12 = 'QUALITY_Q12={r=196,g=220,b=242,a=255}'
    13 = 'QUALITY_Q13={r=141,g=188,b=227,a=255}'
    14 = 'QUALITY_Q14={r=127,g=145,b=217,a=255}'
    15 = 'QUALITY_Q15={r=145,g=120,b=200,a=255}'
    16 = 'QUALITY_Q16={r=168,g=223,b=216,a=255}'
    17 = 'QUALITY_Q17={r=232,g=214,b=111,a=255}'
    18 = 'QUALITY_Q18={r=214,g=154,b=80,a=255}'
    19 = 'QUALITY_Q19={r=227,g=96,b=51,a=255}'
    20 = 'QUALITY_Q20={r=255,g=59,b=48,a=255}'
}
$expectedGradeColors = [ordered]@{
    13 = 'GRADE_G13={r=113,g=129,b=208,a=255}'
    14 = 'GRADE_G14={r=125,g=142,b=219,a=255}'
    15 = 'GRADE_G15={r=137,g=155,b=230,a=255}'
    16 = 'GRADE_G16={r=151,g=170,b=241,a=255}'
    17 = 'GRADE_G17={r=191,g=118,b=64,a=255}'
    18 = 'GRADE_G18={r=199,g=125,b=64,a=255}'
    19 = 'GRADE_G19={r=214,g=140,b=70,a=255}'
    20 = 'GRADE_G20={r=230,g=157,b=78,a=255}'
    21 = 'GRADE_G21={r=211,g=154,b=45,a=255}'
    22 = 'GRADE_G22={r=226,g=170,b=52,a=255}'
    23 = 'GRADE_G23={r=240,g=187,b=60,a=255}'
    24 = 'GRADE_G24={r=255,g=206,b=73,a=255}'
    25 = 'GRADE_G25={r=255,g=240,b=106,a=255}'
}

function Assert-Equal($Actual, $Expected, [string]$Label) {
    if ($Actual -cne $Expected) {
        throw "$Label expected '$Expected' but got '$Actual'."
    }
}

function New-ItemColorFixture([string]$NewLine) {
    $lines = [Collections.Generic.List[string]]::new()
    $lines.Add('<?xml version="1.0" encoding="GB2312"?>')
    $lines.Add('<ItemColor>')
    $lines.Add('  <Equip>')
    $lines.Add('    <Base>')
    for ($level = 1; $level -le 20; $level++) {
        $lines.Add(('      <BaseLevel{0} BaseLv="{0}" BaseName="Q{0}" BaseColor="LEGACY_QUALITY"/>' -f $level))
    }
    $lines.Add('    </Base>')
    $lines.Add('    <Append>')
    for ($level = 1; $level -le 25; $level++) {
        $lines.Add(('      <AppLevel{0} AppendLv="{0}" AppendStar="{0}" AppendColor="LEGACY_GRADE" AppAttributeColor="GREEN_TEXTCOLOR"/>' -f $level))
    }
    for ($offset = 0; $offset -lt $elementalNames.Count; $offset++) {
        $level = 26 + $offset
        $name = $elementalNames[$offset]
        $lines.Add(('      <AppLevel{0} AppendLv="{0}" AppendStar="25" AppendColor="{1}" AppAttributeColor="{1}"/>' -f $level, $name))
    }
    $lines.Add('    </Append>')
    $lines.Add('    <Pet>')
    $lines.Add('      <Aptitude1 BaseLv="1" BaseName="Weak" BaseColor="PET_COLOR"/>')
    $lines.Add('    </Pet>')
    $lines.Add('  </Equip>')
    $lines.Add('</ItemColor>')
    return [string]::Join($NewLine, $lines) + $NewLine
}

function New-FontFixture([string]$NewLine) {
    $lines = [Collections.Generic.List[string]]::new()
    $lines.Add('-- fixture font')
    $lines.Add('UNRELATED_UI_COLOR={r=1,g=2,b=3,a=255}')
    $lines.Add('BRONZE_COLOR={r=205,g=127,b=50,a=255}')
    for ($index = 0; $index -lt $elementalNames.Count; $index++) {
        $lines.Add(('{0}={{r={1},g={2},b={3},a=255}}' -f
                $elementalNames[$index],
                (20 + $index),
                (40 + $index),
                (60 + $index)))
    }
    return [string]::Join($NewLine, $lines) + $NewLine
}

try {
    [IO.Directory]::CreateDirectory($clientRoot) | Out-Null
    foreach ($locale in @('en_us', 'zh_cn')) {
        $itemPath = Join-Path $clientRoot (
            "Localization\$locale\Settings\Sys\ItemColor.xml"
        )
        $fontPath = Join-Path $clientRoot (
            "Localization\$locale\UI\Base\font.lua"
        )
        [IO.Directory]::CreateDirectory((Split-Path $itemPath -Parent)) |
            Out-Null
        [IO.Directory]::CreateDirectory((Split-Path $fontPath -Parent)) |
            Out-Null
        [IO.File]::WriteAllText($itemPath, (New-ItemColorFixture "`r`n"), $gb2312)
        [IO.File]::WriteAllText($fontPath, (New-FontFixture "`r`n"), $utf8Bom)
    }

    $paths = @(Get-ChildItem -LiteralPath $clientRoot -File -Recurse |
        Sort-Object FullName | Select-Object -ExpandProperty FullName)
    $beforePlan = @($paths | ForEach-Object {
            (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash
        })
    $plan = & $patchPath -ClientRoot $clientRoot -BackupRoot $backupRoot
    Assert-Equal $plan.Mode 'Plan' 'Plan mode'
    Assert-Equal $plan.WouldChangeFiles 4 'Plan change count'
    Assert-Equal $plan.ChangedFiles 0 'Plan write count'
    $afterPlan = @($paths | ForEach-Object {
            (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash
        })
    Assert-Equal ($afterPlan -join ',') ($beforePlan -join ',') `
        'Plan-mode hashes'

    $applied = & $patchPath -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Apply
    Assert-Equal $applied.Mode 'Apply' 'Apply mode'
    Assert-Equal $applied.ChangedFiles 4 'First apply change count'
    if (-not (Test-Path -LiteralPath $applied.BackupPath -PathType Container)) {
        throw 'The first apply did not create its backup directory.'
    }

    foreach ($locale in @('en_us', 'zh_cn')) {
        $itemPath = Join-Path $clientRoot (
            "Localization\$locale\Settings\Sys\ItemColor.xml"
        )
        $fontPath = Join-Path $clientRoot (
            "Localization\$locale\UI\Base\font.lua"
        )
        [xml]$item = [IO.File]::ReadAllText($itemPath, $gb2312)
        for ($level = 1; $level -le 20; $level++) {
            $node = $item.SelectSingleNode(
                "/ItemColor/Equip/Base/BaseLevel$level"
            )
            Assert-Equal $node.BaseColor ('QUALITY_Q{0:D2}' -f $level) `
                "$locale quality $level"
        }
        for ($level = 1; $level -le 25; $level++) {
            $node = $item.SelectSingleNode(
                "/ItemColor/Equip/Append/AppLevel$level"
            )
            Assert-Equal $node.AppendColor ('GRADE_G{0:D2}' -f $level) `
                "$locale grade $level"
            Assert-Equal $node.AppAttributeColor 'GREEN_TEXTCOLOR' `
                "$locale grade attribute color $level"
        }
        for ($offset = 0; $offset -lt $elementalNames.Count; $offset++) {
            $level = 26 + $offset
            $node = $item.SelectSingleNode(
                "/ItemColor/Equip/Append/AppLevel$level"
            )
            Assert-Equal $node.AppendColor $elementalNames[$offset] `
                "$locale elemental sentinel $level"
            Assert-Equal $node.AppAttributeColor $elementalNames[$offset] `
                "$locale elemental attribute sentinel $level"
        }
        Assert-Equal $item.ItemColor.Equip.Pet.Aptitude1.BaseColor 'PET_COLOR' `
            "$locale unrelated pet color"

        $font = [IO.File]::ReadAllText($fontPath, $utf8Bom)
        Assert-Equal ([regex]::Matches(
                $font,
                '(?m)^QUALITY_Q\d{2}='
            ).Count) 20 "$locale quality constants"
        Assert-Equal ([regex]::Matches(
                $font,
                '(?m)^GRADE_G\d{2}='
            ).Count) 25 "$locale grade constants"
        foreach ($entry in $expectedQualityColors.GetEnumerator()) {
            if (-not $font.Contains([string]$entry.Value)) {
                throw "$locale approved quality Q$($entry.Key) color is missing."
            }
        }
        foreach ($entry in $expectedGradeColors.GetEnumerator()) {
            if (-not $font.Contains([string]$entry.Value)) {
                throw "$locale approved grade G$($entry.Key) color is missing."
            }
        }
        if (-not $font.Contains(
                'UNRELATED_UI_COLOR={r=1,g=2,b=3,a=255}'
            )) {
            throw "$locale unrelated font color changed."
        }
        foreach ($name in $elementalNames) {
            Assert-Equal ([regex]::Matches(
                    $font,
                    ('(?m)^' + [regex]::Escape($name) + '=')
                ).Count) 1 "$locale $name count"
        }
    }

    $secondApply = & $patchPath -ClientRoot $clientRoot `
        -BackupRoot $backupRoot -Apply
    Assert-Equal $secondApply.ChangedFiles 0 'Second apply change count'
    Assert-Equal $secondApply.WouldChangeFiles 0 'Second apply plan count'
    Assert-Equal $secondApply.BackupPath $null 'Second apply backup path'

    $badItemPath = Join-Path $clientRoot `
        'Localization\en_us\Settings\Sys\ItemColor.xml'
    $badText = [IO.File]::ReadAllText($badItemPath, $gb2312).Replace(
        'AppLevel26 AppendLv="26" AppendStar="25" AppendColor="ELEMENT_FIRE_COLOR"',
        'AppLevel26 AppendLv="26" AppendStar="25" AppendColor="BROKEN_COLOR"'
    )
    [IO.File]::WriteAllText($badItemPath, $badText, $gb2312)
    $rejectedSentinel = $false
    try {
        & $patchPath -ClientRoot $clientRoot -BackupRoot $backupRoot |
            Out-Null
    }
    catch {
        $rejectedSentinel = $_.Exception.Message -like `
            '*elemental sentinel 26 is invalid*'
    }
    Assert-Equal $rejectedSentinel $true 'Elemental sentinel rejection'

    [pscustomobject]@{
        Status = 'PASS'
        PlanIsReadOnly = $true
        FirstApplyChangedFiles = $applied.ChangedFiles
        SecondApplyChangedFiles = $secondApply.ChangedFiles
        QualityMappings = 20
        GradeMappings = 25
        PreservedElementalSentinels = 7
        CorruptSentinelRejected = $rejectedSentinel
    }
}
finally {
    if (Test-Path -LiteralPath $testRoot -PathType Container) {
        $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $resolvedTestRoot.StartsWith(
                $tempRoot,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            -not ([IO.Path]::GetFileName($resolvedTestRoot)).StartsWith(
                'reborn-gear-palette-test-',
                [StringComparison]::Ordinal
            )) {
            throw "Refusing to remove unexpected test path: $resolvedTestRoot"
        }
        [IO.Directory]::Delete($resolvedTestRoot, $true)
    }
}
