"""大屏聚合数据接口与库存接口"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter

from app.services import data_service, inventory_service, forecast_service
from app.schemas import DashboardData, InventoryResult, KpiResult

router = APIRouter()


def _compute_kpi(all_f: list[dict] | None = None) -> Dict[str, Any]:
    """计算 KPI 指标。

    Args:
        all_f: 已计算的预测全集。若为 None，则内部调用一次。
        传入可避免与 get_dashboard 重复调用 get_forecast_all。
    """
    products = data_service.get_products()
    stores = data_service.get_stores()

    # 最近 30 天总销量（所有门店×所有商品）
    total_sales = data_service.get_total_sales_last_n(30)

    # 所有商品×门店的预测总量（与 total_sales 同口径）
    if all_f is None:
        all_f = forecast_service.get_forecast_all(products, stores)
    total_predicted = sum(f.get("total_predicted", 0) for f in all_f)

    # 增长率
    growth_rate = round((total_predicted - total_sales) / total_sales * 100, 2) if total_sales else 0.0

    # 模型准确率（1 - MAPE）
    report = data_service.load_report()
    mape = report.get("ensemble", {}).get("mape", 100)
    accuracy = round(max(0.0, 100.0 - mape), 2)

    # ABC 分布（按商品去重，同一商品取所有门店中最高优先级 A>B>C）
    priority = {"A": 0, "B": 1, "C": 2}
    product_best: Dict[int, str] = {}
    for f in all_f:
        pid = f["product_id"]
        abc = f.get("abc_class", "C")
        if pid not in product_best or priority[abc] < priority[product_best[pid]]:
            product_best[pid] = abc
    abc_dist = {"A": 0, "B": 0, "C": 0}
    for abc in product_best.values():
        abc_dist[abc] = abc_dist.get(abc, 0) + 1

    # 预警商品数（A 类商品数，按商品去重）
    alert_count = abc_dist["A"]

    return {
        "total_sales": int(total_sales),
        "total_predicted": int(total_predicted),
        "growth_rate": growth_rate,
        "accuracy": accuracy,
        "sku_count": len(products),
        "alert_count": alert_count,
        "abc_distribution": abc_dist,
    }


@router.get("/dashboard", response_model=DashboardData, summary="大屏聚合数据")
def get_dashboard():
    """返回大屏所有商品汇总指标。"""
    products = data_service.get_products()
    stores = data_service.get_stores()
    # 预测全集只算一次，KPI 与 Top 商品复用
    all_f = forecast_service.get_forecast_all(products, stores)

    kpi = _compute_kpi(all_f)
    top = data_service.get_top_products(10)

    # 取每个商品在门店1的预测
    pid_to_forecast = {}
    for f in all_f:
        if f["store_id"] == 1 and "error" not in f:
            pid_to_forecast[f["product_id"]] = f

    top_products = []
    for t in top:
        f = pid_to_forecast.get(t["product_id"], {})
        top_products.append({
            "product_id": t["product_id"],
            "product_name": t["product_name"],
            "category": t["category"],
            "sales": t["sales"],
            "predicted": f.get("total_predicted", 0),
            "suggested_purchase": f.get("suggested_purchase", 0),
            "abc_class": f.get("abc_class", "C"),
        })

    category_sales = data_service.get_category_sales()

    return {
        "kpi": kpi,
        "abc_distribution": kpi["abc_distribution"],
        "top_products": top_products,
        "category_sales": category_sales,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/inventory", response_model=InventoryResult, summary="库存分级热力图")
def get_inventory():
    """返回 ABC 分级热力图数据。"""
    return inventory_service.get_inventory()


@router.get("/kpi", response_model=KpiResult, summary="KPI 指标卡片")
def get_kpi():
    """返回核心指标卡片数据。"""
    return _compute_kpi()
