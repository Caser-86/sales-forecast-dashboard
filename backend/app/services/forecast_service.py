"""预测服务

调用 ml/predictor.py 的预测器，缓存结果避免重复计算。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Any

from app.core.logging import get_logger

# 通过 sys.path 注入 ml 目录
import os
import sys

_ml_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml")
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from predictor import forecast as _forecast  # noqa: E402

logger = get_logger(__name__)


@lru_cache(maxsize=128)
def get_forecast(product_id: int, store_id: int) -> Dict[str, Any]:
    """获取 30 天预测结果（带缓存）。"""
    return _forecast(product_id, store_id)


def get_forecast_all(products: list[dict], stores: list[dict]) -> list[dict]:
    """获取所有商品×门店的预测，返回精简列表。"""
    results = []
    for p in products:
        pid = p["product_id"]
        for s in stores:
            sid = s["store_id"]
            try:
                f = get_forecast(pid, sid)
                results.append({
                    "product_id": pid,
                    "product_name": p["product_name"],
                    "category": p["category"],
                    "store_id": sid,
                    "store_name": s["store_name"],
                    "total_predicted": f["total_predicted"],
                    "suggested_purchase": f["suggested_purchase"],
                    "abc_class": f["abc_class"],
                    "forecast": f["forecast"],
                })
            except Exception as e:
                # 单个失败不影响整体，但记录日志便于排查
                logger.warning(
                    "预测失败 product_id=%s store_id=%s: %s", pid, sid, e,
                    exc_info=True,
                )
                results.append({
                    "product_id": pid,
                    "product_name": p["product_name"],
                    "category": p["category"],
                    "store_id": sid,
                    "store_name": s["store_name"],
                    "error": str(e),
                    "total_predicted": 0,
                    "suggested_purchase": 0,
                    "abc_class": "C",
                    "forecast": [],
                })
    return results
