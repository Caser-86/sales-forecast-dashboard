"""预测接口"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.exceptions import ForecastUnavailableError, NotFoundError
from app.schemas import ForecastResult
from app.services import data_service, forecast_service

router = APIRouter()


@router.get("/forecast", response_model=ForecastResult, summary="未来 30 天预测")
def get_forecast(
    product_id: Annotated[int, Query(ge=1, description="商品 ID")],
    store_id: Annotated[int, Query(ge=1, description="门店 ID")],
):
    """返回某商品在某门店未来 30 天的预测结果。"""
    if not any(item["product_id"] == product_id for item in data_service.get_products()):
        raise NotFoundError(f"product_id={product_id} 不存在")
    if not any(item["store_id"] == store_id for item in data_service.get_stores()):
        raise NotFoundError(f"store_id={store_id} 不存在")
    try:
        return forecast_service.get_forecast(product_id, store_id)
    except (FileNotFoundError, ValueError) as exc:
        raise ForecastUnavailableError(
            "当前商品和门店暂无可用预测",
            detail=str(exc),
        ) from exc
