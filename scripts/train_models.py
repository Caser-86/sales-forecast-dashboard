"""模型训练脚本

训练候选模型、按验证集选择策略，并保存最终模型包。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from ml.trainer import train_all  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="训练销售预测候选模型")
    parser.add_argument("--no-activate", action="store_true", help="只生成候选模型包，不切换活动指针")
    parser.add_argument("--data-version", default=None, help="锁定训练输入数据版本")
    args = parser.parse_args()

    print("=" * 60)
    print("销售数据预测大屏 - 模型训练")
    print("=" * 60)
    print()
    report = train_all(activate=not args.no_activate, data_version=args.data_version)
    print()
    print("=" * 60)
    print("模型训练完成。评估报告：")
    for name, m in report.items():
        if not isinstance(m, dict) or "mape" not in m or "rmse" not in m:
            continue
        print(f"  {name:18s} → MAPE={m['mape']:.2f}%, RMSE={m['rmse']:.2f}")
    selection = report.get("metadata", {}).get("model_selection", {})
    if selection:
        print(
            f"  发布策略: {selection.get('strategy')} "
            f"(验证集 {selection.get('metric')}={selection.get('validation_score'):.4f})"
        )
    print("=" * 60)
    print("下一步: uvicorn app.main:app --reload  (在 backend/ 目录下)")


if __name__ == "__main__":
    main()
