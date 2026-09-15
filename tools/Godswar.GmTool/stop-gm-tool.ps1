#requires -Version 7
<#
    停止 Godswar GM 工具。

    只结束监听指定端口的那个进程，不会误杀其它 dotnet 进程。
      .\stop-gm-tool.ps1              # 默认 8090
      .\stop-gm-tool.ps1 -Port 8091
#>
param(
    [int]$Port = 8090
)

$ErrorActionPreference = 'Stop'

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
    Write-Host "端口 $Port 没有监听进程，GM 工具未在运行。" -ForegroundColor Yellow
    exit 0
}

foreach ($owner in ($listener.OwningProcess | Select-Object -Unique)) {
    $process = Get-Process -Id $owner -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    Write-Host "停止 PID $owner（$($process.ProcessName)）…"
    Stop-Process -Id $owner -Force
}

Start-Sleep -Milliseconds 800
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "端口 $Port 仍在监听，请手动检查。" -ForegroundColor Red
    exit 1
}

Write-Host "GM 工具已停止（端口 $Port 已释放）。" -ForegroundColor Green
