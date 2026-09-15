"""元数据与门店选择器接口测试。"""
from __future__ import annotations

import pandas as pd


def test_stores_endpoint_does_not_require_forecast(monkeypatch, client):
    from app.api import stores

    monkeypatch.setattr(stores.data_service, "get_stores", lambda: [{"store_id": 1, "store_name": "一号店"}])
    response = client.get("/api/stores")

    assert response.status_code == 200
    assert response.json() == [{"store_id": 1, "store_name": "一号店"}]


def test_metadata_exposes_active_versions_and_inventory_freshness(monkeypatch, client):
    from app.services import metadata_service

    monkeypatch.setattr(metadata_service, "get_active_dataset_id", lambda: "sales-0123456789abcdef")
    monkeypatch.setattr(metadata_service, "get_active_model_id", lambda: "model-0123456789abcdef")
    monkeypatch.setattr(metadata_service, "get_active_inventory_id", lambda: "inventory-0123456789abcdef")
    monkeypatch.setattr(
        metadata_service.data_service,
        "get_data_quality",
        lambda: {"date_end": "2026-09-15", "status": "healthy"},
    )
    monkeypatch.setattr(
        metadata_service,
        "load_active_inventory_snapshot",
        lambda: pd.DataFrame({"as_of_date": [pd.Timestamp("2026-09-14")]})
    )

    response = client.get("/api/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["data_version"] == "sales-0123456789abcdef"
    assert body["model_version"] == "model-0123456789abcdef"
    assert body["inventory_age_days"] == 1
    assert body["inventory_status"] == "fresh"
