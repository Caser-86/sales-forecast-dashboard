"""历史销量接口"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import data_service
from app.schemas import SalesHistory

router = APIRouter()


@router.get("/sales", response_model=SalesHistory, summary="历史销量")
def get_sales(
    product_id: int = Query(..., description="商品 ID"),
    store_id: int = Query(..., description="门店 ID"),
    days: int = Query(90, ge=1, le=181, description="返回最近 N 天"),
):
    """返回某商品在某门店的历史销量数据。"""
    points = data_service.get_sales_history(product_id, store_id, days)
    return {"product_id": product_id, "store_id": store_id, "points": points}
