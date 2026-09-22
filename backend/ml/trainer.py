"""模型训练脚本

流程：
1. 加载 features.csv
2. 按时间切分训练/验证/测试集（60/20/20）
3. 训练 LSTM 与 LightGBM
4. 用验证集选择策略，再用测试集做最终滚动评估
5. 保存模型与评估报告
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from app.core.config import settings
from sklearn.preprocessing import StandardScaler

from . import lightgbm_model as lgbm_wrapper
from .artifacts import publish_model_package
from .backtest import (
    combine_backtest_results,
    make_lightgbm_forecaster,
    make_lstm_forecaster,
    rolling_backtest,
    seasonal_naive_forecast,
    select_forecast_strategy,
)
from .feature_engineering import (
    FEATURE_COLS,
    LSTM_FEATURE_COLS,
    TARGET_COL,
    load_features,
)
from .future_features import CALENDAR_VERSION
from .lstm_model import SEQ_LEN, SalesLSTM, build_sequences
from .lstm_model import save_model as save_lstm
from .scaler_io import save_scaler

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = settings.DATA_PROCESSED_DIR
MODELS_DIR = settings.MODELS_DIR
LSTM_PATH = os.path.join(MODELS_DIR, "lstm_model.pth")
LGBM_PATH = os.path.join(MODELS_DIR, "lightgbm_model.txt")
SCALER_X_PATH = os.path.join(MODELS_DIR, "lstm_scaler_x.json")
SCALER_Y_PATH = os.path.join(MODELS_DIR, "lstm_scaler_y.json")
REPORT_PATH = str(settings.REPORT_JSON)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EPOCHS = 100
BATCH_SIZE = 64
LR = 1e-3
PATIENCE = 10


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true > 1e-6
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true, float) - np.asarray(y_pred, float)) ** 2)))


def _evaluate_seasonal_naive(
    df: pd.DataFrame,
    test_df: pd.DataFrame,
    lag_days: int = 7,
) -> dict:
    """用同商品同门店前一周同日销量作为无模型基线。"""
    if lag_days <= 0:
        raise ValueError("lag_days 必须大于 0")

    history = df.set_index(["store_id", "product_id", "date"])[TARGET_COL]
    y_true: list[float] = []
    y_pred: list[float] = []
    for row in test_df.itertuples():
        previous_date = pd.Timestamp(row.date) - pd.Timedelta(days=lag_days)
        key = (row.store_id, row.product_id, previous_date)
        if key not in history:
            continue
        y_true.append(float(getattr(row, TARGET_COL)))
        y_pred.append(float(history[key]))

    if not y_true:
        return {"mape": 0.0, "rmse": 0.0, "samples": 0}

    true_arr = np.asarray(y_true, dtype=float)
    pred_arr = np.asarray(y_pred, dtype=float)
    return {
        "mape": round(_mape(true_arr, pred_arr), 4),
        "rmse": round(_rmse(true_arr, pred_arr), 4),
        "samples": len(y_true),
    }


def _time_split(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """按日期时间切分 60/20/20，确保验证集和测试集可容纳30天回测。"""
    dates = np.sort(df["date"].unique())
    n = len(dates)
    if n < 5:
        raise ValueError("训练数据至少需要 5 个日期")
    train_cut = max(1, int(n * 0.60))
    validation_cut = max(train_cut + 1, int(n * 0.80))
    train_end = dates[train_cut - 1]
    val_end = dates[min(validation_cut - 1, n - 2)]
    train = df[df["date"] <= train_end]
    val = df[(df["date"] > train_end) & (df["date"] <= val_end)]
    test = df[df["date"] > val_end]
    return train, val, test


def _early_stopping_window(df: pd.DataFrame, ratio: float = 0.15) -> pd.DataFrame:
    """Use a tail inside the training corpus for early stopping, not selection."""
    dates = np.sort(df["date"].unique())
    holdout_days = max(1, int(len(dates) * ratio))
    start = dates[max(0, len(dates) - holdout_days)]
    return df[df["date"] >= start].copy()


def _backtest_origins(
    frame: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    horizon: int,
    limit: int = 3,
) -> list[pd.Timestamp]:
    """Return early origins whose complete horizon stays inside a split window."""
    if limit <= 0:
        raise ValueError("limit 必须大于 0")
    dates = sorted(pd.to_datetime(frame["date"]).drop_duplicates())
    candidates = [
        date for date in dates
        if pd.Timestamp(start) <= date <= pd.Timestamp(end)
        and date + pd.Timedelta(days=horizon) <= pd.Timestamp(end)
    ]
    if len(candidates) < limit:
        raise ValueError(
            f"时间窗口不足以生成 {limit} 个 {horizon} 天回测 origin，实际只有 {len(candidates)} 个"
        )
    return [pd.Timestamp(date) for date in candidates[:limit]]


# ---------------- LSTM 训练 ----------------

def _prepare_lstm_data(df: pd.DataFrame, scaler_x: StandardScaler,
                       scaler_y: StandardScaler) -> Tuple[np.ndarray, np.ndarray]:
    """把每个 (store, product) 序列切分成样本。"""
    X_all, y_all = [], []
    for (_sid, _pid), g in df.groupby(["store_id", "product_id"]):
        g = g.sort_values("date")
        feats = g[LSTM_FEATURE_COLS].values.astype(np.float32)
        targets = g[TARGET_COL].values.astype(np.float32).reshape(-1, 1)
        if len(feats) <= SEQ_LEN:
            continue
        feats_s = scaler_x.transform(feats)
        targets_s = scaler_y.transform(targets).ravel()
        X, y = build_sequences(feats_s, targets_s, SEQ_LEN)
        X_all.append(X)
        y_all.append(y)
    if not X_all:
        raise RuntimeError("LSTM 数据准备失败：没有可用序列")
    return np.concatenate(X_all), np.concatenate(y_all)


def train_lstm(train_df: pd.DataFrame, val_df: pd.DataFrame) -> Tuple[SalesLSTM, dict]:
    print("[trainer] 训练 LSTM 模型...")

    # 在训练集上拟合 scaler
    scaler_x = StandardScaler()
    scaler_y = StandardScaler()
    scaler_x.fit(train_df[LSTM_FEATURE_COLS].values.astype(np.float32))
    scaler_y.fit(train_df[TARGET_COL].values.astype(np.float32).reshape(-1, 1))

    X_train, y_train = _prepare_lstm_data(train_df, scaler_x, scaler_y)
    X_val, y_val = _prepare_lstm_data(val_df, scaler_x, scaler_y)

    input_dim = X_train.shape[2]
    model = SalesLSTM(input_dim=input_dim).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.MSELoss()

    X_tr = torch.tensor(X_train, dtype=torch.float32, device=DEVICE)
    y_tr = torch.tensor(y_train, dtype=torch.float32, device=DEVICE)
    X_v = torch.tensor(X_val, dtype=torch.float32, device=DEVICE)
    y_v = torch.tensor(y_val, dtype=torch.float32, device=DEVICE)

    best_val = float("inf")
    best_state = None
    no_improve = 0
    n = len(X_tr)

    for epoch in range(1, EPOCHS + 1):
        model.train()
        idx = torch.randperm(n, device=DEVICE)
        total = 0.0
        for s in range(0, n, BATCH_SIZE):
            b = idx[s:s + BATCH_SIZE]
            xb, yb = X_tr[b], y_tr[b]
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            total += loss.item() * len(b)
        train_loss = total / n

        model.eval()
        with torch.no_grad():
            v_pred = model(X_v)
            v_loss = loss_fn(v_pred, y_v).item()

        if v_loss < best_val - 1e-6:
            best_val = v_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1

        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch}/{EPOCHS}, train_loss={train_loss:.4f}, val_loss={v_loss:.4f}")

        if no_improve >= PATIENCE:
            print(f"  Early stopping at epoch {epoch} (val_loss 未改善 {PATIENCE} 轮)")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    # 保存 scaler
    os.makedirs(MODELS_DIR, exist_ok=True)
    save_scaler(scaler_x, SCALER_X_PATH)
    save_scaler(scaler_y, SCALER_Y_PATH)
    save_lstm(model, LSTM_PATH)
    print(f"  LSTM 模型已保存 → {LSTM_PATH}")
    return model, {"scaler_x": scaler_x, "scaler_y": scaler_y}


def eval_lstm(model: SalesLSTM, test_df: pd.DataFrame, scalers: dict) -> Tuple[pd.Series, dict]:
    """在测试集上预测，返回 (对齐到 test_df.index 的预测 Series, 指标)。"""
    scaler_x = scalers["scaler_x"]
    scaler_y = scalers["scaler_y"]
    model.eval()
    pred_series = pd.Series(np.nan, index=test_df.index, dtype=float)
    trues = []
    preds = []
    with torch.no_grad():
        for (_sid, _pid), g in test_df.groupby(["store_id", "product_id"]):
            g = g.sort_values("date")
            feats = g[LSTM_FEATURE_COLS].values.astype(np.float32)
            targets = g[TARGET_COL].values.astype(np.float32)
            if len(feats) <= SEQ_LEN:
                continue
            feats_s = scaler_x.transform(feats)
            X, _ = build_sequences(feats_s, np.zeros(len(feats_s)), SEQ_LEN)
            X_t = torch.tensor(X, dtype=torch.float32, device=DEVICE)
            pred_s = model(X_t).cpu().numpy().reshape(-1, 1)
            pred = scaler_y.inverse_transform(pred_s).ravel()
            pred = np.clip(pred, 0, None)
            # 对齐回 test_df 的原始索引（g 已排序，后 SEQ_LEN 个样本对应预测）
            aligned_idx = g.index[SEQ_LEN:]
            pred_series.loc[aligned_idx] = pred
            trues.extend(targets[SEQ_LEN:].tolist())
            preds.extend(pred.tolist())
    preds = np.array(preds, dtype=float)
    trues = np.array(trues, dtype=float)
    metrics = {"mape": _mape(trues, preds), "rmse": _rmse(trues, preds)}
    return pred_series, metrics


# ---------------- LightGBM 训练 ----------------

def train_lgbm(train_df: pd.DataFrame, val_df: pd.DataFrame) -> lgbm_wrapper:
    print("[trainer] 训练 LightGBM 模型...")
    X_tr = train_df[FEATURE_COLS].values
    y_tr = train_df[TARGET_COL].values.astype(float)
    X_v = val_df[FEATURE_COLS].values
    y_v = val_df[TARGET_COL].values.astype(float)
    model = lgbm_wrapper.train_lgbm(X_tr, y_tr, X_v, y_v)
    lgbm_wrapper.save_model(model, LGBM_PATH, FEATURE_COLS)
    print(f"  LightGBM 模型已保存 → {LGBM_PATH}")
    return model


def eval_lgbm(model, test_df: pd.DataFrame) -> Tuple[pd.Series, dict]:
    """返回对齐到 test_df.index 的预测 Series 与指标。"""
    X = test_df[FEATURE_COLS].values
    y = test_df[TARGET_COL].values.astype(float)
    pred = model.predict(X)
    pred = np.clip(pred, 0, None)
    metrics = {"mape": _mape(y, pred), "rmse": _rmse(y, pred)}
    return pd.Series(pred, index=test_df.index), metrics


def _active_dataset_version() -> str:
    """Read the active dataset ID without making training depend on imports."""
    try:
        from app.services.dataset_service import get_active_dataset_id

        return get_active_dataset_id()
    except Exception:
        return os.environ.get("DATASET_VERSION", "legacy")


# ---------------- 主流程 ----------------

def _rolling_protocol(result: dict) -> dict:
    """Expose the scope shared by every model in one rolling evaluation."""
    return {
        "horizon_days": int(result["horizon"]),
        "origins": list(result["origins"]),
        "origin_count": len(result["origins"]),
        "eligible_key_count": len(result["evaluated_keys"]),
        "min_history_days": SEQ_LEN,
    }


def _build_selection_candidates(lstm_result: dict, lgbm_result: dict) -> dict:
    """Build individual, baseline, and transparent fixed-weight candidates."""
    candidates = {
        "lstm": {
            "metrics": lstm_result["model"],
            "strategy": "lstm",
            "weights": {"lstm": 1.0, "lightgbm": 0.0},
        },
        "lightgbm": {
            "metrics": lgbm_result["model"],
            "strategy": "lightgbm",
            "weights": {"lstm": 0.0, "lightgbm": 1.0},
        },
        "seasonal_naive_7d": {
            "metrics": lgbm_result["baseline"],
            "strategy": "seasonal_naive_7d",
            "weights": {"lstm": 0.0, "lightgbm": 0.0},
        },
    }
    for lightgbm_weight in (0.2, 0.4, 0.6, 0.8):
        combined = combine_backtest_results(
            lstm_result,
            lgbm_result,
            left_weight=1.0 - lightgbm_weight,
            right_weight=lightgbm_weight,
        )
        name = f"ensemble_{int((1.0 - lightgbm_weight) * 100)}_{int(lightgbm_weight * 100)}"
        candidates[name] = {
            "metrics": combined["model"],
            "strategy": "ensemble",
            "weights": {"lstm": 1.0 - lightgbm_weight, "lightgbm": lightgbm_weight},
        }
    return candidates


def _select_test_result(selected: dict, lstm_result: dict, lgbm_result: dict) -> dict:
    """Return the final test result for the strategy selected on validation."""
    strategy = selected["strategy"]
    if strategy == "lstm":
        return lstm_result
    if strategy == "lightgbm":
        return lgbm_result
    if strategy == "seasonal_naive_7d":
        return {
            "origins": lgbm_result["origins"],
            "horizon": lgbm_result["horizon"],
            "evaluated_keys": lgbm_result["evaluated_keys"],
            "model": lgbm_result["baseline"],
        }
    return combine_backtest_results(
        lstm_result,
        lgbm_result,
        left_weight=float(selected["weights"]["lstm"]),
        right_weight=float(selected["weights"]["lightgbm"]),
    )


def train_all() -> dict:
    print("[1/6] 加载特征数据...")
    df = load_features()
    print(f"  数据形状: {df.shape}, 日期范围: {df['date'].min()} ~ {df['date'].max()}")

    train_df, val_df, test_df = _time_split(df)
    print(f"[2/6] 切分数据: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")

    backtest_columns = list(dict.fromkeys(
        ["date", "product_id", "store_id", "sales"] + FEATURE_COLS + LSTM_FEATURE_COLS
    ))
    backtest_frame = df[backtest_columns]

    # 先只用 train 训练候选模型，validation 只用于策略选择。
    early_stop_train = _early_stopping_window(train_df)
    print("[3/6] 训练验证候选模型...")
    selection_lstm, selection_scalers = train_lstm(train_df, early_stop_train)
    selection_lgbm = train_lgbm(train_df, early_stop_train)
    selection_origins = _backtest_origins(
        backtest_frame,
        start=train_df["date"].max(),
        end=val_df["date"].max(),
        horizon=settings.FORECAST_DAYS,
    )
    selection_lgbm_rolling = rolling_backtest(
        backtest_frame,
        make_lightgbm_forecaster(selection_lgbm),
        origins=selection_origins,
        horizon=settings.FORECAST_DAYS,
        min_history_days=SEQ_LEN,
        baseline_forecaster=seasonal_naive_forecast,
    )
    selection_lstm_rolling = rolling_backtest(
        backtest_frame,
        make_lstm_forecaster(
            selection_lstm,
            selection_scalers["scaler_x"],
            selection_scalers["scaler_y"],
            DEVICE,
        ),
        origins=selection_lgbm_rolling["origins"],
        horizon=settings.FORECAST_DAYS,
        min_history_days=SEQ_LEN,
        baseline_forecaster=seasonal_naive_forecast,
    )
    if selection_lgbm_rolling["evaluated_keys"] != selection_lstm_rolling["evaluated_keys"]:
        raise RuntimeError("LSTM 与 LightGBM 滚动回测评估 key 不一致")
    selection_candidates = _build_selection_candidates(
        selection_lstm_rolling,
        selection_lgbm_rolling,
    )
    selected = select_forecast_strategy(selection_candidates)
    selected["protocol"] = _rolling_protocol(selection_lgbm_rolling)
    print(
        f"  验证集选择 → {selected['strategy']} ({selected['candidate']}), "
        f"{selected['metric']}={selected['score']:.4f}"
    )

    # 策略确定后，用 train + validation 重训最终发布模型，test 只做一次最终评估。
    fit_df = pd.concat([train_df, val_df], ignore_index=True)
    print("[4/6] 使用 train + validation 重训发布模型...")
    final_lstm, scalers = train_lstm(fit_df, _early_stopping_window(fit_df))
    final_lgbm = train_lgbm(fit_df, _early_stopping_window(fit_df))
    lstm_preds, lstm_metrics = eval_lstm(final_lstm, test_df, scalers)
    lgbm_preds, lgbm_metrics = eval_lgbm(final_lgbm, test_df)
    baseline_metrics = _evaluate_seasonal_naive(df, test_df)
    align = pd.DataFrame({
        "lstm": lstm_preds,
        "lgbm": lgbm_preds,
        "y": test_df[TARGET_COL].values.astype(float),
    }, index=test_df.index).dropna(subset=["lstm", "lgbm"])
    ensemble_arr = (
        float(selected["weights"].get("lstm", 0.0)) * align["lstm"].values
        + float(selected["weights"].get("lightgbm", 0.0)) * align["lgbm"].values
    )
    ensemble_metrics = {
        "mape": _mape(align["y"].values, ensemble_arr)
        if selected["strategy"] == "ensemble" else 0.0,
        "rmse": _rmse(align["y"].values, ensemble_arr)
        if selected["strategy"] == "ensemble" else 0.0,
    }
    if selected["strategy"] == "lstm":
        ensemble_metrics = lstm_metrics
    elif selected["strategy"] == "lightgbm":
        ensemble_metrics = lgbm_metrics
    elif selected["strategy"] == "seasonal_naive_7d":
        ensemble_metrics = baseline_metrics

    test_origins = _backtest_origins(
        backtest_frame,
        start=val_df["date"].max(),
        end=test_df["date"].max(),
        horizon=settings.FORECAST_DAYS,
    )
    print("[5/6] 在未参与选择的 test 窗口执行最终滚动回测...")
    test_lgbm_rolling = rolling_backtest(
        backtest_frame,
        make_lightgbm_forecaster(final_lgbm),
        origins=test_origins,
        horizon=settings.FORECAST_DAYS,
        min_history_days=SEQ_LEN,
        baseline_forecaster=seasonal_naive_forecast,
    )
    test_lstm_rolling = rolling_backtest(
        backtest_frame,
        make_lstm_forecaster(final_lstm, scalers["scaler_x"], scalers["scaler_y"], DEVICE),
        origins=test_lgbm_rolling["origins"],
        horizon=settings.FORECAST_DAYS,
        min_history_days=SEQ_LEN,
        baseline_forecaster=seasonal_naive_forecast,
    )
    if test_lgbm_rolling["evaluated_keys"] != test_lstm_rolling["evaluated_keys"]:
        raise RuntimeError("最终 LSTM 与 LightGBM 滚动回测评估 key 不一致")
    selected_test = _select_test_result(selected, test_lstm_rolling, test_lgbm_rolling)
    rolling_report = {
        "protocol": _rolling_protocol(test_lgbm_rolling),
        "lstm": test_lstm_rolling["model"],
        "lightgbm": test_lgbm_rolling["model"],
        "seasonal_naive_7d": test_lgbm_rolling["baseline"],
        "selected": {
            "strategy": selected["strategy"],
            "candidate": selected["candidate"],
            "metrics": selected_test["model"],
        },
        "selection": {
            "protocol": selected["protocol"],
            "selected": selected,
            "candidates": {
                name: spec["metrics"] for name, spec in selection_candidates.items()
            },
        },
    }

    model_selection = {
        "strategy": selected["strategy"],
        "candidate": selected["candidate"],
        "weights": selected["weights"],
        "metric": selected["metric"],
        "validation_score": selected["score"],
        "validation_protocol": selected["protocol"],
    }

    report = {
        "metadata": {
            "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "horizon_days": settings.FORECAST_DAYS,
            "feature_count": len(FEATURE_COLS),
            "data": {
                "rows": int(len(df)),
                "date_start": str(df["date"].min().date()),
                "date_end": str(df["date"].max().date()),
            },
            "split": {
                "train_rows": int(len(train_df)),
                "validation_rows": int(len(val_df)),
                "test_rows": int(len(test_df)),
                "train_end": str(train_df["date"].max().date()),
                "validation_end": str(val_df["date"].max().date()),
            },
            "ensemble_weights": selected["weights"],
            "model_selection": model_selection,
            "rolling_backtest": rolling_report,
        },
        "seasonal_naive_7d": baseline_metrics,
        "lstm": lstm_metrics,
        "lightgbm": lgbm_metrics,
        "ensemble": ensemble_metrics,
    }
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    (Path(MODELS_DIR) / "evaluation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[6/6] 评估报告已保存 → {REPORT_PATH}")
    category_encoder_path = Path(MODELS_DIR) / "category_encoder.json"
    category_encoder_path.write_text(
        json.dumps(
            {
                "classes": sorted(df["category"].astype(str).unique().tolist()),
                "calendar_version": CALENDAR_VERSION,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (Path(MODELS_DIR) / "feature_schema.json").write_text(
        json.dumps(
            {
                "feature_cols": FEATURE_COLS,
                "lstm_feature_cols": LSTM_FEATURE_COLS,
                "target_col": TARGET_COL,
                "calendar_version": CALENDAR_VERSION,
                "horizon_days": settings.FORECAST_DAYS,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (Path(MODELS_DIR) / "model_selection.json").write_text(
        json.dumps(model_selection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    data_version = _active_dataset_version()
    package = publish_model_package(
        Path(MODELS_DIR),
        data_version=data_version,
        activate=True,
    )
    report["metadata"]["model_id"] = package["model_id"]
    report["metadata"]["data_version"] = data_version
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  模型版本已发布并激活 → {package['model_id']}")
    print("训练完成。")
    return report

if __name__ == "__main__":
    train_all()
