"""T4 data-center and runtime snapshot contracts."""
from __future__ import annotations

import pandas as pd
import pytest


def _sales_frame():
    return pd.DataFrame([
        {
            "date": "2026-01-01",
            "product_id": 1,
            "store_id": 1,
            "product_name": "P1",
            "store_name": "S1",
            "category": "食品",
            "sales": 10,
            "price": 12.5,
        },
    ])


def _inventory_frame():
    return pd.DataFrame([
        {
            "as_of_date": "2026-01-01",
            "product_id": 1,
            "store_id": 1,
            "on_hand": 40,
            "confirmed_inbound": 10,
            "reserved": 5,
            "lead_time_days": 2,
            "review_period_days": 2,
            "safety_stock": 10,
            "pack_size": 12,
            "minimum_order_quantity": 24,
        },
    ])


def test_sales_preview_reports_row_and_does_not_write(tmp_path):
    from app.services.dataset_service import preview_sales_bytes

    frame = _sales_frame()
    frame.loc[0, "sales"] = -1
    result = preview_sales_bytes(frame.to_csv(index=False).encode("utf-8"))

    assert result["valid"] is False
    assert result["errors"][0]["row"] == 2
    assert result["errors"][0]["column"] == "sales"
    assert list(tmp_path.iterdir()) == []


def test_inventory_preview_accepts_valid_payload_and_returns_summary():
    from app.services.inventory_dataset_service import preview_inventory_bytes

    result = preview_inventory_bytes(_inventory_frame().to_csv(index=False).encode("utf-8"))

    assert result["valid"] is True
    assert result["summary"] == {"as_of_date": "2026-01-01", "product_count": 1, "store_count": 1}


def test_runtime_snapshot_validates_components_and_becomes_single_active_source(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.dataset_service import get_active_dataset_id, import_sales_dataset
    from app.services.inventory_dataset_service import import_inventory_snapshot
    from app.services.runtime_snapshot_service import publish_runtime_snapshot
    from app.services.runtime_state import get_active_runtime_snapshot

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _sales_frame().to_csv(raw_dir / "sales_data.csv", index=False)
    sales_source = tmp_path / "sales-upload.csv"
    inventory_source = tmp_path / "inventory-upload.csv"
    _sales_frame().to_csv(sales_source, index=False)
    _inventory_frame().to_csv(inventory_source, index=False)
    sales_versions = tmp_path / "sales-versions"
    inventory_versions = tmp_path / "inventory-versions"
    imported_sales = import_sales_dataset(sales_source, versions_dir=sales_versions, activate=False)
    imported_inventory = import_inventory_snapshot(
        inventory_source,
        versions_dir=inventory_versions,
        activate=False,
    )

    monkeypatch.setattr(settings, "DATA_RAW_DIR", str(raw_dir))
    monkeypatch.setattr(settings, "DATASET_VERSIONS_DIR", str(sales_versions))
    monkeypatch.setattr(settings, "INVENTORY_VERSIONS_DIR", str(inventory_versions))
    runtime_versions = tmp_path / "runtime-versions"
    runtime_active = tmp_path / "active-runtime.json"
    monkeypatch.setattr(settings, "RUNTIME_SNAPSHOT_DIR", str(runtime_versions))
    monkeypatch.setattr(settings, "ACTIVE_RUNTIME_SNAPSHOT_FILE", str(runtime_active))

    snapshot = publish_runtime_snapshot(
        data_version=imported_sales["dataset_id"],
        model_version="legacy",
        inventory_version=imported_inventory["inventory_id"],
        snapshots_dir=runtime_versions,
        active_file=runtime_active,
        data_versions_dir=sales_versions,
        inventory_versions_dir=inventory_versions,
        activate=True,
    )

    assert snapshot["active"] is True
    assert get_active_runtime_snapshot()["snapshot_id"] == snapshot["snapshot_id"]
    from app.services.inventory_dataset_service import get_active_inventory_id

    assert get_active_dataset_id() == imported_sales["dataset_id"]
    assert get_active_inventory_id() == imported_inventory["inventory_id"]
    assert (runtime_versions / snapshot["snapshot_id"] / "manifest.json").is_file()

    # A fresh import of the read-only resolver models the next process after restart.
    import importlib

    from app.services import data_service, runtime_state

    importlib.reload(runtime_state)
    data_service.clear_data_caches()
    assert runtime_state.get_active_runtime_snapshot()["snapshot_id"] == snapshot["snapshot_id"]
    assert get_active_dataset_id() == imported_sales["dataset_id"]


def test_runtime_snapshot_rollback_is_atomic_and_rejects_invalid_target(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.core.exceptions import RuntimeSnapshotError
    from app.services import runtime_snapshot_service
    from app.services.dataset_service import import_sales_dataset
    from app.services.runtime_state import get_active_runtime_snapshot

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _sales_frame().to_csv(raw_dir / "sales_data.csv", index=False)
    first_source = tmp_path / "first.csv"
    second_source = tmp_path / "second.csv"
    _sales_frame().to_csv(first_source, index=False)
    second = _sales_frame()
    second.loc[0, "sales"] = 20
    second.to_csv(second_source, index=False)
    sales_versions = tmp_path / "sales-versions"
    first = import_sales_dataset(first_source, versions_dir=sales_versions, activate=False)
    second = import_sales_dataset(second_source, versions_dir=sales_versions, activate=False)

    runtime_versions = tmp_path / "runtime-versions"
    runtime_active = tmp_path / "active-runtime.json"
    monkeypatch.setattr(settings, "DATA_RAW_DIR", str(raw_dir))
    monkeypatch.setattr(settings, "DATASET_VERSIONS_DIR", str(sales_versions))
    monkeypatch.setattr(settings, "RUNTIME_SNAPSHOT_DIR", str(runtime_versions))
    monkeypatch.setattr(settings, "ACTIVE_RUNTIME_SNAPSHOT_FILE", str(runtime_active))

    first_snapshot = runtime_snapshot_service.publish_runtime_snapshot(
        data_version=first["dataset_id"],
        model_version="legacy",
        inventory_version="legacy",
        snapshots_dir=runtime_versions,
        active_file=runtime_active,
        data_versions_dir=sales_versions,
        activate=True,
    )
    second_snapshot = runtime_snapshot_service.publish_runtime_snapshot(
        data_version=second["dataset_id"],
        model_version="legacy",
        inventory_version="legacy",
        snapshots_dir=runtime_versions,
        active_file=runtime_active,
        data_versions_dir=sales_versions,
        activate=False,
    )

    rolled_back = runtime_snapshot_service.rollback_runtime_snapshot(second_snapshot["snapshot_id"])
    assert rolled_back["rolled_back_from"] == first_snapshot["snapshot_id"]
    assert get_active_runtime_snapshot()["snapshot_id"] == second_snapshot["snapshot_id"]

    manifest_path = runtime_versions / first_snapshot["snapshot_id"] / "manifest.json"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(manifest.replace(first["dataset_id"], "sales-missing"), encoding="utf-8")
    with pytest.raises(RuntimeSnapshotError):
        runtime_snapshot_service.rollback_runtime_snapshot(first_snapshot["snapshot_id"])
    assert get_active_runtime_snapshot()["snapshot_id"] == second_snapshot["snapshot_id"]


def test_request_snapshot_stays_pinned_during_pointer_switch(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services import runtime_snapshot_service, runtime_state

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _sales_frame().to_csv(raw_dir / "sales_data.csv", index=False)
    monkeypatch.setattr(settings, "DATA_RAW_DIR", str(raw_dir))
    monkeypatch.setattr(settings, "RUNTIME_SNAPSHOT_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(settings, "ACTIVE_RUNTIME_SNAPSHOT_FILE", str(tmp_path / "active.json"))

    first = runtime_snapshot_service.publish_runtime_snapshot(
        data_version="legacy", model_version="legacy", inventory_version="legacy", activate=True,
    )
    second = runtime_snapshot_service.publish_runtime_snapshot(
        data_version="legacy", model_version="legacy", inventory_version="legacy", policy_version="policy-v2", activate=False,
    )
    token = runtime_state.bind_request_runtime_snapshot()
    try:
        runtime_snapshot_service.activate_runtime_snapshot(second["snapshot_id"])
        assert runtime_state.get_active_runtime_snapshot()["snapshot_id"] == first["snapshot_id"]
    finally:
        runtime_state.reset_request_runtime_snapshot(token)
    assert runtime_state.get_active_runtime_snapshot()["snapshot_id"] == second["snapshot_id"]

def test_runtime_snapshot_rejects_model_built_for_other_data(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.core.exceptions import RuntimeSnapshotError
    from app.services import runtime_snapshot_service

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _sales_frame().to_csv(raw_dir / "sales_data.csv", index=False)
    monkeypatch.setattr(settings, "DATA_RAW_DIR", str(raw_dir))
    monkeypatch.setattr(
        runtime_snapshot_service,
        "validate_model_package",
        lambda *_args, **_kwargs: {"data_version": "sales-other"},
    )

    with pytest.raises(RuntimeSnapshotError, match="不兼容"):
        runtime_snapshot_service.validate_runtime_versions(
            data_version="legacy",
            model_version="model-0123456789abcdef",
            inventory_version="legacy",
            model_versions_dir=tmp_path / "models",
        )


def test_dataset_preview_api_returns_row_errors(client):
    response = client.post(
        "/api/datasets/sales/preview",
        content=_sales_frame().assign(sales=-1).to_csv(index=False),
        headers={"X-Filename": "bad-sales.csv", "Content-Type": "text/csv"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["source_name"] == "bad-sales.csv"
    assert body["errors"][0]["row"] == 2


def test_dataset_api_exposes_templates_and_rejects_invalid_upload(client):
    template = client.get("/api/datasets/templates/sales")
    rejected = client.post(
        "/api/datasets/sales",
        content="not,a,sales,file\n",
        headers={"X-Filename": "bad.csv", "Content-Type": "text/csv"},
    )

    assert template.status_code == 200
    assert "product_id" in template.text
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"


def test_dataset_api_saves_valid_upload_as_candidate_and_lists_catalog(client, monkeypatch):
    from app.api import datasets

    manifest = {
        "dataset_id": "sales-0123456789abcdef",
        "source_name": "sales.csv",
        "rows": 1,
        "date_start": "2026-01-01",
        "date_end": "2026-01-01",
        "product_count": 1,
        "store_count": 1,
        "created_at_utc": "2026-01-01T00:00:00+00:00",
    }
    monkeypatch.setattr(
        datasets.dataset_service,
        "import_sales_dataset",
        lambda source, activate=False: {"manifest": manifest, "active": activate},
    )
    upload = client.post(
        "/api/datasets/sales",
        content=_sales_frame().to_csv(index=False),
        headers={"X-Filename": "sales.csv", "Content-Type": "text/csv"},
    )

    monkeypatch.setattr(
        datasets.runtime_snapshot_service,
        "list_dataset_catalog",
        lambda: {"active": {"data_version": "legacy", "model_version": "legacy", "inventory_version": "legacy"}, "active_runtime": None, "sales": [], "inventory": [], "models": [], "runtime_snapshots": []},
    )
    catalog = client.get("/api/datasets")

    assert upload.status_code == 201
    assert upload.json()["dataset_id"] == manifest["dataset_id"]
    assert catalog.status_code == 200
    assert catalog.json()["active"]["data_version"] == "legacy"


def test_runtime_snapshot_api_keeps_publish_and_activate_as_separate_steps(client, monkeypatch):
    from app.api import datasets

    payload = {
        "snapshot_id": "runtime-0123456789abcdef",
        "schema_version": 1,
        "data_version": "legacy",
        "model_version": "legacy",
        "inventory_version": "legacy",
        "policy_version": "policy-v1",
        "created_at_utc": "2026-01-01T00:00:00+00:00",
        "active": False,
    }
    monkeypatch.setattr(datasets.runtime_snapshot_service, "publish_runtime_snapshot", lambda **_: payload)
    monkeypatch.setattr(datasets.runtime_snapshot_service, "activate_runtime_snapshot", lambda _: {**payload, "active": True})
    monkeypatch.setattr(datasets.runtime_snapshot_service, "rollback_runtime_snapshot", lambda _: {**payload, "active": True, "rolled_back_from": "runtime-fedcba9876543210"})
    monkeypatch.setattr(datasets.runtime_snapshot_service, "get_runtime_snapshot_detail", lambda _: payload)

    published = client.post("/api/datasets/runtime", json={
        "data_version": "legacy",
        "model_version": "legacy",
        "inventory_version": "legacy",
    })
    activated = client.post("/api/datasets/runtime/runtime-0123456789abcdef/activate")

    assert published.status_code == 201
    assert published.json()["active"] is False
    assert activated.status_code == 200
    assert activated.json()["active"] is True

    rolled_back = client.post("/api/datasets/runtime/runtime-0123456789abcdef/rollback")
    detail = client.get("/api/datasets/runtime/runtime-0123456789abcdef")

    assert rolled_back.status_code == 200
    assert rolled_back.json()["rolled_back_from"] == "runtime-fedcba9876543210"
    assert detail.status_code == 200
    assert detail.json()["snapshot_id"] == payload["snapshot_id"]
