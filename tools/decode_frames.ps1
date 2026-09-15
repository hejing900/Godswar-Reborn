param(
    [Parameter(Mandatory = $true)][string]$Path,
    [int]$StringMin = 4
)

# Decoder for `captured_at|direction|opcode|declared_length|hex` rows exported from
# packet_transactions. Offsets printed are ABSOLUTE frame offsets, so +4 is the first
# payload word after the 2-byte length and 2-byte opcode header.
foreach ($line in Get-Content -LiteralPath $Path) {
    if ($line -notmatch '\S') { continue }
    $f = $line.Trim() -split '\|'
    if ($f.Count -lt 5) { continue }
    $id = $f[0]; $t = $f[1]; $dir = $f[2]; $op = $f[3]; $len = $f[4]; $hex = $f[5]
    if ($hex.Length % 2 -ne 0) { continue }
    $b = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $b.Length; $i++) {
        $b[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }
    Write-Output ("=== id={0} {1} {2} op={3} declared={4} bytes={5}" -f $id, $t, $dir, $op, $len, $b.Length)
    for ($o = 0; $o + 4 -le $b.Length; $o += 4) {
        $u = [BitConverter]::ToUInt32($b, $o)
        $i32 = [BitConverter]::ToInt32($b, $o)
        $f32 = [BitConverter]::ToSingle($b, $o)
        $show = ''
        if ([math]::Abs($f32) -gt 0.0005 -and [math]::Abs($f32) -lt 100000) { $show = ("{0:0.####}" -f $f32) }
        Write-Output ("  +{0,-4} u32={1,-12} i32={2,-12} f32={3}" -f $o, $u, $i32, $show)
    }
    # printable ASCII runs
    $sb = [System.Text.StringBuilder]::new()
    $runs = @()
    for ($o = 0; $o -lt $b.Length; $o++) {
        $c = $b[$o]
        if ($c -ge 32 -and $c -lt 127) { [void]$sb.Append([char]$c) }
        else {
            if ($sb.Length -ge $StringMin) { $runs += ("+{0}:'{1}'" -f ($o - $sb.Length), $sb.ToString()) }
            [void]$sb.Clear()
        }
    }
    if ($sb.Length -ge $StringMin) { $runs += ("+{0}:'{1}'" -f ($b.Length - $sb.Length), $sb.ToString()) }
    if ($runs.Count -gt 0) { Write-Output ("  ascii: " + ($runs -join ' ')) }
}
