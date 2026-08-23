"""模型训练脚本

训练 LSTM + LightGBM 集成模型并保存。
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR / "ml"))

from trainer import train_all  # noqa: E402


def main():
    print("=" * 60)
    print("销售数据预测大屏 - 模型训练")
    print("=" * 60)
    print()
    report = train_all()
    print()
    print("=" * 60)
    print("模型训练完成。评估报告：")
    for name, m in report.items():
        print(f"  {name:10s} → MAPE={m['mape']:.2f}%, RMSE={m['rmse']:.2f}")
    print("=" * 60)
    print("下一步: uvicorn app.main:app --reload  (在 backend/ 目录下)")


if __name__ == "__main__":
    main()
