[CmdletBinding()]
param(
    [string]$Root = "",
    [int]$BackendPort = 18006,
    [int]$FrontendPort = 13006,
    [switch]$RunBrowserE2E,
    [switch]$RunModelRecoveryE2E,
    [switch]$RunModelConsistencyE2E,
    [switch]$RunModelStabilityE2E,
    [switch]$RunRuntimeRollbackE2E,
    [switch]$RunFullReplayE2E
)

$ErrorActionPreference = "Stop"
$selectedModes = @($RunBrowserE2E, $RunModelRecoveryE2E, $RunModelConsistencyE2E, $RunModelStabilityE2E, $RunRuntimeRollbackE2E, $RunFullReplayE2E) | Where-Object { $_ }
if ($selectedModes.Count -gt 1) {
    throw "Choose only one browser E2E mode."
}
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = if ([string]::IsNullOrWhiteSpace($Root)) {
    [IO.Path]::GetFullPath((Join-Path $projectRoot ".demo-runtime"))
} elseif ([IO.Path]::IsPathRooted($Root)) {
    [IO.Path]::GetFullPath($Root)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $Root))
}
$python = (Get-Command python -ErrorAction Stop).Source
$previousPythonPath = $env:PYTHONPATH
$previousBaseUrl = $env:BASE_URL
$previousApiBaseUrl = $env:API_BASE_URL
$previousCorsOrigins = $env:CORS_ORIGINS
$previousRateLimitRequests = $env:RATE_LIMIT_REQUESTS
$previousTrainingFailureMode = $env:DEMO_TRAINING_FAILURE_MODE
$previousTrainingFailureMarker = $env:DEMO_TRAINING_FAILURE_MARKER
$previousTrainingProfile = $env:DEMO_TRAINING_PROFILE
$previousRuntimeRollbackE2E = $env:DEMO_RUNTIME_ROLLBACK_E2E
$previousDemoAuth = $env:DEMO_AUTH_ENABLED
$statePath = Join-Path $runtimeRoot "demo-process.json"
$trainingFailureMarker = Join-Path $runtimeRoot ".training-failure.marker"
$startedByScript = $false

try {
    if (Test-Path -LiteralPath $statePath) {
        $existingState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $existingBackend = Get-Process -Id ([int]$existingState.backendPid) -ErrorAction SilentlyContinue
        $existingFrontend = Get-Process -Id ([int]$existingState.frontendPid) -ErrorAction SilentlyContinue
        if ($existingBackend -or $existingFrontend) {
            throw "Demo services are already running. Stop them before running the offline smoke test."
        }
    }
    & $python (Join-Path $projectRoot "scripts\verify_offline_demo.py") --root $runtimeRoot
    if ($LASTEXITCODE -ne 0) { throw "Static offline verification failed." }

    $env:PYTHONPATH = if ($previousPythonPath) {
        "$(Join-Path $projectRoot 'scripts');$previousPythonPath"
    } else {
        (Join-Path $projectRoot "scripts")
    }
    $guardErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $python -c "import offline_socket_guard, socket; socket.create_connection(('example.com', 80), 1); raise SystemExit('external socket was not blocked')" 2>$null
        $guardExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $guardErrorAction
    }
    if ($guardExitCode -eq 0) { throw "Offline socket guard did not block the external connection." }

    if ($RunFullReplayE2E) {
        $resetDemoRoot = $env:DEMO_ROOT
        $resetPythonPath = $env:PYTHONPATH
        try {
            $env:DEMO_ROOT = $runtimeRoot
            $env:PYTHONPATH = if ($previousPythonPath) {
                "$(Join-Path $projectRoot 'backend');$previousPythonPath"
            } else {
                (Join-Path $projectRoot "backend")
            }
            & $python -c "from app.services import demo_service; demo_service.switch_scenario('standard', confirm=True)"
            $resetExitCode = $LASTEXITCODE
        } finally {
            if ($null -eq $resetDemoRoot) { Remove-Item Env:DEMO_ROOT -ErrorAction SilentlyContinue } else { $env:DEMO_ROOT = $resetDemoRoot }
            if ($null -eq $resetPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue } else { $env:PYTHONPATH = $resetPythonPath }
        }
        if ($resetExitCode -ne 0) { throw "Full replay could not reset the demo scenario to standard (exit code $resetExitCode)." }
    }

    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"
    if ($RunBrowserE2E -or $RunModelRecoveryE2E -or $RunModelConsistencyE2E -or $RunModelStabilityE2E -or $RunRuntimeRollbackE2E -or $RunFullReplayE2E) { $env:RATE_LIMIT_REQUESTS = "1000" }
    if ($RunModelRecoveryE2E) {
        Remove-Item -LiteralPath $trainingFailureMarker -Force -ErrorAction SilentlyContinue
        $env:DEMO_TRAINING_FAILURE_MODE = "fail_once"
        $env:DEMO_TRAINING_FAILURE_MARKER = $trainingFailureMarker
        $env:DEMO_TRAINING_PROFILE = "smoke"
    }
    if ($RunModelConsistencyE2E) {
        Remove-Item Env:DEMO_TRAINING_FAILURE_MODE -ErrorAction SilentlyContinue
        Remove-Item Env:DEMO_TRAINING_FAILURE_MARKER -ErrorAction SilentlyContinue
        $env:DEMO_TRAINING_PROFILE = "full"
    }
    if ($RunModelStabilityE2E) {
        Remove-Item Env:DEMO_TRAINING_FAILURE_MODE -ErrorAction SilentlyContinue
        Remove-Item Env:DEMO_TRAINING_FAILURE_MARKER -ErrorAction SilentlyContinue
        $env:DEMO_TRAINING_PROFILE = "full"
    }
    if ($RunRuntimeRollbackE2E) {
        Remove-Item Env:DEMO_TRAINING_FAILURE_MODE -ErrorAction SilentlyContinue
        Remove-Item Env:DEMO_TRAINING_FAILURE_MARKER -ErrorAction SilentlyContinue
        Remove-Item Env:DEMO_TRAINING_PROFILE -ErrorAction SilentlyContinue
        $env:DEMO_RUNTIME_ROLLBACK_E2E = "true"
    }
    if ($RunFullReplayE2E) {
        Remove-Item Env:DEMO_TRAINING_FAILURE_MODE -ErrorAction SilentlyContinue
        Remove-Item Env:DEMO_TRAINING_FAILURE_MARKER -ErrorAction SilentlyContinue
        Remove-Item Env:DEMO_TRAINING_PROFILE -ErrorAction SilentlyContinue
        $env:DEMO_AUTH_ENABLED = "true"
    }
    if ($RunFullReplayE2E) {
        & (Join-Path $projectRoot "scripts\start_demo.ps1") -Root $runtimeRoot -BackendPort $BackendPort -FrontendPort $FrontendPort -Offline -WithAuth
    } else {
        & (Join-Path $projectRoot "scripts\start_demo.ps1") -Root $runtimeRoot -BackendPort $BackendPort -FrontendPort $FrontendPort -Offline
    }
    $startedByScript = $true
    $baseUrl = "http://127.0.0.1:$BackendPort"
    $frontendUrl = "http://127.0.0.1:$FrontendPort"
    $health = Invoke-RestMethod "$baseUrl/health"
    $products = Invoke-RestMethod "$baseUrl/api/products"
    $model = Invoke-RestMethod "$baseUrl/api/model-info"
    $inventory = Invoke-RestMethod "$baseUrl/api/inventory"
    Invoke-WebRequest $frontendUrl -UseBasicParsing | Out-Null
    if ($health.status -ne "healthy") { throw "Offline demo health was $($health.status)." }
    if (-not $products.products) { throw "Offline demo returned no products." }
    if ($model.status -ne "ready") { throw "Offline demo model status was $($model.status)." }
    if (-not $inventory.cells) { throw "Offline demo returned no inventory cells." }

    if ($RunBrowserE2E -or $RunModelRecoveryE2E -or $RunModelConsistencyE2E -or $RunModelStabilityE2E -or $RunRuntimeRollbackE2E -or $RunFullReplayE2E) {
        $env:BASE_URL = $frontendUrl
        $env:API_BASE_URL = "$baseUrl/api"
        Push-Location (Join-Path $projectRoot "frontend")
        try {
            if ($RunFullReplayE2E) {
                & npm.cmd run test:e2e -- full.replay.spec.js
                if ($LASTEXITCODE -ne 0) { throw "Offline full replay E2E failed with exit code $LASTEXITCODE." }
            } elseif ($RunModelRecoveryE2E) {
                & npm.cmd run test:e2e -- model.recovery.spec.js
                if ($LASTEXITCODE -ne 0) { throw "Offline model recovery E2E failed with exit code $LASTEXITCODE." }
            } elseif ($RunModelConsistencyE2E) {
                & npm.cmd run test:e2e -- model.consistency.spec.js
                if ($LASTEXITCODE -ne 0) { throw "Offline model consistency E2E failed with exit code $LASTEXITCODE." }
            } elseif ($RunModelStabilityE2E) {
                & npm.cmd run test:e2e -- model.stability.spec.js
                if ($LASTEXITCODE -ne 0) { throw "Offline model stability E2E failed with exit code $LASTEXITCODE." }
            } elseif ($RunRuntimeRollbackE2E) {
                & npm.cmd run test:e2e -- runtime.rollback.spec.js
                if ($LASTEXITCODE -ne 0) { throw "Offline runtime rollback E2E failed with exit code $LASTEXITCODE." }
            } else {
                & npm.cmd run test:e2e
                if ($LASTEXITCODE -ne 0) { throw "Offline browser E2E failed with exit code $LASTEXITCODE." }
            }
        } finally {
            Pop-Location
        }
    }

    [ordered]@{
        ready = $true
        offline_guard = $true
        health = $health.status
        product_count = $products.products.Count
        model_status = $model.status
        inventory_count = $inventory.cells.Count
        frontend = $frontendUrl
        browser_e2e = [bool]$RunBrowserE2E
        model_recovery_e2e = [bool]$RunModelRecoveryE2E
        model_consistency_e2e = [bool]$RunModelConsistencyE2E
        model_stability_e2e = [bool]$RunModelStabilityE2E
        runtime_rollback_e2e = [bool]$RunRuntimeRollbackE2E
        full_replay_e2e = [bool]$RunFullReplayE2E
    } | ConvertTo-Json
} finally {
    if ($startedByScript -and (Test-Path -LiteralPath $statePath)) {
        & (Join-Path $projectRoot "scripts\stop_demo.ps1") -Root $runtimeRoot
    }
    if ($null -eq $previousPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue } else { $env:PYTHONPATH = $previousPythonPath }
    if ($null -eq $previousBaseUrl) { Remove-Item Env:BASE_URL -ErrorAction SilentlyContinue } else { $env:BASE_URL = $previousBaseUrl }
    if ($null -eq $previousApiBaseUrl) { Remove-Item Env:API_BASE_URL -ErrorAction SilentlyContinue } else { $env:API_BASE_URL = $previousApiBaseUrl }
    if ($null -eq $previousCorsOrigins) { Remove-Item Env:CORS_ORIGINS -ErrorAction SilentlyContinue } else { $env:CORS_ORIGINS = $previousCorsOrigins }
    if ($null -eq $previousRateLimitRequests) { Remove-Item Env:RATE_LIMIT_REQUESTS -ErrorAction SilentlyContinue } else { $env:RATE_LIMIT_REQUESTS = $previousRateLimitRequests }
    if ($null -eq $previousTrainingFailureMode) { Remove-Item Env:DEMO_TRAINING_FAILURE_MODE -ErrorAction SilentlyContinue } else { $env:DEMO_TRAINING_FAILURE_MODE = $previousTrainingFailureMode }
    if ($null -eq $previousTrainingFailureMarker) { Remove-Item Env:DEMO_TRAINING_FAILURE_MARKER -ErrorAction SilentlyContinue } else { $env:DEMO_TRAINING_FAILURE_MARKER = $previousTrainingFailureMarker }
    if ($null -eq $previousTrainingProfile) { Remove-Item Env:DEMO_TRAINING_PROFILE -ErrorAction SilentlyContinue } else { $env:DEMO_TRAINING_PROFILE = $previousTrainingProfile }
    if ($null -eq $previousRuntimeRollbackE2E) { Remove-Item Env:DEMO_RUNTIME_ROLLBACK_E2E -ErrorAction SilentlyContinue } else { $env:DEMO_RUNTIME_ROLLBACK_E2E = $previousRuntimeRollbackE2E }
    if ($null -eq $previousDemoAuth) { Remove-Item Env:DEMO_AUTH_ENABLED -ErrorAction SilentlyContinue } else { $env:DEMO_AUTH_ENABLED = $previousDemoAuth }
    Remove-Item -LiteralPath $trainingFailureMarker -Force -ErrorAction SilentlyContinue
}
