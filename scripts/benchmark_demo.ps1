[CmdletBinding()]
param(
    [string]$Root = (Join-Path $PSScriptRoot "..\.demo-runtime"),
    [int]$BackendPort = 18007,
    [int]$FrontendPort = 13007,
    [ValidateRange(1, 32)]
    [int]$CpuCores = 4,
    [ValidateRange(1, 128)]
    [int]$MemoryBudgetGB = 8,
    [int]$Requests = 100,
    [int]$Concurrency = 10
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = if ([IO.Path]::IsPathRooted($Root)) {
    [IO.Path]::GetFullPath($Root)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $Root))
}
$python = (Get-Command python -ErrorAction Stop).Source
$statePath = Join-Path $runtimeRoot "demo-process.json"
$stopwatch = [Diagnostics.Stopwatch]::StartNew()

try {
    & (Join-Path $projectRoot "scripts\start_demo.ps1") -Root $runtimeRoot -BackendPort $BackendPort -FrontendPort $FrontendPort -CpuAffinityCores $CpuCores
    $stopwatch.Stop()
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $backendProcess = Get-Process -Id ([int]$state.backendPid)
    $frontendProcess = Get-Process -Id ([int]$state.frontendPid)
    $workingSetMb = [math]::Round(($backendProcess.WorkingSet64 + $frontendProcess.WorkingSet64) / 1MB, 1)
    $benchmarkJson = & $python (Join-Path $projectRoot "scripts\benchmark_api.py") `
        --base-url "http://127.0.0.1:$BackendPort" `
        --path "/api/model-info" `
        --requests $Requests `
        --concurrency $Concurrency
    if ($LASTEXITCODE -ne 0) { throw "API benchmark failed." }
    $benchmark = $benchmarkJson | ConvertFrom-Json
    [ordered]@{
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        host = [ordered]@{
            processor = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)
            logical_processors = (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
            physical_memory_gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
        }
        target = [ordered]@{
            cpu_affinity_cores = $CpuCores
            memory_budget_gb = $MemoryBudgetGB
            memory_budget_is_process_observation = $true
        }
        startup_seconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 2)
        working_set_mb = $workingSetMb
        under_memory_budget = $workingSetMb -lt ($MemoryBudgetGB * 1024)
        api = $benchmark
    } | ConvertTo-Json -Depth 8
} finally {
    if (Test-Path -LiteralPath $statePath) {
        & (Join-Path $projectRoot "scripts\stop_demo.ps1") -Root $runtimeRoot
    }
}
