"""LSTM 销量预测模型

架构：
- 输入：(batch, seq_len=14, input_dim)
- LSTM：hidden_size=128, num_layers=2, dropout=0.2
- 全连接：128 → 64 → 1
- 输出：未来 1 天销量预测
"""
from __future__ import annotations

import os
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn

SEQ_LEN = 14  # 输入序列长度（天）


class SalesLSTM(nn.Module):
    def __init__(self, input_dim: int, hidden_size: int = 128,
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_dim)
        out, _ = self.lstm(x)
        # 取最后一个时间步
        last = out[:, -1, :]
        return self.fc(last).squeeze(-1)


def build_sequences(features: np.ndarray, targets: np.ndarray, seq_len: int = SEQ_LEN
                    ) -> Tuple[np.ndarray, np.ndarray]:
    """把二维特征切分成 (样本, seq_len, feat) 与对应目标。

    features: (T, F)  单个商品×门店的时间序列
    targets:  (T,)
    """
    X, y = [], []
    for i in range(len(features) - seq_len):
        X.append(features[i:i + seq_len])
        y.append(targets[i + seq_len])
    return np.array(X), np.array(y)


def save_model(model: nn.Module, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "input_dim": model.input_dim,
        "hidden_size": model.hidden_size,
        "num_layers": model.num_layers,
    }, path)


def load_model(path: str, device: torch.device | str = "cpu") -> SalesLSTM:
    ckpt = torch.load(path, map_location=device, weights_only=True)
    if not isinstance(ckpt, dict) or not {"state_dict", "input_dim", "hidden_size", "num_layers"}.issubset(ckpt):
        raise ValueError("LSTM 模型产物格式无效")
    model = SalesLSTM(
        input_dim=ckpt["input_dim"],
        hidden_size=ckpt["hidden_size"],
        num_layers=ckpt["num_layers"],
    )
    model.load_state_dict(ckpt["state_dict"])
    model.to(device)
    model.eval()
    return model
