param(
    [Parameter(Mandatory = $true)][string[]]$Path,
    [Parameter(Mandatory = $true)][string]$HexPattern,
    [int]$Context = 48,
    [int]$Max = 20
)

# Scan a binary for a hex byte pattern and print the surrounding bytes with a
# float/u32 interpretation of the neighbourhood.
$pattern = $HexPattern -replace '\s', ''
$needle = [byte[]]::new($pattern.Length / 2)
for ($i = 0; $i -lt $needle.Length; $i++) {
    $needle[$i] = [Convert]::ToByte($pattern.Substring($i * 2, 2), 16)
}

foreach ($file in $Path) {
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $file))
    $hits = 0
    for ($i = 0; $i -le $bytes.Length - $needle.Length; $i++) {
        if ($bytes[$i] -ne $needle[0]) { continue }
        $ok = $true
        for ($j = 1; $j -lt $needle.Length; $j++) {
            if ($bytes[$i + $j] -ne $needle[$j]) { $ok = $false; break }
        }
        if (-not $ok) { continue }
        $hits++
        $start = [Math]::Max(0, $i - $Context)
        $end = [Math]::Min($bytes.Length - 1, $i + $needle.Length + $Context)
        $slice = $bytes[$start..$end]
        $hex = ($slice | ForEach-Object { $_.ToString('x2') }) -join ''
        Write-Output ("{0} @0x{1:X}" -f (Split-Path $file -Leaf), $i)
        Write-Output ("  hex: {0}" -f $hex)
        # floats for the 64 bytes before the hit, 4-byte aligned relative to the hit
        $words = @()
        for ($o = -[Math]::Min($Context, $i) ; $o + 4 -le $Context + $needle.Length + 4; $o += 4) {
            $p = $i + $o
            if ($p -lt 0 -or $p + 4 -gt $bytes.Length) { continue }
            $f = [BitConverter]::ToSingle($bytes, $p)
            $u = [BitConverter]::ToUInt32($bytes, $p)
            $fs = ''
            if ([math]::Abs($f) -gt 0.0005 -and [math]::Abs($f) -lt 100000) { $fs = ("{0:0.###}" -f $f) }
            $words += ("{0}:[u={1} f={2}]" -f $o, $u, $fs)
        }
        Write-Output ("  words: " + ($words -join ' '))
        if ($hits -ge $Max) { Write-Output '  (hit cap reached)'; break }
    }
    Write-Output ("-- {0}: {1} hit(s)" -f (Split-Path $file -Leaf), $hits)
}
