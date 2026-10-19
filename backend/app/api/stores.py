"""轻量商品/门店选择器元数据接口。"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Store
from app.services import data_service

router = APIRouter()


@router.get("/stores", response_model=list[Store], summary="门店列表")
def get_stores():
    """只读取有效销售数据目录，不触发批量预测。"""
    return data_service.get_stores()

