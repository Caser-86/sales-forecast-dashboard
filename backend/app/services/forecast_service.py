"""预测服务

调用 ml/predictor.py 的预测器，缓存结果避免重复计算。
"""
from __future__ import annotations

# 通过 sys.path 注入 ml 目录
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any, Dict

from app.core.config import settings
from app.core.logging import get_logger
from app.services.dataset_service import get_active_dataset_id

_ml_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml")
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from artifacts import get_active_model_id  # noqa: E402
from predictor import ForecastPredictor  # noqa: E402
from predictor import forecast as _forecast  # noqa: E402

logger = get_logger(__name__)


@lru_cache(maxsize=128)
def _get_forecast_cached(
    product_id: int,
    store_id: int,
    model_version: str,
    data_version: str,
) -> Dict[str, Any]:
    """Cache predictions with the model and dataset versions in the key."""
    return _forecast(product_id, store_id)


def get_forecast(product_id: int, store_id: int) -> Dict[str, Any]:
    """获取 30 天预测结果（带模型与数据版本缓存）。"""
    model_version = get_active_model_id()
    data_version = get_active_dataset_id()
    loaded = ForecastPredictor._instance
    if loaded is not None and (
        loaded.model_version != model_version or loaded.data_version != data_version
    ):
        ForecastPredictor.reset()
    return _get_forecast_cached(product_id, store_id, model_version, data_version)


def clear_forecast_cache() -> None:
    """Clear cached predictions after an explicit data/model activation."""
    _get_forecast_cached.cache_clear()
    ForecastPredictor.reset()


def summarize_forecasts(results: list[dict]) -> Dict[str, int | str]:
    """Summarize successful and failed combinations without treating failures as zero."""
    requested = len(results)
    failed = sum(1 for item in results if "error" in item)
    succeeded = requested - failed
    status = "ok" if failed == 0 else ("partial" if succeeded else "unavailable")
    return {
        "status": status,
        "requested": requested,
        "succeeded": succeeded,
        "failed": failed,
    }


def get_forecast_all(products: list[dict], stores: list[dict]) -> list[dict]:
    """获取所有商品×门店的预测，返回稳定顺序的精简列表。

    预测模型加载和推理是批量接口的主要耗时来源，因此使用受控线程池；
    结果仍按商品、门店输入顺序返回，避免前端因 future 完成顺序而抖动。
    """
    items = [(p, s) for p in products for s in stores]
    if not items:
        return []

    results: dict[tuple[int, int], dict[str, Any]] = {}
    max_workers = min(settings.FORECAST_WORKERS, len(items))
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="forecast") as executor:
        future_to_item = {
            executor.submit(get_forecast, p["product_id"], s["store_id"]): (p, s)
            for p, s in items
        }
        for future in as_completed(future_to_item):
            p, s = future_to_item[future]
            pid = p["product_id"]
            sid = s["store_id"]
            try:
                f = future.result()
                results[(pid, sid)] = {
                    "product_id": pid,
                    "product_name": p["product_name"],
                    "category": p["category"],
                    "store_id": sid,
                    "store_name": s["store_name"],
                    "total_predicted": f["total_predicted"],
                    "suggested_purchase": f["suggested_purchase"],
                    "abc_class": f["abc_class"],
                    "forecast": f["forecast"],
                }
            except Exception as e:
                # 单个失败不影响整体，但记录日志便于排查。
                logger.warning(
                    "预测失败 product_id=%s store_id=%s: %s", pid, sid, e,
                    exc_info=True,
                )
                results[(pid, sid)] = {
                    "product_id": pid,
                    "product_name": p["product_name"],
                    "category": p["category"],
                    "store_id": sid,
                    "store_name": s["store_name"],
                    "error": str(e),
                }

    return [results[(p["product_id"], s["store_id"])] for p, s in items]
