"""Legacy SQLite migration and restart persistence contracts."""
from __future__ import annotations

import importlib
import json
import sqlite3


def _snapshot() -> dict:
    return {
        "name": "旧版补货草案",
        "as_of_date": "2026-09-15",
        "inventory_as_of_date": "2026-09-15",
        "data_version": "sales-0123456789abcdef",
        "model_version": "model-0123456789abcdef",
        "inventory_version": "inventory-0123456789abcdef",
        "policy_version": "replenishment-v1",
        "coverage": {"status": "ok", "requested": 1, "succeeded": 1, "failed": 0},
        "items": [
            {
                "product_id": 1,
                "store_id": 1,
                "product_name": "经典商品",
                "store_name": "一号店",
                "predicted_sales": 100,
                "suggested_purchase": 12,
                "risk_level": "medium",
                "on_hand": 10,
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


def test_legacy_plan_database_migrates_and_survives_service_restart(tmp_path):
    from app.services.plan_repository import PlanRepository
    from app.services.plan_workflow_service import PlanWorkflowService

    database = tmp_path / "legacy.db"
    snapshot = _snapshot()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE plan_drafts (plan_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO plan_drafts(plan_id, snapshot_json, created_at) VALUES (?, ?, ?)",
            ("plan-legacy", json.dumps(snapshot, ensure_ascii=False), "2026-09-15T00:00:00+00:00"),
        )

    restarted = PlanRepository(database)
    assert database.with_name("legacy.db.migration.bak").exists()
    loaded = restarted.get("plan-legacy")
    assert loaded is not None
    assert loaded.snapshot["name"] == "旧版补货草案"

    workflow = PlanWorkflowService(database)
    assert workflow.get("plan-legacy")["status"] == "draft"
    created = restarted.save("request-new", snapshot | {"name": "新版本补货草案"})
    assert created.created is True
    assert len(PlanRepository(database).list()) == 2


def test_demo_session_survives_auth_service_reload(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services import auth_service

    database = tmp_path / "session.db"
    monkeypatch.setattr(settings, "DEMO_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{database.as_posix()}")

    token, user, _expires = auth_service.login("analyst", "demo-analyst")
    assert user.username == "analyst"

    reloaded = importlib.reload(auth_service)
    current = reloaded.current_user(token)
    assert current is not None
    assert current.username == "analyst"
