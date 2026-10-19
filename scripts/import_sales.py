"""Validate and publish a sales CSV dataset version."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.dataset_service import import_sales_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="导入并校验销售 CSV")
    parser.add_argument("source", type=Path, help="销售 CSV 文件路径")
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="只写入不可变版本，不切换 active 数据集",
    )
    args = parser.parse_args()
    result = import_sales_dataset(args.source, activate=not args.no_activate)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
