Set-StrictMode -Version Latest

function Initialize-NameplateGrantEnvironment(
    [string]$PostgresName,
    [string]$ServerName,
    [string]$RedisName
) {
    if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker is required but was not found on PATH.'
    }

    Import-Module (
        Join-Path $PSScriptRoot 'DevelopmentStack.Common.psm1'
    ) -Force
    $postgres = Assert-DevelopmentContainer $PostgresName 'postgres'
    $server = Assert-DevelopmentContainer $ServerName 'server'
    $redis = Assert-DevelopmentContainer $RedisName 'redis-coordination'
    foreach ($container in @($postgres, $redis)) {
        if (-not [bool]$container.State.Running) {
            throw "Required container '$($container.Name)' is stopped."
        }
        $health = $container.State.PSObject.Properties['Health']
        if ($null -ne $health -and $null -ne $health.Value -and
            [string]$health.Value.Status -cne 'healthy') {
            throw "Required container '$($container.Name)' is unhealthy."
        }
    }
    if ([string]$postgres.Config.Labels.'com.reborn.data.role' -cne
            'cloned-nonproduction-authority' -or
        [string]$redis.Config.Labels.'com.reborn.data.role' -cne
            'disposable-coordination') {
        throw 'The nameplate fixture requires isolated development data.'
    }
    $dataMounts = @($postgres.Mounts | Where-Object {
        $_.Destination -ceq '/var/lib/postgresql/data'
    })
    if ($dataMounts.Count -ne 1 -or
        [string]$dataMounts[0].Name -cne 'godswar-dev-postgres-data') {
        throw 'Development PostgreSQL has an unexpected data volume.'
    }
    if (-not (@($server.Config.Env) -contains
            'GODSWAR_RUNTIME_PROFILE=LocalDevelopment')) {
        throw "Server '$ServerName' is not a LocalDevelopment worker."
    }

    [pscustomobject]@{
        Postgres = $postgres
        Server = $server
        Redis = $redis
    }
}

function Get-NameplateGrantOpaqueId([string]$Domain, [byte[]]$Value) {
    [byte[]]$domainBytes = [Text.Encoding]::ASCII.GetBytes($Domain)
    [byte[]]$hashInput = [byte[]]::new(
        $domainBytes.Length + 1 + $Value.Length)
    [Array]::Copy($domainBytes, 0, $hashInput, 0, $domainBytes.Length)
    [Array]::Copy(
        $Value, 0, $hashInput, $domainBytes.Length + 1, $Value.Length)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $hex = -join ($sha.ComputeHash($hashInput) | ForEach-Object {
            $_.ToString('X2')
        })
        return $hex.Substring(0, 32)
    }
    finally {
        $sha.Dispose()
        [Array]::Clear($domainBytes, 0, $domainBytes.Length)
        [Array]::Clear($hashInput, 0, $hashInput.Length)
    }
}

function Get-NameplateGrantRedisKeyCount([string]$RedisName) {
    $prefix = 'godswar:tempest-dev:v1'
    [byte[]]$idBytes = [byte[]](0, 0, 0, 2)
    [byte[]]$usernameBytes = [Text.Encoding]::UTF8.GetBytes('test2')
    try {
        $keys = @(
            $prefix + ':player:' +
                (Get-NameplateGrantOpaqueId 'character' $idBytes)
            $prefix + ':login-account:' +
                (Get-NameplateGrantOpaqueId 'account' (
                    [byte[]](0, 0, 0, 13)))
            $prefix + ':login-name:' +
                (Get-NameplateGrantOpaqueId 'username' $usernameBytes)
        )
    }
    finally {
        [Array]::Clear($idBytes, 0, $idBytes.Length)
        [Array]::Clear($usernameBytes, 0, $usernameBytes.Length)
    }

    $passwordPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot `
        '..\artifacts\development-stack\redis.password'))
    $password = Read-DevelopmentSecretFile -LiteralPath $passwordPath
    if ($password -notmatch '^[a-f0-9]{64}$') {
        throw 'The isolated-development Redis secret is malformed.'
    }
    try {
        $output = & docker exec --env "REDISCLI_AUTH=$password" `
            $RedisName redis-cli --user godswar_runtime `
            --no-auth-warning -n 0 EXISTS $keys 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally { $password = $null }
    $count = 0
    if ($exitCode -ne 0 -or
        -not [int]::TryParse(
            (@($output)[-1].ToString().Trim()), [ref]$count)) {
        throw 'Could not verify the target Redis lease absence.'
    }
    return $count
}

function Test-NameplateGrantOriginRunning {
    $processes = @(Get-Process Origin -ErrorAction SilentlyContinue)
    try { return $processes.Count -ne 0 }
    finally {
        foreach ($process in $processes) { $process.Dispose() }
    }
}

function Assert-NameplateGrantOffline(
    $Environment,
    [string]$ServerName,
    [string]$RedisName
) {
    $server = Assert-DevelopmentContainer $ServerName 'server'
    if ([bool]$server.State.Running) {
        throw "Stop '$ServerName' cleanly before granting Nameplates."
    }
    if (Test-NameplateGrantOriginRunning) {
        throw 'Close Origin.exe before granting Nameplates.'
    }
    if ((Get-NameplateGrantRedisKeyCount $RedisName) -ne 0) {
        throw 'Redis still has a test2 player or login lease.'
    }
    if ([string]$Environment.Postgres.Id -cne
        [string](Assert-DevelopmentContainer `
            'godswar-dev-postgres' 'postgres').Id) {
        throw 'The development PostgreSQL identity changed.'
    }
}

function Get-NameplateGrantSha256Hex([string]$Value) {
    [byte[]]$bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return -join ($sha.ComputeHash($bytes) | ForEach-Object {
            $_.ToString('x2')
        })
    }
    finally {
        $sha.Dispose()
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}
