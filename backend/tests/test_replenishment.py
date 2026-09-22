"""补货规则领域测试。"""
from __future__ import annotations

import pandas as pd
import pytest


def test_replenishment_uses_window_demand_and_rounds_moq_and_pack():
    from common.replenishment import calculate_replenishment

    result = calculate_replenishment(
        demand_forecast=[25] * 30,
        on_hand=40,
        confirmed_inbound=0,
        reserved=0,
        lead_time_days=2,
        review_period_days=2,
        safety_stock=10,
        pack_size=12,
        minimum_order_quantity=24,
    )

    assert result == {
        "window_days": 4,
        "window_demand": 100.0,
        "net_available": 40.0,
        "target_stock": 110.0,
        "raw_replenishment": 70.0,
        "suggested_quantity": 72,
        "risk_level": "high",
    }


def test_replenishment_returns_zero_when_net_available_covers_target():
    from common.replenishment import calculate_replenishment

    result = calculate_replenishment(
        demand_forecast=[10] * 30,
        on_hand=200,
        confirmed_inbound=0,
        reserved=0,
        lead_time_days=2,
        review_period_days=2,
        safety_stock=10,
        pack_size=12,
        minimum_order_quantity=24,
    )

    assert result["suggested_quantity"] == 0
    assert result["risk_level"] == "low"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"on_hand": None}, "on_hand"),
        ({"lead_time_days": 30, "review_period_days": 1}, "forecast horizon"),
        ({"pack_size": 0}, "pack_size"),
        ({"minimum_order_quantity": -1}, "minimum_order_quantity"),
    ],
)
def test_replenishment_rejects_missing_or_unsupported_inputs(kwargs, message):
    from common.replenishment import calculate_replenishment

    params = {
        "demand_forecast": [10] * 30,
        "on_hand": 40,
        "confirmed_inbound": 0,
        "reserved": 0,
        "lead_time_days": 2,
        "review_period_days": 2,
        "safety_stock": 10,
        "pack_size": 12,
        "minimum_order_quantity": 24,
    }
    params.update(kwargs)

    with pytest.raises(ValueError, match=message):
        calculate_replenishment(**params)


def test_inventory_service_uses_active_snapshot_policy(monkeypatch):
    from app.services import inventory_service

    monkeypatch.setattr(
        inventory_service.data_service,
        "get_products",
        lambda: [{"product_id": 1, "product_name": "P1", "category": "食品"}],
    )
    monkeypatch.setattr(
        inventory_service.data_service,
        "get_stores",
        lambda: [{"store_id": 1, "store_name": "S1"}],
    )
    monkeypatch.setattr(
        inventory_service.data_service,
        "load_sales",
        lambda: pd.DataFrame({"date": [pd.Timestamp("2025-06-30")]}),
    )
    monkeypatch.setattr(
        inventory_service.forecast_service,
        "get_forecast_all",
        lambda _products, _stores: [{
            "product_id": 1,
            "product_name": "P1",
            "category": "食品",
            "store_id": 1,
            "store_name": "S1",
            "total_predicted": 100,
            "suggested_purchase": 108,
            "abc_class": "A",
            "forecast": [{"predicted_sales": 25}] * 30,
        }],
    )
    monkeypatch.setattr(
        inventory_service,
        "load_active_inventory_snapshot",
        lambda: pd.DataFrame([{
            "as_of_date": pd.Timestamp("2025-06-30"),
            "product_id": 1,
            "store_id": 1,
            "on_hand": 40,
            "confirmed_inbound": 0,
            "reserved": 0,
            "lead_time_days": 2,
            "review_period_days": 2,
            "safety_stock": 10,
            "pack_size": 12,
            "minimum_order_quantity": 24,
        }]),
    )

    result = inventory_service.get_inventory()

    assert result["cells"][0]["suggested_purchase"] == 72
    assert result["cells"][0]["risk_level"] == "high"


def test_inventory_service_rejects_missing_snapshot(monkeypatch):
    from app.core.exceptions import InventoryUnavailableError
    from app.services import inventory_service

    monkeypatch.setattr(
        inventory_service,
        "load_active_inventory_snapshot",
        lambda: None,
    )
    monkeypatch.setattr(
        inventory_service.forecast_service,
        "get_forecast_all",
        lambda *_args: pytest.fail("missing inventory must fail before forecasting"),
    )

    with pytest.raises(InventoryUnavailableError, match="库存快照"):
        inventory_service.get_inventory()


def test_inventory_service_rejects_stale_snapshot(monkeypatch):
    from app.core.exceptions import InventoryUnavailableError
    from app.services import inventory_service

    monkeypatch.setattr(
        inventory_service.data_service,
        "get_products",
        lambda: [{"product_id": 1, "product_name": "P1", "category": "食品"}],
    )
    monkeypatch.setattr(
        inventory_service.data_service,
        "get_stores",
        lambda: [{"store_id": 1, "store_name": "S1"}],
    )
    monkeypatch.setattr(
        inventory_service.data_service,
        "load_sales",
        lambda: pd.DataFrame({"date": [pd.Timestamp("2026-09-15")]}),
    )
    monkeypatch.setattr(
        inventory_service.forecast_service,
        "get_forecast_all",
        lambda _products, _stores: [],
    )
    monkeypatch.setattr(
        inventory_service,
        "load_active_inventory_snapshot",
        lambda: pd.DataFrame({"as_of_date": [pd.Timestamp("2026-09-01")]}),
    )

    with pytest.raises(InventoryUnavailableError):
        inventory_service.get_inventory()


def test_inventory_service_rejects_missing_snapshot_key(monkeypatch):
    from app.core.exceptions import InventoryUnavailableError
    from app.services import inventory_service

    monkeypatch.setattr(
        inventory_service.data_service,
        "get_products",
        lambda: [{"product_id": 1, "product_name": "P1", "category": "食品"}],
    )
    monkeypatch.setattr(
        inventory_service.data_service,
        "get_stores",
        lambda: [{"store_id": 1, "store_name": "S1"}],
    )
    monkeypatch.setattr(
        inventory_service.data_service,
        "load_sales",
        lambda: pd.DataFrame({"date": [pd.Timestamp("2026-09-15")]}),
    )
    monkeypatch.setattr(
        inventory_service.forecast_service,
        "get_forecast_all",
        lambda _products, _stores: [{
            "product_id": 1,
            "store_id": 1,
            "total_predicted": 30,
            "suggested_purchase": 10,
            "abc_class": "A",
            "forecast": [{"predicted_sales": 1}] * 30,
        }],
    )
    monkeypatch.setattr(
        inventory_service,
        "load_active_inventory_snapshot",
        lambda: pd.DataFrame({
            "as_of_date": [pd.Timestamp("2026-09-15")],
            "product_id": [2],
            "store_id": [1],
        }),
    )

    with pytest.raises(InventoryUnavailableError, match="product_id=1, store_id=1"):
        inventory_service.get_inventory()


def test_replenishment_preview_applies_client_overrides(monkeypatch):
    from app.services import replenishment_service

    monkeypatch.setattr(replenishment_service.data_service, "get_products", lambda: [
        {"product_id": 1, "product_name": "P1", "category": "食品"},
    ])
    monkeypatch.setattr(replenishment_service.data_service, "get_stores", lambda: [
        {"store_id": 1, "store_name": "S1"},
    ])
    monkeypatch.setattr(replenishment_service.inventory_service, "load_active_inventory_snapshot", lambda: pd.DataFrame([{
        "as_of_date": pd.Timestamp("2026-09-20"),
        "product_id": 1,
        "store_id": 1,
        "on_hand": 40,
        "confirmed_inbound": 0,
        "reserved": 0,
        "lead_time_days": 2,
        "review_period_days": 2,
        "safety_stock": 10,
        "pack_size": 12,
        "minimum_order_quantity": 24,
    }]))
    monkeypatch.setattr(replenishment_service.inventory_service, "_validate_snapshot_freshness", lambda _: None)
    monkeypatch.setattr(replenishment_service, "get_active_inventory_id", lambda: "inventory-v1")
    monkeypatch.setattr(replenishment_service.forecast_service, "get_forecast", lambda *_: {
        "forecast": [{"predicted_sales": 25}] * 30,
    })

    result = replenishment_service.preview_replenishment(
        product_id=1,
        store_id=1,
        lead_time_days=3,
        review_period_days=2,
        safety_stock=20,
        pack_size=10,
        minimum_order_quantity=30,
    )

    assert result["window_days"] == 5
    assert result["window_demand"] == 125.0
    assert result["target_stock"] == 145.0
    assert result["suggested_quantity"] == 110
    assert result["inventory_version"] == "inventory-v1"


def test_replenishment_preview_api_returns_formula_contract(client, monkeypatch):
    from app.api import replenishment

    payload = {
        "product_id": 1,
        "store_id": 1,
        "window_days": 4,
        "window_demand": 100.0,
        "net_available": 30.0,
        "target_stock": 110.0,
        "raw_replenishment": 80.0,
        "suggested_quantity": 84,
        "risk_level": "high",
        "inventory_version": "inventory-v1",
    }
    monkeypatch.setattr(replenishment.replenishment_service, "preview_replenishment", lambda **_: payload)

    response = client.post("/api/replenishment/preview", json={"product_id": 1, "store_id": 1})

    assert response.status_code == 200
    assert response.json()["suggested_quantity"] == 84
    assert response.json()["risk_level"] == "high"
