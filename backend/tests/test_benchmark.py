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
