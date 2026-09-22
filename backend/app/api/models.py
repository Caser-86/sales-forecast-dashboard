"""Model-center catalog, training status, and manual activation APIs."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services import model_service

router = APIRouter()


@router.get("/models", response_model=dict[str, Any], summary="查看模型中心")
def list_models():
    return model_service.build_model_catalog()


@router.get("/models/{model_id}", response_model=dict[str, Any], summary="查看模型详情")
def get_model(model_id: str):
    return model_service.get_model_detail(model_id)


@router.post("/models/{model_id}/activate", response_model=dict[str, Any], summary="人工激活模型")
def activate_model(model_id: str):
    return model_service.activate_model_for_serving(model_id)
