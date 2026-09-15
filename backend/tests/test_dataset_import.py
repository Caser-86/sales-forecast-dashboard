"""Sales dataset import contract tests."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from app.core.exceptions import DatasetValidationError
from app.services.dataset_service import get_active_sales_path, import_sales_dataset


def _write_sales_csv(path, rows=None):
    rows = rows or [
        {
            "date": "2025-01-01",
            "product_id": 1,
            "store_id": 1,
            "product_name": "P1",
            "store_name": "S1",
            "category": "食品",
            "sales": 10,
            "price": 12.5,
        },
        {
            "date": "2025-01-02",
            "product_id": 2,
            "store_id": 2,
            "product_name": "P2",
            "store_name": "S2",
            "category": "家居",
            "sales": 4,
            "price": 20.0,
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def test_import_sales_dataset_writes_manifest_and_atomic_active_pointer(tmp_path):
    source = tmp_path / "sales.csv"
    versions = tmp_path / "versions"
    active = tmp_path / "active.json"
    _write_sales_csv(source)

    result = import_sales_dataset(source, versions_dir=versions, active_file=active)

    assert result["manifest"]["rows"] == 2
    assert result["manifest"]["product_count"] == 2
    assert Path(result["sales_path"]).is_file()
    assert json.loads(active.read_text(encoding="utf-8"))["dataset_id"] == result["dataset_id"]
    assert get_active_sales_path(active_file=active, fallback=source) == Path(result["sales_path"])


def test_invalid_sales_dataset_does_not_replace_previous_active_version(tmp_path):
    source = tmp_path / "invalid.csv"
    active = tmp_path / "active.json"
    versions = tmp_path / "versions"
    active.write_text(json.dumps({"dataset_id": "old-version"}), encoding="utf-8")
    _write_sales_csv(source, [
        {
            "date": "2025-01-01",
            "product_id": 1,
            "store_id": 1,
            "product_name": "P1",
            "store_name": "S1",
            "category": "食品",
            "sales": -1,
            "price": 12.5,
        },
    ])

    with pytest.raises(DatasetValidationError, match="负销量"):
        import_sales_dataset(source, versions_dir=versions, active_file=active)

    assert json.loads(active.read_text(encoding="utf-8"))["dataset_id"] == "old-version"
    assert not versions.exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: frame.drop(columns=["price"]), "缺少必需列"),
        (lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True), "重复"),
        (lambda frame: frame.assign(sales=float("nan")), "有限数值"),
    ],
)
def test_import_rejects_invalid_schema_and_values(tmp_path, mutation, message):
    source = tmp_path / "invalid.csv"
    frame = pd.DataFrame([
        {
            "date": "2025-01-01",
            "product_id": 1,
            "store_id": 1,
            "product_name": "P1",
            "store_name": "S1",
            "category": "食品",
            "sales": 10,
            "price": 12.5,
        },
    ])
    mutation(frame).to_csv(source, index=False)

    with pytest.raises(DatasetValidationError, match=message):
        import_sales_dataset(source, versions_dir=tmp_path / "versions", active_file=tmp_path / "active.json")
