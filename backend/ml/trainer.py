"""模型训练脚本

流程：
1. 加载 features.csv
2. 按时间切分训练/验证/测试集（70/15/15）
3. 训练 LSTM 与 LightGBM
4. 评估 MAPE、RMSE，集成评估
5. 保存模型与评估报告
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import joblib
import lightgbm_model as lgbm_wrapper
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from artifacts import publish_model_package
from feature_engineering import (
    FEATURE_COLS,
    LSTM_FEATURE_COLS,
    TARGET_COL,
    load_features,
)
from lstm_model import SEQ_LEN, SalesLSTM, build_sequences
from lstm_model import save_model as save_lstm
from sklearn.preprocessing import StandardScaler

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BACKEND_DIR, "data", "processed")
MODELS_DIR = os.path.join(BACKEND_DIR, "ml", "saved_models")
LSTM_PATH = os.path.join(MODELS_DIR, "lstm_model.pth")
LGBM_PATH = os.path.join(MODELS_DIR, "lightgbm_model.txt")
SCALER_X_PATH = os.path.join(MODELS_DIR, "lstm_scaler_x.joblib")
SCALER_Y_PATH = os.path.join(MODELS_DIR, "lstm_scaler_y.joblib")
REPORT_PATH = os.path.join(PROCESSED_DIR, "evaluation_report.json")

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
    """按日期时间切分 70/15/15。"""
    dates = np.sort(df["date"].unique())
    n = len(dates)
    train_end = dates[int(n * 0.70)]
    val_end = dates[int(n * 0.85)]
    train = df[df["date"] <= train_end]
    val = df[(df["date"] > train_end) & (df["date"] <= val_end)]
    test = df[df["date"] > val_end]
    return train, val, test


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
    joblib.dump(scaler_x, SCALER_X_PATH)
    joblib.dump(scaler_y, SCALER_Y_PATH)
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

def train_all() -> dict:
    print("[1/4] 加载特征数据...")
    df = load_features()
    print(f"  数据形状: {df.shape}, 日期范围: {df['date'].min()} ~ {df['date'].max()}")

    train_df, val_df, test_df = _time_split(df)
    print(f"[2/4] 切分数据: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")

    # 训练 LSTM
    lstm_model, scalers = train_lstm(train_df, val_df)
    lstm_preds, lstm_metrics = eval_lstm(lstm_model, test_df, scalers)
    print(f"  LSTM  → MAPE={lstm_metrics['mape']:.2f}%, RMSE={lstm_metrics['rmse']:.2f}")

    # 训练 LightGBM
    lgbm_model = train_lgbm(train_df, val_df)
    lgbm_preds, lgbm_metrics = eval_lgbm(lgbm_model, test_df)
    print(f"  LGBM  → MAPE={lgbm_metrics['mape']:.2f}%, RMSE={lgbm_metrics['rmse']:.2f}")

    # 集成（对齐到同一行：LSTM 只能在有 14 天历史的样本上预测）
    align = pd.DataFrame({
        "lstm": lstm_preds,
        "lgbm": lgbm_preds,
        "y": test_df[TARGET_COL].values.astype(float),
    }, index=test_df.index)
    align = align.dropna(subset=["lstm", "lgbm"])
    ensemble_arr = 0.4 * align["lstm"].values + 0.6 * align["lgbm"].values
    ensemble_metrics = {
        "mape": _mape(align["y"].values, ensemble_arr),
        "rmse": _rmse(align["y"].values, ensemble_arr),
    }
    print(f"  集成  → MAPE={ensemble_metrics['mape']:.2f}%, RMSE={ensemble_metrics['rmse']:.2f} "
          f"(对齐样本数: {len(align)})")

    baseline_metrics = _evaluate_seasonal_naive(df, test_df)
    print(f"  前一周同日基线 → MAPE={baseline_metrics['mape']:.2f}%, "
          f"RMSE={baseline_metrics['rmse']:.2f} (样本数: {baseline_metrics['samples']})")

    report = {
        "metadata": {
            "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "horizon_days": 30,
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
            "ensemble_weights": {"lstm": 0.4, "lightgbm": 0.6},
        },
        "seasonal_naive_7d": baseline_metrics,
        "lstm": lstm_metrics,
        "lightgbm": lgbm_metrics,
        "ensemble": ensemble_metrics,
    }
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[4/4] 评估报告已保存 → {REPORT_PATH}")
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
