[CmdletBinding()]
param(
    [ValidateRange(1, 128)]
    [int]$ExpectedLogicalProcessors = 4,
    [ValidateRange(1, 512)]
    [int]$ExpectedMemoryGB = 8,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
$processors = Get-CimInstance Win32_Processor
$computer = Get-CimInstance Win32_ComputerSystem
$logicalProcessors = [int](($processors | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum)
$physicalMemoryGb = [math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
$memoryDeltaGb = [math]::Abs($physicalMemoryGb - $ExpectedMemoryGB)
$cpuMatches = $logicalProcessors -eq $ExpectedLogicalProcessors
$memoryMatches = $memoryDeltaGb -lt 0.05
$ready = $cpuMatches -and $memoryMatches

[ordered]@{
    ready = $ready
    host = [ordered]@{
        processor = ($processors | Select-Object -First 1 -ExpandProperty Name)
        logical_processors = $logicalProcessors
        physical_memory_gb = $physicalMemoryGb
    }
    expected = [ordered]@{
        logical_processors = $ExpectedLogicalProcessors
        physical_memory_gb = $ExpectedMemoryGB
    }
    checks = [ordered]@{
        logical_processors_match = $cpuMatches
        physical_memory_match = $memoryMatches
    }
} | ConvertTo-Json -Depth 8

if ($Strict -and -not $ready) {
    throw "Reference machine mismatch: expected $ExpectedLogicalProcessors logical processors and $ExpectedMemoryGB GB physical memory."
}
