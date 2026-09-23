"""批量预测服务测试。"""
from __future__ import annotations

from threading import Barrier, BrokenBarrierError


def _products():
    return [
        {"product_id": 1, "product_name": "P1", "category": "服装"},
        {"product_id": 2, "product_name": "P2", "category": "家居"},
    ]


def _stores():
    return [{"store_id": 1, "store_name": "S1"}]


def test_forecast_all_runs_items_concurrently(monkeypatch):
    import app.services.forecast_service as service

    barrier = Barrier(2)

    def fake_get_forecast(product_id, store_id):
        try:
            barrier.wait(timeout=1)
        except BrokenBarrierError as exc:
            raise AssertionError("batch forecast did not run concurrently") from exc
        return {
            "total_predicted": product_id,
            "suggested_purchase": product_id + 1,
            "abc_class": "A",
            "forecast": [],
        }

    monkeypatch.setattr(service, "get_forecast", fake_get_forecast)

    result = service.get_forecast_all(_products(), _stores())

    assert [item["error"] for item in result if "error" in item] == []


def test_forecast_all_preserves_product_store_order(monkeypatch):
    import app.services.forecast_service as service

    def fake_get_forecast(product_id, store_id):
        return {
            "total_predicted": product_id * 100 + store_id,
            "suggested_purchase": product_id * 100 + store_id + 1,
            "abc_class": "A",
            "forecast": [],
        }

    monkeypatch.setattr(service, "get_forecast", fake_get_forecast)
    products = [
        {"product_id": 2, "product_name": "P2", "category": "服装"},
        {"product_id": 1, "product_name": "P1", "category": "家居"},
    ]
    stores = [
        {"store_id": 2, "store_name": "S2"},
        {"store_id": 1, "store_name": "S1"},
    ]

    result = service.get_forecast_all(products, stores)

    assert [(item["product_id"], item["store_id"]) for item in result] == [
        (2, 2), (2, 1), (1, 2), (1, 1)
    ]


def test_forecast_all_isolates_single_item_failure(monkeypatch):
    import app.services.forecast_service as service

    def fake_get_forecast(product_id, store_id):
        if product_id == 2:
            raise RuntimeError("model unavailable")
        return {
            "total_predicted": 10,
            "suggested_purchase": 11,
            "abc_class": "B",
            "forecast": [],
        }

    monkeypatch.setattr(service, "get_forecast", fake_get_forecast)

    result = service.get_forecast_all(_products(), _stores())

    assert result[0]["total_predicted"] == 10
    assert result[1]["error"] == "model unavailable"
    assert "total_predicted" not in result[1]


def test_forecast_cache_key_includes_active_versions(monkeypatch):
    import app.services.forecast_service as service

    versions = {"model": "model-a", "data": "sales-a"}
    calls = []

    def fake_forecast(product_id, store_id):
        calls.append((product_id, store_id))
        return {"product_id": product_id, "store_id": store_id}

    monkeypatch.setattr(service, "_forecast", fake_forecast)
    monkeypatch.setattr(service, "get_active_model_id", lambda: versions["model"])
    monkeypatch.setattr(service, "get_active_dataset_id", lambda: versions["data"])
    service.clear_forecast_cache()

    service.get_forecast(1, 1)
    service.get_forecast(1, 1)
    versions["model"] = "model-b"
    service.get_forecast(1, 1)
    versions["data"] = "sales-b"
    service.get_forecast(1, 1)

    assert calls == [(1, 1), (1, 1), (1, 1)]
    service.clear_forecast_cache()
