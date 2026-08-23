"""数据初始化脚本

依次执行：
1. 生成模拟销售原始数据
2. 特征工程生成 features.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 backend/ 加入 sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from ml import data_generator, feature_engineering  # noqa: E402


def main():
    print("=" * 60)
    print("销售数据预测大屏 - 数据初始化")
    print("=" * 60)

    print("\n[1/2] 生成模拟销售数据...")
    raw_path = data_generator.generate_sales_data()
    print(f"  原始数据 → {raw_path}")

    print("\n[2/2] 特征工程...")
    feat_path = feature_engineering.build_features()
    print(f"  特征数据 → {feat_path}")

    print("\n" + "=" * 60)
    print("数据初始化完成。下一步: python scripts/train_models.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
