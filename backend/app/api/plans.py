"""保存、查看和导出补货草案。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse, Response

from app.core.exceptions import NotFoundError, PlanValidationError
from app.schemas import PlanDetail, PlanDraftCreate, PlanSaveResult, PlanSummary
from app.services.plan_repository import PlanRepository, SavedPlan

router = APIRouter()


def get_repository() -> PlanRepository:
    return PlanRepository()


def _summary(plan: SavedPlan) -> PlanSummary:
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
    )


@router.post("/plans", response_model=PlanSaveResult, summary="保存补货草案")
def create_plan(
    payload: PlanDraftCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if not idempotency_key:
        raise PlanValidationError("保存草案必须提供 Idempotency-Key")
    saved = get_repository().save(idempotency_key, payload.model_dump(mode="json"))
    result = PlanSaveResult(plan_id=saved.plan_id, created=saved.created, created_at=saved.created_at)
    return JSONResponse(status_code=201 if saved.created else 200, content=result.model_dump())


@router.get("/plans", response_model=list[PlanSummary], summary="查看补货草案列表")
def list_plans(limit: Annotated[int, Query(ge=1, le=100)] = 50):
    return [_summary(plan) for plan in get_repository().list(limit)]


@router.get("/plans/{plan_id}", response_model=PlanDetail, summary="查看补货草案")
def get_plan(plan_id: str):
    plan = get_repository().get(plan_id)
    if plan is None:
        raise NotFoundError(f"草案 {plan_id} 不存在")
    return PlanDetail(**_summary(plan).model_dump(), snapshot=plan.snapshot)


@router.get("/plans/{plan_id}/export", summary="导出补货草案 CSV")
def export_plan(plan_id: str):
    csv_text = get_repository().export_csv(plan_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{plan_id}.csv"'},
    )

