"""Shared feature construction for recursive future predictions."""
from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from datetime import date
from math import nan
from typing import Any

CALENDAR_VERSION = "cn-2025-v1"
DEFAULT_HOLIDAYS = frozenset(
    {
        date(2025, 1, 1),
        date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
        date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2), date(2025, 2, 3),
        date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 6),
        date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3),
        date(2025, 6, 1), date(2025, 6, 14), date(2025, 6, 15),
        date(2025, 9, 30), date(2025, 10, 1), date(2025, 10, 2),
        date(2025, 10, 3), date(2025, 10, 4), date(2025, 10, 5),
        date(2025, 10, 6), date(2025, 10, 7),
    }
)


def build_future_feature_row(
    *,
    forecast_date: date,
    sales_history: Sequence[float],
    price: float,
    competitor_price: float,
    category_enc: int,
    predicted_sales: float | None = None,
    promotion_policy: Callable[[date], int] | None = None,
    holidays: Collection[date] = DEFAULT_HOLIDAYS,
) -> dict[str, Any]:
    """Build one future row using only history available before ``forecast_date``.

    Future price and competitor price are held constant at the latest observed
    values, price change is therefore zero, and promotion defaults to off.
    ``sales_history`` may contain only observed values plus earlier predictions.
    """
    if not sales_history:
        raise ValueError("sales_history 不能为空")

    history = [float(value) for value in sales_history]
    promotion = promotion_policy(forecast_date) if promotion_policy else 0
    return {
        "sales": float(predicted_sales) if predicted_sales is not None else nan,
        "price": float(price),
        "competitor_price": float(competitor_price),
        "price_diff": 0.0,
        "is_weekend": int(forecast_date.weekday() >= 5),
        "is_holiday": int(forecast_date in holidays),
        "is_promotion": int(promotion),
        "sales_lag_1": history[-1],
        "sales_lag_7": history[-7] if len(history) >= 7 else history[-1],
        "sales_lag_14": history[-14] if len(history) >= 14 else history[-1],
        "sales_rolling_7": sum(history[-7:]) / min(len(history), 7),
        "sales_rolling_30": sum(history[-30:]) / min(len(history), 30),
        "day_of_week": forecast_date.weekday(),
        "month": forecast_date.month,
        "day_of_month": forecast_date.day,
        "category_enc": int(category_enc),
    }
