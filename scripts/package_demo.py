"""Package the safe, generated assets needed for the local demo."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

def main() -> int:
    parser = argparse.ArgumentParser(description="打包本地演示资源（不包含数据库、日志和会话）")
    parser.add_argument("--root", default=os.environ.get("DEMO_ROOT", str(PROJECT_ROOT / ".demo-runtime")))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    os.environ["DEMO_ROOT"] = str(Path(args.root).expanduser().resolve())
    from app.services.demo_service import package_demo

    output = Path(args.output) if args.output else Path(args.root) / "dist" / "local-demo.zip"
    result = package_demo(output=output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
