[CmdletBinding()]
param(
    [string]$ClientPath = 'C:\Godswar Origin',
    [ValidateSet('en_us', 'zh_cn')][string[]]$Locales = @('en_us', 'zh_cn'),
    [string[]]$TitleNames = @('Gatebreaker', 'Demonbreaker', 'Flamebreaker', 'Stonebreaker',
        "Marshal's Bane", 'Dragonbane', "Hydra's Bane", 'Wonderland Sovereign'),
    [switch]$ValidateOnly,
    [switch]$Preview
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($TitleNames.Count -ne 8 -or @($TitleNames | Where-Object {
    [string]::IsNullOrWhiteSpace($_) -or $_.Length -gt 64 -or $_ -match '[\r\n\t|\[\]]'
}).Count -ne 0) { throw 'Provide exactly eight plain title names in island order, each 1-64 characters.' }
if ($Locales.Count -eq 0 -or @($Locales | Select-Object -Unique).Count -ne $Locales.Count) {
    throw 'Provide at least one unique supported locale.'
}
$clientRoot = (Get-Item -LiteralPath $ClientPath -ErrorAction Stop).FullName.TrimEnd('\')
if (-not (Test-Path -LiteralPath $clientRoot -PathType Container)) { throw 'ClientPath must be a directory.' }
$encoding = [Text.UnicodeEncoding]::new($false, $true, $true)
$sha = [Security.Cryptography.SHA256]::Create()
function Get-BytesHash([byte[]]$Bytes) {
    return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '')
}
function Assert-ClientPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($clientRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escaped the selected client directory: $full"
    }
    return $full
}
# Keep the five published IDs stable. Native catalogs already use IDs through 6000;
# 5155-5157 were absent in both installed locales at allocation (2026-09-10).
$titleIds = @(5155, 5114, 5156, 5115, 5157, 5116, 5117, 5118)
$newTitleIds = @(5155, 5156, 5157)
function Get-TitleDescription([int]$Island, [string]$Name) {
    return "Clear Wonderland island $Island with your admitted party. Unlocks the $Name title. Select it in the title menu."
}
function Read-TitleCatalog([string]$Locale, [string]$File) {
    $relative = "Localization\$Locale\Text\$File"
    $path = Assert-ClientPath (Join-Path $clientRoot $relative)
    [byte[]]$before = [IO.File]::ReadAllBytes($path)
    if ($before.Length -lt 2 -or $before.Length -ge 20000 -or ($before.Length % 2) -ne 0 -or
        $before[0] -ne 0xFF -or $before[1] -ne 0xFE) {
        throw "Unsupported title file size or UTF-16LE encoding: $path"
    }
    $content = $encoding.GetString($before, 2, $before.Length - 2)
    $lineEndings = @([regex]::Matches($content, '\r\n|\r|\n') |
        ForEach-Object { $_.Value } | Select-Object -Unique)
    if ($lineEndings.Count -ne 1 -or $lineEndings[0] -eq "`r") {
        throw "Expected consistent CRLF or LF title rows: $path"
    }
    return [pscustomobject]@{ Relative = $relative; Path = $path; Before = $before
        Content = $content; NewLine = $lineEndings[0]; HasFinalNewLine = $content.EndsWith($lineEndings[0]) }
}
$plans = [Collections.Generic.List[object]]::new()
try {
    foreach ($locale in $Locales) {
        $catalogs = @{}
        foreach ($file in @('DesigName.dat', 'DesigInfo.dat')) {
            $catalogs[$file] = Read-TitleCatalog $locale $file
        }
        # A reserved ID may be absent or a matching pair written by this tool.
        # Fail before any writes if another patch has allocated it or only half a pair exists.
        for ($index = 0; $index -lt $titleIds.Count; $index++) {
            $id = $titleIds[$index]
            if ($id -notin $newTitleIds) { continue }
            $pattern = '(?m)^' + $id + '\t[^\r\n]*(?=\r?$)'
            $names = [regex]::Matches($catalogs['DesigName.dat'].Content, $pattern)
            $infos = [regex]::Matches($catalogs['DesigInfo.dat'].Content, $pattern)
            if ($names.Count -eq 0 -and $infos.Count -eq 0) { continue }
            if ($names.Count -ne 1 -or $infos.Count -ne 1) {
                throw "Expected an absent or complete unique title ID $id pair in $locale"
            }
            $oldName = $names[0].Value.Substring($id.ToString().Length + 1)
            $expectedInfo = "$id`t" + (Get-TitleDescription ($index + 1) $oldName)
            if ($infos[0].Value -cne $expectedInfo) {
                throw "Reserved title ID $id is occupied by unrelated content in $locale"
            }
        }
        foreach ($file in @('DesigName.dat', 'DesigInfo.dat')) {
            $catalog = $catalogs[$file]
            $relative = $catalog.Relative
            $path = $catalog.Path
            [byte[]]$before = $catalog.Before
            $content = $catalog.Content
            $rows = [Collections.Generic.List[object]]::new()
            $append = [Collections.Generic.List[string]]::new()
            for ($index = 0; $index -lt $titleIds.Count; $index++) {
                $id = $titleIds[$index]
                $pattern = '(?m)^' + $id + '\t[^\r\n]*(?=\r?$)'
                $matches = [regex]::Matches($content, $pattern)
                if ($matches.Count -gt 1 -or ($matches.Count -eq 0 -and $id -notin $newTitleIds)) {
                    throw "Expected exactly one title ID $id in $path"
                }
                $text = if ($file -eq 'DesigName.dat') { $TitleNames[$index] } else {
                    Get-TitleDescription ($index + 1) $TitleNames[$index]
                }
                $replacement = "$id`t$text"
                $oldValue = if ($matches.Count -eq 1) { $matches[0].Value } else { $null }
                $rows.Add([ordered]@{ Id = $id; Island = ($index + 1); Before = $oldValue; After = $replacement })
                if ($matches.Count -eq 0) { $append.Add($replacement) } else {
                    $old = $matches[0]
                    $content = $content.Remove($old.Index, $old.Length).Insert($old.Index, $replacement)
                }
            }
            if ($append.Count -gt 0) {
                if (-not $catalog.HasFinalNewLine) { $content += $catalog.NewLine }
                $content += [string]::Join($catalog.NewLine, $append)
                if ($catalog.HasFinalNewLine) { $content += $catalog.NewLine }
            }
            [byte[]]$after = $encoding.GetPreamble() + $encoding.GetBytes($content)
            if ($after.Length -ge 20000) { throw "Patched title file would exceed 20 KB: $path" }
            $beforeHash = Get-BytesHash $before
            $afterHash = Get-BytesHash $after
            $plans.Add([pscustomobject]@{
                Relative = $relative; Path = $path; Before = $before; After = $after
                BeforeHash = $beforeHash; AfterHash = $afterHash; Changed = ($beforeHash -ne $afterHash); Rows = $rows
            })
        }
    }
    $summary = @($plans | ForEach-Object {
        [ordered]@{ Path = $_.Relative; BeforeSha256 = $_.BeforeHash; AfterSha256 = $_.AfterHash
            Changed = $_.Changed; Rows = @($_.Rows) }
    })
    if ($Preview) { $summary | ConvertTo-Json -Depth 8; return }
    if ($ValidateOnly) {
        if (@($plans | Where-Object { $_.Changed }).Count -ne 0) { throw 'Wonderland title localization needs an update.' }
        Write-Output 'Eight Wonderland titles verified (5114-5118, 5155-5157); UTF-16LE and selected names are correct.'
        return
    }
    if (@($plans | Where-Object { $_.Changed }).Count -eq 0) {
        Write-Output 'Wonderland title localization already matches; no files changed.'
        return
    }
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N')
    $backupRoot = Assert-ClientPath (Join-Path $clientRoot "backups\wonderland-titles\$stamp")
    [IO.Directory]::CreateDirectory($backupRoot) | Out-Null
    $manifestPath = Assert-ClientPath (Join-Path $backupRoot 'manifest.json')
    $manifest = [ordered]@{ SchemaVersion = 1; CreatedUtc = [DateTime]::UtcNow.ToString('O')
        ClientPath = $clientRoot; Status = 'Prepared'; Files = $summary }
    foreach ($plan in $plans) {
        $backup = Assert-ClientPath (Join-Path $backupRoot $plan.Relative)
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($backup)) | Out-Null
        [IO.File]::WriteAllBytes($backup, $plan.Before)
        if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $plan.BeforeHash) {
            throw "Backup verification failed: $backup"
        }
    }
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 9), [Text.UTF8Encoding]::new($false))
    $written = [Collections.Generic.List[object]]::new()
    try {
        foreach ($plan in $plans) {
            if (-not $plan.Changed) { continue }
            if ((Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash -ne $plan.BeforeHash) {
                throw "Client title file changed after preflight: $($plan.Path)"
            }
            $stage = Assert-ClientPath ($plan.Path + '.' + [guid]::NewGuid().ToString('N') + '.stage')
            $replaceBackup = Assert-ClientPath ($stage + '.original')
            try {
                [IO.File]::WriteAllBytes($stage, $plan.After)
                [IO.File]::Replace($stage, $plan.Path, $replaceBackup)
                $written.Add($plan)
            }
            finally {
                if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Force }
                if (Test-Path -LiteralPath $replaceBackup) { Remove-Item -LiteralPath $replaceBackup -Force }
            }
            if ((Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash -ne $plan.AfterHash) {
                throw "Patched file verification failed: $($plan.Path)"
            }
        }
        $manifest.Status = 'Verified'
    }
    catch {
        foreach ($plan in $written) {
            [IO.File]::WriteAllBytes($plan.Path, $plan.Before)
            if ((Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash -ne $plan.BeforeHash) {
                throw "Rollback failed; restore the verified backup for $($plan.Path)"
            }
        }
        $manifest.Status = 'RolledBack'
        throw
    }
    finally {
        [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 9), [Text.UTF8Encoding]::new($false))
    }
    Write-Output "Wonderland title localization verified. Backup manifest: $manifestPath"
}
finally { $sha.Dispose() }
