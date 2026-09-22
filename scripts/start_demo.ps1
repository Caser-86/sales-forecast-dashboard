[CmdletBinding()]
param(
    [string]$Root = (Join-Path $PSScriptRoot "..\.demo-runtime"),
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$Prepare
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = if ([IO.Path]::IsPathRooted($Root)) {
    [IO.Path]::GetFullPath($Root)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $Root))
}
$statePath = Join-Path $runtimeRoot "demo-process.json"
$backendLog = Join-Path $runtimeRoot "logs\backend-console.log"
$backendErrorLog = Join-Path $runtimeRoot "logs\backend-error.log"
$frontendLog = Join-Path $runtimeRoot "logs\frontend-console.log"
$frontendErrorLog = Join-Path $runtimeRoot "logs\frontend-error.log"

New-Item -ItemType Directory -Force $runtimeRoot | Out-Null
New-Item -ItemType Directory -Force (Split-Path $backendLog) | Out-Null

function Get-ExistingProcess([int]$ProcessId) {
    if ($ProcessId -le 0) { return $null }
    return Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
}

function Assert-PortFree([int]$Port, [string]$Label) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $owner = ($listener | Select-Object -First 1).OwningProcess
        throw "$Label 端口 $Port 已被占用（PID $owner），请更换端口或先停止占用进程"
    }
}

if (Test-Path -LiteralPath $statePath) {
    $oldState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $oldBackend = Get-ExistingProcess ([int]$oldState.backendPid)
    $oldFrontend = Get-ExistingProcess ([int]$oldState.frontendPid)
    if ($oldBackend -or $oldFrontend) {
        throw "演示服务已在运行，先执行 scripts/stop_demo.ps1 -Root '$runtimeRoot'"
    }
    Remove-Item -LiteralPath $statePath -Force
}

Assert-PortFree $BackendPort "后端"
Assert-PortFree $FrontendPort "前端"

$python = (Get-Command python -ErrorAction Stop).Source
if ($Prepare) {
    & $python (Join-Path $projectRoot "scripts\prepare_demo.py") --root $runtimeRoot
    if ($LASTEXITCODE -ne 0) { throw "演示资源准备失败，退出码: $LASTEXITCODE" }
} elseif (-not (Test-Path -LiteralPath (Join-Path $runtimeRoot "demo-manifest.json"))) {
    throw "没有找到已验证的演示包，请先执行 python scripts/prepare_demo.py --root '$runtimeRoot'，或启动时附加 -Prepare"
}

$backendProcess = $null
$frontendProcess = $null
$previousDemoRoot = $env:DEMO_ROOT
$previousPythonUtf8 = $env:PYTHONUTF8
try {
    $env:DEMO_ROOT = $runtimeRoot
    $env:PYTHONUTF8 = "1"
    $backendProcess = Start-Process -FilePath $python -ArgumentList @(
        "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort"
    ) -WorkingDirectory $projectRoot -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrorLog -PassThru
    $frontendProcess = Start-Process -FilePath $python -ArgumentList @(
        "-m", "http.server", "$FrontendPort", "--bind", "127.0.0.1"
    ) -WorkingDirectory (Join-Path $projectRoot "frontend") -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErrorLog -PassThru

    $backendUrl = "http://127.0.0.1:$BackendPort"
    $frontendUrl = "http://127.0.0.1:$FrontendPort"
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) { throw "演示进程提前退出，请查看 $runtimeRoot\logs" }
        try {
            $health = Invoke-WebRequest -Uri "$backendUrl/health" -UseBasicParsing -TimeoutSec 2
            $frontend = Invoke-WebRequest -Uri $frontendUrl -UseBasicParsing -TimeoutSec 2
            if ($health.StatusCode -eq 200 -and $frontend.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "演示服务未在 60 秒内就绪，请查看 $runtimeRoot\logs" }

    $state = [ordered]@{
        version = 1
        root = $runtimeRoot
        backendPid = $backendProcess.Id
        backendStartTime = $backendProcess.StartTime.ToUniversalTime().ToString("o")
        backendPort = $BackendPort
        frontendPid = $frontendProcess.Id
        frontendStartTime = $frontendProcess.StartTime.ToUniversalTime().ToString("o")
        frontendPort = $FrontendPort
        startedAt = (Get-Date).ToUniversalTime().ToString("o")
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    Write-Output "本地演示已启动: $frontendUrl"
    Write-Output "后端健康检查: $backendUrl/health"
    Write-Output "运行状态: $statePath"
} catch {
    foreach ($process in @($frontendProcess, $backendProcess)) {
        if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
    throw
} finally {
    if ($null -eq $previousDemoRoot) { Remove-Item Env:DEMO_ROOT -ErrorAction SilentlyContinue } else { $env:DEMO_ROOT = $previousDemoRoot }
    if ($null -eq $previousPythonUtf8) { Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue } else { $env:PYTHONUTF8 = $previousPythonUtf8 }
}
