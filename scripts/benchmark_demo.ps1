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
    [int]$Concurrency = 10,
    [ValidateRange(0, 86400)]
    [int]$DurationSeconds = 0,
    [ValidateRange(1, 60)]
    [int]$MemorySampleIntervalSeconds = 5,
    [switch]$DisableRateLimit
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
$benchmarkScript = Join-Path $projectRoot "scripts\benchmark_api.py"
$benchmarkOutputPath = Join-Path $runtimeRoot "logs\benchmark-api.json"
$benchmarkErrorPath = Join-Path $runtimeRoot "logs\benchmark-api.error.log"
$stopwatch = [Diagnostics.Stopwatch]::StartNew()
$benchmarkProcess = $null
$workingSetSamples = [System.Collections.Generic.List[object]]::new()
$previousRateLimitEnabled = $env:RATE_LIMIT_ENABLED

function Get-WorkingSetSample($backendPid, $frontendPid) {
    $backend = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
    $frontend = Get-Process -Id $frontendPid -ErrorAction SilentlyContinue
    if (-not $backend -and -not $frontend) { return $null }
    $backendMb = if ($backend) { [math]::Round($backend.WorkingSet64 / 1MB, 1) } else { 0 }
    $frontendMb = if ($frontend) { [math]::Round($frontend.WorkingSet64 / 1MB, 1) } else { 0 }
    return [ordered]@{
        captured_at = (Get-Date).ToUniversalTime().ToString("o")
        backend_mb = $backendMb
        frontend_mb = $frontendMb
        total_mb = [math]::Round($backendMb + $frontendMb, 1)
    }
}

try {
    if ($DisableRateLimit) { $env:RATE_LIMIT_ENABLED = "false" }
    & (Join-Path $projectRoot "scripts\start_demo.ps1") -Root $runtimeRoot -BackendPort $BackendPort -FrontendPort $FrontendPort -CpuAffinityCores $CpuCores
    $stopwatch.Stop()
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $backendProcess = Get-Process -Id ([int]$state.backendPid)
    $frontendProcess = Get-Process -Id ([int]$state.frontendPid)
    $initialSample = Get-WorkingSetSample $state.backendPid $state.frontendPid
    if ($initialSample) { $workingSetSamples.Add($initialSample) }

    $benchmarkArguments = @(
        "`"$benchmarkScript`"",
        "--base-url", "http://127.0.0.1:$BackendPort",
        "--path", "/api/model-info",
        "--requests", "$Requests",
        "--concurrency", "$Concurrency"
    )
    if ($DurationSeconds -gt 0) {
        $benchmarkArguments += @("--duration-seconds", "$DurationSeconds")
        Remove-Item -LiteralPath $benchmarkOutputPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $benchmarkErrorPath -Force -ErrorAction SilentlyContinue
        $benchmarkProcess = Start-Process -FilePath $python -ArgumentList $benchmarkArguments `
            -RedirectStandardOutput $benchmarkOutputPath -RedirectStandardError $benchmarkErrorPath -PassThru
        while (-not $benchmarkProcess.HasExited) {
            $sample = Get-WorkingSetSample $state.backendPid $state.frontendPid
            if ($sample) { $workingSetSamples.Add($sample) }
            Start-Sleep -Seconds $MemorySampleIntervalSeconds
            $benchmarkProcess.Refresh()
        }
        $benchmarkProcess.WaitForExit()
        if ($benchmarkProcess.ExitCode -ne 0) {
            $errorText = if (Test-Path -LiteralPath $benchmarkErrorPath) { Get-Content -LiteralPath $benchmarkErrorPath -Raw } else { "" }
            throw "API duration benchmark failed with exit code $($benchmarkProcess.ExitCode): $errorText"
        }
        $finalSample = Get-WorkingSetSample $state.backendPid $state.frontendPid
        if ($finalSample) { $workingSetSamples.Add($finalSample) }
        $benchmark = (Get-Content -LiteralPath $benchmarkOutputPath -Raw) | ConvertFrom-Json
    } else {
        $benchmarkArguments[0] = $benchmarkScript
        $benchmarkJson = & $python @benchmarkArguments
        if ($LASTEXITCODE -ne 0) { throw "API benchmark failed." }
        $benchmark = $benchmarkJson | ConvertFrom-Json
    }
    if ($workingSetSamples.Count -eq 0) { throw "No process working-set sample was collected." }
    $workingSetValues = @($workingSetSamples | ForEach-Object { [double]$_.total_mb })
    $workingSetMb = [math]::Round($workingSetValues[-1], 1)
    $peakWorkingSetMb = [math]::Round(($workingSetValues | Measure-Object -Maximum).Maximum, 1)
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
        peak_working_set_mb = $peakWorkingSetMb
        under_memory_budget = $peakWorkingSetMb -lt ($MemoryBudgetGB * 1024)
        working_set_samples = @($workingSetSamples)
        api = $benchmark
    } | ConvertTo-Json -Depth 10
} finally {
    if ($benchmarkProcess -and -not $benchmarkProcess.HasExited) {
        Stop-Process -Id $benchmarkProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $statePath) {
        & (Join-Path $projectRoot "scripts\stop_demo.ps1") -Root $runtimeRoot
    }
    if ($null -eq $previousRateLimitEnabled) { Remove-Item Env:RATE_LIMIT_ENABLED -ErrorAction SilentlyContinue } else { $env:RATE_LIMIT_ENABLED = $previousRateLimitEnabled }
}
