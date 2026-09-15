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


def test_abc_chart_is_labeled_as_demand_priority_not_stock_risk():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "需求优先级热力图" in html
    assert "库存热力图（ABC 分级）" not in html


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


def test_trend_chart_labels_scenario_range_and_draws_band_width():
    chart = (PROJECT_ROOT / "frontend" / "js" / "charts" / "sales-line.js").read_text(encoding="utf-8")

    assert "情景范围" in chart
    assert "confBand" in chart
    assert "{ data: confBand }" in chart
    assert "Math.max(histDates.length - 1, 0)" in chart


def test_chart_tooltips_escape_api_text_before_html_rendering():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    top = (PROJECT_ROOT / "frontend" / "js" / "charts" / "top-products.js").read_text(encoding="utf-8")
    inventory = (PROJECT_ROOT / "frontend" / "js" / "charts" / "inventory-heatmap.js").read_text(encoding="utf-8")

    assert "safe-text.js" in html
    assert "escapeHtml(d.product_name)" in top
    assert "escapeHtml(d.product_name)" in inventory


def test_frontend_requests_have_timeout_cancellation_and_stale_guards():
    api = (PROJECT_ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")
    dashboard = (PROJECT_ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    trend = (PROJECT_ROOT / "frontend" / "js" / "charts" / "sales-line.js").read_text(encoding="utf-8")
    inventory = (PROJECT_ROOT / "frontend" / "js" / "charts" / "inventory-heatmap.js").read_text(encoding="utf-8")

    assert "AbortController" in api
    assert "timeoutMs = 10000" in api
    assert "TimeoutError" in api
    assert "dashboardRequestId" in dashboard
    assert "requestId !== this.requestId" in trend
    assert "requestId !== this.requestId" in inventory


def test_frontend_has_mobile_scroll_focus_and_chart_accessibility_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "css" / "dashboard.css").read_text(encoding="utf-8")
    dashboard = (PROJECT_ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")

    assert 'id="headerStatus"' in html
    assert 'role="img"' in html
    assert "@media screen and (max-width: 700px)" in css
    assert "overflow-y: auto" in css
    assert ":focus-visible" in css
    assert "SalesLineChart.init();" in dashboard
