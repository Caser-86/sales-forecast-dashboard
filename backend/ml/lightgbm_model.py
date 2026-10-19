"""LightGBM 销量预测模型

表格型数据上的回归模型，与 LSTM 集成使用。
"""
from __future__ import annotations

import json
import os
from typing import Tuple

import lightgbm as lgb
import numpy as np

DEFAULT_PARAMS = {
    "objective": "regression",
    "metric": "rmse",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "n_estimators": 500,
    "early_stopping_rounds": 50,
}


def train_lgbm(X_train: np.ndarray, y_train: np.ndarray,
               X_val: np.ndarray, y_val: np.ndarray,
               params: dict | None = None) -> lgb.LGBMRegressor | lgb.Booster:
    """训练 LightGBM 回归器并返回模型对象。"""
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)

    # early_stopping_rounds 需通过 callback 或参数传入
    es = p.pop("early_stopping_rounds", 50)
    n_estimators = p.pop("n_estimators", 500)

    model = lgb.LGBMRegressor(n_estimators=n_estimators, **p)
    try:
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[
                lgb.early_stopping(es, verbose=False),
                lgb.log_evaluation(period=0),
            ],
        )
        return model
    except TypeError as exc:
        # LightGBM 4.5's sklearn wrapper passes force_all_finite, which was
        # removed by newer scikit-learn releases. Native training avoids that
        # adapter boundary while keeping the same validation protocol.
        if "force_all_finite" not in str(exc):
            raise
        native_params = dict(p)
        native_params["verbosity"] = native_params.pop("verbose", -1)
        return lgb.train(
            native_params,
            lgb.Dataset(X_train, label=y_train),
            num_boost_round=n_estimators,
            valid_sets=[lgb.Dataset(X_val, label=y_val)],
            callbacks=[
                lgb.early_stopping(es, verbose=False),
                lgb.log_evaluation(period=0),
            ],
        )


def save_model(model: lgb.LGBMRegressor | lgb.Booster, path: str, feature_cols: list[str]) -> None:
    """保存 LightGBM 模型与特征列。

    注意：LightGBM 的 C 库在 Windows 上对非 ASCII 路径支持不佳，
    因此先导出为字符串，再用 Python 的 open 写入（正确处理 Unicode 路径）。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    booster = model.booster_ if hasattr(model, "booster_") else model
    model_str = booster.model_to_string()
    with open(path, "w", encoding="utf-8") as f:
        f.write(model_str)
    sidecar = path + ".meta.json"
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump({"feature_cols": feature_cols}, f, ensure_ascii=False, indent=2)


def load_model(path: str) -> Tuple[lgb.Booster, list[str]]:
    """加载 LightGBM 模型与特征列，返回 Booster（可直接调用 .predict）。"""
    with open(path, "r", encoding="utf-8") as f:
        model_str = f.read()
    booster = lgb.Booster(model_str=model_str)

    sidecar = path + ".meta.json"
    feature_cols: list[str] = []
    if os.path.exists(sidecar):
        with open(sidecar, "r", encoding="utf-8") as f:
            feature_cols = json.load(f).get("feature_cols", [])
    return booster, feature_cols
