"""保存、查看和导出补货草案。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse, Response

from app.core.exceptions import NotFoundError, PlanValidationError
from app.schemas import PlanDetail, PlanDraftCreate, PlanSaveResult, PlanSummary, PlanTransitionRequest
from app.services.auth_service import DemoUser, require_roles, require_user
from app.services.plan_repository import PlanRepository, SavedPlan
from app.services.plan_workflow_service import PlanWorkflowService

router = APIRouter()
_UserDependency = Depends(require_user)
_AnalystOrAdminDependency = Depends(require_roles("analyst", "admin"))
_AdminDependency = Depends(require_roles("admin"))


def get_repository() -> PlanRepository:
    return PlanRepository()


def get_workflow() -> PlanWorkflowService:
    return PlanWorkflowService(get_repository().database)


def _summary(plan: SavedPlan, workflow: dict | None = None) -> PlanSummary:
    snapshot = plan.snapshot
    return PlanSummary(
        plan_id=plan.plan_id,
        name=snapshot["name"],
        created_at=plan.created_at,
        item_count=len(snapshot["items"]),
        data_version=snapshot["data_version"],
        model_version=snapshot["model_version"],
        inventory_version=snapshot["inventory_version"],
        policy_version=snapshot["policy_version"],
        status=(workflow or {}).get("status", "draft"),
        version=int((workflow or {}).get("version", 1)),
        updated_at=(workflow or {}).get("updated_at"),
    )


@router.post("/plans", response_model=PlanSaveResult, summary="保存补货草案")
def create_plan(
    payload: PlanDraftCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: DemoUser = _AnalystOrAdminDependency,
):
    if not idempotency_key:
        raise PlanValidationError("保存草案必须提供 Idempotency-Key")
    repository = get_repository()
    saved = repository.save(idempotency_key, payload.model_dump(mode="json"))
    PlanWorkflowService(repository.database).ensure_plan(saved.plan_id, user)
    result = PlanSaveResult(plan_id=saved.plan_id, created=saved.created, created_at=saved.created_at)
    return JSONResponse(status_code=201 if saved.created else 200, content=result.model_dump())


@router.get("/plans", response_model=list[PlanSummary], summary="查看补货草案列表")
def list_plans(limit: Annotated[int, Query(ge=1, le=100)] = 50, _user: DemoUser = _UserDependency):
    repository = get_repository()
    workflow = PlanWorkflowService(repository.database)
    return [_summary(plan, workflow.get(plan.plan_id)) for plan in repository.list(limit)]


@router.get("/plans/{plan_id}", response_model=PlanDetail, summary="查看补货草案")
def get_plan(plan_id: str, _user: DemoUser = _UserDependency):
    repository = get_repository()
    plan = repository.get(plan_id)
    if plan is None:
        raise NotFoundError(f"草案 {plan_id} 不存在")
    workflow = PlanWorkflowService(repository.database)
    return PlanDetail(**_summary(plan, workflow.get(plan.plan_id)).model_dump(), snapshot=plan.snapshot)


@router.get("/plans/{plan_id}/export", summary="导出补货草案 CSV")
def export_plan(plan_id: str, _user: DemoUser = _UserDependency):
    csv_text = get_repository().export_csv(plan_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{plan_id}.csv"'},
    )


@router.post("/plans/{plan_id}/transition", response_model=PlanSummary, summary="变更补货计划状态")
def transition_plan(
    plan_id: str,
    payload: PlanTransitionRequest,
    user: DemoUser = _UserDependency,
):
    repository = get_repository()
    workflow = PlanWorkflowService(repository.database)
    state = workflow.transition(plan_id, payload.action, user, payload.expected_version, payload.reason)
    plan = repository.get(plan_id)
    if plan is None:
        raise NotFoundError(f"草案 {plan_id} 不存在")
    return _summary(plan, state)


@router.post("/plans/{plan_id}/revisions", response_model=PlanSaveResult, summary="创建被驳回计划修订版")
def create_revision(
    plan_id: str,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: DemoUser = _AnalystOrAdminDependency,
):
    if not idempotency_key:
        raise PlanValidationError("创建修订版必须提供 Idempotency-Key")
    result = get_workflow().create_revision(plan_id, user, idempotency_key)
    plan = get_repository().get(result["plan_id"])
    return PlanSaveResult(plan_id=plan.plan_id, created=result["created"], created_at=plan.created_at)


@router.get("/plans/{plan_id}/events", summary="查看计划审计事件")
def list_plan_events(plan_id: str, _user: DemoUser = _AdminDependency):
    return get_workflow().events(plan_id)
