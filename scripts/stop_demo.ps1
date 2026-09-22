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
    Write-Output "No local demo runtime state found: $statePath"
    exit 0
}

$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
function Stop-OwnedProcess([int]$ProcessId, [object]$ExpectedStartTime, [string]$Label) {
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) { Write-Output "$Label has already exited"; return }
    $actual = $process.StartTime.ToUniversalTime()
    $expected = if ($ExpectedStartTime -is [datetime]) {
        $ExpectedStartTime.ToUniversalTime()
    } else {
        [DateTimeOffset]::Parse([string]$ExpectedStartTime).UtcDateTime
    }
    if ([math]::Abs(($actual - $expected).TotalSeconds) -gt 2) {
        Write-Warning "$Label PID is owned by another process; it was not stopped"
        return
    }
    Stop-Process -Id $ProcessId -Force
    Write-Output "$Label stopped"
}

Stop-OwnedProcess ([int]$state.frontendPid) $state.frontendStartTime "Frontend"
Stop-OwnedProcess ([int]$state.backendPid) $state.backendStartTime "Backend"
Remove-Item -LiteralPath $statePath -Force
Write-Output "Local demo stopped"
