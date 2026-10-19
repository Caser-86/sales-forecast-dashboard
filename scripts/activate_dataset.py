"""Validate and activate a previously published sales dataset version."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.dataset_service import activate_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="激活已发布的销售数据版本")
    parser.add_argument("dataset_id", help="sales-<16 hex chars>")
    args = parser.parse_args()
    result = activate_dataset(args.dataset_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
