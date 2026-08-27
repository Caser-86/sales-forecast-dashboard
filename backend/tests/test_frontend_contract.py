"""前端关键交互契约测试。"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_has_scope_controls_and_refresh_action():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")

    assert 'id="scopeProductSelect"' in html
    assert 'id="scopeStoreSelect"' in html
    assert 'id="refreshDashboard"' in html
    assert 'id="modelSummary"' in html
    assert "loadSystemStatus" in script
    assert "showEmptyState" in script


def test_frontend_api_exposes_quality_endpoints():
    api = (PROJECT_ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    assert "getModelInfo" in api
    assert "getDataQuality" in api
    assert "product_id" in api
    assert "store_id" in api
