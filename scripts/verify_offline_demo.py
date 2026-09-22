"""Check that the prepared local demo has no runtime CDN dependency."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REMOTE_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def verify(root: Path) -> dict[str, object]:
    frontend = PROJECT_ROOT / "frontend"
    remote_references: list[str] = []
    paths = [frontend / "index.html", *frontend.glob("js/**/*.js"), *frontend.glob("css/**/*.css")]
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        external = []
        for match in _REMOTE_PATTERN.findall(text):
            hostname = (urlparse(match).hostname or "").lower()
            if hostname not in {"localhost", "127.0.0.1", "::1"}:
                external.append(match)
        if external:
            remote_references.append(str(path.relative_to(PROJECT_ROOT)))
    package = root / "dist" / "local-demo.zip"
    vendor = frontend / "vendor" / "echarts.min.js"
    result = {
        "root": str(root),
        "package": str(package),
        "package_exists": package.is_file(),
        "bundled_echarts_exists": vendor.is_file() and vendor.stat().st_size > 100_000,
        "remote_references": remote_references,
    }
    result["ready"] = bool(
        result["package_exists"]
        and result["bundled_echarts_exists"]
        and not remote_references
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="检查本地演示版的离线资源完整性")
    parser.add_argument("--root", default=os.environ.get("DEMO_ROOT", str(PROJECT_ROOT / ".demo-runtime")))
    args = parser.parse_args()
    result = verify(Path(args.root).expanduser().resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
