"""库存分级服务

基于预测结果计算 ABC 分级与缺货风险热力图。
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.exceptions import NotFoundError
from app.services import data_service, forecast_service


def _risk_level(predicted: int, suggested: int, abc: str) -> str:
    """简单的风险等级判定。"""
    if abc == "A" and suggested > 0:
        # A 类商品：高周转，需重点关注
        return "high"
    elif abc == "B":
        return "medium"
    else:
        return "low"


def get_inventory(
    product_id: int | None = None,
    store_id: int | None = None,
) -> Dict[str, Any]:
    products = data_service.get_products()
    stores = data_service.get_stores()

    if product_id is not None:
        products = [p for p in products if p["product_id"] == product_id]
        if not products:
            raise NotFoundError(f"product_id={product_id} 不存在")
    if store_id is not None:
        stores = [s for s in stores if s["store_id"] == store_id]
        if not stores:
            raise NotFoundError(f"store_id={store_id} 不存在")

    all_forecasts = forecast_service.get_forecast_all(products, stores)

    cells: List[Dict[str, Any]] = []
    risk_summary = {"high": 0, "medium": 0, "low": 0}

    for f in all_forecasts:
        if "error" in f:
            continue
        predicted = f["total_predicted"]
        suggested = f["suggested_purchase"]
        abc = f["abc_class"]
        risk = _risk_level(predicted, suggested, abc)
        risk_summary[risk] += 1
        cells.append({
            "product_id": f["product_id"],
            "product_name": f["product_name"],
            "store_id": f["store_id"],
            "store_name": f["store_name"],
            "predicted_sales": predicted,
            "suggested_purchase": suggested,
            "abc_class": abc,
            "risk_level": risk,
        })

    return {
        "total": len(cells),
        "cells": cells,
        "risk_summary": risk_summary,
    }
