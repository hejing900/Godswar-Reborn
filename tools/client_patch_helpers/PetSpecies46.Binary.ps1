Set-StrictMode -Version Latest

function Convert-BloodfangHex([string]$Hex) {
    $compact = $Hex -replace '\s', ''
    if ($compact -notmatch '^(?:[0-9A-Fa-f]{2})+$') {
        throw 'Invalid Bloodfang native hex definition.'
    }
    [byte[]]$bytes = for ($index = 0; $index -lt $compact.Length; $index += 2) {
        [Convert]::ToByte($compact.Substring($index, 2), 16)
    }
    return ,$bytes
}

function Get-BloodfangBytesHash([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '') }
    finally { $sha.Dispose() }
}

function Test-BloodfangBytes([byte[]]$Bytes, [int]$Offset, [byte[]]$Expected) {
    if ($Offset -lt 0 -or $Offset + $Expected.Length -gt $Bytes.Length) { return $false }
    for ($index = 0; $index -lt $Expected.Length; $index++) {
        if ($Bytes[$Offset + $index] -ne $Expected[$index]) { return $false }
    }
    return $true
}

function Get-BloodfangPetNativeDefinition {
    # Successor of the installed title-bracket composite, preserving every
    # historical patch. Only the four existing comparison immediates change.
    $gender = Convert-BloodfangHex @'
9C 66 83 3E 44 74 6C 66 83 3E 48 0F 84 81 04 00 00
66 83 3E 4C 0F 85 58 02 00 00 50 8B 46 44 3D 2D 01
00 00 77 23 84 C0 74 1F 3C 2D 77 1B 83 7E 48 01 77
15 88 47 3C 88 A7 BC 00 00 00 8A 46 48 88 47 3F 58
E9 2A 00 00 00 58 E9 24 02 00 00
'@
    $appearance = Convert-BloodfangHex @'
50 8B 46 44 3D 2D 01 00 00 77 17 84 C0 74 13 3C
2D 77 0F 88 47 3C 88 A7 BC 00 00 00 58 E9 BF FB
FF FF 58 E9 B9 FD FF FF 00 00 00 00 00 00 00
'@
    $dispatcher = Convert-BloodfangHex @'
E9 9A FF FF FF 74 0B 66 83 3E 48 75 1E E9 1F 04 00
00 51 56 57 83 C6 14 81 C7 84 00 00 00 6A 0C 59 F3
A5 5F 5E 59 E9 E7 01 00 00 E9 E2 01 00 00
'@
    $definition = [pscustomobject]@{
        Length = 6676480
        SourceHash = '42C8BA150871FF07C325A742CF84F09468CD8EA1F24B747B1C32D791D809A4D6'
        PatchedHash = '402B2E777AF33A8BE82AF0BB74CF910C58BFA14E155CFAAAC3B8F53CC7DA0F66'
        Changes = @(
            [pscustomobject]@{ Offset = 0x5C343F; Label = '76-byte species/bound DWORD maximum' }
            [pscustomobject]@{ Offset = 0x5C344A; Label = '76-byte species byte maximum' }
            [pscustomobject]@{ Offset = 0x5C38B6; Label = '72-byte species/bound DWORD maximum' }
            [pscustomobject]@{ Offset = 0x5C38C1; Label = '72-byte species byte maximum' }
        )
        Blocks = @(
            [pscustomobject]@{ Offset = 0x5C341F; Bytes = $gender; Label = 'gender decoder' }
            [pscustomobject]@{ Offset = 0x5C38B1; Bytes = $appearance; Label = 'appearance decoder' }
        )
        Pins = @(
            [pscustomobject]@{ Offset = 0x5C3480; Bytes = $dispatcher }
            [pscustomobject]@{ Offset = 0x5C341A; Bytes = (Convert-BloodfangHex 'E95506ADFF') }
            [pscustomobject]@{ Offset = 0x5C346E; Bytes = [byte[]]::new(18) }
            [pscustomobject]@{ Offset = 0x5C3692; Bytes = (Convert-BloodfangHex '9DC78424E400000007000000EBB8') }
        )
    }
    if ($gender.Length -ne 79 -or $appearance.Length -ne 47 -or $dispatcher.Length -ne 48) {
        throw 'Invalid Bloodfang native decoder lengths.'
    }
    return $definition
}

function Assert-BloodfangPetPe([byte[]]$Bytes) {
    if ($Bytes.Length -lt 0x100 -or $Bytes[0] -ne 0x4D -or $Bytes[1] -ne 0x5A) {
        throw 'Bloodfang patch requires the audited DOS/PE image.'
    }
    $pe = [BitConverter]::ToInt32($Bytes, 0x3C)
    if ($pe -lt 0x40 -or $pe + 24 -gt $Bytes.Length -or
        [BitConverter]::ToUInt32($Bytes, $pe) -ne 0x4550) { throw 'Invalid PE header.' }
    $count = [BitConverter]::ToUInt16($Bytes, $pe + 6)
    $optional = $pe + 24
    $size = [BitConverter]::ToUInt16($Bytes, $pe + 20)
    if ($count -lt 1 -or $count -gt 16 -or $size -lt 224 -or
        $optional + $size + $count * 40 -gt $Bytes.Length -or
        [BitConverter]::ToUInt16($Bytes, $pe + 4) -ne 0x14C -or
        [BitConverter]::ToUInt16($Bytes, $optional) -ne 0x10B -or
        [BitConverter]::ToUInt32($Bytes, $optional + 28) -ne 0x400000 -or
        ([BitConverter]::ToUInt16($Bytes, $pe + 22) -band 1) -eq 0 -or
        ([BitConverter]::ToUInt16($Bytes, $optional + 70) -band 0x40) -ne 0 -or
        [BitConverter]::ToUInt32($Bytes, $optional + 136) -ne 0 -or
        [BitConverter]::ToUInt32($Bytes, $optional + 140) -ne 0) {
        throw 'Bloodfang patch requires the fixed-base, relocation-stripped x86 PE32 image.'
    }
    $mapped = $false
    for ($index = 0; $index -lt $count; $index++) {
        $offset = $optional + $size + $index * 40
        $name = [Text.Encoding]::ASCII.GetString($Bytes, $offset, 8).Trim([char]0)
        $rva = [BitConverter]::ToUInt32($Bytes, $offset + 12)
        $rawSize = [BitConverter]::ToUInt32($Bytes, $offset + 16)
        $raw = [BitConverter]::ToUInt32($Bytes, $offset + 20)
        $flags = [BitConverter]::ToUInt32($Bytes, $offset + 36)
        if ($raw -le 0x5C341A -and [uint64]$raw + $rawSize -ge 0x5C38E0) {
            $mapped = $name -eq '.rdata' -and ($flags -band 0x20000000) -ne 0 -and $rva -eq $raw
        }
    }
    if (-not $mapped) { throw 'Pet decoder ranges are not in the audited executable .rdata mapping.' }
}

function Get-BloodfangPetNativeState([byte[]]$Bytes) {
    $definition = Get-BloodfangPetNativeDefinition
    if ($Bytes.Length -ne $definition.Length) { throw "Unsupported Origin.exe length $($Bytes.Length)." }
    Assert-BloodfangPetPe $Bytes
    $hash = Get-BloodfangBytesHash $Bytes
    $patched = $hash -ceq $definition.PatchedHash
    if (-not $patched -and $hash -cne $definition.SourceHash) {
        throw "Unsupported or partial species-46 client state (SHA-256 $hash)."
    }
    foreach ($pin in $definition.Pins) {
        if (-not (Test-BloodfangBytes $Bytes $pin.Offset $pin.Bytes)) {
            throw "Pet decoder prerequisite differs at 0x$($pin.Offset.ToString('X'))."
        }
    }
    foreach ($block in $definition.Blocks) {
        [byte[]]$expected = $block.Bytes.Clone()
        if ($patched) {
            foreach ($change in $definition.Changes) {
                if ($change.Offset -ge $block.Offset -and $change.Offset -lt $block.Offset + $expected.Length) {
                    $expected[$change.Offset - $block.Offset] = 46
                }
            }
        }
        if (-not (Test-BloodfangBytes $Bytes $block.Offset $expected)) {
            throw "Native $($block.Label) does not match its complete audited block."
        }
    }
    [pscustomobject]@{ Patched = $patched; MaximumSpecies = $(if ($patched) { 46 } else { 45 }); Hash = $hash }
}

function New-BloodfangPetNativeBytes([byte[]]$Bytes, [bool]$Patched) {
    $state = Get-BloodfangPetNativeState $Bytes
    $definition = Get-BloodfangPetNativeDefinition
    [byte[]]$result = $Bytes.Clone()
    foreach ($change in $definition.Changes) { $result[$change.Offset] = $(if ($Patched) { 46 } else { 45 }) }
    $expected = if ($Patched) { $definition.PatchedHash } else { $definition.SourceHash }
    if ((Get-BloodfangBytesHash $result) -cne $expected) { throw 'Species-46 target hash mismatch.' }
    $null = Get-BloodfangPetNativeState $result
    return ,$result
}
