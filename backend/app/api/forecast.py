"""预测接口"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import forecast_service
from app.schemas import ForecastResult

router = APIRouter()


@router.get("/forecast", response_model=ForecastResult, summary="未来 30 天预测")
def get_forecast(
    product_id: int = Query(..., description="商品 ID"),
    store_id: int = Query(..., description="门店 ID"),
):
    """返回某商品在某门店未来 30 天的预测结果。"""
    return forecast_service.get_forecast(product_id, store_id)
