[CmdletBinding()]
param(
    [string]$Root = (Join-Path $PSScriptRoot "..\.demo-runtime")
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = if ([IO.Path]::IsPathRooted($Root)) {
    [IO.Path]::GetFullPath($Root)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $Root))
}
$statePath = Join-Path $runtimeRoot "demo-process.json"

if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Output "没有找到本地演示运行状态: $statePath"
    exit 0
}

$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
function Stop-OwnedProcess([int]$ProcessId, [object]$ExpectedStartTime, [string]$Label) {
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) { Write-Output "$Label 已退出"; return }
    $actual = $process.StartTime.ToUniversalTime()
    $expected = if ($ExpectedStartTime -is [datetime]) {
        $ExpectedStartTime.ToUniversalTime()
    } else {
        [DateTimeOffset]::Parse([string]$ExpectedStartTime).UtcDateTime
    }
    if ([math]::Abs(($actual - $expected).TotalSeconds) -gt 2) {
        Write-Warning "$Label 的 PID 已被其他进程复用，未执行停止"
        return
    }
    Stop-Process -Id $ProcessId -Force
    Write-Output "$Label 已停止"
}

Stop-OwnedProcess ([int]$state.frontendPid) $state.frontendStartTime "前端"
Stop-OwnedProcess ([int]$state.backendPid) $state.backendStartTime "后端"
Remove-Item -LiteralPath $statePath -Force
Write-Output "本地演示已停止"
