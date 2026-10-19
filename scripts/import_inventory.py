"""Validate and optionally activate an inventory snapshot CSV."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.inventory_dataset_service import import_inventory_snapshot  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a validated inventory snapshot")
    parser.add_argument("source", type=Path)
    parser.add_argument("--no-activate", action="store_true")
    args = parser.parse_args()
    result = import_inventory_snapshot(args.source, activate=not args.no_activate)
    print(f"库存版本: {result['inventory_id']}")
    print(f"快照路径: {result['snapshot_path']}")
    print(f"已激活: {result['active']}")


if __name__ == "__main__":
    main()
