"""训练评估辅助函数测试。"""
from __future__ import annotations

import numpy as np
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


def test_time_split_reserves_separate_validation_and_test_windows():
    from ml.trainer import _time_split

    rows = []
    for day in pd.date_range("2025-01-01", periods=150, freq="D"):
        rows.append({"date": day, "store_id": 1, "product_id": 1, "sales": 10.0})
    frame = pd.DataFrame(rows)

    train, validation, test = _time_split(frame)

    assert train["date"].nunique() == 90
    assert validation["date"].nunique() == 30
    assert test["date"].nunique() == 30
    assert train["date"].max() < validation["date"].min()
    assert validation["date"].max() < test["date"].min()


def test_lightgbm_training_supports_current_sklearn_check_x_y_signature():
    from ml.lightgbm_model import train_lgbm

    features = np.arange(40, dtype=float).reshape(20, 2)
    target = features[:, 0] * 0.5 + features[:, 1]

    model = train_lgbm(
        features[:14],
        target[:14],
        features[14:],
        target[14:],
        params={"n_estimators": 5, "early_stopping_rounds": 2},
    )

    predictions = model.predict(features[14:])
    assert len(predictions) == 6
