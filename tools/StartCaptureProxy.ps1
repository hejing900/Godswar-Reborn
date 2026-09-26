param(
    [Parameter(Mandatory = $true)]
    [string]$LoginHost,

    [int]$LoginPort = 5999,
    [int]$LocalLoginPort = 5998,
    [int]$LocalGamePort = 7000,
    [string]$LocalAdvertisedHost = "127.1.1.110",
    # 参考服与本机中转同址时（登录回包里的 game 端点 host 等于 LoginHost），
    # 代理不会跟随回包，游戏连接一律发往下面这一对；不填就会一直等目标而卡登录。
    [string]$GameHost = "127.1.1.110",
    [int]$GamePort = 13333,
    [string]$PostgresConnectionString = "Host=127.0.0.1;Port=5432;Database=godswar;Username=godswar;Password=godswar_dev_password;Pooling=true",
    [string]$Out = ".\captures\godswar-proxy.log",
    [Nullable[int]]$MonsterMapId = $null
)

$proxyArgs = @(
    "--login-host", $LoginHost,
    "--login-port", $LoginPort,
    "--local-login-port", $LocalLoginPort,
    "--local-game-port", $LocalGamePort,
    "--local-advertised-host", $LocalAdvertisedHost,
    "--default-game-host", $GameHost,
    "--default-game-port", [string]$GamePort,
    "--postgres-connection-string", $PostgresConnectionString,
    "--out", $Out
)
if ($null -ne $MonsterMapId) {
    $proxyArgs += @("--monster-map-id", [string]$MonsterMapId)
}

dotnet run --project .\tools\Godswar.CaptureProxy -- @proxyArgs
