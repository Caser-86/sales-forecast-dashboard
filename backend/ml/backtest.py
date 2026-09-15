"""Leakage-safe rolling backtest primitives for fixed forecast horizons."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd
import torch

try:
    from .feature_engineering import FEATURE_COLS, LSTM_FEATURE_COLS
    from .future_features import build_future_feature_row
except ImportError:  # Support the existing scripts that import ml modules as top-level modules.
    from feature_engineering import FEATURE_COLS, LSTM_FEATURE_COLS
    from future_features import build_future_feature_row

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


def _basic_metric_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "samples": 0,
            "mape_samples": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "wape": 0.0,
            "mape": None,
            "per_horizon": {},
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
    }


def _metric_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return overall, per-horizon, and product/store segment metrics."""
    if not records:
        return {**_basic_metric_summary(records), "keys": [], "segments": {}}
    by_segment: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        segment = row["key"].split(":", 1)[1]
        by_segment.setdefault(segment, []).append(row)
    return {
        **_basic_metric_summary(records),
        "keys": sorted({row["key"] for row in records}),
        "segments": {
            segment: _basic_metric_summary(segment_records)
            for segment, segment_records in sorted(by_segment.items())
        },
    }


def _prediction_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep actuals with predictions so compatible result sets can be combined."""
    return [
        {key: row[key] for key in ("key", "origin", "step", "actual", "predicted")}
        for row in records
    ]


def combine_backtest_results(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    left_weight: float,
    right_weight: float,
) -> dict[str, Any]:
    """Combine two aligned rolling results without changing their evaluation scope."""
    if left_weight < 0 or right_weight < 0 or abs(left_weight + right_weight - 1.0) > 1e-6:
        raise ValueError("回测组合权重必须非负且总和为 1")
    for field in ("origins", "horizon", "evaluated_keys"):
        if left.get(field) != right.get(field):
            raise ValueError(f"回测结果的 {field} 不一致，不能组合")

    left_rows = {
        (row["key"], int(row["step"])): row
        for row in left.get("predictions", [])
    }
    right_rows = {
        (row["key"], int(row["step"])): row
        for row in right.get("predictions", [])
    }
    if set(left_rows) != set(right_rows):
        raise ValueError("回测预测 key 不一致，不能组合")

    records: list[dict[str, Any]] = []
    for key in sorted(left_rows):
        left_row = left_rows[key]
        right_row = right_rows[key]
        if left_row["actual"] != right_row["actual"]:
            raise ValueError("回测真实值不一致，不能组合")
        records.append({
            "key": left_row["key"],
            "origin": left_row["origin"],
            "step": int(left_row["step"]),
            "actual": float(left_row["actual"]),
            "predicted": left_weight * float(left_row["predicted"])
            + right_weight * float(right_row["predicted"]),
        })

    return {
        "origins": list(left["origins"]),
        "horizon": int(left["horizon"]),
        "evaluated_keys": list(left["evaluated_keys"]),
        "predictions": _prediction_records(records),
        "model": _metric_summary(records),
    }


def select_forecast_strategy(
    candidates: Mapping[str, Mapping[str, Any]],
    *,
    metric: str = "wape",
) -> dict[str, Any]:
    """Choose the lowest-error candidate using validation metrics only."""
    ranked: list[tuple[float, float, str, Mapping[str, Any]]] = []
    for candidate_name, spec in candidates.items():
        metrics = spec.get("metrics", spec)
        score = metrics.get(metric)
        samples = metrics.get("samples", 0)
        rmse = metrics.get("rmse")
        if not isinstance(score, (int, float)) or not np.isfinite(score):
            continue
        if not isinstance(rmse, (int, float)) or not np.isfinite(rmse):
            continue
        if not isinstance(samples, (int, float)) or samples <= 0:
            continue
        ranked.append((float(score), float(rmse), str(candidate_name), spec))
    if not ranked:
        raise ValueError("没有可用于模型选择的有效回测候选")

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    score, _rmse, candidate_name, selected_spec = ranked[0]
    return {
        "candidate": candidate_name,
        "strategy": str(selected_spec.get("strategy", candidate_name)),
        "weights": {
            str(key): float(value)
            for key, value in selected_spec.get("weights", {}).items()
        },
        "metric": metric,
        "score": score,
        "ranking": [
            {
                "candidate": name,
                "score": candidate_score,
                "rmse": candidate_rmse,
                "samples": int(spec.get("metrics", spec).get("samples", 0)),
            }
            for candidate_score, candidate_rmse, name, spec in ranked
        ],
    }


def make_lightgbm_forecaster(model: Any, feature_cols: Sequence[str] = FEATURE_COLS) -> Forecaster:
    """Adapt a trained LightGBM model to the leakage-safe rolling protocol."""

    def forecaster(history: pd.DataFrame, horizon: int) -> list[float]:
        if history.empty:
            raise ValueError("history 不能为空")
        sales_history = history["sales"].astype(float).tolist()
        last = history.iloc[-1]
        price = float(history["price"].iloc[-1]) if "price" in history else 0.0
        competitor = (
            float(history["competitor_price"].iloc[-1])
            if "competitor_price" in history else price
        )
        category_enc = int(last["category_enc"]) if "category_enc" in history else 0
        product_id = int(last["product_id"])
        store_id = int(last["store_id"])
        last_date = pd.Timestamp(last["date"]).date()
        predictions: list[float] = []
        for step in range(horizon):
            future_date = last_date + pd.Timedelta(days=step + 1)
            row = build_future_feature_row(
                forecast_date=future_date,
                sales_history=sales_history,
                price=price,
                competitor_price=competitor,
                category_enc=category_enc,
            )
            model_row = {"product_id": product_id, "store_id": store_id, **row}
            prediction = max(
                0.0,
                float(model.predict(np.asarray([[model_row[col] for col in feature_cols]]))[0]),
            )
            predictions.append(prediction)
            sales_history.append(prediction)
        return predictions

    return forecaster


def make_lstm_forecaster(model: Any, scaler_x: Any, scaler_y: Any, device: str | torch.device = "cpu") -> Forecaster:
    """Adapt a trained LSTM to the same recursive, origin-only protocol."""

    def forecaster(history: pd.DataFrame, horizon: int) -> list[float]:
        if len(history) < 14:
            raise ValueError("history 不足 14 天")
        recent = history.sort_values("date").tail(14)
        sequence = scaler_x.transform(recent[LSTM_FEATURE_COLS].values.astype(np.float32))
        sales_history = history.sort_values("date")["sales"].astype(float).tolist()
        price = float(recent["price"].iloc[-1]) if "price" in recent else 0.0
        competitor = (
            float(recent["competitor_price"].iloc[-1])
            if "competitor_price" in recent else price
        )
        category_enc = int(recent["category_enc"].iloc[-1]) if "category_enc" in recent else 0
        last_date = pd.Timestamp(recent["date"].iloc[-1]).date()
        predictions: list[float] = []
        model.eval()
        with torch.no_grad():
            for step in range(horizon):
                input_tensor = torch.tensor(sequence[None], dtype=torch.float32, device=device)
                prediction = max(0.0, float(scaler_y.inverse_transform(
                    model(input_tensor).detach().cpu().numpy().reshape(-1, 1)
                )[0, 0]))
                predictions.append(prediction)
                sales_history.append(prediction)
                future_row = build_future_feature_row(
                    forecast_date=last_date + pd.Timedelta(days=step + 1),
                    sales_history=sales_history,
                    price=price,
                    competitor_price=competitor,
                    category_enc=category_enc,
                    predicted_sales=prediction,
                )
                next_row = np.asarray([[future_row[column] for column in LSTM_FEATURE_COLS]], dtype=np.float32)
                sequence = np.vstack([sequence[1:], scaler_x.transform(next_row)])
        return predictions

    return forecaster


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

    return {
        "origins": [origin.date().isoformat() for origin in normalized_origins],
        "horizon": horizon,
        "evaluated_keys": sorted(set(evaluated_keys)),
        "predictions": _prediction_records(model_records),
        "model": _metric_summary(model_records),
        "baseline": _metric_summary(baseline_records),
    }
