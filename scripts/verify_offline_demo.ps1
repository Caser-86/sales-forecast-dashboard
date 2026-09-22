[CmdletBinding()]
param(
    [string]$Root = (Join-Path $PSScriptRoot "..\.demo-runtime"),
    [int]$BackendPort = 18006,
    [int]$FrontendPort = 13006,
    [switch]$RunBrowserE2E
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = if ([IO.Path]::IsPathRooted($Root)) {
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
$statePath = Join-Path $runtimeRoot "demo-process.json"
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
    & $python -c "import offline_socket_guard, socket; socket.create_connection(('example.com', 80), 1); raise SystemExit('external socket was not blocked')" 2>$null
    if ($LASTEXITCODE -eq 0) { throw "Offline socket guard did not block the external connection." }

    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"
    if ($RunBrowserE2E) { $env:RATE_LIMIT_REQUESTS = "1000" }
    & (Join-Path $projectRoot "scripts\start_demo.ps1") -Root $runtimeRoot -BackendPort $BackendPort -FrontendPort $FrontendPort -Offline
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

    if ($RunBrowserE2E) {
        $env:BASE_URL = $frontendUrl
        $env:API_BASE_URL = "$baseUrl/api"
        Push-Location (Join-Path $projectRoot "frontend")
        try {
            & npm.cmd run test:e2e
            if ($LASTEXITCODE -ne 0) { throw "Offline browser E2E failed with exit code $LASTEXITCODE." }
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
}
