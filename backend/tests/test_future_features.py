"""未来时序特征测试。"""
from __future__ import annotations

from datetime import date, timedelta


def test_future_row_updates_calendar_and_lag_features():
    from ml.future_features import build_future_feature_row

    row = build_future_feature_row(
        forecast_date=date(2025, 7, 5),
        sales_history=list(range(1, 15)),
        price=10.0,
        competitor_price=9.0,
        category_enc=2,
    )

    assert row["is_weekend"] == 1
    assert row["is_holiday"] == 0
    assert row["sales_lag_1"] == 14
    assert row["sales_lag_7"] == 8
    assert row["sales_lag_14"] == 1
    assert row["sales_rolling_7"] == 11
    assert row["sales_rolling_30"] == 7.5
    assert row["price_diff"] == 0.0


def test_next_future_row_uses_the_previous_prediction_not_future_truth():
    from ml.future_features import build_future_feature_row

    history = list(range(1, 15))
    first_date = date(2025, 7, 1)
    first = build_future_feature_row(
        forecast_date=first_date,
        sales_history=history,
        price=10.0,
        competitor_price=9.0,
        category_enc=2,
        predicted_sales=20.0,
    )
    history.append(first["sales"])
    second = build_future_feature_row(
        forecast_date=first_date + timedelta(days=1),
        sales_history=history,
        price=10.0,
        competitor_price=9.0,
        category_enc=2,
    )

    assert first["sales"] == 20.0
    assert second["sales_lag_1"] == 20.0
    assert second["sales_rolling_7"] == sum([9, 10, 11, 12, 13, 14, 20]) / 7
