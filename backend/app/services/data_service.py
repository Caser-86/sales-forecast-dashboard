"""数据查询服务

从 CSV 加载历史销量数据，提供查询接口。
使用模块级缓存避免重复 IO。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List

import pandas as pd

from app.config import REPORT_JSON, SALES_CSV, settings
from app.core.exceptions import DataNotInitializedError, NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def load_sales() -> pd.DataFrame:
    """加载并缓存历史销量数据。"""
    if not SALES_CSV.exists():
        logger.error("销售数据文件不存在: %s", SALES_CSV)
        raise DataNotInitializedError(
            "销售数据未初始化",
            detail=f"请先运行 python scripts/init_data.py 生成数据。路径: {SALES_CSV}",
        )
    logger.info("加载销售数据: %s", SALES_CSV)
    df = pd.read_csv(SALES_CSV)
    df["date"] = pd.to_datetime(df["date"])
    return df


@lru_cache(maxsize=1)
def load_report() -> Dict[str, Any]:
    """加载模型评估报告。"""
    if not REPORT_JSON.exists():
        return {}
    import json
    with open(REPORT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def get_model_info() -> Dict[str, Any]:
    """规范化模型报告，兼容旧版只有指标的 JSON。"""
    report = load_report()
    metric_keys = ("seasonal_naive_7d", "lstm", "lightgbm", "ensemble")
    metrics = {
        name: {
            "mape": float(report[name]["mape"]),
            "rmse": float(report[name]["rmse"]),
        }
        for name in metric_keys
        if isinstance(report.get(name), dict)
        and "mape" in report[name]
        and "rmse" in report[name]
    }
    metadata = report.get("metadata", {})
    data = metadata.get("data", {})
    split = metadata.get("split", {})
    default_weights = {
        "lstm": float(settings.ENSEMBLE_WEIGHTS[0]),
        "lightgbm": float(settings.ENSEMBLE_WEIGHTS[1]),
    }
    weights = metadata.get("ensemble_weights", default_weights)
    return {
        "status": "ready" if "ensemble" in metrics else "unavailable",
        "trained_at_utc": metadata.get("trained_at_utc"),
        "data_start": data.get("date_start"),
        "data_end": data.get("date_end"),
        "horizon_days": int(metadata.get("horizon_days", settings.FORECAST_DAYS)),
        "feature_count": metadata.get("feature_count"),
        "ensemble_weights": {str(k): float(v) for k, v in weights.items()},
        "split": split,
        "metrics": metrics,
    }


@lru_cache(maxsize=1)
def get_data_quality() -> Dict[str, Any]:
    """检查销售数据完整性，返回适合监控和面试演示的摘要。"""
    df = load_sales()
    missing_values = {
        str(column): int(count)
        for column, count in df.isna().sum().items()
    }

    key_columns = ["date", "product_id", "store_id"]
    duplicate_rows = int(df.duplicated(subset=key_columns).sum())
    date_gap_count = 0
    for _, group in df.groupby(["product_id", "store_id"]):
        unique_dates = group["date"].dropna().drop_duplicates()
        if unique_dates.empty:
            continue
        expected_days = (unique_dates.max() - unique_dates.min()).days + 1
        date_gap_count += max(0, expected_days - len(unique_dates))

    negative_sales_count = int((df["sales"] < 0).sum())
    issues: list[str] = []
    if df.empty:
        issues.append("销售数据为空")
    if any(missing_values.values()):
        issues.append("存在缺失值")
    if duplicate_rows:
        issues.append("存在重复的商品/门店/日期记录")
    if date_gap_count:
        issues.append("存在日期断档")
    if negative_sales_count:
        issues.append("存在负销量")

    return {
        "status": "error" if df.empty else ("healthy" if not issues else "warning"),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SALES_CSV.name,
        "rows": int(len(df)),
        "date_start": str(df["date"].min().date()) if len(df) else None,
        "date_end": str(df["date"].max().date()) if len(df) else None,
        "product_count": int(df["product_id"].nunique()),
        "store_count": int(df["store_id"].nunique()),
        "missing_values": missing_values,
        "duplicate_rows": duplicate_rows,
        "date_gap_count": date_gap_count,
        "negative_sales_count": negative_sales_count,
        "issues": issues,
    }


def get_products() -> List[Dict[str, Any]]:
    df = load_sales()
    products = (
        df[["product_id", "product_name", "category", "price"]]
        .drop_duplicates(["product_id"])
        .sort_values("product_id")
    )
    return [
        {
            "product_id": int(r.product_id),
            "product_name": str(r.product_name),
            "category": str(r.category),
            "base_price": round(float(r.price), 2),
        }
        for r in products.itertuples()
    ]


def get_stores() -> List[Dict[str, Any]]:
    df = load_sales()
    stores = df[["store_id", "store_name"]].drop_duplicates().sort_values("store_id")
    return [
        {"store_id": int(r.store_id), "store_name": str(r.store_name)}
        for r in stores.itertuples()
    ]


def _validate_product_store(df: pd.DataFrame, product_id: int, store_id: int) -> None:
    """校验商品与门店是否存在。"""
    if not ((df["product_id"] == product_id) & (df["store_id"] == store_id)).any():
        valid_pids = df["product_id"].unique().tolist()
        valid_sids = df["store_id"].unique().tolist()
        raise NotFoundError(
            f"商品 {product_id} 或门店 {store_id} 不存在",
            detail=f"有效商品 ID: {valid_pids}; 有效门店 ID: {valid_sids}",
        )


def get_sales_history(product_id: int, store_id: int, days: int = 90) -> List[Dict[str, Any]]:
    df = load_sales()
    _validate_product_store(df, product_id, store_id)
    mask = (df["product_id"] == product_id) & (df["store_id"] == store_id)
    sub = df[mask].sort_values("date").tail(days)
    return [
        {
            "date": str(r.date.date()),
            "sales": int(r.sales),
            "price": float(r.price),
            "is_promotion": int(r.is_promotion),
            "is_holiday": int(r.is_holiday),
            "is_weekend": int(r.is_weekend),
        }
        for r in sub.itertuples()
    ]


def _apply_scope(
    df: pd.DataFrame,
    product_id: int | None = None,
    store_id: int | None = None,
) -> pd.DataFrame:
    """按可选商品/门店范围过滤数据。"""
    if product_id is not None:
        df = df[df["product_id"] == product_id]
    if store_id is not None:
        df = df[df["store_id"] == store_id]
    return df


def get_total_sales_last_n(
    days: int = 30,
    product_id: int | None = None,
    store_id: int | None = None,
) -> int:
    df = load_sales()
    last_date = df["date"].max()
    start = last_date - timedelta(days=days - 1)
    recent = df[df["date"] >= start]
    return int(_apply_scope(recent, product_id, store_id)["sales"].sum())


@lru_cache(maxsize=16)
def get_recent_product_demand(
    days: int = 30,
    product_id: int | None = None,
    store_id: int | None = None,
) -> Dict[int, float]:
    """返回最近 N 天按商品汇总的需求量，用于商品级 ABC 分级。"""
    if days <= 0:
        raise ValueError("days 必须大于 0")
    df = load_sales()
    last_date = df["date"].max()
    start = last_date - timedelta(days=days - 1)
    recent = _apply_scope(df[df["date"] >= start], product_id, store_id)
    grouped = recent.groupby("product_id")["sales"].sum()
    return {int(product_id): float(total) for product_id, total in grouped.items()}


def get_category_sales(
    product_id: int | None = None,
    store_id: int | None = None,
) -> List[Dict[str, Any]]:
    df = load_sales()
    df = _apply_scope(df, product_id, store_id)
    g = df.groupby("category")["sales"].sum().reset_index()
    total = int(g["sales"].sum())
    g = g.sort_values("sales", ascending=False)
    return [
        {
            "category": str(r.category),
            "sales": int(r.sales),
            "ratio": round(float(r.sales) / total, 4) if total else 0.0,
        }
        for r in g.itertuples()
    ]


def get_top_products(
    n: int = 10,
    product_id: int | None = None,
    store_id: int | None = None,
) -> List[Dict[str, Any]]:
    df = load_sales()
    df = _apply_scope(df, product_id, store_id)
    g = df.groupby(["product_id", "product_name", "category"])["sales"].sum().reset_index()
    g = g.sort_values("sales", ascending=False).head(n)
    return [
        {
            "product_id": int(r.product_id),
            "product_name": str(r.product_name),
            "category": str(r.category),
            "sales": int(r.sales),
        }
        for r in g.itertuples()
    ]
