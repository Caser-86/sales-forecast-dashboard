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
    assert 'id="versionSummary"' in html
    assert 'id="savePlan"' in html
    assert 'id="exportPlan"' in html
    assert "loadSystemStatus" in script
    assert "showEmptyState" in script
    assert "api.getStores()" in script
    assert "api.getInventory()" not in script.split("async function loadSelectors()", 1)[1].split("async function currentScope", 1)[0]


def test_frontend_has_v2_navigation_contract_and_explicit_unavailable_state():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app_script = (PROJECT_ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")

    for route in ("overview", "data", "forecast", "inventory", "plans", "models", "system"):
        assert f'data-route="{route}"' in html
        assert f'"{route}"' in app_script
    assert 'id="routePlaceholder"' in html
    assert "规划中" in html
    assert 'src="js/app.js?v=1"' in html
    assert "hashchange" in app_script
    assert "ROUTE_ORDER" in app_script
    assert 'src="js/ui.js?v=1"' in html
    assert "syncScopeToRoute" in app_script
    assert "routeScopeSummary" in html


def test_frontend_has_real_data_center_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "frontend" / "js" / "pages" / "data-center.js").read_text(encoding="utf-8")
    api = (PROJECT_ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    for element_id in (
        "dataCenterPage",
        "salesDatasetFile",
        "inventoryDatasetFile",
        "previewSalesDataset",
        "uploadSalesDataset",
        "runtimeDataVersion",
        "datasetVersionsBody",
        "datasetVersionSummary",
        "datasetVersionPrev",
        "datasetVersionNext",
    ):
        assert f'id="{element_id}"' in html
    assert "previewDataset" in page
    assert "uploadDataset" in page
    assert "publishRuntimeSnapshot" in page
    assert "rollbackRuntimeSnapshot" in page
    assert "downloadErrors" in page
    assert "getDatasets" in api
    assert "postRaw" in api
    assert "rollbackRuntimeSnapshot" in api
    assert "versionPage" in page


def test_frontend_has_real_model_center_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "frontend" / "js" / "pages" / "model-center.js").read_text(encoding="utf-8")
    api = (PROJECT_ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    for element_id in ("modelCenterPage", "startModelTraining", "modelVersionsBody", "modelJobsBody"):
        assert f'id="{element_id}"' in html
    assert "activateModel" in page
    assert "model-job-retry" in page
    assert "retryJob" in page
    assert "getModels" in api
    assert "submitTraining" in api


def test_frontend_has_forecast_analysis_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "frontend" / "js" / "pages" / "forecast-analysis.js").read_text(encoding="utf-8")
    catalog = (PROJECT_ROOT / "frontend" / "js" / "pages" / "catalog.js").read_text(encoding="utf-8")

    for element_id in (
        "forecastAnalysisPage",
        "forecastCatalogSearch",
        "forecastCatalogSummary",
        "forecastCatalogPrev",
        "forecastCatalogNext",
        "forecastProductSelect",
        "forecastStoreSelect",
        "forecastHistoryBody",
        "forecastFutureBody",
        "exportForecastCsv",
    ):
        assert f'id="{element_id}"' in html
    assert "getSales" in page
    assert "getForecast" in page
    assert "downloadForecastCsv" in page
    assert "filterAndPage" in catalog
    assert "productPage" in page
    assert "forecastCatalogNext" in page
    assert "有效回测样本" in page
    assert "实际销量大于 0" in page


def test_frontend_has_inventory_decision_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "frontend" / "js" / "pages" / "replenishment.js").read_text(encoding="utf-8")
    api = (PROJECT_ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    for element_id in (
        "inventoryDecisionPage",
        "replenishmentAbcFilter",
        "replenishmentRiskFilter",
        "replenishmentBody",
        "inventorySourceSummary",
        "replenishmentForm",
        "runReplenishmentPreview",
        "addReplenishmentPlan",
    ):
        assert f'id="{element_id}"' in html
    assert "getInventory" in page
    assert "model_version" in page
    assert "previewReplenishment" in page
    assert "previewReplenishment" in api
    assert "selectedKeys" in page
    assert "createPlan" in page


def test_frontend_has_plan_center_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "frontend" / "js" / "pages" / "plans.js").read_text(encoding="utf-8")
    api = (PROJECT_ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    for element_id in (
        "planCenterPage",
        "planVersionsBody",
        "planDetail",
        "refreshPlans",
        "planWorkflowActions",
        "demoIdentity",
        "demoLogin",
    ):
        assert f'id="{element_id}"' in html
    assert "getPlans" in page
    assert "getPlan" in page
    assert "planExportUrl" in page
    assert "transitionPlan" in page
    assert "createPlanRevision" in page
    assert "getPlanEvents" in page
    assert 'byId("planWorkflowActions").addEventListener' in page
    assert "getPlans" in api
    assert "getAuthConfig" in api
    assert "credentials: \"include\"" in api


def test_frontend_has_system_status_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "frontend" / "js" / "pages" / "system.js").read_text(encoding="utf-8")

    for element_id in (
        "systemPage", "systemPageStatus", "systemRuntimeBody", "systemQualityBody",
        "demoScenarioSelect", "applyDemoScenario", "createDemoBackup", "restoreDemoBackup",
        "createDiagnosticPackage",
    ):
        assert f'id="{element_id}"' in html
    assert "getMetadata" in page
    assert "getDataQuality" in page
    assert "getDatasets" in page
    assert "switchDemoScenario" in page
    assert "createDemoBackup" in page
    assert "restoreDemoBackup" in page
    assert "createDiagnosticPackage" in page


def test_frontend_has_shared_runtime_context_and_retry_contract():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    ui = (PROJECT_ROOT / "frontend" / "js" / "ui.js").read_text(encoding="utf-8")
    dashboard = (PROJECT_ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")

    for element_id in ("businessDate", "routeBusinessDate", "routeVersion", "routeScopeSummary"):
        assert f'id="{element_id}"' in html
    assert "showError" in ui
    assert "retry" in ui
    assert "setLoading" in ui
    assert "DemoUI.showError" in dashboard
    assert "DemoUI.setRuntimeContext" in dashboard
    app = (PROJECT_ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert "DashboardPage?.refresh" in app
    assert "dashboardInitialized" in dashboard


def test_frontend_api_exposes_quality_endpoints():
    api = (PROJECT_ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    assert "getModelInfo" in api
    assert "getDataQuality" in api
    assert "getStores" in api
    assert "getMetadata" in api
    assert "createPlan" in api
    assert "submitTraining" in api
    assert "getJobs" in api
    assert "retryJob" in api
    assert "Idempotency-Key" in api
    assert "product_id" in api
    assert "store_id" in api


def test_frontend_bundles_pinned_echarts_without_runtime_cdn_dependency():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    vendor = PROJECT_ROOT / "frontend" / "vendor" / "echarts.min.js"
    notices = PROJECT_ROOT / "frontend" / "vendor" / "THIRD_PARTY_NOTICES.md"

    assert 'src="vendor/echarts.min.js"' in html
    assert "cdn.jsdelivr.net" not in html
    assert vendor.is_file() and vendor.stat().st_size > 100_000
    assert "Apache License 2.0" in notices.read_text(encoding="utf-8")


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


def test_dashboard_labels_mape_with_directional_metric_name():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    cards = (PROJECT_ROOT / "frontend" / "js" / "charts" / "kpi-cards.js").read_text(encoding="utf-8")

    assert "MAPE（越低越好）" in html
    assert 'id="kpiMape"' in html
    assert 'this.animate("kpiMape", kpi.mape' in cards
    assert "预测准确率" not in html


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
    assert "inventory-heatmap.js?v=3" in html


def test_inventory_tooltip_explains_replenishment_inputs():
    inventory = (PROJECT_ROOT / "frontend" / "js" / "charts" / "inventory-heatmap.js").read_text(encoding="utf-8")

    for field in ("window_demand", "net_available", "target_stock", "raw_replenishment", "pack_size", "minimum_order_quantity"):
        assert field in inventory


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
    assert "updatePlanAvailability" in dashboard
    assert "api.createPlan" in dashboard


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


def test_frontend_has_a_tablet_desktop_layout_for_1366_viewports():
    css = (PROJECT_ROOT / "frontend" / "css" / "dashboard.css").read_text(encoding="utf-8")

    assert "min-width: 701px" in css
    assert "max-width: 1366px" in css
    assert "grid-template-columns: max-content max-content max-content max-content max-content minmax(0, 1fr)" in css
    assert "overflow-y: auto" in css
    assert "min-height: 430px" in css
