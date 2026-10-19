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
    assert result["model"]["keys"] == result["baseline"]["keys"]


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

    assert [row["predicted"] for row in first["predictions"]] == [
        row["predicted"] for row in second["predictions"]
    ]
    assert first["model"]["keys"] == second["model"]["keys"]
    assert first["model"]["mae"] != second["model"]["mae"]


def test_seasonal_naive_repeats_last_observed_week_without_future_truth():
    from ml.backtest import seasonal_naive_forecast

    history = pd.DataFrame({"sales": [10, 20, 30, 40, 50, 60, 70]})

    assert seasonal_naive_forecast(history, horizon=10, lag_days=7) == [
        10, 20, 30, 40, 50, 60, 70, 10, 20, 30
    ]


def test_rolling_backtest_reports_segment_and_per_horizon_metrics():
    from ml.backtest import rolling_backtest

    result = rolling_backtest(
        _sales_frame(1.0),
        lambda history, horizon: [history["sales"].iloc[-1]] * horizon,
        origins=[pd.Timestamp("2025-01-15")],
        horizon=3,
        min_history_days=14,
    )

    assert result["model"]["per_horizon"]["1"]["samples"] == 1
    assert "1:1" in result["model"]["segments"]


def test_combine_backtest_results_preserves_protocol_and_metrics():
    from ml.backtest import combine_backtest_results, rolling_backtest

    kwargs = {
        "origins": [pd.Timestamp("2025-01-15")],
        "horizon": 3,
        "min_history_days": 14,
    }
    left = rolling_backtest(
        _sales_frame(),
        lambda history, horizon: [float(history["sales"].iloc[-1])] * horizon,
        **kwargs,
    )
    right = rolling_backtest(
        _sales_frame(),
        lambda history, horizon: [float(history["sales"].iloc[-1] + 2)] * horizon,
        **kwargs,
    )

    combined = combine_backtest_results(left, right, left_weight=0.25, right_weight=0.75)

    assert combined["origins"] == left["origins"]
    assert combined["evaluated_keys"] == left["evaluated_keys"] == right["evaluated_keys"]
    assert combined["model"]["samples"] == 3
    assert combined["predictions"][0]["predicted"] == left["predictions"][0]["predicted"] + 1.5


def test_select_forecast_strategy_can_choose_a_baseline():
    from ml.backtest import select_forecast_strategy

    selected = select_forecast_strategy(
        {
            "lstm": {
                "metrics": {"wape": 0.42, "rmse": 4.0, "samples": 90},
                "strategy": "lstm",
                "weights": {"lstm": 1.0, "lightgbm": 0.0},
            },
            "lightgbm": {
                "metrics": {"wape": 0.35, "rmse": 3.0, "samples": 90},
                "strategy": "lightgbm",
                "weights": {"lstm": 0.0, "lightgbm": 1.0},
            },
            "seasonal_naive_7d": {
                "metrics": {"wape": 0.20, "rmse": 7.0, "samples": 90},
                "strategy": "seasonal_naive_7d",
                "weights": {"lstm": 0.0, "lightgbm": 0.0},
            },
        }
    )

    assert selected["candidate"] == "seasonal_naive_7d"
    assert selected["strategy"] == "seasonal_naive_7d"
    assert selected["metric"] == "wape"
