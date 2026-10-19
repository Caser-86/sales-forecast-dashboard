"""T5 model-center API and candidate-promotion contracts."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_model_catalog_api_exposes_models_and_jobs(client, monkeypatch):
    from app.api import models

    payload = {
        "active_model": "model-0123456789abcdef",
        "active_runtime": None,
        "models": [{"model_id": "model-0123456789abcdef", "active": True}],
        "jobs": [{"job_id": "job-1", "status": "succeeded"}],
    }
    monkeypatch.setattr(models.model_service, "build_model_catalog", lambda: payload)

    response = client.get("/api/models")

    assert response.status_code == 200
    assert response.json() == payload


def test_model_detail_and_activation_api_are_explicit(client, monkeypatch):
    from app.api import models

    model_id = "model-0123456789abcdef"
    detail = {"model_id": model_id, "data_version": "sales-v1", "publishable": True}
    activated = {
        "model_id": model_id,
        "active": True,
        "runtime_snapshot": {"snapshot_id": "runtime-0123456789abcdef"},
    }
    monkeypatch.setattr(models.model_service, "get_model_detail", lambda _: detail)
    monkeypatch.setattr(models.model_service, "activate_model_for_serving", lambda _: activated)

    assert client.get(f"/api/models/{model_id}").json() == detail
    response = client.post(f"/api/models/{model_id}/activate")

    assert response.status_code == 200
    assert response.json() == activated


def test_model_activation_rejects_data_version_mismatch(monkeypatch):
    from app.core.exceptions import ConflictError
    from app.services import model_service

    monkeypatch.setattr(
        model_service,
        "_resolve_model_package",
        lambda _: ("model-0123456789abcdef", {"model_id": "model-0123456789abcdef", "data_version": "sales-new"}, None),
    )
    monkeypatch.setattr(model_service, "get_active_runtime_snapshot", lambda: {
        "snapshot_id": "runtime-0123456789abcdef",
        "data_version": "sales-active",
        "model_version": "model-old",
        "inventory_version": "inventory-v1",
    })

    with pytest.raises(ConflictError, match="数据版本"):
        model_service.activate_model_for_serving("model-0123456789abcdef")


def test_model_service_catalog_and_detail_include_publishability(monkeypatch):
    from app.services import model_service

    model = {
        "model_id": "model-0123456789abcdef",
        "data_version": "sales-v1",
        "created_at_utc": "2026-01-01T00:00:00+00:00",
        "selected_strategy": "ensemble",
        "metrics": {"ensemble": {"mape": 1.2, "rmse": 2.3}},
        "package_checksum": "abc",
        "artifact_count": 9,
    }
    monkeypatch.setattr(model_service, "get_active_runtime_snapshot", lambda: None)
    monkeypatch.setattr(model_service, "get_active_model_id", lambda: model["model_id"])
    monkeypatch.setattr(model_service.dataset_service, "get_active_dataset_id", lambda: "sales-v1")
    monkeypatch.setattr(model_service, "list_model_versions", lambda **_: [model])
    monkeypatch.setattr(model_service.JobService, "list", lambda *_args, **_kwargs: [])
    catalog = model_service.build_model_catalog()

    assert catalog["active_model"] == model["model_id"]
    assert catalog["models"][0]["active"] is True
    assert catalog["models"][0]["publishable"] is True

    manifest = {"model_id": model["model_id"], "data_version": "sales-v1", "files": []}
    monkeypatch.setattr(
        model_service,
        "_resolve_model_package",
        lambda _: (model["model_id"], manifest, Path("published-models")),
    )
    detail = model_service.get_model_detail(model["model_id"])
    assert detail["model_id"] == model["model_id"]
    assert detail["publishable"] is True


def test_model_activation_promotes_candidate_into_runtime_snapshot(tmp_path, monkeypatch):
    from app.services import model_service

    model_id = "model-0123456789abcdef"
    source_versions = tmp_path / "candidate" / "versions"
    manifest = {"model_id": model_id, "data_version": "sales-v1"}
    runtime = {
        "snapshot_id": "runtime-0123456789abcdef",
        "data_version": "sales-v1",
        "model_version": "model-old",
        "inventory_version": "inventory-v1",
        "policy_version": "policy-v1",
    }
    promoted = {"model_id": model_id, "active": False}
    runtime_result = {"snapshot_id": "runtime-fedcba9876543210", "active": True}
    monkeypatch.setattr(model_service, "_resolve_model_package", lambda _: (model_id, manifest, source_versions))
    monkeypatch.setattr(model_service, "get_active_runtime_snapshot", lambda: runtime)
    monkeypatch.setattr(model_service, "publish_model_package", lambda **_: promoted)
    monkeypatch.setattr(model_service, "publish_runtime_snapshot", lambda **_: runtime_result)

    result = model_service.activate_model_for_serving(model_id)

    assert result["model_id"] == model_id
    assert result["runtime_snapshot"] == runtime_result


def test_model_activation_uses_legacy_pointer_without_runtime_snapshot(tmp_path, monkeypatch):
    from app.services import model_service

    model_id = "model-0123456789abcdef"
    manifest = {"model_id": model_id, "data_version": "legacy"}
    monkeypatch.setattr(model_service, "_resolve_model_package", lambda _: (model_id, manifest, tmp_path / "versions"))
    monkeypatch.setattr(model_service, "get_active_runtime_snapshot", lambda: None)
    monkeypatch.setattr(model_service.dataset_service, "get_active_dataset_id", lambda: "legacy")
    monkeypatch.setattr(model_service, "publish_model_package", lambda **_: {"model_id": model_id})
    monkeypatch.setattr(model_service, "activate_model", lambda *args, **kwargs: {"model_id": model_id, "active": True})

    result = model_service.activate_model_for_serving(model_id)

    assert result["active"] is True
    assert result["runtime_snapshot"] is None
