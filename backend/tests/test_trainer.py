"""训练评估辅助函数测试。"""
from __future__ import annotations

import pandas as pd


def test_seasonal_naive_uses_same_store_product_from_previous_week():
    from ml.trainer import _evaluate_seasonal_naive

    df = pd.DataFrame(
        [
            {"date": "2025-01-01", "store_id": 1, "product_id": 1, "sales": 100},
            {"date": "2025-01-08", "store_id": 1, "product_id": 1, "sales": 120},
            {"date": "2025-01-09", "store_id": 1, "product_id": 1, "sales": 130},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    test_df = df.iloc[1:]

    result = _evaluate_seasonal_naive(df, test_df, lag_days=7)

    assert result["samples"] == 1
    assert result["mape"] == 16.6667
    assert result["rmse"] == 20.0

