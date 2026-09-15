$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function ConvertFrom-OaUnicodeHex([string]$Hex) {
    if (($Hex.Length % 4) -ne 0 -or $Hex -notmatch '\A[0-9A-Fa-f]*\z') {
        throw 'Unicode hex text must contain complete UTF-16 code units.'
    }
    $characters = [Collections.Generic.List[char]]::new()
    for ($offset = 0; $offset -lt $Hex.Length; $offset += 4) {
        $characters.Add([char][Convert]::ToUInt16($Hex.Substring($offset, 4), 16))
    }
    return -join $characters.ToArray()
}

function Get-OaTextCatalog {
    $curlyApostrophe = [char]0x2019
    $zhDaily = ConvertFrom-OaUnicodeHex (
        '6BCF592953EF988653D64E006B2157287EBF595652B13002595652B151855BB9' +
        '7531670D52A15668914D7F6EFF0C53EF80FD4F1A8C0365743002')
    $zhSection = ConvertFrom-OaUnicodeHex '57287EBF595652B1'
    return [pscustomobject]@{
        En = [ordered]@{
            Description = 'Claim one Online Award per server day. Rewards are configured by the server and may change.'
            StayReward1 = 'Claim one Online Award per server day. Rewards are configured by the server and may change.'
            StayReward2 = 'Claim the Online Award'
            StayReward3 = 'The Online Award is not available yet. Try again later.'
            StayReward4 = "You claimed today's Online Award."
            StayReward5 = "You've already claimed today's Online Award. Try again after the next server-day reset."
            StayReward6 = 'Your inventory is full.'
            StayReward7 = "The Event isn't available at the moment."
        }
        Zh = [ordered]@{
            Description = $zhDaily
            Section = $zhSection
            StayReward1 = $zhDaily
            StayReward2 = ConvertFrom-OaUnicodeHex '988653D657287EBF595652B1'
            StayReward3 = ConvertFrom-OaUnicodeHex (
                '57287EBF595652B166824E0D53EF988653D6FF0C8BF77A0D540E518D8BD53002')
            StayReward4 = ConvertFrom-OaUnicodeHex (
                '4F605DF2988653D64ECA5929768457287EBF595652B13002')
            StayReward5 = ConvertFrom-OaUnicodeHex (
                '4F604ECA59295DF27ECF988653D68FC757287EBF595652B1FF0C8BF757284E0B' +
                '4E004E2A670D52A1566865E5671F91CD7F6E540E518D8BD53002')
            StayReward6 = ConvertFrom-OaUnicodeHex '80CC53055DF26EE13002'
            StayReward7 = ConvertFrom-OaUnicodeHex '57287EBF595652B176EE524D4E0D53EF75283002'
        }
        Original = [pscustomobject]@{
            EnDescription = 'Just stay online for 4 hours each day to receive one free Quest Scroll.'
            ZhAthensDescription = ConvertFrom-OaUnicodeHex (
                '53EA89816BCF592957287EBF00345C0F65F6FF0C5C3153EF4EE583B75F974E00' +
                '5F20514D8D3976844EFB52A153778F743002')
            ZhSpartaDescription = ConvertFrom-OaUnicodeHex (
                '53EA97006BCF592957287EBF00345C0F65F6FF0C537353EF83B75F974E005F20' +
                '514D8D394EFB52A153778F743002')
            StayReward1 = 'Just stay online for 4 hours each day to receive one free Quest Scroll,this event is available at 12:00am - 11:55pm.'
            StayReward3 = "You don't qualify for any Quest Scrolls until you$curlyApostrophe" +
                "ve been online for 4 hours in one day. You$curlyApostrophe" +
                've only been online for %d hours.'
            StayReward4First = 'You stayed online for 4 hours today, earning you a Quest Scroll. Stay online for 4 more hours tomorrow to claim another!'
            StayReward4Second = "You've been online today, earning you a Daily Rewards!"
            StayReward5First = "You've already claimed a your Reward today. Try again tomorrow."
            StayReward5Second = "You've already claimed your Daily Rewards today. Try again tomorrow."
        }
    }
}

function Get-OaFileSpecifications {
    return @(
        [pscustomobject]@{
            Role = 'EnNpcDescription'; Locale = 'en_us';
            RelativePath = 'Localization\en_us\Text\NPCDescription.dat';
            BackupName = 'en_us-NPCDescription.dat' },
        [pscustomobject]@{
            Role = 'ZhNpcDescription'; Locale = 'zh_cn';
            RelativePath = 'Localization\zh_cn\Text\NPCDescription.dat';
            BackupName = 'zh_cn-NPCDescription.dat' },
        [pscustomobject]@{
            Role = 'EnLuaText'; Locale = 'en_us';
            RelativePath = 'Localization\en_us\UI\Base\LuaText.lua';
            BackupName = 'en_us-LuaText.lua' },
        [pscustomobject]@{
            Role = 'ZhLuaText'; Locale = 'zh_cn';
            RelativePath = 'Localization\zh_cn\UI\Base\LuaText.lua';
            BackupName = 'zh_cn-LuaText.lua' }
    )
}

function Get-OaFullPath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.Equals($root, [StringComparison]::OrdinalIgnoreCase)) {
        return $root
    }
    return $fullPath.TrimEnd('\', '/')
}

function Test-OaPathWithin([string]$Candidate, [string]$Parent) {
    $candidatePath = Get-OaFullPath $Candidate
    $parentPath = Get-OaFullPath $Parent
    return $candidatePath.Equals(
            $parentPath,
            [StringComparison]::OrdinalIgnoreCase) -or
        $candidatePath.StartsWith(
            $parentPath + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)
}

function Get-OaSha256([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($Data))).Replace('-', '')
    }
    finally {
        $algorithm.Dispose()
    }
}

function Test-OaBytesEqual([byte[]]$Left, [byte[]]$Right) {
    if ($Left.Length -ne $Right.Length) { return $false }
    for ($index = 0; $index -lt $Left.Length; $index++) {
        if ($Left[$index] -ne $Right[$index]) { return $false }
    }
    return $true
}

function Find-OaBytes([byte[]]$Haystack, [byte[]]$Needle) {
    if ($Needle.Length -eq 0) { throw 'An empty byte pattern is not valid.' }
    $matches = [Collections.Generic.List[int]]::new()
    for ($offset = 0; $offset -le $Haystack.Length - $Needle.Length; $offset++) {
        $matched = $true
        for ($index = 0; $index -lt $Needle.Length; $index++) {
            if ($Haystack[$offset + $index] -ne $Needle[$index]) {
                $matched = $false
                break
            }
        }
        if ($matched) { $matches.Add($offset) }
    }
    return $matches.ToArray()
}

function Get-OaByteCount([byte[]]$Data, [byte[]]$Pattern) {
    return @(Find-OaBytes $Data $Pattern).Count
}

function Replace-OaBytes(
    [byte[]]$Data,
    [byte[]]$Before,
    [byte[]]$After,
    [int]$ExpectedCount
) {
    $matches = @(Find-OaBytes $Data $Before)
    if ($matches.Count -ne $ExpectedCount) {
        throw "Expected $ExpectedCount exact byte match(es), found $($matches.Count)."
    }
    [byte[]]$result = $Data
    for ($matchIndex = $matches.Count - 1; $matchIndex -ge 0; $matchIndex--) {
        $offset = $matches[$matchIndex]
        [byte[]]$updated = [byte[]]::new(
            $result.Length - $Before.Length + $After.Length)
        [Array]::Copy($result, 0, $updated, 0, $offset)
        [Array]::Copy($After, 0, $updated, $offset, $After.Length)
        $suffix = $offset + $Before.Length
        [Array]::Copy(
            $result,
            $suffix,
            $updated,
            $offset + $After.Length,
            $result.Length - $suffix)
        $result = $updated
    }
    return $result
}

function ConvertTo-OaBytes([string]$Text, [ValidateSet('Utf16Le', 'Utf8')]$Encoding) {
    if ($Encoding -ceq 'Utf16Le') {
        return [Text.Encoding]::Unicode.GetBytes($Text)
    }
    return [Text.UTF8Encoding]::new($false, $true).GetBytes($Text)
}

function Assert-OaEncoding([byte[]]$Data, [string]$Role, [string]$Path) {
    if ($Role -like '*NpcDescription') {
        if ($Data.Length -lt 2 -or $Data[0] -ne 0xFF -or $Data[1] -ne 0xFE -or
            ($Data.Length % 2) -ne 0) {
            throw "NPCDescription.dat must be complete UTF-16LE with a BOM: $Path"
        }
        $encoding = [Text.UnicodeEncoding]::new($false, $true, $true)
        [void]$encoding.GetString($Data, 2, $Data.Length - 2)
        return
    }
    $hasBom = $Data.Length -ge 3 -and $Data[0] -eq 0xEF -and
        $Data[1] -eq 0xBB -and $Data[2] -eq 0xBF
    if ($Role -ceq 'EnLuaText' -and $hasBom) {
        throw "English LuaText.lua must retain its BOM-less UTF-8 encoding: $Path"
    }
    if ($Role -ceq 'ZhLuaText' -and -not $hasBom) {
        throw "Chinese LuaText.lua must retain its UTF-8 BOM: $Path"
    }
    $offset = if ($hasBom) { 3 } else { 0 }
    $encoding = [Text.UTF8Encoding]::new($false, $true)
    [void]$encoding.GetString($Data, $offset, $Data.Length - $offset)
}

function Test-OaPatternSet([byte[]]$Data, [object[]]$Patterns) {
    foreach ($pattern in $Patterns) {
        if ((Get-OaByteCount $Data $pattern.Bytes) -ne $pattern.Count) {
            return $false
        }
    }
    return $true
}

function New-OaPattern([byte[]]$Bytes, [int]$Count) {
    return [pscustomobject]@{ Bytes = $Bytes; Count = $Count }
}

function Get-OaNpcPlan([byte[]]$Data, [string]$Locale, [object]$Catalog) {
    $encoding = 'Utf16Le'
    $text = [Text.Encoding]::Unicode.GetString($Data, 2, $Data.Length - 2)
    foreach ($key in @('Athens_132', 'Sparta_132')) {
        if ([regex]::Matches($text, "(?m)^$key`t").Count -ne 1) {
            throw "NPC-description key $key is not unique for $Locale."
        }
    }
    $oldAthens = if ($Locale -ceq 'en_us') {
        $Catalog.Original.EnDescription
    } else { $Catalog.Original.ZhAthensDescription }
    $oldSparta = if ($Locale -ceq 'en_us') {
        $Catalog.Original.EnDescription
    } else { $Catalog.Original.ZhSpartaDescription }
    $newDescription = if ($Locale -ceq 'en_us') {
        $Catalog.En.Description
    } else { $Catalog.Zh.Description }
    $operations = @(
        [pscustomobject]@{
            Before = ConvertTo-OaBytes "Athens_132`t$oldAthens" $encoding
            After = ConvertTo-OaBytes "Athens_132`t$newDescription" $encoding
        },
        [pscustomobject]@{
            Before = ConvertTo-OaBytes "Sparta_132`t$oldSparta" $encoding
            After = ConvertTo-OaBytes "Sparta_132`t$newDescription" $encoding
        }
    )
    $original = @($operations | ForEach-Object { New-OaPattern $_.Before 1 }) +
        @($operations | ForEach-Object { New-OaPattern $_.After 0 })
    $applied = @($operations | ForEach-Object { New-OaPattern $_.Before 0 }) +
        @($operations | ForEach-Object { New-OaPattern $_.After 1 })
    if (Test-OaPatternSet $Data $original) {
        [byte[]]$planned = $Data
        foreach ($operation in $operations) {
            $planned = Replace-OaBytes $planned $operation.Before $operation.After 1
        }
        return [pscustomobject]@{ State = 'Original'; PlannedData = $planned }
    }
    if (Test-OaPatternSet $Data $applied) {
        return [pscustomobject]@{ State = 'Applied'; PlannedData = $Data }
    }
    throw "Refusing foreign or partial Online Award NPC-description state for $Locale."
}

function Get-OaEnLuaPlan([byte[]]$Data, [object]$Catalog) {
    $text = [Text.UTF8Encoding]::new($false, $true).GetString($Data)
    for ($index = 1; $index -le 7; $index++) {
        if ([regex]::Matches(
            $text, "(?m)^[ `t]*StayReward$index[ `t]*=").Count -ne 2) {
            throw "English StayReward$index assignment count is foreign."
        }
    }
    $prefix = "`r`n"
    $line = {
        param([string]$Key, [string]$Value)
        ConvertTo-OaBytes ($prefix + $Key + ' = "' + $Value + '"') 'Utf8'
    }
    $operations = @(
        [pscustomobject]@{
            Before = & $line 'StayReward1' $Catalog.Original.StayReward1
            After = & $line 'StayReward1' $Catalog.En.StayReward1; Count = 2
        },
        [pscustomobject]@{
            Before = & $line 'StayReward3' $Catalog.Original.StayReward3
            After = & $line 'StayReward3' $Catalog.En.StayReward3; Count = 2
        },
        [pscustomobject]@{
            Before = & $line 'StayReward4' $Catalog.Original.StayReward4First
            After = & $line 'StayReward4' $Catalog.En.StayReward4; Count = 1
        },
        [pscustomobject]@{
            Before = & $line 'StayReward4' $Catalog.Original.StayReward4Second
            After = & $line 'StayReward4' $Catalog.En.StayReward4; Count = 1
        },
        [pscustomobject]@{
            Before = & $line 'StayReward5' $Catalog.Original.StayReward5First
            After = & $line 'StayReward5' $Catalog.En.StayReward5; Count = 1
        },
        [pscustomobject]@{
            Before = & $line 'StayReward5' $Catalog.Original.StayReward5Second
            After = & $line 'StayReward5' $Catalog.En.StayReward5; Count = 1
        }
    )
    $targetPatterns = @(
        New-OaPattern (& $line 'StayReward1' $Catalog.En.StayReward1) 2
        New-OaPattern (& $line 'StayReward3' $Catalog.En.StayReward3) 2
        New-OaPattern (& $line 'StayReward4' $Catalog.En.StayReward4) 2
        New-OaPattern (& $line 'StayReward5' $Catalog.En.StayReward5) 2
    )
    $original = @($operations | ForEach-Object {
        New-OaPattern $_.Before $_.Count
    }) + @($targetPatterns | ForEach-Object { New-OaPattern $_.Bytes 0 })
    $applied = @($operations | ForEach-Object {
        New-OaPattern $_.Before 0
    }) + $targetPatterns
    if (Test-OaPatternSet $Data $original) {
        [byte[]]$planned = $Data
        foreach ($operation in $operations) {
            $planned = Replace-OaBytes `
                $planned $operation.Before $operation.After $operation.Count
        }
        return [pscustomobject]@{ State = 'Original'; PlannedData = $planned }
    }
    if (Test-OaPatternSet $Data $applied) {
        return [pscustomobject]@{ State = 'Applied'; PlannedData = $Data }
    }
    throw 'Refusing foreign or partial English StayReward definition state.'
}

function Get-OaZhBlock([object]$Catalog) {
    $lines = [Collections.Generic.List[string]]::new()
    $lines.Add('--' + $Catalog.Zh.Section)
    for ($index = 1; $index -le 7; $index++) {
        $key = "StayReward$index"
        $lines.Add($key + ' = "' + $Catalog.Zh[$key] + '"')
    }
    return "`r`n`r`n" + ($lines.ToArray() -join "`r`n")
}

function Get-OaZhLuaPlan([byte[]]$Data, [object]$Catalog) {
    [byte[]]$block = ConvertTo-OaBytes (Get-OaZhBlock $Catalog) 'Utf8'
    $text = [Text.UTF8Encoding]::new($false, $true).GetString(
        $Data, 3, $Data.Length - 3)
    $assignmentCounts = [Collections.Generic.List[int]]::new()
    for ($index = 1; $index -le 7; $index++) {
        $assignmentCounts.Add([regex]::Matches(
            $text, "(?m)^[ `t]*StayReward$index[ `t]*=").Count)
    }
    $definitionPatterns = [Collections.Generic.List[object]]::new()
    for ($index = 1; $index -le 7; $index++) {
        $key = "StayReward$index"
        [byte[]]$bytes = ConvertTo-OaBytes (
            "`r`n$key" + ' = "' + $Catalog.Zh[$key] + '"') 'Utf8'
        $definitionPatterns.Add((New-OaPattern $bytes 1))
    }
    $blockCount = Get-OaByteCount $Data $block
    if ($blockCount -eq 0 -and
        @($assignmentCounts | Where-Object { $_ -ne 0 }).Count -eq 0) {
        [byte[]]$planned = [byte[]]::new($Data.Length + $block.Length)
        [Array]::Copy($Data, 0, $planned, 0, $Data.Length)
        [Array]::Copy($block, 0, $planned, $Data.Length, $block.Length)
        return [pscustomobject]@{ State = 'Original'; PlannedData = $planned }
    }
    $endsWithBlock = $Data.Length -ge $block.Length
    if ($endsWithBlock) {
        for ($index = 0; $index -lt $block.Length; $index++) {
            if ($Data[$Data.Length - $block.Length + $index] -ne $block[$index]) {
                $endsWithBlock = $false
                break
            }
        }
    }
    if ($blockCount -eq 1 -and $endsWithBlock -and
        @($assignmentCounts | Where-Object { $_ -ne 1 }).Count -eq 0 -and
        (Test-OaPatternSet $Data $definitionPatterns.ToArray())) {
        return [pscustomobject]@{ State = 'Applied'; PlannedData = $Data }
    }
    throw 'Refusing foreign or partial Chinese StayReward definition state.'
}

function Assert-OaRegularClientFile([string]$Path, [string]$Root) {
    if (-not (Test-OaPathWithin $Path $Root)) {
        throw "Client file escaped ClientRoot: $Path"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Client localization file was not found: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Client localization file must not be a reparse point: $Path"
    }
}

function Get-OnlineAwardClientStates([string]$Root) {
    $catalog = Get-OaTextCatalog
    $states = [Collections.Generic.List[object]]::new()
    foreach ($specification in Get-OaFileSpecifications) {
        $path = Join-Path $Root $specification.RelativePath
        Assert-OaRegularClientFile $path $Root
        [byte[]]$data = [IO.File]::ReadAllBytes($path)
        Assert-OaEncoding $data $specification.Role $path
        $plan = switch ($specification.Role) {
            'EnNpcDescription' { Get-OaNpcPlan $data 'en_us' $catalog; break }
            'ZhNpcDescription' { Get-OaNpcPlan $data 'zh_cn' $catalog; break }
            'EnLuaText' { Get-OaEnLuaPlan $data $catalog; break }
            'ZhLuaText' { Get-OaZhLuaPlan $data $catalog; break }
            default { throw "Unknown Online Award localization role: $($specification.Role)" }
        }
        $states.Add([pscustomobject]@{
            Role = $specification.Role
            Locale = $specification.Locale
            RelativePath = $specification.RelativePath
            BackupName = $specification.BackupName
            Path = $path
            State = $plan.State
            Data = $data
            PlannedData = [byte[]]$plan.PlannedData
            Length = $data.Length
            Sha256 = Get-OaSha256 $data
            PlannedLength = $plan.PlannedData.Length
            PlannedSha256 = Get-OaSha256 $plan.PlannedData
        })
    }
    return $states.ToArray()
}
