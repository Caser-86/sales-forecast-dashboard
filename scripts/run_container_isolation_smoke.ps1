[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$ReportPath = ".demo-runtime\logs\t10-acceptance\container-isolation.json",
    [ValidateRange(1, 32)]
    [int]$CpuCores = 4,
    [ValidateRange(1, 128)]
    [int]$MemoryBudgetGB = 8
)

$ErrorActionPreference = "Stop"
$projectRootInput = if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    Join-Path $PSScriptRoot ".."
} else {
    $ProjectRoot
}
$projectRoot = (Resolve-Path $projectRootInput).Path
$reportPath = if ([IO.Path]::IsPathRooted($ReportPath)) {
    [IO.Path]::GetFullPath($ReportPath)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $ReportPath))
}
$dataPath = (Resolve-Path (Join-Path $projectRoot "backend\data")).Path
$modelPath = (Resolve-Path (Join-Path $projectRoot "backend\ml\saved_models")).Path
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$networkName = "sales-t10-internal-$suffix"
$backendName = "sales-t10-backend-$suffix"
$frontendName = "sales-t10-frontend-$suffix"
$runtimeVolume = "sales-t10-runtime-$suffix"
$logsVolume = "sales-t10-logs-$suffix"
$createdContainers = @()
$createdVolumes = @()
$networkCreated = $false

function Invoke-DockerOutput([string[]]$Arguments) {
    $output = & docker @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($Arguments -join ' ') failed with exit code $($LASTEXITCODE): $($output -join ' ')"
    }
    return ($output -join [Environment]::NewLine)
}

function Get-ContainerJson([string]$Name) {
    return (Invoke-DockerOutput @("inspect", $Name) | ConvertFrom-Json)
}

try {
    Invoke-DockerOutput @("network", "create", "--internal", $networkName) | Out-Null
    $networkCreated = $true
    Invoke-DockerOutput @("volume", "create", $runtimeVolume) | Out-Null
    Invoke-DockerOutput @("volume", "create", $logsVolume) | Out-Null
    $createdVolumes = @($runtimeVolume, $logsVolume)

    $backendArguments = @(
        "run", "-d", "--name", $backendName, "--network", $networkName, "--network-alias", "backend",
        "--cpus", $CpuCores.ToString(), "--memory", ("{0}g" -f $MemoryBudgetGB),
        "--mount", ("type=bind,source={0},target=/app/data,readonly" -f $dataPath),
        "--mount", ("type=bind,source={0},target=/app/ml/saved_models,readonly" -f $modelPath),
        "--mount", ("type=volume,source={0},target=/app/runtime" -f $runtimeVolume),
        "--mount", ("type=volume,source={0},target=/app/logs" -f $logsVolume),
        "--env", "ENV=development", "--env", "DEBUG=false", "--env", "LOG_LEVEL=INFO",
        "--env", "DEMO_AUTH_ENABLED=true", "--env", "RATE_LIMIT_ENABLED=false",
        "--env", "DATABASE_URL=sqlite:////app/runtime/dashboard.db",
        "--env", "FORECAST_DAYS=30", "--env", "FORECAST_WORKERS=4", "--env", "INVENTORY_MAX_AGE_DAYS=7",
        "--health-cmd", "curl -fsS http://localhost:8000/health || exit 1",
        "--health-interval", "5s", "--health-timeout", "3s", "--health-start-period", "10s", "--health-retries", "12",
        "sales-forecast-dashboard-backend:latest"
    )
    Invoke-DockerOutput $backendArguments | Out-Null
    $createdContainers += $backendName

    $backendReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 2
        $backendState = Get-ContainerJson $backendName
        if ($backendState[0].State.Status -eq "running" -and $backendState[0].State.Health.Status -eq "healthy") {
            $backendReady = $true
            break
        }
    }
    if (-not $backendReady) {
        $logs = Invoke-DockerOutput @("logs", $backendName)
        throw "isolated backend did not become healthy: $logs"
    }

    $frontendArguments = @(
        "run", "-d", "--name", $frontendName, "--network", $networkName,
        "--cpus", $CpuCores.ToString(), "--memory", ("{0}g" -f $MemoryBudgetGB),
        "sales-forecast-dashboard-frontend:latest"
    )
    Invoke-DockerOutput $frontendArguments | Out-Null
    $createdContainers += $frontendName
    $frontendPage = ""
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $frontendCandidate = & docker exec $frontendName wget -qO- http://127.0.0.1/ 2>$null
        $frontendExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorAction
        if ($frontendExitCode -eq 0) {
            $frontendPage = $frontendCandidate -join [Environment]::NewLine
            break
        }
        Start-Sleep -Seconds 1
    }
    if ($frontendPage.Length -eq 0) {
        $logs = Invoke-DockerOutput @("logs", $frontendName)
        throw "isolated frontend did not become ready: $logs"
    }
    $backendHealth = Invoke-DockerOutput @("exec", $frontendName, "wget", "-qO-", "http://backend:8000/health")
    $authStatus = Invoke-DockerOutput @("exec", $frontendName, "wget", "-qO-", "http://backend:8000/api/auth/config")
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $externalOutput = & docker exec $backendName curl --connect-timeout 2 --max-time 3 -fsS https://example.com 2>&1
    $externalExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction

    $network = (Invoke-DockerOutput @("network", "inspect", $networkName) | ConvertFrom-Json)[0]
    $backend = Get-ContainerJson $backendName
    $frontend = Get-ContainerJson $frontendName
    $backendStats = Invoke-DockerOutput @("stats", $backendName, "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}")
    $frontendStats = Invoke-DockerOutput @("stats", $frontendName, "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}")
    $passed = [bool]$network.Internal -and $externalExitCode -ne 0 -and $frontendPage.Length -gt 0 -and $backendHealth -match '"status":"healthy"' -and $authStatus -match '"enabled":true'

    $report = [ordered]@{
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        result = if ($passed) { "passed" } else { "failed" }
        network_internal = [bool]$network.Internal
        external_https_exit_code = $externalExitCode
        external_https_output = ($externalOutput -join " ").Trim()
        frontend_served_bytes = $frontendPage.Length
        backend_health = $backendHealth
        demo_auth_status = $authStatus
        backend_limits = [ordered]@{
            cpus = $backend[0].HostConfig.NanoCpus / 1e9
            memory_bytes = $backend[0].HostConfig.Memory
            stats = $backendStats
        }
        frontend_limits = [ordered]@{
            cpus = $frontend[0].HostConfig.NanoCpus / 1e9
            memory_bytes = $frontend[0].HostConfig.Memory
            stats = $frontendStats
        }
        browser_replay = "not_executed_in_internal_network"
        physical_reference_machine = $false
        manual_fully_disconnected_replay = "not_executed"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding utf8
    $report | ConvertTo-Json -Depth 10
    if (-not $passed) { throw "container isolation smoke failed; see $reportPath" }
} finally {
    foreach ($container in $createdContainers) {
        docker rm -f $container 2>$null | Out-Null
    }
    foreach ($volume in $createdVolumes) {
        docker volume rm $volume 2>$null | Out-Null
    }
    if ($networkCreated) {
        docker network rm $networkName 2>$null | Out-Null
    }
}
