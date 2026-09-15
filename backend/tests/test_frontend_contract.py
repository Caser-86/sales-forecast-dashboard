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


def test_dashboard_surfaces_partial_forecast_coverage():
    script = (PROJECT_ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")

    assert "dashboard.coverage" in script
    assert "coverage.failed" in script
    assert "coverage.status" in script


def test_dashboard_labels_quantity_metrics_without_revenue_claim():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    pie = (PROJECT_ROOT / "frontend" / "js" / "charts" / "category-pie.js").read_text(encoding="utf-8")

    assert "总销量（30天）" in html
    assert "总销售额（30天）" not in html
    assert "品类销量占比" in html
    assert "总销量" in pie
    assert "总销售额" not in pie


def test_top_products_chart_uses_dashboard_contract_field_names():
    chart = (PROJECT_ROOT / "frontend" / "js" / "charts" / "top-products.js").read_text(encoding="utf-8")

    assert "d.suggested_purchase" in chart
    assert "d.abc_class" in chart
    assert "d.suggested}`" not in chart
    assert "d.abc}`" not in chart
