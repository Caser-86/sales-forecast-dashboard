"""前端 API 地址解析契约测试。"""
from __future__ import annotations

from pathlib import Path

FRONTEND_API = Path(__file__).resolve().parents[2] / "frontend" / "js" / "api.js"


def test_frontend_supports_explicit_api_base_url():
    source = FRONTEND_API.read_text(encoding="utf-8")

    assert "API_BASE_URL" in source
    assert "file:" in source
    assert "replace(/\\/+$/" in source
