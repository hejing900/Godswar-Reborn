# Load the built server assembly and dump the migration catalog exactly as the
# server sees it: id, checksum and order. Bypasses source parsing entirely.
$ErrorActionPreference = 'Stop'

$serverDir = 'D:\Godswar-Reborn-main\src\Godswar.Server\bin\Release\net10.0'
[void][Reflection.Assembly]::LoadFrom((Join-Path $serverDir 'Godswar.Server.dll'))

$catalogType = [Type]::GetType('Godswar.Server.State.PostgresSchemaMigrationCatalog, Godswar.Server')
if ($null -eq $catalogType) { throw 'catalog type not found' }

$all = $catalogType.GetField('All', [Reflection.BindingFlags]'Public,Static').GetValue($null)
Write-Output "registered count: $($all.Count)"

$rows = New-Object System.Collections.Generic.List[string]
foreach ($m in $all) {
    $t = $m.GetType()
    $id = [string]$t.GetProperty('Id').GetValue($m)
    $sum = [string]$t.GetProperty('Checksum').GetValue($m)
    $rows.Add("$id|$sum")
}

$rows | Set-Content 'D:\Godswar-Reborn-main\artifacts\db-repair\reflected-catalog.txt' -Encoding utf8

$ids = $rows | ForEach-Object { ($_ -split '\|')[0] }
$dupes = $ids | Group-Object | Where-Object { $_.Count -gt 1 }
Write-Output "duplicates: $(if ($dupes) { ($dupes | ForEach-Object { $_.Name }) -join ', ' } else { 'none' })"

$desc = 0
for ($i = 1; $i -lt $ids.Count; $i++) {
    if ([string]::CompareOrdinal($ids[$i-1], $ids[$i]) -ge 0) { $desc++ }
}
Write-Output "descending pairs: $desc"
Write-Output "wrote reflected-catalog.txt"
