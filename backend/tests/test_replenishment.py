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
