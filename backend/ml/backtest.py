"""Leakage-safe rolling backtest primitives for fixed forecast horizons."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pandas as pd

Forecaster = Callable[[pd.DataFrame, int], Sequence[float]]
REQUIRED_COLUMNS = {"date", "product_id", "store_id", "sales"}


def seasonal_naive_forecast(history: pd.DataFrame, horizon: int, lag_days: int = 7) -> list[float]:
    """Repeat the latest observed seasonal cycle without reading future rows."""
    if horizon <= 0:
        raise ValueError("horizon 必须大于 0")
    if lag_days <= 0:
        raise ValueError("lag_days 必须大于 0")
    values = history["sales"].astype(float).tolist()
    if not values:
        raise ValueError("history 不能为空")
    cycle = values[-lag_days:] if len(values) >= lag_days else [values[-1]]
    return [float(cycle[index % len(cycle)]) for index in range(horizon)]


def _metric_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "samples": 0,
            "mape_samples": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "wape": 0.0,
            "mape": None,
            "per_horizon": {},
            "keys": [],
        }

    actual = np.asarray([row["actual"] for row in records], dtype=float)
    predicted = np.asarray([row["predicted"] for row in records], dtype=float)
    error = predicted - actual
    positive = actual > 1e-6
    per_horizon: dict[str, dict[str, float | int | None]] = {}
    for step in sorted({int(row["step"]) for row in records}):
        step_records = [row for row in records if row["step"] == step]
        step_actual = np.asarray([row["actual"] for row in step_records], dtype=float)
        step_pred = np.asarray([row["predicted"] for row in step_records], dtype=float)
        step_error = step_pred - step_actual
        step_positive = step_actual > 1e-6
        per_horizon[str(step)] = {
            "samples": len(step_records),
            "mae": float(np.mean(np.abs(step_error))),
            "rmse": float(np.sqrt(np.mean(step_error ** 2))),
            "wape": float(np.sum(np.abs(step_error)) / np.sum(np.abs(step_actual)))
            if np.sum(np.abs(step_actual)) > 1e-6 else 0.0,
            "mape": float(np.mean(np.abs(step_error[step_positive] / step_actual[step_positive])) * 100)
            if step_positive.any() else None,
        }
    keys = sorted({row["key"] for row in records})
    return {
        "samples": len(records),
        "mape_samples": int(positive.sum()),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "wape": float(np.sum(np.abs(error)) / np.sum(np.abs(actual)))
        if np.sum(np.abs(actual)) > 1e-6 else 0.0,
        "mape": float(np.mean(np.abs(error[positive] / actual[positive])) * 100)
        if positive.any() else None,
        "per_horizon": per_horizon,
        "keys": keys,
    }


def rolling_backtest(
    frame: pd.DataFrame,
    forecaster: Forecaster,
    *,
    origins: Sequence[pd.Timestamp] | None = None,
    horizon: int = 30,
    min_history_days: int = 14,
    baseline_forecaster: Forecaster | None = None,
) -> dict[str, Any]:
    """Evaluate model and baseline on exactly the same origin/key/horizon set."""
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"回测数据缺少列: {', '.join(sorted(missing))}")
    if horizon <= 0 or min_history_days <= 0:
        raise ValueError("horizon 和 min_history_days 必须大于 0")

    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["product_id", "store_id", "date"])
    max_date = df["date"].max()
    if origins is None:
        eligible_dates = sorted(
            date for date in df["date"].drop_duplicates()
            if date + pd.Timedelta(days=horizon) <= max_date
        )
        origins = eligible_dates[-3:]
    normalized_origins = sorted(pd.Timestamp(origin) for origin in origins)
    baseline_forecaster = baseline_forecaster or seasonal_naive_forecast
    model_records: list[dict[str, Any]] = []
    baseline_records: list[dict[str, Any]] = []
    evaluated_keys: list[str] = []

    for origin in normalized_origins:
        for (product_id, store_id), group in df.groupby(["product_id", "store_id"]):
            history = group[group["date"] <= origin].copy().sort_values("date")
            future = group[
                (group["date"] > origin)
                & (group["date"] <= origin + pd.Timedelta(days=horizon))
            ].copy().sort_values("date")
            expected_dates = pd.date_range(origin + pd.Timedelta(days=1), periods=horizon, freq="D")
            if len(history) < min_history_days or not future["date"].equals(pd.Series(expected_dates, index=future.index)):
                continue

            key = f"{origin.date().isoformat()}:{int(product_id)}:{int(store_id)}"
            model_prediction = [float(value) for value in forecaster(history.copy(), horizon)]
            baseline_prediction = [float(value) for value in baseline_forecaster(history.copy(), horizon)]
            if len(model_prediction) != horizon or len(baseline_prediction) != horizon:
                raise ValueError(f"回测预测长度必须等于 horizon: {key}")
            actual = future["sales"].astype(float).tolist()
            evaluated_keys.append(key)
            for step, (truth, prediction, baseline) in enumerate(
                zip(actual, model_prediction, baseline_prediction, strict=True), start=1
            ):
                base = {"key": key, "origin": origin.date().isoformat(), "step": step, "actual": truth}
                model_records.append({**base, "predicted": prediction})
                baseline_records.append({**base, "predicted": baseline})

    def predictions_only(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {key: row[key] for key in ("key", "origin", "step", "predicted")}
            for row in records
        ]

    return {
        "origins": [origin.date().isoformat() for origin in normalized_origins],
        "horizon": horizon,
        "evaluated_keys": sorted(set(evaluated_keys)),
        "predictions": predictions_only(model_records),
        "model": _metric_summary(model_records),
        "baseline": _metric_summary(baseline_records),
    }
