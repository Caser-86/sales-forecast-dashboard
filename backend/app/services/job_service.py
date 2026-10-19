"""Training job orchestration around the persistent job repository."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from ml.artifacts import get_active_model_id

from app.core.config import PROJECT_ROOT, settings
from app.core.exceptions import ConflictError, DataNotInitializedError
from app.services import dataset_service
from app.services.job_repository import JobRecord, JobRepository, JobSubmission


class JobService:
    """Submit and retry isolated candidate-training workers."""

    def __init__(self, repository: JobRepository | None = None):
        self.repository = repository or JobRepository()

    def _active_versions(self) -> tuple[str, str]:
        data_version = dataset_service.get_active_dataset_id()
        model_version = get_active_model_id()
        if not data_version or not model_version:
            raise DataNotInitializedError("训练输入版本尚未准备完成")
        if not Path(settings.FEATURES_CSV).is_file():
            raise DataNotInitializedError(f"特征文件不存在: {settings.FEATURES_CSV}")
        return data_version, model_version

    def submit_training(
        self,
        idempotency_key: str,
        *,
        data_version: str | None = None,
        model_version: str | None = None,
    ) -> JobSubmission:
        active_data, active_model = self._active_versions()
        if data_version and data_version != active_data:
            raise ConflictError("训练数据版本不是当前活动版本")
        if model_version and model_version != active_model:
            raise ConflictError("训练模型版本不是当前活动版本")

        candidate_root = Path(settings.JOBS_DIR) / f"candidate-{uuid.uuid4().hex}"
        submission = self.repository.create_training(
            idempotency_key=idempotency_key,
            data_version=active_data,
            model_version=active_model,
            candidate_root=candidate_root,
        )
        if submission.created:
            self._start_worker(submission.job)
        return submission

    def retry_training(self, job_id: str) -> JobRecord:
        existing = self.repository.get(job_id)
        if existing is None:
            raise ConflictError(f"任务 {job_id} 不存在")
        candidate_root = Path(settings.JOBS_DIR) / f"candidate-{uuid.uuid4().hex}"
        retried = self.repository.retry(job_id, candidate_root)
        self._start_worker(retried)
        return retried

    def get(self, job_id: str) -> JobRecord | None:
        return self.repository.get(job_id)

    def list(self, limit: int = 50) -> list[JobRecord]:
        return self.repository.list(limit)

    def _start_worker(self, job: JobRecord) -> None:
        script = PROJECT_ROOT / "scripts" / "run_job.py"
        candidate_root = Path(job.candidate_root)
        log_dir = candidate_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / "worker.stdout.log"
        stderr_path = log_dir / "worker.stderr.log"
        environment = os.environ.copy()
        environment.update({
            "DEMO_ROOT": str(candidate_root),
            "DATABASE_URL": settings.DATABASE_URL,
            "JOB_ID": job.job_id,
            "JOB_SOURCE_FEATURES": str(settings.FEATURES_CSV),
            "JOB_DATA_VERSION": job.input_data_version,
            "PYTHONUTF8": "1",
        })
        try:
            with stdout_path.open("a", encoding="utf-8") as stdout, stderr_path.open("a", encoding="utf-8") as stderr:
                process = subprocess.Popen(
                    [sys.executable, str(script), job.job_id],
                    cwd=str(PROJECT_ROOT),
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    close_fds=True,
                )
        except OSError as exc:
            self.repository.fail(job.job_id, "WORKER_START_FAILED", str(exc))
            return
        self.repository.attach_pid(job.job_id, process.pid)

    @staticmethod
    def cleanup_candidate(job: JobRecord) -> None:
        """Remove a failed candidate only when its path is under the jobs root."""
        candidate = Path(job.candidate_root).resolve()
        jobs_root = Path(settings.JOBS_DIR).resolve()
        try:
            candidate.relative_to(jobs_root)
        except ValueError:
            return
        shutil.rmtree(candidate, ignore_errors=True)
