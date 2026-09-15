[CmdletBinding()]
param([switch]$SelfTest)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-EndpointIds {
    param([string]$Source, [string]$Role, [switch]$Native)

    $constantPattern = if ($Native) {
        'inline constexpr std::uint32_t\s+(\w+)\s*=\s*([0-9_]+);'
    } else {
        'public const uint\s+(\w+)\s*=\s*([0-9_]+);'
    }
    $constants = @{}
    foreach ($match in [regex]::Matches($Source, $constantPattern)) {
        $constants.Add($match.Groups[1].Value,
            [uint32]$match.Groups[2].Value.Replace('_', ''))
    }
    $bodyPattern = if ($Native) {
        '(?s)inline constexpr std::uint32_t ' + $Role +
            'NpcIds\[\]\s*=\s*\{(?<body>.*?)\};'
    } else {
        $method = if ($Role -eq 'Warehouse') {
            'IsWarehouseEndpoint'
        } else { 'IsManagerEndpoint' }
        '(?s)public static bool ' + $method +
            '\(.*?=>\s*(?<body>.*?);'
    }
    $bodies = [regex]::Matches($Source, $bodyPattern)
    if ($bodies.Count -ne 1) {
        throw "Cannot identify exactly one $Role endpoint definition."
    }
    $body = $bodies[0].Groups['body'].Value
    $names = if ($Native) {
        @($body.Split(',') | ForEach-Object { $_.Trim() } |
            Where-Object { $_ })
    } else {
        @([regex]::Matches($body, '\("[^"]+",\s*(\w+)\)') |
            ForEach-Object { $_.Groups[1].Value })
    }
    if ($names.Count -eq 0) {
        throw "No $Role endpoints were found."
    }
    $ids = @($names | ForEach-Object {
        if (-not $constants.ContainsKey($_)) {
            throw "Unresolved $Role endpoint constant: $_"
        }
        $constants[$_]
    })
    if (@($ids | Select-Object -Unique).Count -ne $ids.Count) {
        throw "Duplicate $Role endpoint identity."
    }
    return @($ids | Sort-Object)
}

function Assert-WarehouseEndpointParity {
    param([string]$Managed, [string]$Native)
    foreach ($role in @('Warehouse', 'WarehouseManager')) {
        $serverIds = @(Get-EndpointIds -Source $Managed -Role $role)
        $nativeIds = @(Get-EndpointIds -Source $Native -Role $role -Native)
        if (($serverIds -join ',') -ne ($nativeIds -join ',')) {
            throw ("$role endpoint drift: server [$($serverIds -join ',')] " +
                "versus native [$($nativeIds -join ',')].")
        }
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$managed = [IO.File]::ReadAllText((Join-Path $repoRoot (
    'src/Godswar.Server/Domain/World/Content/WarehouseNpcProtocol.cs')))
$native = [IO.File]::ReadAllText((Join-Path $repoRoot (
    'client/network-shim/src/WarehouseNpcEndpoints.h')))
Assert-WarehouseEndpointParity -Managed $managed -Native $native

if ($SelfTest) {
    $cases = @(
        @{ Managed = $managed; Native = $native.Replace('= 5202;', '= 5201;') },
        @{ Managed = $managed; Native = $native.Replace(
            ', DuelArenaWarehouseNpcId', '') },
        @{ Managed = $managed.Replace(
            '("DuelArena_001", DuelArenaWarehouseNpcId);',
            '("DuelArena_001", DuelArenaWarehouseNpcId) or ' +
            '("NewWarehouse", 9999);'); Native = $native },
        @{ Managed = $managed; Native = $native.Replace('= 5131;', '= 5132;') }
    )
    foreach ($case in $cases) {
        $rejected = $false
        try {
            Assert-WarehouseEndpointParity @case
        } catch { $rejected = $true }
        if (-not $rejected) {
            throw 'Warehouse parity self-test accepted mismatched endpoints.'
        }
    }
}

Write-Output 'PASS warehouse server/native endpoint parity'
