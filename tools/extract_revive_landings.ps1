param(
    [string]$Container = 'godswar-postgres',
    [string]$Database = 'godswar',
    [string]$User = 'godswar',
    [int]$Limit = 50
)

# Lists every captured 10018 placement frame (28 bytes) as map + x/z and says
# whether it answered a revive request. The same frame is used for map travel
# and for the free revive, so only a landing that answers a C2S 10028 revive
# request may become a ReviveLandingCatalog row - a map-travel landing is not a
# revive point.
#
# Frame layout (absolute offsets):
#   +4  player object id
#   +8  x (f32)  +12 y (f32)  +16 z (f32)
#   +20 placement kind (u16: 1 or 2 captured)
#   +22 map id (u16)
#   +24 captured terminal marker
$rows = docker exec $Container psql -U $User -d $Database -t -A -F"|" -c @"
select l.id,
       to_char(l.captured_at AT TIME ZONE 'Asia/Shanghai','MM-DD HH24:MI:SS.MS'),
       encode(l.clear_bytes,'hex'),
       exists (
           select 1 from packet_transactions r
           where r.opcode = 10028
             and r.direction = 'C2S'
             and r.captured_at between l.captured_at - interval '5 seconds'
                                  and l.captured_at) as answered_revive
from packet_transactions l
where l.opcode = 10018 and l.declared_length = 28
order by l.id
limit $Limit
"@

if (-not $rows) {
    Write-Output 'no 28-byte 10018 placement frames captured yet'
    return
}

$landings = New-Object System.Collections.Generic.List[string]
foreach ($row in $rows) {
    if ($row -notmatch '\|') { continue }
    $parts = $row -split '\|'
    $id = $parts[0]; $when = $parts[1]; $hex = $parts[2].Trim(); $revive = $parts[3].Trim()
    $bytes = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }

    $objectId = [BitConverter]::ToUInt32($bytes, 4)
    $x = [BitConverter]::ToSingle($bytes, 8)
    $y = [BitConverter]::ToSingle($bytes, 12)
    $z = [BitConverter]::ToSingle($bytes, 16)
    $map = [BitConverter]::ToUInt16($bytes, 22)
    $kind = [BitConverter]::ToUInt16($bytes, 20)
    $terminal = [BitConverter]::ToUInt32($bytes, 24)
    $kindText = if ($revive -eq 't') { 'REVIVE' } else { 'transfer' }

    Write-Output ("id={0} {1} {2,-8} object={3} map={4} x={5} y={6} z={7} kind={8} terminal={9}" -f `
        $id, $when, $kindText, $objectId, $map, $x, $y, $z, $kind, $terminal)

    if ($revive -eq 't') {
        $landings.Add("  map $map`: new ReviveLanding(MapId: $map, X: ${x}f, Z: ${z}f)")
    }
}

Write-Output ''
if ($landings.Count -eq 0) {
    Write-Output 'no revive landing captured yet (die on the reference server once per map)'
} else {
    Write-Output 'ReviveLandingCatalog rows (revive-triggered landings only):'
    $landings | Sort-Object -Unique
}
