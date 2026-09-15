"""预测服务

加载训练好的模型，对未来 30 天进行递推预测。
- LSTM：使用 14 天序列递推
- LightGBM：递归构建未来特征
- 集成：0.4 * LSTM + 0.6 * LightGBM
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from threading import Lock
from typing import Dict, List

import lightgbm_model as lgbm_wrapper
import numpy as np
import pandas as pd
import torch
from app.core.exceptions import ModelArtifactError
from app.services.dataset_service import get_active_dataset_id, get_active_sales_path
from artifacts import get_active_model_dir, get_active_model_id, get_active_model_manifest
from common.abc import classify_abc
from feature_engineering import FEATURE_COLS, LSTM_FEATURE_COLS
from lstm_model import SEQ_LEN, SalesLSTM
from lstm_model import load_model as load_lstm
from sklearn.preprocessing import LabelEncoder

# 类别编码器：品类集合固定（服装/家居/日化/电子/食品），
# 在模块加载时构造一次，避免在预测循环内重复 fit。
_CATEGORY_ENCODER = LabelEncoder().fit(["服装", "家居", "日化", "电子", "食品"])

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BACKEND_DIR, "ml", "saved_models")
FEATURES_PATH = os.path.join(BACKEND_DIR, "data", "processed", "features.csv")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FORECAST_DAYS = 30
LSTM_WEIGHT = 0.4
LGBM_WEIGHT = 0.6

# 2025 年下半年节假日（用于未来特征）
HOLIDAYS_FUTURE = {
    date(2025, 9, 30), date(2025, 10, 1), date(2025, 10, 2),
    date(2025, 10, 3), date(2025, 10, 4), date(2025, 10, 5),
    date(2025, 10, 6), date(2025, 10, 7),
}


class ForecastPredictor:
    """单例式预测器，加载一次模型后可重复调用。"""

    _instance: "ForecastPredictor | None" = None
    _instance_lock = Lock()

    def __init__(self):
        import joblib
        model_dir = get_active_model_dir()
        self.model_version = get_active_model_id()
        self.data_version = get_active_dataset_id()
        manifest = get_active_model_manifest()
        if manifest is not None and manifest.get("data_version") != self.data_version:
            raise ModelArtifactError(
                f"模型 {self.model_version} 与数据集 {self.data_version} 不匹配"
            )
        self.lstm: SalesLSTM = load_lstm(str(model_dir / "lstm_model.pth"), DEVICE)
        self.lgbm, self.feature_cols = lgbm_wrapper.load_model(str(model_dir / "lightgbm_model.txt"))
        self.scaler_x = joblib.load(model_dir / "lstm_scaler_x.joblib")
        self.scaler_y = joblib.load(model_dir / "lstm_scaler_y.joblib")
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
        feats = recent[LSTM_FEATURE_COLS].values.astype(np.float32)
        feats_s = self.scaler_x.transform(feats)
        seq = feats_s.copy()  # (SEQ_LEN, F)

        preds = []
        for _ in range(FORECAST_DAYS):
            x = torch.tensor(seq[np.newaxis], dtype=torch.float32, device=DEVICE)
            with torch.no_grad():
                p = self.lstm(x).cpu().numpy()[0]
            # 反归一化得到销量
            pred_val = float(self.scaler_y.inverse_transform([[p]])[0, 0])
            pred_val = max(0.0, pred_val)
            preds.append(pred_val)
            # 递推：把预测的销量作为下一时间步的 sales，其余特征用最近一天复制
            next_row = feats[-1:].copy()
            next_row[0, 0] = pred_val  # sales 在 LSTM_FEATURE_COLS[0]
            next_row_s = self.scaler_x.transform(next_row)
            seq = np.vstack([seq[1:], next_row_s])
        return preds

    def _lgbm_forecast(self, product_id: int, store_id: int,
                       recent: pd.DataFrame) -> List[float]:
        """用 LightGBM 递归预测 30 天。"""
        # 构建历史特征（lag/rolling）
        hist = self.history[
            (self.history["product_id"] == product_id) &
            (self.history["store_id"] == store_id)
        ].sort_values("date").copy()

        # 最近的均价作为未来价格估计
        recent_price = float(recent["price"].mean())
        recent_comp = float(recent["competitor_price"].mean())
        category = recent["category"].iloc[0]

        # 维护一个滚动 sales 列表（包含历史）
        sales_series = hist["sales"].astype(float).tolist()

        last_date = recent["date"].iloc[-1].date()
        preds = []
        for i in range(FORECAST_DAYS):
            d = last_date + timedelta(days=i + 1)
            is_weekend = int(d.weekday() >= 5)
            is_holiday = int(d in HOLIDAYS_FUTURE)
            is_promotion = 0
            # lag 特征
            lag_1 = sales_series[-1]
            lag_7 = sales_series[-7] if len(sales_series) >= 7 else lag_1
            lag_14 = sales_series[-14] if len(sales_series) >= 14 else lag_1
            # rolling
            rolling_7 = float(np.mean(sales_series[-7:]))
            rolling_30 = float(np.mean(sales_series[-30:])) if len(sales_series) >= 30 else float(np.mean(sales_series))
            price_diff = 0.0
            # category_enc：复用模块级编码器
            cat_enc = int(_CATEGORY_ENCODER.transform([category])[0])

            row = {
                "product_id": product_id,
                "store_id": store_id,
                "category_enc": cat_enc,
                "price": recent_price,
                "competitor_price": recent_comp,
                "price_diff": price_diff,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "is_promotion": is_promotion,
                "sales_lag_1": lag_1,
                "sales_lag_7": lag_7,
                "sales_lag_14": lag_14,
                "sales_rolling_7": rolling_7,
                "sales_rolling_30": rolling_30,
                "day_of_week": d.weekday(),
                "month": d.month,
                "day_of_month": d.day,
            }
            X = np.array([[row[c] for c in FEATURE_COLS]], dtype=float)
            pred = float(self.lgbm.predict(X)[0])
            pred = max(0.0, pred)
            preds.append(pred)
            sales_series.append(pred)
        return preds

    # ---------- 对外接口 ----------

    def forecast(self, product_id: int, store_id: int) -> Dict:
        recent = self._recent_sequence(product_id, store_id)
        last_date = recent["date"].iloc[-1].date()

        lstm_preds = self._lstm_forecast(recent)
        lgbm_preds = self._lgbm_forecast(product_id, store_id, recent)
        # 集成
        ensemble = [
            LSTM_WEIGHT * lv + LGBM_WEIGHT * gv
            for lv, gv in zip(lstm_preds, lgbm_preds, strict=True)
        ]

        # 置信区间：基于集成值 ±15%
        forecast_list = []
        for i, val in enumerate(ensemble):
            d = last_date + timedelta(days=i + 1)
            low = max(0, val * 0.85)
            high = val * 1.15
            forecast_list.append({
                "date": d.isoformat(),
                "predicted_sales": int(round(val)),
                "confidence_low": int(round(low)),
                "confidence_high": int(round(high)),
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
