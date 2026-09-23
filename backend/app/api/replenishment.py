"""Replenishment what-if API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.schemas import ReplenishmentPreviewRequest
from app.services import replenishment_service

router = APIRouter()


@router.post("/replenishment/preview", response_model=dict[str, Any], summary="试算补货建议")
def preview_replenishment(payload: ReplenishmentPreviewRequest):
    return replenishment_service.preview_replenishment(**payload.model_dump())
