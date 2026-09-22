"""持久化训练任务的状态机与错误边界。"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from app.core.exceptions import ConflictError
from app.services.job_repository import JobRecord, JobRepository, JobSubmission


def _repository(tmp_path: Path) -> JobRepository:
    return JobRepository(tmp_path / "jobs.db")


def _create(repo: JobRepository, tmp_path: Path, key: str = "job-key"):
    return repo.create_training(
        idempotency_key=key,
        data_version="data-v1",
        model_version="model-v1",
        candidate_root=tmp_path / "candidates" / key,
    )


def test_create_training_is_idempotent_and_rejects_payload_reuse(tmp_path):
    repo = _repository(tmp_path)

    first = _create(repo, tmp_path)
    replay = _create(repo, tmp_path)

    assert first.created is True
    assert replay.created is False
    assert replay.job.job_id == first.job.job_id
    with pytest.raises(ConflictError):
        repo.create_training(
            idempotency_key="job-key",
            data_version="data-v2",
            model_version="model-v1",
            candidate_root=tmp_path / "other",
        )


def test_claim_allows_one_running_training_and_recovery_marks_it_interrupted(tmp_path):
    repo = _repository(tmp_path)
    first = _create(repo, tmp_path, "first")
    second = _create(repo, tmp_path, "second")

    running = repo.claim(first.job.job_id)
    blocked = repo.claim(second.job.job_id)

    assert running.status == "running"
    assert blocked.status == "queued"
    assert repo.recover_interrupted() == 1
    assert repo.get(first.job.job_id).status == "interrupted"
    assert repo.get(second.job.job_id).status == "queued"


def test_failed_job_can_be_retried_as_a_new_attempt(tmp_path):
    repo = _repository(tmp_path)
    created = _create(repo, tmp_path)
    repo.claim(created.job.job_id)
    failed = repo.fail(created.job.job_id, "TRAINING_FAILED", "训练失败")

    retried = repo.retry(created.job.job_id, tmp_path / "candidates" / "retry")

    assert failed.status == "failed"
    assert retried.status == "queued"
    assert retried.attempt == 2
    assert retried.error_code is None
    assert retried.candidate_root == str(tmp_path / "candidates" / "retry")


def test_error_text_is_redacted_and_truncated(tmp_path):
    repo = _repository(tmp_path)
    created = _create(repo, tmp_path)
    repo.claim(created.job.job_id)

    failed = repo.fail(
        created.job.job_id,
        "TRAINING_FAILED",
        "API_TOKEN=top-secret " + "x" * 1000,
        detail="password: hidden " + "y" * 1000,
    )

    assert "top-secret" not in failed.error_message
    assert "hidden" not in failed.error_detail
    assert len(failed.error_message) <= 500
    assert len(failed.error_detail) <= 2000
    assert "[REDACTED]" in failed.error_message


def test_training_job_api_requires_idempotency_key(client):
    response = client.post("/api/jobs/training", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_training_job_api_returns_accepted_job(monkeypatch, client):
    record = JobRecord(
        job_id="job-test",
        kind="training",
        status="queued",
        phase="queued",
        input_data_version="data-v1",
        input_model_version="model-v1",
        candidate_root="C:/demo/jobs/candidate",
        idempotency_key="key",
        attempt=1,
        created_at="2026-09-22T00:00:00+00:00",
        started_at=None,
        finished_at=None,
        heartbeat_at=None,
        pid=None,
        result=None,
        error_code=None,
        error_message=None,
        error_detail=None,
    )

    class FakeService:
        def submit_training(self, *args, **kwargs):
            return JobSubmission(record, True)

    monkeypatch.setattr("app.api.jobs.get_service", lambda: FakeService())
    response = client.post(
        "/api/jobs/training",
        headers={"Idempotency-Key": "key"},
        json={"data_version": "data-v1", "model_version": "model-v1"},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-test"
    assert response.json()["status"] == "queued"


def test_job_service_starts_worker_with_isolated_candidate_environment(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.job_service import JobService

    feature_file = tmp_path / "active" / "features.csv"
    feature_file.parent.mkdir()
    feature_file.write_text("features", encoding="utf-8")
    database = tmp_path / "active" / "dashboard.db"
    repository = JobRepository(database)
    monkeypatch.setattr(settings, "DATA_PROCESSED_DIR", str(feature_file.parent))
    monkeypatch.setattr(settings, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{database.as_posix()}")
    monkeypatch.setattr("app.services.job_service.dataset_service.get_active_dataset_id", lambda: "data-v1")
    monkeypatch.setattr("app.services.job_service.get_active_model_id", lambda: "model-v1")

    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr("app.services.job_service.subprocess.Popen", fake_popen)
    submission = JobService(repository).submit_training("service-key")

    environment = captured["env"]
    assert submission.created is True
    assert Path(environment["DEMO_ROOT"]).parent == tmp_path / "jobs"
    assert environment["JOB_SOURCE_FEATURES"] == str(feature_file)
    assert environment["DATABASE_URL"] == f"sqlite:///{database.as_posix()}"
    assert submission.job.job_id in captured["command"]
