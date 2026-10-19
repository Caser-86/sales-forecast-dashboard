"""Run one isolated candidate-training job from the persistent queue."""
from __future__ import annotations

import os
import shutil
import sys
import traceback
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.job_repository import JobRepository  # noqa: E402


def should_inject_demo_failure() -> bool:
    """Inject one explicit local-demo failure without enabling it in production."""
    if os.environ.get("ENV", "development").strip().lower() == "production":
        return False
    if os.environ.get("DEMO_TRAINING_FAILURE_MODE", "").strip().lower() != "fail_once":
        return False
    marker_value = os.environ.get("DEMO_TRAINING_FAILURE_MARKER", "").strip()
    if not marker_value:
        return False

    marker = Path(marker_value).expanduser()
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    else:
        os.close(descriptor)
        return True


def demo_training_profile() -> str | None:
    """Return an explicit non-production training profile for local acceptance."""
    if os.environ.get("ENV", "development").strip().lower() == "production":
        return None
    profile = os.environ.get("DEMO_TRAINING_PROFILE", "").strip().lower()
    return profile if profile == "smoke" else None


def apply_demo_training_profile() -> None:
    """Shorten only the opt-in local smoke profile without changing production defaults."""
    if demo_training_profile() != "smoke":
        return
    from ml import trainer

    trainer.EPOCHS = 8
    trainer.PATIENCE = 2
    trainer.lgbm_wrapper.DEFAULT_PARAMS["n_estimators"] = 50
    trainer.lgbm_wrapper.DEFAULT_PARAMS["early_stopping_rounds"] = 5


def _copy_training_input() -> None:
    source = Path(os.environ.get("JOB_SOURCE_FEATURES", ""))
    if not source.is_file():
        raise FileNotFoundError(f"训练输入特征不存在: {source}")
    destination = Path(settings.FEATURES_CSV)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def run(job_id: str) -> int:
    repository = JobRepository()
    job = repository.claim(job_id)
    if job.status != "running":
        if job.status == "queued":
            repository.fail(job_id, "TRAINING_LOCKED", "已有训练任务正在运行，本任务未开始")
        return 2

    try:
        if should_inject_demo_failure():
            raise RuntimeError("演示故障注入：首次训练失败，可点击重试")
        repository.update_phase(job_id, "preparing")
        _copy_training_input()
        repository.update_phase(job_id, "training")

        apply_demo_training_profile()
        from ml.trainer import train_all

        report = train_all(activate=False, data_version=job.input_data_version)
        repository.update_phase(job_id, "candidate_ready")
        metadata = report.get("metadata", {})
        result = {
            "candidate_root": job.candidate_root,
            "model_id": metadata.get("model_id"),
            "model_dir": str(Path(settings.MODEL_VERSIONS_DIR) / str(metadata.get("model_id", ""))),
            "data_version": metadata.get("data_version", job.input_data_version),
            "selected_strategy": metadata.get("model_selection", {}).get("strategy"),
            "report_path": str(settings.REPORT_JSON),
        }
        repository.succeed(job_id, result)
        print(f"training job {job_id} completed with candidate {result['model_id']}")
        return 0
    except Exception as exc:  # noqa: BLE001 - worker must persist every failure
        detail = traceback.format_exc()
        repository.fail(job_id, "TRAINING_FAILED", str(exc), detail=detail)
        print(f"training job {job_id} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    job_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JOB_ID", "")
    if not job_id:
        print("JOB_ID is required", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(run(job_id))
