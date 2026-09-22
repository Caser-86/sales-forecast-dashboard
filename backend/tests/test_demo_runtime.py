"""本地演示运行时隔离契约。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_prepare_demo_module():
    module_path = PROJECT_ROOT / "scripts" / "prepare_demo.py"
    spec = importlib.util.spec_from_file_location("prepare_demo", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_root_rewrites_all_runtime_paths(tmp_path):
    from app.core.config import Settings

    demo_root = tmp_path / "demo-runtime"
    settings = Settings(DEMO_ROOT=str(demo_root))

    assert Path(settings.DATA_RAW_DIR) == demo_root / "data" / "raw"
    assert Path(settings.DATA_PROCESSED_DIR) == demo_root / "data" / "processed"
    assert Path(settings.MODELS_DIR) == demo_root / "ml" / "saved_models"
    assert Path(settings.LOG_DIR) == demo_root / "logs"
    assert settings.DATABASE_URL == f"sqlite:///{(demo_root / 'dashboard.db').as_posix()}"


def test_demo_root_ensure_dirs_creates_runtime_layout(tmp_path):
    from app.core.config import Settings

    settings = Settings(DEMO_ROOT=str(tmp_path / "demo-runtime"))
    settings.ensure_dirs()

    for relative_path in (
        "data/raw",
        "data/processed",
        "data/raw/versions",
        "data/inventory/versions",
        "ml/saved_models/versions",
        "logs",
    ):
        assert (Path(settings.DEMO_ROOT) / relative_path).is_dir()


def test_demo_asset_check_reports_missing_assets_without_writing(tmp_path):
    from app.core.config import Settings

    module = _load_prepare_demo_module()
    settings = Settings(DEMO_ROOT=str(tmp_path / "demo-runtime"))

    result = module.check_demo_assets(settings)

    assert result["ready"] is False
    assert "sales_data" in result["missing"]
    assert not (Path(settings.DEMO_ROOT) / "demo-manifest.json").exists()


def test_prepare_demo_module_does_not_cache_runtime_settings_at_import():
    source = (PROJECT_ROOT / "scripts" / "prepare_demo.py").read_text(encoding="utf-8")

    assert "from app.core.config import Settings" not in source.split("if TYPE_CHECKING:", 1)[0]
    assert "from app.core.config import settings" in source


def test_windows_demo_scripts_use_loopback_and_scoped_pid_state():
    start_script = (PROJECT_ROOT / "scripts" / "start_demo.ps1").read_text(encoding="utf-8")
    stop_script = (PROJECT_ROOT / "scripts" / "stop_demo.ps1").read_text(encoding="utf-8")

    assert "127.0.0.1" in start_script
    assert "DEMO_ROOT" in start_script
    assert "demo-process.json" in start_script
    assert "Get-NetTCPConnection" in start_script
    assert "-Prepare" in start_script
    assert 'WorkingDirectory (Join-Path $projectRoot "backend")' in start_script
    assert "Stop-Process" in stop_script
    assert "demo-process.json" in stop_script
    assert "DateTimeOffset" in stop_script
    assert "[object]$ExpectedStartTime" in stop_script
    assert "Get-NetTCPConnection" not in stop_script


def test_offline_demo_verifier_checks_bundled_assets_and_remote_references():
    script = (PROJECT_ROOT / "scripts" / "verify_offline_demo.py").read_text(encoding="utf-8")

    assert "remote_references" in script
    assert "echarts.min.js" in script
    assert "local-demo.zip" in script


def test_windows_demo_supports_offline_guard_and_reference_cpu_affinity():
    start_script = (PROJECT_ROOT / "scripts" / "start_demo.ps1").read_text(encoding="utf-8")
    offline_script = (PROJECT_ROOT / "scripts" / "verify_offline_demo.ps1").read_text(encoding="utf-8")
    benchmark_script = (PROJECT_ROOT / "scripts" / "benchmark_demo.ps1").read_text(encoding="utf-8")
    reference_script = (PROJECT_ROOT / "scripts" / "check_reference_machine.ps1").read_text(encoding="utf-8")

    assert "[switch]$Offline" in start_script
    assert "$CpuAffinityCores" in start_script
    assert "offline_socket_guard" in start_script
    assert "offline_socket_guard" in offline_script
    assert "-Offline" in offline_script
    assert "RunBrowserE2E" in offline_script
    assert "API_BASE_URL" in offline_script
    assert "CORS_ORIGINS" in offline_script
    assert "RATE_LIMIT_REQUESTS" in offline_script
    assert "RunModelRecoveryE2E" in offline_script
    assert "RunModelConsistencyE2E" in offline_script
    assert "model.consistency.spec.js" in offline_script
    assert "RunRuntimeRollbackE2E" in offline_script
    assert "runtime.rollback.spec.js" in offline_script
    assert "RunFullReplayE2E" in offline_script
    assert "full.replay.spec.js" in offline_script
    assert "DEMO_AUTH_ENABLED" in offline_script
    assert "-WithAuth" in offline_script
    assert "switch_scenario('standard', confirm=True)" in offline_script
    assert '$ErrorActionPreference = "Continue"' in offline_script
    assert "$guardExitCode = $LASTEXITCODE" in offline_script
    assert "DEMO_TRAINING_FAILURE_MODE" in offline_script
    assert "DEMO_TRAINING_FAILURE_MARKER" in offline_script
    assert "DEMO_TRAINING_PROFILE" in offline_script
    t10_script = (PROJECT_ROOT / "scripts" / "run_t10_acceptance.ps1").read_text(encoding="utf-8")
    assert "check_reference_machine.ps1" in t10_script
    assert "verify_offline_demo.ps1" in t10_script
    assert "benchmark_demo.ps1" in t10_script
    assert "manual_fully_disconnected_replay = \"required_external\"" in t10_script
    assert "-CpuAffinityCores" in benchmark_script
    assert "under_memory_budget" in benchmark_script
    assert "ExpectedLogicalProcessors" in reference_script
    assert "ExpectedMemoryGB" in reference_script
    assert "Win32_ComputerSystem" in reference_script
    assert "$Strict" in reference_script
