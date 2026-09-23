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
$manualTemplateSource = Join-Path $projectRoot "docs\t10-manual-evidence-template.md"
$manualTemplatePath = Join-Path $evidenceRoot "manual-replay.md"
$checkScript = Join-Path $projectRoot "scripts\check_reference_machine.ps1"
$verifyScript = Join-Path $projectRoot "scripts\verify_offline_demo.ps1"
$benchmarkScript = Join-Path $projectRoot "scripts\benchmark_demo.ps1"

New-Item -ItemType Directory -Force $evidenceRoot | Out-Null
if (-not (Test-Path -LiteralPath $manualTemplateSource)) {
    throw "T10 manual evidence template is missing: $manualTemplateSource"
}
if (-not (Test-Path -LiteralPath $manualTemplatePath)) {
    Copy-Item -LiteralPath $manualTemplateSource -Destination $manualTemplatePath
}
if (-not (Test-Path -LiteralPath (Join-Path $runtimeRoot "demo-manifest.json"))) {
    throw "No verified demo manifest found. Run python scripts/prepare_demo.py --root '$runtimeRoot' before the offline handoff."
}
$manualEvidenceText = Get-Content -LiteralPath $manualTemplatePath -Raw -Encoding UTF8
$manualConclusion = [regex]::Match($manualEvidenceText, '(?m)^T10_FINAL_CONCLUSION:\s*(.+?)\s*$')
$unfilledPlaceholder = [string]([char]0x672A) + [string]([char]0x586B) + [string]([char]0x5199)
$manualHasUnfilledPlaceholder = $manualEvidenceText.Contains($unfilledPlaceholder)
$manualHasUncheckedItems = [regex]::IsMatch($manualEvidenceText, '(?m)^\s*-\s*\[\s\]')
$manualHasEmptyTableCells = [regex]::IsMatch($manualEvidenceText, '(?m)\|[ \t]*\|')
$manualEvidenceComplete = $true
if ($manualHasUnfilledPlaceholder) { $manualEvidenceComplete = $false }
if ($manualHasUncheckedItems) { $manualEvidenceComplete = $false }
if ($manualHasEmptyTableCells) { $manualEvidenceComplete = $false }
if (-not $manualConclusion.Success) { $manualEvidenceComplete = $false }
$manualReplayStatus = "required_external"
if ($manualEvidenceComplete) {
    $manualReplayStatus = "operator_recorded"
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
    manual_evidence_template = $manualTemplatePath
    manual_evidence_complete = $manualEvidenceComplete
    manual_fully_disconnected_replay = $manualReplayStatus
}

if ($referenceExitCode -ne 0) {
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding utf8
    throw "T10 physical reference-machine gate failed. See $referenceStrictPath and $reportPath."
}
if (-not $manualEvidenceComplete) {
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding utf8
    throw "T10 manual evidence is incomplete. Complete every field and sign-off in $manualTemplatePath before running automated replay and benchmark. See $reportPath."
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
