"""预测服务

加载训练好的模型，按模型包中的发布策略对未来 horizon 进行递推预测。
- LSTM：使用 14 天序列递推
- LightGBM：递归构建未来特征
- seasonal-naive 或 ensemble：由验证集选择结果决定
"""
from __future__ import annotations

import json
import os
from datetime import timedelta
from threading import Lock
from typing import Dict, List

import numpy as np
import pandas as pd
import torch
from app.core.config import settings
from app.core.exceptions import ModelArtifactError
from app.services.dataset_service import get_active_dataset_id, get_active_sales_path
from common.abc import classify_abc
from sklearn.preprocessing import LabelEncoder

from . import lightgbm_model as lgbm_wrapper
from .artifacts import get_active_model_dir, get_active_model_id, get_active_model_manifest
from .feature_engineering import FEATURE_COLS, LSTM_FEATURE_COLS
from .future_features import DEFAULT_HOLIDAYS, build_future_feature_row
from .lstm_model import SEQ_LEN, SalesLSTM
from .lstm_model import load_model as load_lstm

# 类别编码器：品类集合固定（服装/家居/日化/电子/食品），
# 在模块加载时构造一次，避免在预测循环内重复 fit。
_CATEGORY_ENCODER = LabelEncoder().fit(["服装", "家居", "日化", "电子", "食品"])

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = settings.MODELS_DIR
FEATURES_PATH = str(settings.FEATURES_CSV)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FORECAST_DAYS = settings.FORECAST_DAYS
SCENARIO_RANGE_RATIO = 0.15

# Backward-compatible alias for callers that imported the old constant.
HOLIDAYS_FUTURE = DEFAULT_HOLIDAYS


def _load_category_encoder(model_dir):
    """Load the encoder versioned with an active package, with legacy fallback."""
    encoder_path = model_dir / "category_encoder.json"
    if not encoder_path.is_file():
        return _CATEGORY_ENCODER
    try:
        payload = json.loads(encoder_path.read_text(encoding="utf-8"))
        classes = payload["classes"]
        if not isinstance(classes, list) or not classes or not all(isinstance(item, str) for item in classes):
            raise ValueError("classes 无效")
        return LabelEncoder().fit(classes)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ModelArtifactError("模型类别编码器无效") from exc


def _validate_feature_schema(model_dir) -> None:
    """Reject a published package whose feature contract differs from serving code."""
    schema_path = model_dir / "feature_schema.json"
    if not schema_path.is_file():
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("feature_cols") != FEATURE_COLS:
            raise ValueError("feature_cols 不一致")
        if schema.get("lstm_feature_cols") != LSTM_FEATURE_COLS:
            raise ValueError("lstm_feature_cols 不一致")
        if schema.get("target_col") != "sales":
            raise ValueError("target_col 不一致")
        if schema.get("horizon_days") != settings.FORECAST_DAYS:
            raise ValueError("horizon_days 不一致")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ModelArtifactError("模型特征 schema 无效") from exc


def _load_model_selection(model_dir) -> dict:
    """Load the strategy selected on validation, with legacy ensemble fallback."""
    path = model_dir / "model_selection.json"
    if not path.is_file():
        weights = settings.ENSEMBLE_WEIGHTS
        return {
            "strategy": "ensemble",
            "candidate": "legacy_fixed_weights",
            "weights": {"lstm": float(weights[0]), "lightgbm": float(weights[1])},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        strategy = payload["strategy"]
        if strategy not in {"lstm", "lightgbm", "ensemble", "seasonal_naive_7d"}:
            raise ValueError("strategy 无效")
        weights = payload.get("weights", {})
        if not isinstance(weights, dict):
            raise ValueError("weights 无效")
        normalized = {
            "lstm": float(weights.get("lstm", 0.0)),
            "lightgbm": float(weights.get("lightgbm", 0.0)),
        }
        if any(not np.isfinite(value) or value < 0 for value in normalized.values()):
            raise ValueError("weights 不能为负")
        if strategy == "ensemble" and abs(sum(normalized.values()) - 1.0) > 1e-6:
            raise ValueError("ensemble weights 总和必须为 1")
        expected_weights = {
            "lstm": {"lstm": 1.0, "lightgbm": 0.0},
            "lightgbm": {"lstm": 0.0, "lightgbm": 1.0},
            "seasonal_naive_7d": {"lstm": 0.0, "lightgbm": 0.0},
        }.get(strategy)
        if expected_weights and normalized != expected_weights:
            raise ValueError("strategy 与 weights 不一致")
        return {
            "strategy": strategy,
            "candidate": str(payload.get("candidate", strategy)),
            "weights": normalized,
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ModelArtifactError("模型选择配置无效") from exc


class ForecastPredictor:
    """单例式预测器，加载一次模型后可重复调用。"""

    _instance: "ForecastPredictor | None" = None
    _instance_lock = Lock()

    def __init__(self):
        model_dir = get_active_model_dir()
        self.model_version = get_active_model_id()
        self.data_version = get_active_dataset_id()
        manifest = get_active_model_manifest()
        if manifest is not None and manifest.get("data_version") != self.data_version:
            raise ModelArtifactError(
                f"模型 {self.model_version} 与数据集 {self.data_version} 不匹配"
            )
        self.category_encoder = _load_category_encoder(model_dir)
        _validate_feature_schema(model_dir)
        self.model_selection = _load_model_selection(model_dir)
        self.forecast_strategy = self.model_selection["strategy"]
        self.lstm_weight = self.model_selection["weights"]["lstm"]
        self.lgbm_weight = self.model_selection["weights"]["lightgbm"]
        self.lstm: SalesLSTM = load_lstm(str(model_dir / "lstm_model.pth"), DEVICE)
        self.lgbm, self.feature_cols = lgbm_wrapper.load_model(str(model_dir / "lightgbm_model.txt"))
        from .scaler_io import load_scaler

        scaler_x_json = model_dir / "lstm_scaler_x.json"
        scaler_y_json = model_dir / "lstm_scaler_y.json"
        if not scaler_x_json.is_file() or not scaler_y_json.is_file():
            raise ModelArtifactError("模型必须使用 JSON scaler；旧版 joblib 产物需要重新训练")
        self.scaler_x = load_scaler(scaler_x_json)
        self.scaler_y = load_scaler(scaler_y_json)
        # 加载含工程特征的历史数据（用于构建 LSTM 输入序列与 LightGBM lag）
        self.history: pd.DataFrame = pd.read_csv(FEATURES_PATH)
        self.history["date"] = pd.to_datetime(self.history["date"])
        # raw 数据仅用于 ABC 分级时的总量统计
        self.raw: pd.DataFrame = pd.read_csv(get_active_sales_path())
        self.raw["date"] = pd.to_datetime(self.raw["date"])
        recent_start = self.raw["date"].max() - pd.Timedelta(days=29)
        recent_demand = (
            self.raw[self.raw["date"] >= recent_start]
            .groupby(["product_id", "store_id"])["sales"]
            .sum()
        )
        self.recent_demand = {
            (int(product_id), int(store_id)): float(total)
            for (product_id, store_id), total in recent_demand.items()
        }
        self.abc_classes = classify_abc(self.recent_demand)

    @classmethod
    def get(cls) -> "ForecastPredictor":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the loaded singleton so a newly activated model can be used."""
        with cls._instance_lock:
            cls._instance = None

    # ---------- 内部工具 ----------

    def _recent_sequence(self, product_id: int, store_id: int) -> pd.DataFrame:
        """获取某商品×门店最近的历史数据（至少 SEQ_LEN 天）。"""
        g = self.history[
            (self.history["product_id"] == product_id) &
            (self.history["store_id"] == store_id)
        ].sort_values("date")
        if len(g) < SEQ_LEN:
            raise ValueError(f"历史数据不足：商品 {product_id} 门店 {store_id} 仅有 {len(g)} 天")
        return g.tail(SEQ_LEN).copy()

    def _lstm_forecast(self, recent: pd.DataFrame) -> List[float]:
        """用 LSTM 递推预测 30 天。"""
        seq = self.scaler_x.transform(recent[LSTM_FEATURE_COLS].values.astype(np.float32))
        sales_history = recent["sales"].astype(float).tolist()
        price = float(recent["price"].mean())
        competitor_price = float(recent["competitor_price"].mean())
        category = str(recent["category"].iloc[0])
        category_enc = self._category_encoding(category)
        last_date = recent["date"].iloc[-1].date()

        preds = []
        for step in range(FORECAST_DAYS):
            x = torch.tensor(seq[np.newaxis], dtype=torch.float32, device=DEVICE)
            with torch.no_grad():
                p = self.lstm(x).cpu().numpy()[0]
            # 反归一化得到销量
            pred_val = float(self.scaler_y.inverse_transform([[p]])[0, 0])
            pred_val = max(0.0, pred_val)
            preds.append(pred_val)
            future_row = build_future_feature_row(
                forecast_date=last_date + timedelta(days=step + 1),
                sales_history=sales_history,
                price=price,
                competitor_price=competitor_price,
                category_enc=category_enc,
                predicted_sales=pred_val,
            )
            next_row = np.array([[future_row[column] for column in LSTM_FEATURE_COLS]], dtype=np.float32)
            seq = np.vstack([seq[1:], self.scaler_x.transform(next_row)])
            sales_history.append(pred_val)
        return preds

    def _category_encoding(self, category: str) -> int:
        try:
            return int(self.category_encoder.transform([category])[0])
        except ValueError as exc:
            raise ModelArtifactError(f"模型编码器不支持品类: {category}") from exc

    def _lgbm_forecast(self, product_id: int, store_id: int,
                       recent: pd.DataFrame) -> List[float]:
        """用 LightGBM 递归预测 30 天。"""
        # 构建历史特征（lag/rolling）
        hist = self.history[
            (self.history["product_id"] == product_id) &
            (self.history["store_id"] == store_id)
        ].sort_values("date").copy()

        # 使用最近窗口均价作为未来价格估计，且未来促销默认关闭。
        recent_price = float(recent["price"].mean())
        recent_comp = float(recent["competitor_price"].mean())
        category = recent["category"].iloc[0]
        category_enc = self._category_encoding(str(category))

        # 维护一个只包含历史与先前预测的销量列表。
        sales_series = hist["sales"].astype(float).tolist()

        last_date = recent["date"].iloc[-1].date()
        preds = []
        for i in range(FORECAST_DAYS):
            d = last_date + timedelta(days=i + 1)
            row = {
                "product_id": product_id,
                "store_id": store_id,
                **build_future_feature_row(
                    forecast_date=d,
                    sales_history=sales_series,
                    price=recent_price,
                    competitor_price=recent_comp,
                    category_enc=category_enc,
                ),
            }
            X = np.array([[row[c] for c in FEATURE_COLS]], dtype=float)
            pred = float(self.lgbm.predict(X)[0])
            pred = max(0.0, pred)
            preds.append(pred)
            sales_series.append(pred)
        return preds

    def _seasonal_naive_forecast(self, recent: pd.DataFrame) -> List[float]:
        """Repeat the last observed week when validation selects the baseline."""
        cycle = recent["sales"].astype(float).tail(7).tolist()
        if not cycle:
            raise ValueError("历史数据为空，无法执行季节性基线")
        return [float(cycle[index % len(cycle)]) for index in range(FORECAST_DAYS)]

    # ---------- 对外接口 ----------

    def forecast(self, product_id: int, store_id: int) -> Dict:
        recent = self._recent_sequence(product_id, store_id)
        last_date = recent["date"].iloc[-1].date()

        if self.forecast_strategy == "seasonal_naive_7d":
            ensemble = self._seasonal_naive_forecast(recent)
        else:
            lstm_preds = self._lstm_forecast(recent) if self.lstm_weight else []
            lgbm_preds = self._lgbm_forecast(product_id, store_id, recent) if self.lgbm_weight else []
            if self.forecast_strategy == "lstm":
                ensemble = lstm_preds
            elif self.forecast_strategy == "lightgbm":
                ensemble = lgbm_preds
            else:
                ensemble = [
                    self.lstm_weight * lv + self.lgbm_weight * gv
                    for lv, gv in zip(lstm_preds, lgbm_preds, strict=True)
                ]

        # 情景范围：基于集成值 ±15%，不是经回测校准的统计预测区间。
        forecast_list = []
        for i, val in enumerate(ensemble):
            d = last_date + timedelta(days=i + 1)
            low = max(0, val * (1 - SCENARIO_RANGE_RATIO))
            high = val * (1 + SCENARIO_RANGE_RATIO)
            forecast_list.append({
                "date": d.isoformat(),
                "predicted_sales": int(round(val)),
                "confidence_low": int(round(low)),
                "confidence_high": int(round(high)),
                "range_type": "scenario",
            })

        total_predicted = int(round(sum(ensemble)))
        # 安全库存：预测总量 × 1.08
        suggested_purchase = int(round(total_predicted * 1.08))

        # ABC 分级使用原始销售数据最近 30 天需求量，不与未来预测值混用。
        abc = self.abc_classes.get((product_id, store_id), "C")

        return {
            "product_id": product_id,
            "store_id": store_id,
            "forecast": forecast_list,
            "total_predicted": total_predicted,
            "suggested_purchase": suggested_purchase,
            "abc_class": abc,
            "range_type": "scenario",
        }


def forecast(product_id: int, store_id: int) -> Dict:
    """便捷入口。"""
    return ForecastPredictor.get().forecast(product_id, store_id)


if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sid = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    result = forecast(pid, sid)
    print(json.dumps(result, ensure_ascii=False, indent=2))
