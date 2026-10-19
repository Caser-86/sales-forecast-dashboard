"""Validate and activate a previously published model version."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from ml.artifacts import activate_model  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate a validated model package")
    parser.add_argument("model_id", help="model-<16 hex chars>")
    args = parser.parse_args()
    result = activate_model(args.model_id)
    print(f"已激活模型: {result['model_id']}")
    print(f"模型目录: {result['model_dir']}")


if __name__ == "__main__":
    main()
