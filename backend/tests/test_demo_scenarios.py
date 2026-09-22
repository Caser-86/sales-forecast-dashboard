"""Deterministic local-demo scenario and artifact contracts."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest


def _configure_demo_settings(monkeypatch, tmp_path):
    from app.core.config import settings

    root = tmp_path / "demo"
    raw = root / "data" / "raw"
    processed = root / "data" / "processed"
    inventory = root / "data" / "inventory"
    models = root / "ml" / "saved_models"
    values = {
        "DEMO_ROOT": str(root),
        "DATA_RAW_DIR": str(raw),
        "DATA_PROCESSED_DIR": str(processed),
        "DATASET_VERSIONS_DIR": str(raw / "versions"),
        "ACTIVE_DATASET_FILE": str(raw / "active_dataset.json"),
        "INVENTORY_VERSIONS_DIR": str(inventory / "versions"),
        "ACTIVE_INVENTORY_FILE": str(inventory / "active_inventory.json"),
        "MODELS_DIR": str(models),
        "MODEL_VERSIONS_DIR": str(models / "versions"),
        "ACTIVE_MODEL_FILE": str(models / "active_model.json"),
        "RUNTIME_SNAPSHOT_DIR": str(root / "runtime" / "versions"),
        "ACTIVE_RUNTIME_SNAPSHOT_FILE": str(root / "runtime" / "active_runtime.json"),
        "JOBS_DIR": str(root / "jobs"),
        "LOG_DIR": str(root / "logs"),
        "DATABASE_URL": f"sqlite:///{(root / 'dashboard.db').as_posix()}",
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    settings.ensure_dirs()
    return root


def _sales_frame(days=14):
    rows = []
    start = pd.Timestamp("2026-09-09")
    for offset in range(days):
        rows.append({
            "date": (start + pd.Timedelta(days=offset)).date().isoformat(),
            "product_id": 1,
            "store_id": 1,
            "product_name": "P1",
            "store_name": "S1",
            "category": "食品",
            "sales": 10,
            "price": 12.5,
        })
    return pd.DataFrame(rows)


def _inventory_frame(as_of="2026-09-22"):
    return pd.DataFrame([{
        "as_of_date": as_of,
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
    }])


def _prepare_runtime(monkeypatch, tmp_path):
    from app.services.dataset_service import import_sales_dataset
    from app.services.inventory_dataset_service import import_inventory_snapshot
    from app.services.runtime_snapshot_service import publish_runtime_snapshot

    root = _configure_demo_settings(monkeypatch, tmp_path)
    sales_source = root / "sales.csv"
    inventory_source = root / "inventory.csv"
    _sales_frame().to_csv(sales_source, index=False)
    _inventory_frame().to_csv(inventory_source, index=False)
    sales = import_sales_dataset(sales_source, activate=True)
    inventory = import_inventory_snapshot(inventory_source, activate=True)
    runtime = publish_runtime_snapshot(
        data_version=sales["dataset_id"],
        model_version="legacy",
        inventory_version=inventory["inventory_id"],
        activate=True,
    )
    return root, runtime


def test_scenario_catalog_requires_confirmation_and_switches_inventory_inputs(monkeypatch, tmp_path):
    from app.services import demo_service
    from app.services.inventory_dataset_service import get_active_inventory_path

    _, runtime = _prepare_runtime(monkeypatch, tmp_path)
    catalog = demo_service.list_scenarios()
    assert catalog["active"] == "standard"
    assert {item["name"] for item in catalog["scenarios"]} == {
        "standard", "stockout", "stale_inventory", "insufficient_history", "import_error",
    }

    with pytest.raises(Exception, match="confirm=true"):
        demo_service.switch_scenario("stockout")

    stockout = demo_service.switch_scenario("stockout", confirm=True)
    assert stockout["active"] == "stockout"
    assert pd.read_csv(get_active_inventory_path())["on_hand"].eq(0).all()

    stale = demo_service.switch_scenario("stale_inventory", confirm=True)
    assert stale["scenario"]["expected_status"] == "inventory_stale"
    assert pd.read_csv(get_active_inventory_path())["as_of_date"].iloc[0] == "2020-01-01"

    standard = demo_service.switch_scenario("standard", confirm=True)
    assert standard["active"] == "standard"
    assert standard["scenario"]["active_snapshot_id"] == runtime["snapshot_id"]


def test_backup_restore_validates_archive_and_preserves_state_on_bad_package(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import demo_service
    from app.services.plan_repository import PlanRepository

    root = _configure_demo_settings(monkeypatch, tmp_path)
    (root / "data" / "raw" / "sales_data.csv").write_text("demo", encoding="utf-8")
    repository = PlanRepository()
    saved = repository.save("backup-test", {
        "name": "backup",
        "as_of_date": "2026-09-22",
        "inventory_as_of_date": "2026-09-22",
        "data_version": "legacy",
        "model_version": "legacy",
        "inventory_version": "legacy",
        "policy_version": "policy-v1",
        "coverage": {"status": "ok", "requested": 1, "succeeded": 1, "failed": 0},
        "items": [{"suggested_purchase": 1, "adjustment_quantity": 0}],
    })
    backup = demo_service.create_backup(artifact_name="demo-backup-test.zip")
    assert backup["file_count"] >= 1

    repository.save("backup-test-2", {
        "name": "second",
        "as_of_date": "2026-09-22",
        "inventory_as_of_date": "2026-09-22",
        "data_version": "legacy",
        "model_version": "legacy",
        "inventory_version": "legacy",
        "policy_version": "policy-v1",
        "coverage": {"status": "ok", "requested": 1, "succeeded": 1, "failed": 0},
        "items": [{"suggested_purchase": 1, "adjustment_quantity": 0}],
    })
    assert len(PlanRepository().list()) == 2
    (root / "runtime").mkdir(parents=True, exist_ok=True)
    (root / "runtime" / "active_runtime.json").write_text("{}", encoding="utf-8")
    (root / "demo-scenario.json").write_text("{}", encoding="utf-8")
    restored = demo_service.restore_backup("demo-backup-test.zip")
    assert restored["restored"] is True
    assert [plan.plan_id for plan in PlanRepository().list()] == [saved.plan_id]
    assert not (root / "runtime" / "active_runtime.json").exists()
    assert not (root / "demo-scenario.json").exists()

    before = Path(settings.DATABASE_URL[10:]).read_bytes()
    bad = root / "backups" / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("../escape.txt", "no")
        archive.writestr("backup-manifest.json", json.dumps({"schema_version": 1, "files": []}))
    with pytest.raises(Exception, match="路径穿越"):
        demo_service.restore_backup("bad.zip")
    assert Path(settings.DATABASE_URL[10:]).read_bytes() == before


def test_diagnostic_and_demo_package_exclude_sensitive_runtime_files(monkeypatch, tmp_path):
    from app.services import demo_service

    root = _configure_demo_settings(monkeypatch, tmp_path)
    (root / "demo-manifest.json").write_text("{}", encoding="utf-8")
    (root / "data" / "raw" / "sales_data.csv").write_text("demo", encoding="utf-8")
    (root / "data" / "processed" / "features.csv").write_text("demo", encoding="utf-8")
    (root / "data" / "processed" / "evaluation_report.json").write_text("{}", encoding="utf-8")
    (root / "data" / "inventory" / "inventory_snapshot.csv").write_text("demo", encoding="utf-8")
    (root / "logs" / "app.log").write_text("api_token=secret\n", encoding="utf-8")
    (root / "dashboard.db").write_bytes(b"private")
    packaged = demo_service.package_demo(output=root / "dist" / "local-demo.zip")
    with zipfile.ZipFile(packaged["path"]) as archive:
        names = archive.namelist()
        assert "dashboard.db" not in names
        assert "data/raw/sales_data.csv" in names

    diagnostic = demo_service.create_diagnostic_package(artifact_name="diagnostic-test.zip")
    with zipfile.ZipFile(diagnostic["path"]) as archive:
        names = archive.namelist()
        content = archive.read("diagnostic.json").decode("utf-8")
        assert "dashboard.db" not in names
        assert "REDACTED" not in content
        assert "passwords" in content
        if "logs/app.log" in names:
            assert "secret" not in archive.read("logs/app.log").decode("utf-8")
