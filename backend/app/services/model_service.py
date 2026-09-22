"""Model-center catalog and safe candidate promotion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.artifacts import (
    activate_model,
    get_active_model_id,
    list_model_versions,
    publish_model_package,
    validate_model_package,
)

from app.core.config import settings
from app.core.exceptions import ConflictError, ModelArtifactError, NotFoundError
from app.services import dataset_service
from app.services.job_service import JobService
from app.services.runtime_snapshot_service import publish_runtime_snapshot
from app.services.runtime_state import get_active_runtime_snapshot


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelArtifactError(f"模型文件无效: {path.name}") from exc
    if not isinstance(value, dict):
        raise ModelArtifactError(f"模型文件格式无效: {path.name}")
    return value


def _job_summary(job) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "phase": job.phase,
        "input_data_version": job.input_data_version,
        "input_model_version": job.input_model_version,
        "attempt": job.attempt,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
        "error_code": job.error_code,
        "error_message": job.error_message,
    }


def _resolve_model_package(model_id: str) -> tuple[str, dict[str, Any], Path]:
    """Find a published package or a successful job's isolated candidate package."""
    try:
        manifest = validate_model_package(model_id)
        return model_id, manifest, Path(settings.MODEL_VERSIONS_DIR)
    except ModelArtifactError as published_error:
        for job in JobService().list(limit=100):
            result = job.result or {}
            model_dir_value = result.get("model_dir")
            if not isinstance(model_dir_value, str):
                continue
            model_dir = Path(model_dir_value)
            if model_dir.name != model_id:
                continue
            try:
                manifest = validate_model_package(model_id, versions_dir=model_dir.parent)
            except ModelArtifactError:
                continue
            return model_id, manifest, model_dir.parent
        raise NotFoundError(f"模型 {model_id} 不存在或产物未通过校验") from published_error


def _active_data_version(runtime: dict[str, Any] | None) -> str:
    return (
        runtime.get("data_version")
        if runtime is not None
        else dataset_service.get_active_dataset_id()
    ) or "legacy"


def _is_publishable(manifest: dict[str, Any], runtime: dict[str, Any] | None) -> bool:
    return manifest.get("data_version") == _active_data_version(runtime)


def build_model_catalog() -> dict[str, Any]:
    runtime = get_active_runtime_snapshot()
    active_model = get_active_model_id()
    published = {item["model_id"]: {**item, "source": "published"} for item in list_model_versions()}
    jobs = JobService().list(limit=100)
    for job in jobs:
        result = job.result or {}
        model_dir_value = result.get("model_dir")
        model_id = result.get("model_id")
        if not isinstance(model_id, str) or not isinstance(model_dir_value, str):
            continue
        model_dir = Path(model_dir_value)
        try:
            candidate = next(
                item for item in list_model_versions(versions_dir=model_dir.parent)
                if item["model_id"] == model_id
            )
        except (StopIteration, OSError):
            continue
        published.setdefault(model_id, {
            **candidate,
            "source": "candidate",
            "job_id": job.job_id,
            "job_status": job.status,
        })

    models = []
    for item in published.values():
        item = dict(item)
        item["active"] = item["model_id"] == active_model
        item["publishable"] = item["data_version"] == _active_data_version(runtime)
        models.append(item)
    models.sort(key=lambda item: (not item["active"], item.get("created_at_utc") or ""), reverse=False)
    return {
        "active_model": active_model,
        "active_runtime": runtime,
        "active_data_version": _active_data_version(runtime),
        "models": models,
        "jobs": [_job_summary(job) for job in jobs],
    }


def get_model_detail(model_id: str) -> dict[str, Any]:
    if model_id == "legacy":
        return {
            "model_id": "legacy",
            "data_version": "legacy",
            "active": get_active_model_id() == "legacy",
            "publishable": False,
            "source": "legacy-flat-files",
        }
    resolved_id, manifest, versions_dir = _resolve_model_package(model_id)
    catalog_item = next(
        (item for item in list_model_versions(versions_dir=versions_dir) if item["model_id"] == resolved_id),
        {},
    )
    return {
        **catalog_item,
        "model_id": resolved_id,
        "manifest": manifest,
        "active": get_active_model_id() == resolved_id,
        "publishable": _is_publishable(manifest, get_active_runtime_snapshot()),
        "source": "published" if versions_dir == Path(settings.MODEL_VERSIONS_DIR) else "candidate",
    }


def activate_model_for_serving(model_id: str) -> dict[str, Any]:
    resolved_id, manifest, source_versions_dir = _resolve_model_package(model_id)
    runtime = get_active_runtime_snapshot()
    expected_data = _active_data_version(runtime)
    if manifest.get("data_version") != expected_data:
        raise ConflictError(
            "模型与当前活动数据版本不兼容",
            detail=f"model={manifest.get('data_version')!r}, active={expected_data!r}",
        )

    source_dir = source_versions_dir / resolved_id
    promoted = publish_model_package(
        source_dir=source_dir,
        versions_dir=Path(settings.MODEL_VERSIONS_DIR),
        activate=False,
        data_version=manifest["data_version"],
    )
    promoted_id = promoted["model_id"]
    if runtime is not None:
        runtime_snapshot = publish_runtime_snapshot(
            data_version=runtime["data_version"],
            model_version=promoted_id,
            inventory_version=runtime["inventory_version"],
            policy_version=runtime.get("policy_version", "policy-v1"),
            activate=True,
        )
        return {"model_id": promoted_id, "active": True, "runtime_snapshot": runtime_snapshot}

    activated = activate_model(
        promoted_id,
        versions_dir=Path(settings.MODEL_VERSIONS_DIR),
        active_file=Path(settings.ACTIVE_MODEL_FILE),
    )
    return {"model_id": promoted_id, "active": True, "runtime_snapshot": None, "model": activated}
