"""Persistent background training jobs."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas import JobResponse, JobSubmitRequest
from app.services.job_repository import JobRecord
from app.services.job_service import JobService

router = APIRouter()


def get_service() -> JobService:
    return JobService()


def _response(job: JobRecord, *, created: bool = True) -> JobResponse:
    return JobResponse(**job.to_dict(), created=created)


@router.post("/jobs/training", response_model=JobResponse, summary="提交候选训练任务")
def submit_training(
    payload: JobSubmitRequest | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if not idempotency_key:
        raise ValidationError("提交训练任务必须提供 Idempotency-Key")
    body = payload or JobSubmitRequest()
    submission = get_service().submit_training(
        idempotency_key,
        data_version=body.data_version,
        model_version=body.model_version,
    )
    result = _response(submission.job, created=submission.created)
    return JSONResponse(
        status_code=202 if submission.created else 200,
        content=result.model_dump(mode="json"),
    )


@router.get("/jobs", response_model=list[JobResponse], summary="查看任务列表")
def list_jobs(limit: Annotated[int, Query(ge=1, le=100)] = 50):
    return [_response(job) for job in get_service().list(limit)]


@router.get("/jobs/{job_id}", response_model=JobResponse, summary="查看任务状态")
def get_job(job_id: str):
    job = get_service().get(job_id)
    if job is None:
        raise NotFoundError(f"任务 {job_id} 不存在")
    return _response(job)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse, summary="重试失败任务")
def retry_job(job_id: str):
    return _response(get_service().retry_training(job_id))
