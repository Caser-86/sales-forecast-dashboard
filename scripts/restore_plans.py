"""Validate and atomically restore the SQLite replenishment-plan database."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.plan_repository import restore_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="恢复补货草案 SQLite 数据库")
    parser.add_argument("backup", type=Path, help="已验证的 .db.bak 文件")
    parser.add_argument(
        "--database",
        default=str(settings.DATABASE_URL),
        help="目标 SQLite 文件路径或 sqlite:/// URL",
    )
    args = parser.parse_args()
    result = restore_database(args.backup, args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
