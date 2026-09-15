"""大屏聚合数据接口与库存接口"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict

from common.abc import classify_abc
from fastapi import APIRouter, Query

from app.core.config import settings
from app.core.exceptions import ForecastUnavailableError, NotFoundError
from app.schemas import DashboardData, InventoryResult, KpiResult
from app.services import data_service, forecast_service, inventory_service

router = APIRouter()


def _compute_kpi(
    all_f: list[dict] | None = None,
    products: list[dict] | None = None,
    stores: list[dict] | None = None,
    product_id: int | None = None,
    store_id: int | None = None,
) -> Dict[str, Any]:
    """计算 KPI 指标。

    Args:
        all_f: 已计算的预测全集。若为 None，则内部调用一次。
        传入可避免与 get_dashboard 重复调用 get_forecast_all。
    """
    products = products if products is not None else data_service.get_products()
    stores = stores if stores is not None else data_service.get_stores()

    # 最近 30 天总销量（所有门店×所有商品）
    if product_id is None and store_id is None:
        total_sales = data_service.get_total_sales_last_n(30)
    else:
        total_sales = data_service.get_total_sales_last_n(30, product_id, store_id)

    # 所有商品×门店的预测总量（与 total_sales 同口径）
    if all_f is None:
        all_f = forecast_service.get_forecast_all(products, stores)
    coverage = forecast_service.summarize_forecasts(all_f)
    if coverage["requested"] and coverage["succeeded"] == 0:
        raise ForecastUnavailableError("当前范围内没有可用预测")
    total_predicted = sum(f["total_predicted"] for f in all_f if "error" not in f)

    # 增长率
    growth_rate = round((total_predicted - total_sales) / total_sales * 100, 2) if total_sales else 0.0

    # 模型准确率（1 - MAPE）
    report = data_service.load_report()
    mape = report.get("ensemble", {}).get("mape", 100)
    accuracy = round(max(0.0, 100.0 - mape), 2)
    window = data_service.get_metric_window(30, settings.FORECAST_DAYS)

    # ABC 总体固定为全量商品，再按当前筛选范围取等级，避免筛选导致等级漂移。
    global_product_demand = data_service.get_recent_product_demand(30)
    global_product_abc = classify_abc(global_product_demand)
    selected_product_ids = {p["product_id"] for p in products}
    product_abc = {
        product_id: global_product_abc.get(product_id, "C")
        for product_id in selected_product_ids
    }
    abc_dist = {"A": 0, "B": 0, "C": 0}
    for abc in product_abc.values():
        abc_dist[abc] = abc_dist.get(abc, 0) + 1

    # 预警商品数（A 类商品数，按商品去重）
    alert_count = abc_dist["A"]

    return {
        "total_sales": int(total_sales),
        "total_predicted": int(total_predicted),
        "growth_rate": growth_rate,
        "accuracy": accuracy,
        "mape": round(float(mape), 2),
        "window": window,
        "coverage": coverage,
        "sku_count": len(products),
        "alert_count": alert_count,
        "abc_distribution": abc_dist,
    }


@router.get("/dashboard", response_model=DashboardData, summary="大屏聚合数据")
def get_dashboard(
    product_id: Annotated[int | None, Query(ge=1)] = None,
    store_id: Annotated[int | None, Query(ge=1)] = None,
):
    """返回大屏指标，默认全量，也支持按商品和门店缩小范围。"""
    all_products = data_service.get_products()
    all_stores = data_service.get_stores()
    products = _select_scope(all_products, "product_id", product_id)
    stores = _select_scope(all_stores, "store_id", store_id)
    # 预测全集只算一次，KPI 与 Top 商品复用
    all_f = forecast_service.get_forecast_all(products, stores)

    kpi = _compute_kpi(all_f, products, stores, product_id, store_id)
    if product_id is None and store_id is None:
        top = data_service.get_top_products(10)
    else:
        top = data_service.get_top_products(10, product_id, store_id)

    # 按商品汇总所有门店预测，保持与历史销量的商品粒度一致。
    product_forecasts: Dict[int, Dict[str, int]] = {}
    for f in all_f:
        if "error" in f:
            continue
        aggregate = product_forecasts.setdefault(
            f["product_id"],
            {"predicted": 0, "suggested_purchase": 0},
        )
        aggregate["predicted"] += int(f.get("total_predicted", 0))
        aggregate["suggested_purchase"] += int(f.get("suggested_purchase", 0))

    global_product_demand = data_service.get_recent_product_demand(30)
    global_product_abc = classify_abc(global_product_demand)
    selected_product_ids = {p["product_id"] for p in products}
    product_abc = {
        selected_id: global_product_abc.get(selected_id, "C")
        for selected_id in selected_product_ids
    }

    top_products = []
    for t in top:
        aggregate = product_forecasts.get(
            t["product_id"],
            {"predicted": 0, "suggested_purchase": 0},
        )
        top_products.append({
            "product_id": t["product_id"],
            "product_name": t["product_name"],
            "category": t["category"],
            "sales": t["sales"],
            "predicted": aggregate["predicted"],
            "suggested_purchase": aggregate["suggested_purchase"],
            "abc_class": product_abc.get(t["product_id"], "C"),
        })

    if product_id is None and store_id is None:
        category_sales = data_service.get_category_sales()
    else:
        category_sales = data_service.get_category_sales(product_id, store_id)

    return {
        "kpi": kpi,
        "abc_distribution": kpi["abc_distribution"],
        "top_products": top_products,
        "category_sales": category_sales,
        "coverage": kpi["coverage"],
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/inventory", response_model=InventoryResult, summary="库存分级热力图")
def get_inventory(
    product_id: Annotated[int | None, Query(ge=1)] = None,
    store_id: Annotated[int | None, Query(ge=1)] = None,
):
    """返回 ABC 分级热力图数据。"""
    return inventory_service.get_inventory(product_id, store_id)


@router.get("/kpi", response_model=KpiResult, summary="KPI 指标卡片")
def get_kpi():
    """返回核心指标卡片数据。"""
    return _compute_kpi()


def _select_scope(items: list[dict], key: str, value: int | None) -> list[dict]:
    """选择作用域并对不存在的筛选 ID 返回明确错误。"""
    if value is None:
        return items
    selected = [item for item in items if item[key] == value]
    if not selected:
        raise NotFoundError(f"{key}={value} 不存在")
    return selected
