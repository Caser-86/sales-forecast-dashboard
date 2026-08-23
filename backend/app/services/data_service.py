"""数据查询服务

从 CSV 加载历史销量数据，提供查询接口。
使用模块级缓存避免重复 IO。
"""
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Any, Dict, List

import pandas as pd

from app.config import REPORT_JSON, SALES_CSV
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


def get_total_sales_last_n(days: int = 30) -> int:
    df = load_sales()
    last_date = df["date"].max()
    start = last_date - timedelta(days=days - 1)
    return int(df[df["date"] >= start]["sales"].sum())


@lru_cache(maxsize=4)
def get_recent_product_demand(days: int = 30) -> Dict[int, float]:
    """返回最近 N 天按商品汇总的需求量，用于商品级 ABC 分级。"""
    if days <= 0:
        raise ValueError("days 必须大于 0")
    df = load_sales()
    last_date = df["date"].max()
    start = last_date - timedelta(days=days - 1)
    recent = df[df["date"] >= start]
    grouped = recent.groupby("product_id")["sales"].sum()
    return {int(product_id): float(total) for product_id, total in grouped.items()}


def get_category_sales() -> List[Dict[str, Any]]:
    df = load_sales()
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


def get_top_products(n: int = 10) -> List[Dict[str, Any]]:
    df = load_sales()
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
