"""计划草案持久化、幂等和导出契约测试。"""
from __future__ import annotations

import shutil

import pytest


def _payload(*, status: str = "ok", product_name: str = "经典商品") -> dict:
    return {
        "name": "首轮补货草案",
        "as_of_date": "2026-09-15",
        "inventory_as_of_date": "2026-09-15",
        "data_version": "sales-0123456789abcdef",
        "model_version": "model-0123456789abcdef",
        "inventory_version": "inventory-0123456789abcdef",
        "policy_version": "replenishment-v1",
        "coverage": {"status": status, "requested": 1, "succeeded": 1, "failed": 0},
        "items": [
            {
                "product_id": 1,
                "store_id": 1,
                "product_name": product_name,
                "store_name": "一号店",
                "predicted_sales": 100,
                "suggested_purchase": 72,
                "risk_level": "high",
                "on_hand": 40,
                "confirmed_inbound": 0,
                "reserved": 0,
                "lead_time_days": 3,
                "review_period_days": 4,
                "safety_stock": 10,
                "pack_size": 12,
                "minimum_order_quantity": 24,
            }
        ],
        "adjustments": [],
    }


def test_plan_repository_is_idempotent_and_survives_restart(tmp_path):
    from app.services.plan_repository import PlanRepository

    database = tmp_path / "plans.db"
    first_repo = PlanRepository(database)
    first = first_repo.save("request-001", _payload())
    retry = first_repo.save("request-001", _payload())

    assert retry.plan_id == first.plan_id
    assert retry.created is False

    restarted = PlanRepository(database)
    loaded = restarted.get(first.plan_id)
    assert loaded is not None
    assert loaded.snapshot["model_version"] == "model-0123456789abcdef"
    backup = PlanRepository(tmp_path / "plans.db.bak")
    assert backup.get(first.plan_id).snapshot["model_version"] == "model-0123456789abcdef"


def test_restore_plans_replaces_database_only_after_validating_backup(tmp_path):
    from app.services.plan_repository import PlanRepository, restore_database

    database = tmp_path / "plans.db"
    backup = tmp_path / "plans.db.bak"
    backup_source = tmp_path / "backup-source.db"
    original = PlanRepository(database).save("request-001", _payload())
    backup_plan = PlanRepository(backup_source).save("request-001", _payload(product_name="备份商品"))
    shutil.copy2(backup_source, backup)

    result = restore_database(backup, database)

    assert result["plan_count"] == 1
    restored = PlanRepository(database).get(original.plan_id)
    assert restored is None
    restored = PlanRepository(database).get(backup_plan.plan_id)
    assert restored is not None
    assert restored.snapshot["items"][0]["product_name"] == "备份商品"


def test_restore_plans_rejects_corrupt_backup_without_replacing_database(tmp_path):
    from app.core.exceptions import NotFoundError
    from app.services.plan_repository import PlanRepository, restore_database

    database = tmp_path / "plans.db"
    backup = tmp_path / "corrupt.db.bak"
    original = PlanRepository(database).save("request-001", _payload())
    backup.write_bytes(b"not a sqlite database")

    with pytest.raises(ValueError, match="SQLite"):
        restore_database(backup, database)

    restored = PlanRepository(database).get(original.plan_id)
    assert restored is not None
    with pytest.raises(NotFoundError):
        PlanRepository(database).export_csv("plan-does-not-exist")


def test_plan_repository_rejects_reused_key_with_different_payload(tmp_path):
    from app.core.exceptions import ConflictError
    from app.services.plan_repository import PlanRepository

    repo = PlanRepository(tmp_path / "plans.db")
    repo.save("request-001", _payload())

    with pytest.raises(ConflictError):
        repo.save("request-001", _payload(product_name="另一商品"))


def test_plan_repository_rejects_partial_forecast(tmp_path):
    from app.core.exceptions import PlanValidationError
    from app.services.plan_repository import PlanRepository

    with pytest.raises(PlanValidationError):
        PlanRepository(tmp_path / "plans.db").save("request-001", _payload(status="partial"))


def test_plan_csv_export_prefixes_formula_cells(tmp_path):
    from app.services.plan_repository import PlanRepository

    repo = PlanRepository(tmp_path / "plans.db")
    saved = repo.save("request-001", _payload(product_name="=HYPERLINK(\"https://evil.test\")"))

    csv_text = repo.export_csv(saved.plan_id)
    assert "'=HYPERLINK" in csv_text
    assert "data_version,model_version,inventory_version,policy_version" in csv_text


def test_plan_api_save_get_and_export(client, monkeypatch, tmp_path):
    from app.api import plans
    from app.services.plan_repository import PlanRepository

    monkeypatch.setattr(plans, "get_repository", lambda: PlanRepository(tmp_path / "plans.db"))
    payload = _payload()
    headers = {"Idempotency-Key": "api-request-001"}

    response = client.post("/api/plans", json=payload, headers=headers)
    assert response.status_code == 201
    plan_id = response.json()["plan_id"]

    retry = client.post("/api/plans", json=payload, headers=headers)
    assert retry.status_code == 200
    assert retry.json()["plan_id"] == plan_id
    assert retry.json()["created"] is False

    detail = client.get(f"/api/plans/{plan_id}")
    assert detail.status_code == 200
    assert detail.json()["snapshot"]["data_version"] == payload["data_version"]

    exported = client.get(f"/api/plans/{plan_id}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "首轮补货草案" in exported.text

    partial = client.post(
        "/api/plans",
        json=_payload(status="partial"),
        headers={"Idempotency-Key": "api-request-partial"},
    )
    assert partial.status_code == 422
    assert partial.json()["error"]["code"] == "PLAN_INVALID"
