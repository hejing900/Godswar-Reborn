#requires -Version 7
<#
    启动 Godswar GM 工具（独立进程，不依赖当前终端会话）。

    连接串解析顺序：
      1) -ConnectionString 参数
      2) 环境变量 GODSWAR_GM_POSTGRES_CONNECTION_STRING
      3) 环境变量 GODSWAR_POSTGRES_CONNECTION_STRING
      4) 仓库 appsettings.json 的 postgresConnectionString
         （即：服务器换库时，这里会自动跟着换）
      5) -Database/-Host/-Port/-User/-Password 组合

    示例：
      # 跟随仓库 appsettings.json
      .\start-gm-tool.ps1

      # 指向另一个库
      .\start-gm-tool.ps1 -Database godswar_test

      # 显式连接串 + 换端口
      .\start-gm-tool.ps1 -ConnectionString 'Host=10.0.0.5;Port=5432;Database=godswar;Username=gm;Password=***' -Url 'http://0.0.0.0:8090'
#>
param(
    [string]$ConnectionString,
    [string]$Database,
    [string]$Host_ = '127.0.0.1',
    [int]$Port = 5432,
    [string]$User = 'godswar',
    [string]$Password = 'godswar_dev_password',
    [string]$Url,
    [string]$ClientRoot,
    [switch]$Rebuild,
    [switch]$Foreground
)

$ErrorActionPreference = 'Stop'

$toolRoot = $PSScriptRoot
$repoRoot = Resolve-Path (Join-Path $toolRoot '..\..')
$project = Join-Path $toolRoot 'Godswar.GmTool.csproj'
$dll = Join-Path $toolRoot 'bin\Release\net10.0\Godswar.GmTool.dll'
$logDir = Join-Path $toolRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Resolve-ConnectionString {
    if (-not [string]::IsNullOrWhiteSpace($ConnectionString)) { return $ConnectionString }
    foreach ($name in 'GODSWAR_GM_POSTGRES_CONNECTION_STRING', 'GODSWAR_POSTGRES_CONNECTION_STRING') {
        $value = [Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
    }
    $settings = Join-Path $repoRoot 'appsettings.json'
    if (Test-Path $settings) {
        try {
            $raw = Get-Content $settings -Raw
            $found = ($raw | ConvertFrom-Json).storage.postgresConnectionString
            if ([string]::IsNullOrWhiteSpace($found)) {
                # 结构可能被调整过：按属性名兜底查找。
                $match = [regex]'"postgresConnectionString"\s*:\s*"([^"]+)"'
                if ($match.IsMatch($raw)) { $found = $match.Match($raw).Groups[1].Value }
            }
            if (-not [string]::IsNullOrWhiteSpace($found)) {
                if ($Database) { $found = ($found -replace 'Database=[^;]*', "Database=$Database") }
                return $found
            }
        }
        catch { }
    }
    if ($Database) {
        return "Host=$Host_;Port=$Port;Database=$Database;Username=$User;Password=$Password"
    }
    throw '未找到连接串：请用 -ConnectionString，或设置 GODSWAR_GM_POSTGRES_CONNECTION_STRING，或确认仓库 appsettings.json 可读。'
}

$resolved = Resolve-ConnectionString
if (-not $Url) { $Url = [Environment]::GetEnvironmentVariable('GODSWAR_GM_BIND_URL') }
if (-not $Url) { $Url = 'http://127.0.0.1:8090' }
if (-not $ClientRoot) { $ClientRoot = [Environment]::GetEnvironmentVariable('GODSWAR_GM_CLIENT_ROOT') }
if (-not $ClientRoot -and (Test-Path 'D:\Godswar Origin')) { $ClientRoot = 'D:\Godswar Origin' }

$listenPort = ([uri]$Url).Port
$existing = Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "端口 $listenPort 已被 PID $($existing[0].OwningProcess) 占用；GM 工具可能已在运行。" -ForegroundColor Yellow
    Write-Host "如需重启：先运行 .\stop-gm-tool.ps1 -Port $listenPort" -ForegroundColor Yellow
    Write-Host "访问地址：$Url"
    exit 0
}

if ($Rebuild -or -not (Test-Path $dll)) {
    Write-Host "构建 Godswar.GmTool …" -ForegroundColor Cyan
    dotnet build $project -c Release -v m --nologo
    if ($LASTEXITCODE -ne 0) { throw '构建失败' }
}

$env:GODSWAR_GM_POSTGRES_CONNECTION_STRING = $resolved
$env:GODSWAR_GM_BIND_URL = $Url
if ($ClientRoot) { $env:GODSWAR_GM_CLIENT_ROOT = $ClientRoot }

$outLog = Join-Path $logDir 'gm-tool.out.log'
$errLog = Join-Path $logDir 'gm-tool.err.log'

if ($Foreground) {
    Write-Host "前台运行（Ctrl+C 结束）。访问地址：$Url"
    dotnet $dll --contentRoot $toolRoot
    exit $LASTEXITCODE
}

$process = Start-Process -FilePath 'dotnet' `
    -ArgumentList @($dll, '--contentRoot', $toolRoot) `
    -WorkingDirectory $toolRoot `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog

for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 250
    if (Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue) { break }
    if ($process.HasExited) {
        Write-Host '启动失败，错误日志：' -ForegroundColor Red
        if (Test-Path $errLog) { Get-Content $errLog -Tail 20 }
        if (Test-Path $outLog) { Get-Content $outLog -Tail 20 }
        exit 1
    }
}

try {
    $status = Invoke-RestMethod "$Url/api/status" -TimeoutSec 10
    $target = "$($status.connection.database)@$($status.connection.host):$($status.connection.port)"
}
catch {
    $target = "（状态检查失败：$($_.Exception.Message)）"
}

Write-Host "GM 工具已作为独立进程启动。" -ForegroundColor Green
Write-Host "  PID      : $($process.Id)（独立于当前终端；关闭终端不会停止它）"
Write-Host "  访问地址 : $Url"
Write-Host "  数据库   : $target"
Write-Host "  日志     : $outLog"
Write-Host "  停止     : .\stop-gm-tool.ps1 -Port $listenPort"
