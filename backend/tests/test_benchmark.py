"""容量基线脚本契约测试。"""
from __future__ import annotations

from pathlib import Path


def test_benchmark_script_records_bounded_latency_and_error_metrics():
    script = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_api.py"
    source = script.read_text(encoding="utf-8")

    assert "--concurrency" in source
    assert '"p50"' in source
    assert '"p95"' in source
    assert '"error_rate"' in source


def test_benchmark_script_supports_duration_mode_and_keeps_raw_run_metadata():
    script = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_api.py"
    source = script.read_text(encoding="utf-8")

    assert "run_for_duration" in source
    assert "--duration-seconds" in source
    assert '"duration_seconds"' in source


def test_windows_benchmark_samples_process_memory_during_duration_runs():
    script = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_demo.ps1"
    source = script.read_text(encoding="utf-8")

    assert "DurationSeconds" in source
    assert "MemorySampleIntervalSeconds" in source
    assert "working_set_samples" in source
    assert "DisableRateLimit" in source
    assert "$benchmarkScript = Join-Path" in source
    assert '"`"$benchmarkScript`""' in source
