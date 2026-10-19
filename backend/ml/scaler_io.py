"""Safe JSON serialization for StandardScaler parameters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.preprocessing import StandardScaler


def save_scaler(scaler: StandardScaler, path: str | Path) -> None:
    """Persist only numeric scaler parameters, never a pickle payload."""
    payload = {
        "mean": np.asarray(scaler.mean_, dtype=float).tolist(),
        "scale": np.asarray(scaler.scale_, dtype=float).tolist(),
        "var": np.asarray(scaler.var_, dtype=float).tolist(),
        "n_features_in": int(scaler.n_features_in_),
        "n_samples_seen": int(np.asarray(scaler.n_samples_seen_).reshape(-1)[0]),
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_scaler(path: str | Path) -> StandardScaler:
    """Load and validate a JSON scaler parameter file."""
    try:
        payload: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        mean = np.asarray(payload["mean"], dtype=float)
        scale = np.asarray(payload["scale"], dtype=float)
        var = np.asarray(payload["var"], dtype=float)
        n_features = int(payload["n_features_in"])
        n_samples = int(payload["n_samples_seen"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("scaler JSON 无效") from exc

    if n_features <= 0 or n_samples <= 0:
        raise ValueError("scaler 元数据无效")
    if mean.shape != (n_features,) or scale.shape != (n_features,) or var.shape != (n_features,):
        raise ValueError("scaler 参数维度不一致")
    if not np.isfinite(mean).all() or not np.isfinite(scale).all() or not np.isfinite(var).all():
        raise ValueError("scaler 参数必须是有限数值")
    if (scale <= 0).any() or (var < 0).any():
        raise ValueError("scaler 参数范围无效")

    scaler = StandardScaler()
    scaler.mean_ = mean
    scaler.scale_ = scale
    scaler.var_ = var
    scaler.n_features_in_ = n_features
    scaler.n_samples_seen_ = n_samples
    return scaler
