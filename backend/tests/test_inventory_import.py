"""库存快照导入测试。"""
from __future__ import annotations

import json

import pandas as pd
import pytest


def _frame():
    return pd.DataFrame(
        [
            {
                "as_of_date": "2025-06-30",
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
            }
        ]
    )


def test_import_inventory_snapshot_writes_manifest_and_active_pointer(tmp_path):
    from app.services.inventory_dataset_service import import_inventory_snapshot

    source = tmp_path / "inventory.csv"
    _frame().to_csv(source, index=False)
    active = tmp_path / "active.json"
    result = import_inventory_snapshot(source, versions_dir=tmp_path / "versions", active_file=active)

    assert result["active"] is True
    assert json.loads(active.read_text(encoding="utf-8"))["inventory_id"] == result["inventory_id"]
    assert json.loads((tmp_path / "versions" / result["inventory_id"] / "manifest.json").read_text(encoding="utf-8"))["rows"] == 1


def test_invalid_inventory_snapshot_preserves_previous_active(tmp_path):
    from app.core.exceptions import InventoryValidationError
    from app.services.inventory_dataset_service import import_inventory_snapshot

    source = tmp_path / "inventory.csv"
    _frame().to_csv(source, index=False)
    active = tmp_path / "active.json"
    versions = tmp_path / "versions"
    first = import_inventory_snapshot(source, versions_dir=versions, active_file=active)
    invalid = _frame()
    invalid.loc[0, "pack_size"] = 0
    invalid.to_csv(source, index=False)

    with pytest.raises(InventoryValidationError, match="pack_size"):
        import_inventory_snapshot(source, versions_dir=versions, active_file=active)

    assert json.loads(active.read_text(encoding="utf-8"))["inventory_id"] == first["inventory_id"]
