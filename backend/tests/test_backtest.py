"""滚动回测契约测试。"""
from __future__ import annotations

import pandas as pd


def _sales_frame(scale: float = 1.0) -> pd.DataFrame:
    rows = []
    for day in pd.date_range("2025-01-01", periods=24, freq="D"):
        rows.append(
            {
                "date": day,
                "product_id": 1,
                "store_id": 1,
                "sales": float(day.day * scale),
            }
        )
    return pd.DataFrame(rows)


def test_rolling_backtest_forecaster_only_receives_origin_history():
    from ml.backtest import rolling_backtest

    seen = []

    def forecaster(history, horizon):
        seen.append(history["date"].max())
        return [float(history["sales"].iloc[-1])] * horizon

    result = rolling_backtest(
        _sales_frame(),
        forecaster,
        origins=[pd.Timestamp("2025-01-15")],
        horizon=3,
        min_history_days=14,
    )

    assert result["origins"] == ["2025-01-15"]
    assert seen == [pd.Timestamp("2025-01-15")]
    assert result["model"]["samples"] == result["baseline"]["samples"] == 3


def test_rolling_backtest_predictions_do_not_change_when_future_truth_changes():
    from ml.backtest import rolling_backtest

    def forecaster(history, horizon):
        return [float(history["sales"].iloc[-1])] * horizon

    kwargs = {
        "origins": [pd.Timestamp("2025-01-15")],
        "horizon": 3,
        "min_history_days": 14,
    }
    first = rolling_backtest(_sales_frame(1.0), forecaster, **kwargs)
    changed = _sales_frame(1.0)
    changed.loc[changed["date"] > pd.Timestamp("2025-01-15"), "sales"] = 9999
    second = rolling_backtest(changed, forecaster, **kwargs)

    assert first["predictions"] == second["predictions"]
    assert first["model"]["keys"] == second["model"]["keys"]
    assert first["model"]["mae"] != second["model"]["mae"]


def test_seasonal_naive_repeats_last_observed_week_without_future_truth():
    from ml.backtest import seasonal_naive_forecast

    history = pd.DataFrame({"sales": [10, 20, 30, 40, 50, 60, 70]})

    assert seasonal_naive_forecast(history, horizon=10, lag_days=7) == [
        10, 20, 30, 40, 50, 60, 70, 10, 20, 30
    ]
