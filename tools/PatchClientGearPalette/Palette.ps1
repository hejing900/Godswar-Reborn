$script:QualityPalette = @(
    @{ Name = 'QUALITY_Q01'; Label = 'Common'; R = 220; G = 224; B = 232 },
    @{ Name = 'QUALITY_Q02'; Label = 'Enhanced'; R = 168; G = 208; B = 232 },
    @{ Name = 'QUALITY_Q03'; Label = 'Delicate'; R = 83; G = 214; B = 199 },
    @{ Name = 'QUALITY_Q04'; Label = 'Good'; R = 92; G = 220; B = 112 },
    @{ Name = 'QUALITY_Q05'; Label = 'Superior'; R = 255; G = 153; B = 0 },
    @{ Name = 'QUALITY_Q06'; Label = 'Classic'; R = 229; G = 194; B = 62 },
    @{ Name = 'QUALITY_Q07'; Label = 'Eternal'; R = 255; G = 218; B = 77 },
    @{ Name = 'QUALITY_Q08'; Label = 'Epic'; R = 255; G = 139; B = 223 },
    @{ Name = 'QUALITY_Q09'; Label = 'Legendary'; R = 255; G = 105; B = 55 },
    @{ Name = 'QUALITY_Q10'; Label = 'Mystic'; R = 218; G = 85; B = 238 },
    @{ Name = 'QUALITY_Q11'; Label = 'Divine'; R = 255; G = 240; B = 176 },
    @{ Name = 'QUALITY_Q12'; Label = 'Celestial'; R = 196; G = 220; B = 242 },
    @{ Name = 'QUALITY_Q13'; Label = 'Mythical'; R = 141; G = 188; B = 227 },
    @{ Name = 'QUALITY_Q14'; Label = 'Astral'; R = 127; G = 145; B = 217 },
    @{ Name = 'QUALITY_Q15'; Label = 'Arcane'; R = 145; G = 120; B = 200 },
    @{ Name = 'QUALITY_Q16'; Label = 'Ethereal'; R = 168; G = 223; B = 216 },
    @{ Name = 'QUALITY_Q17'; Label = 'Transcendent'; R = 232; G = 214; B = 111 },
    @{ Name = 'QUALITY_Q18'; Label = 'Ancient'; R = 214; G = 154; B = 80 },
    @{ Name = 'QUALITY_Q19'; Label = 'Primordial'; R = 227; G = 96; B = 51 },
    # Restore the native crimson cap identity at a luminance the dark client
    # UI can render clearly.
    @{ Name = 'QUALITY_Q20'; Label = 'Boundless'; R = 255; G = 59; B = 48 }
)

$script:GradePalette = @(
    @{ Name = 'GRADE_G01'; Family = 'Silver'; R = 176; G = 184; B = 200 },
    @{ Name = 'GRADE_G02'; Family = 'Silver'; R = 190; G = 198; B = 214 },
    @{ Name = 'GRADE_G03'; Family = 'Silver'; R = 204; G = 212; B = 226 },
    @{ Name = 'GRADE_G04'; Family = 'Silver'; R = 220; G = 226; B = 236 },
    @{ Name = 'GRADE_G05'; Family = 'Jade'; R = 66; G = 170; B = 118 },
    @{ Name = 'GRADE_G06'; Family = 'Jade'; R = 70; G = 186; B = 127 },
    @{ Name = 'GRADE_G07'; Family = 'Jade'; R = 75; G = 202; B = 137 },
    @{ Name = 'GRADE_G08'; Family = 'Jade'; R = 82; G = 220; B = 148 },
    @{ Name = 'GRADE_G09'; Family = 'Azure'; R = 64; G = 132; B = 220 },
    @{ Name = 'GRADE_G10'; Family = 'Azure'; R = 66; G = 147; B = 234 },
    @{ Name = 'GRADE_G11'; Family = 'Azure'; R = 72; G = 162; B = 246 },
    @{ Name = 'GRADE_G12'; Family = 'Azure'; R = 82; G = 180; B = 255 },
    @{ Name = 'GRADE_G13'; Family = 'Royal steel'; R = 113; G = 129; B = 208 },
    @{ Name = 'GRADE_G14'; Family = 'Royal steel'; R = 125; G = 142; B = 219 },
    @{ Name = 'GRADE_G15'; Family = 'Royal steel'; R = 137; G = 155; B = 230 },
    @{ Name = 'GRADE_G16'; Family = 'Royal steel'; R = 151; G = 170; B = 241 },
    @{ Name = 'GRADE_G17'; Family = 'Bronze'; R = 191; G = 118; B = 64 },
    @{ Name = 'GRADE_G18'; Family = 'Bronze'; R = 199; G = 125; B = 64 },
    @{ Name = 'GRADE_G19'; Family = 'Bronze'; R = 214; G = 140; B = 70 },
    @{ Name = 'GRADE_G20'; Family = 'Bronze'; R = 230; G = 157; B = 78 },
    @{ Name = 'GRADE_G21'; Family = 'Gold'; R = 211; G = 154; B = 45 },
    @{ Name = 'GRADE_G22'; Family = 'Gold'; R = 226; G = 170; B = 52 },
    @{ Name = 'GRADE_G23'; Family = 'Gold'; R = 240; G = 187; B = 60 },
    @{ Name = 'GRADE_G24'; Family = 'Gold'; R = 255; G = 206; B = 73 },
    # Crown gold is saturated enough to remain distinct from Common and from
    # the imperial-scarlet Boundless label beside it.
    @{ Name = 'GRADE_G25'; Family = 'Crown gold'; R = 255; G = 240; B = 106 }
)

$script:ElementalSentinels = @(
    'ELEMENT_FIRE_COLOR',
    'ELEMENT_WATER_COLOR',
    'ELEMENT_LIGHTNING_COLOR',
    'ELEMENT_EARTH_COLOR',
    'ELEMENT_WIND_COLOR',
    'ELEMENT_LIGHT_COLOR',
    'ELEMENT_DARK_COLOR'
)

$script:PaletteBlockBegin = '-- Reborn gear palette: BEGIN managed block'
$script:PaletteBlockEnd = '-- Reborn gear palette: END managed block'

function Get-GearPaletteLuaBlock([string]$NewLine) {
    $lines = [Collections.Generic.List[string]]::new()
    $lines.Add($script:PaletteBlockBegin)
    $lines.Add('-- Item quality controls the equipment name color only.')
    foreach ($color in $script:QualityPalette) {
        $lines.Add(('{0}={{r={1},g={2},b={3},a=255}}' -f
                $color.Name, $color.R, $color.G, $color.B))
    }
    $lines.Add('')
    $lines.Add('-- Grade families brighten within each four-grade milestone.')
    foreach ($color in $script:GradePalette) {
        $lines.Add(('{0}={{r={1},g={2},b={3},a=255}}' -f
                $color.Name, $color.R, $color.G, $color.B))
    }
    $lines.Add($script:PaletteBlockEnd)
    return [string]::Join($NewLine, $lines)
}
