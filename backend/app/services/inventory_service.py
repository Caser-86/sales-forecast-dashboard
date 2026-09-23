"""库存分级服务

基于预测结果计算 ABC 分级与缺货风险热力图。
"""
from __future__ import annotations

from typing import Any, Dict, List

from common.replenishment import calculate_replenishment

from app.core.config import settings
from app.core.exceptions import ForecastUnavailableError, InventoryUnavailableError, NotFoundError
from app.services import data_service, forecast_service
from app.services.inventory_dataset_service import get_active_inventory_id, load_active_inventory_snapshot


def _snapshot_by_key():
    snapshot = load_active_inventory_snapshot()
    if snapshot is None:
        return None
    return {
        (int(row.product_id), int(row.store_id)): row
        for row in snapshot.itertuples()
    }


def _validate_snapshot_freshness(snapshot) -> None:
    reference = data_service.load_sales()["date"].max().date()
    inventory_date = snapshot["as_of_date"].max().date()
    age_days = (reference - inventory_date).days
    if age_days < 0 or age_days > settings.INVENTORY_MAX_AGE_DAYS:
        raise InventoryUnavailableError(
            f"库存快照已过期（{age_days} 天），请导入不超过 {settings.INVENTORY_MAX_AGE_DAYS} 天的新快照"
        )


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

    snapshot = load_active_inventory_snapshot()
    if snapshot is None or snapshot.empty:
        raise InventoryUnavailableError("缺少有效库存快照，请先导入库存数据")
    _validate_snapshot_freshness(snapshot)
    inventory_by_key = {
        (int(row.product_id), int(row.store_id)): row
        for row in snapshot.itertuples()
    }
    inventory_version = get_active_inventory_id()

    all_forecasts = forecast_service.get_forecast_all(products, stores)
    coverage = forecast_service.summarize_forecasts(all_forecasts)
    if coverage["requested"] and coverage["succeeded"] == 0:
        raise ForecastUnavailableError("当前范围内没有可用库存预测")

    cells: List[Dict[str, Any]] = []
    risk_summary = {"high": 0, "medium": 0, "low": 0}

    for f in all_forecasts:
        if "error" in f:
            continue
        inventory = inventory_by_key.get((f["product_id"], f["store_id"]))
        if inventory is None:
            raise InventoryUnavailableError(
                "库存快照缺少商品/门店记录："
                f"product_id={f['product_id']}, store_id={f['store_id']}"
            )
        policy = calculate_replenishment(
            demand_forecast=[point["predicted_sales"] for point in f["forecast"]],
            on_hand=inventory.on_hand,
            confirmed_inbound=inventory.confirmed_inbound,
            reserved=inventory.reserved,
            lead_time_days=int(inventory.lead_time_days),
            review_period_days=int(inventory.review_period_days),
            safety_stock=inventory.safety_stock,
            pack_size=int(inventory.pack_size),
            minimum_order_quantity=int(inventory.minimum_order_quantity),
        )
        predicted = f["total_predicted"]
        suggested = int(policy["suggested_quantity"])
        risk = str(policy["risk_level"])
        risk_summary[risk] += 1
        cells.append({
            "product_id": f["product_id"],
            "product_name": f["product_name"],
            "store_id": f["store_id"],
            "store_name": f["store_name"],
            "predicted_sales": predicted,
            "suggested_purchase": suggested,
            "abc_class": f["abc_class"],
            "risk_level": risk,
            "inventory_version": inventory_version,
            "inventory_as_of_date": str(inventory.as_of_date.date()),
            "window_demand": policy["window_demand"],
            "net_available": policy["net_available"],
            "target_stock": policy["target_stock"],
            "raw_replenishment": policy["raw_replenishment"],
            "on_hand": float(inventory.on_hand),
            "confirmed_inbound": float(inventory.confirmed_inbound),
            "reserved": float(inventory.reserved),
            "lead_time_days": int(inventory.lead_time_days),
            "review_period_days": int(inventory.review_period_days),
            "safety_stock": float(inventory.safety_stock),
            "pack_size": int(inventory.pack_size),
            "minimum_order_quantity": int(inventory.minimum_order_quantity),
        })

    return {
        "total": len(cells),
        "cells": cells,
        "risk_summary": risk_summary,
        "coverage": coverage,
    }
