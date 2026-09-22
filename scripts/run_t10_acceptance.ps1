[CmdletBinding()]
param(
    [string]$Root = "",
    [int]$BackendPort = 18008,
    [int]$FrontendPort = 13008,
    [ValidateRange(1, 86400)]
    [int]$DurationSeconds = 300,
    [ValidateRange(1, 128)]
    [int]$ExpectedLogicalProcessors = 4,
    [ValidateRange(1, 512)]
    [int]$ExpectedMemoryGB = 8
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = if ([string]::IsNullOrWhiteSpace($Root)) {
    [IO.Path]::GetFullPath((Join-Path $projectRoot ".demo-runtime"))
} elseif ([IO.Path]::IsPathRooted($Root)) {
    [IO.Path]::GetFullPath($Root)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $Root))
}
$evidenceRoot = Join-Path $runtimeRoot "logs\t10-acceptance"
$reportPath = Join-Path $evidenceRoot "report.json"
$referenceFactsPath = Join-Path $evidenceRoot "reference-machine.json"
$referenceStrictPath = Join-Path $evidenceRoot "reference-machine-strict.log"
$replayLogPath = Join-Path $evidenceRoot "full-replay.log"
$benchmarkLogPath = Join-Path $evidenceRoot "benchmark.log"
$checkScript = Join-Path $projectRoot "scripts\check_reference_machine.ps1"
$verifyScript = Join-Path $projectRoot "scripts\verify_offline_demo.ps1"
$benchmarkScript = Join-Path $projectRoot "scripts\benchmark_demo.ps1"

New-Item -ItemType Directory -Force $evidenceRoot | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $runtimeRoot "demo-manifest.json"))) {
    throw "No verified demo manifest found. Run python scripts/prepare_demo.py --root '$runtimeRoot' before the offline handoff."
}

$referenceFactsText = & powershell -NoProfile -ExecutionPolicy Bypass -File $checkScript `
    -ExpectedLogicalProcessors $ExpectedLogicalProcessors -ExpectedMemoryGB $ExpectedMemoryGB
$referenceFactsText | Set-Content -LiteralPath $referenceFactsPath -Encoding utf8
$referenceFacts = $referenceFactsText | ConvertFrom-Json

$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -NoProfile -ExecutionPolicy Bypass -File $checkScript `
    -ExpectedLogicalProcessors $ExpectedLogicalProcessors -ExpectedMemoryGB $ExpectedMemoryGB -Strict `
    2>&1 | Tee-Object -FilePath $referenceStrictPath
$referenceExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorAction

$report = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    root = $runtimeRoot
    evidence_root = $evidenceRoot
    reference_machine = $referenceFacts
    reference_machine_strict_exit_code = $referenceExitCode
    reference_machine_strict_log = $referenceStrictPath
    full_replay_e2e = $null
    full_replay_log = $replayLogPath
    benchmark = $null
    benchmark_log = $benchmarkLogPath
    manual_fully_disconnected_replay = "required_external"
}

if ($referenceExitCode -ne 0) {
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding utf8
    throw "T10 physical reference-machine gate failed. See $referenceStrictPath and $reportPath."
}

$ErrorActionPreference = "Continue"
& powershell -NoProfile -ExecutionPolicy Bypass -File $verifyScript `
    -Root $runtimeRoot -BackendPort $BackendPort -FrontendPort $FrontendPort -RunFullReplayE2E `
    2>&1 | Tee-Object -FilePath $replayLogPath
$replayExitCode = $LASTEXITCODE
$report.full_replay_e2e = [ordered]@{
    exit_code = $replayExitCode
    passed = ($replayExitCode -eq 0)
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $benchmarkScript `
    -Root $runtimeRoot -BackendPort ($BackendPort + 1) -FrontendPort ($FrontendPort + 1) `
    -CpuCores $ExpectedLogicalProcessors -MemoryBudgetGB $ExpectedMemoryGB `
    -DurationSeconds $DurationSeconds -DisableRateLimit `
    2>&1 | Tee-Object -FilePath $benchmarkLogPath
$benchmarkExitCode = $LASTEXITCODE
$report.benchmark = [ordered]@{
    exit_code = $benchmarkExitCode
    passed = ($benchmarkExitCode -eq 0)
    duration_seconds = $DurationSeconds
}
$ErrorActionPreference = $previousErrorAction

$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding utf8
Write-Output ($report | ConvertTo-Json -Depth 12)

if ($replayExitCode -ne 0 -or $benchmarkExitCode -ne 0) {
    throw "T10 runtime evidence failed. See $replayLogPath, $benchmarkLogPath, and $reportPath."
}
