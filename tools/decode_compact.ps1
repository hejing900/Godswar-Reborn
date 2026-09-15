param(
    [Parameter(Mandatory = $true)][string]$Sql,
    [int]$Words = 8
)

# Decodes frames selected by $Sql (columns: id, time, direction, opcode, hex)
# and prints one compact line per frame: header plus the first $Words payload
# words as u32 / f32.
$rows = docker exec godswar-postgres psql -U godswar -d godswar -t -A -F"|" -c $Sql
foreach ($row in $rows) {
    if ($row -notmatch '\|') { continue }
    $parts = $row -split '\|'
    $id = $parts[0]; $when = $parts[1]; $dir = $parts[2]; $op = $parts[3]; $hex = $parts[4].Trim()
    $bytes = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }

    $fields = @()
    for ($o = 4; $o -lt [Math]::Min($bytes.Length, 4 + ($Words * 4)); $o += 4) {
        $u = [BitConverter]::ToUInt32($bytes, $o)
        $f = [BitConverter]::ToSingle($bytes, $o)
        $text = if ($u -eq 0xFFFFFFFF) { '-1' } else { "$u" }
        if ([math]::Abs($f) -gt 0.0005 -and [math]::Abs($f) -lt 100000 -and $u -ne 0xFFFFFFFF) {
            $text = "$u/$('{0:0.##}' -f $f)"
        }
        $fields += "+$o=$text"
    }

    $ascii = ''
    $run = New-Object System.Text.StringBuilder
    for ($o = 4; $o -lt $bytes.Length; $o++) {
        $c = $bytes[$o]
        if ($c -ge 32 -and $c -lt 127) { [void]$run.Append([char]$c) }
        else {
            if ($run.Length -ge 5) { $ascii += "'" + $run.ToString() + "' " }
            [void]$run.Clear()
        }
    }
    if ($run.Length -ge 5) { $ascii += "'" + $run.ToString() + "'" }

    Write-Output ("{0} {1} {2} op={3} len={4} {5} {6}" -f $id, $when, $dir, $op, $bytes.Length, ($fields -join ' '), $ascii)
}
