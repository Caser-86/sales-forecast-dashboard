"""计划状态机、角色边界和审计事件测试。"""
from __future__ import annotations

import pytest
from app.core.exceptions import ConflictError, UnauthorizedError
from app.services.auth_service import DemoUser
from app.services.plan_repository import PlanRepository
from app.services.plan_workflow_service import PlanWorkflowService


def _payload(name: str = "演示草案") -> dict:
    return {
        "name": name,
        "as_of_date": "2026-09-22",
        "inventory_as_of_date": "2026-09-22",
        "data_version": "sales-v1",
        "model_version": "model-v1",
        "inventory_version": "inventory-v1",
        "policy_version": "policy-v1",
        "coverage": {"status": "ok", "requested": 1, "succeeded": 1, "failed": 0},
        "items": [{
            "product_id": 1,
            "store_id": 1,
            "product_name": "商品",
            "store_name": "门店",
            "predicted_sales": 10,
            "suggested_purchase": 12,
            "original_suggested_purchase": 12,
            "risk_level": "medium",
            "on_hand": 2,
            "confirmed_inbound": 0,
            "reserved": 0,
            "lead_time_days": 2,
            "review_period_days": 2,
            "safety_stock": 1,
            "pack_size": 1,
            "minimum_order_quantity": 0,
        }],
        "adjustments": [],
    }


def test_plan_workflow_enforces_roles_versions_and_audit(tmp_path):
    repository = PlanRepository(tmp_path / "plans.db")
    saved = repository.save("request-1", _payload())
    workflow = PlanWorkflowService(repository.database)
    analyst = DemoUser("analyst", "分析员", "analyst")
    approver = DemoUser("approver", "审批员", "approver")

    workflow.ensure_plan(saved.plan_id, analyst)
    submitted = workflow.transition(saved.plan_id, "submit", analyst, expected_version=1)
    assert submitted["status"] == "submitted"
    assert submitted["version"] == 2

    with pytest.raises(UnauthorizedError):
        workflow.transition(saved.plan_id, "approve", analyst, expected_version=2)
    with pytest.raises(ConflictError):
        workflow.transition(saved.plan_id, "approve", approver, expected_version=1)

    approved = workflow.transition(saved.plan_id, "approve", approver, expected_version=2)
    assert approved["status"] == "approved"
    assert len(workflow.events(saved.plan_id)) == 2


def test_rejected_plan_can_create_a_new_draft_revision(tmp_path):
    repository = PlanRepository(tmp_path / "plans.db")
    saved = repository.save("request-1", _payload())
    workflow = PlanWorkflowService(repository.database)
    analyst = DemoUser("analyst", "分析员", "analyst")
    approver = DemoUser("approver", "审批员", "approver")

    workflow.ensure_plan(saved.plan_id, analyst)
    workflow.transition(saved.plan_id, "submit", analyst, expected_version=1)
    rejected = workflow.transition(saved.plan_id, "reject", approver, expected_version=2, reason="请补充活动说明")
    assert rejected["status"] == "rejected"

    revision = workflow.create_revision(saved.plan_id, analyst, "revision-1")
    assert revision["created"] is True
    assert revision["plan_id"] != saved.plan_id
    assert revision["workflow"]["status"] == "draft"
    assert revision["workflow"]["parent_plan_id"] == saved.plan_id
    assert repository.get(revision["plan_id"]).snapshot["name"].endswith("修订版）")
