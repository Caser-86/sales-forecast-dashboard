/* 大屏主逻辑：初始化、筛选、刷新与可见状态反馈 */
let productsCache = [];
let storesCache = [];
let dashboardRequestId = 0;
let dashboardController = null;
let lastDashboardData = null;
let lastInventoryData = null;
let lastMetadata = null;
let lastSavedPlanId = null;
let planRequestKey = null;

async function init() {
    initNavigation();
    DemoUI.setLoading(true, "正在加载演示数据...");
    updateClock();
    setInterval(updateClock, 1000);

    try {
        SalesLineChart.init();
        InventoryHeatmap.init();
        CategoryPieChart.init();
        TopProductsChart.init();
        await loadSelectors();
        await Promise.all([loadSystemStatus(), loadDashboard()]);
    } catch (e) {
        showDashboardError(`初始化失败: ${e.message}`);
    } finally {
        DemoUI.setLoading(false);
    }

    setInterval(loadDashboard, 5 * 60 * 1000);
}

function updateClock() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    document.getElementById("currentDate").textContent =
        `本地日期：${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    document.getElementById("currentTime").textContent =
        `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

function populateSelect(selectId, items, valueKey, labelBuilder, allLabel = null) {
    const select = document.getElementById(selectId);
    select.replaceChildren();
    if (allLabel !== null) {
        const allOption = document.createElement("option");
        allOption.value = "";
        allOption.textContent = allLabel;
        select.appendChild(allOption);
    }
    items.forEach(item => {
        const option = document.createElement("option");
        option.value = item[valueKey];
        option.textContent = labelBuilder(item);
        select.appendChild(option);
    });
}

async function loadSelectors() {
    const [products, stores] = await Promise.all([
        api.getProducts(),
        api.getStores()
    ]);
    productsCache = products.products || [];
    populateSelect("productSelect", productsCache, "product_id", p => p.product_name);
    populateSelect(
        "scopeProductSelect",
        productsCache,
        "product_id",
        p => `#${p.product_id} ${p.product_name}`,
        "全部商品"
    );

    storesCache = stores || [];
    populateSelect("storeSelect", storesCache, "store_id", s => s.store_name);
    populateSelect(
        "scopeStoreSelect",
        storesCache,
        "store_id",
        s => `#${s.store_id} ${s.store_name}`,
        "全部门店"
    );

    const routeScope = AppNavigation.getRouteState().scope;
    document.getElementById("scopeProductSelect").value = routeScope.productId || "";
    document.getElementById("scopeStoreSelect").value = routeScope.storeId || "";
    RoutePlaceholder.setScope(routeScope);

    document.getElementById("productSelect").addEventListener("change", loadTrend);
    document.getElementById("storeSelect").addEventListener("change", loadTrend);
    const handleScopeChange = () => {
        AppNavigation.syncScopeToRoute(currentScope());
        loadDashboard();
    };
    document.getElementById("scopeProductSelect").addEventListener("change", handleScopeChange);
    document.getElementById("scopeStoreSelect").addEventListener("change", handleScopeChange);
    document.getElementById("refreshDashboard").addEventListener("click", refreshAll);
    document.getElementById("savePlan").addEventListener("click", savePlanDraft);
}

function currentScope() {
    const productValue = document.getElementById("scopeProductSelect").value;
    const storeValue = document.getElementById("scopeStoreSelect").value;
    return {
        productId: productValue ? Number(productValue) : undefined,
        storeId: storeValue ? Number(storeValue) : undefined
    };
}

function scopeText() {
    const productSelect = document.getElementById("scopeProductSelect");
    const storeSelect = document.getElementById("scopeStoreSelect");
    const product = productSelect.selectedOptions[0]?.textContent || "全部商品";
    const store = storeSelect.selectedOptions[0]?.textContent || "全部门店";
    return `当前范围：${product} · ${store}`;
}

async function loadTrend() {
    const productId = Number(document.getElementById("productSelect").value);
    const storeId = Number(document.getElementById("storeSelect").value);
    if (!productId || !storeId) return;
    try {
        await SalesLineChart.load(productId, storeId);
    } catch (e) {
        console.error("销量趋势加载失败:", e);
    }
}

function setBusy(isBusy) {
    const button = document.getElementById("refreshDashboard");
    button.disabled = isBusy;
    button.textContent = isBusy ? "刷新中..." : "刷新数据";
    button.setAttribute("aria-busy", String(isBusy));
}

function showDashboardError(message) {
    DemoUI.showError(
        `${message}。请检查后端服务 (http://localhost:8000/health)`,
        { retry: refreshAll }
    );
}

function clearDashboardError() {
    DemoUI.clearError();
}

function showEmptyState(message = "") {
    if (message) {
        DemoUI.showEmpty(message);
    } else {
        DemoUI.clearEmpty();
    }
}

async function loadDashboard() {
    const requestId = ++dashboardRequestId;
    dashboardController?.abort();
    dashboardController = new AbortController();
    const signal = dashboardController.signal;
    setBusy(true);
    clearDashboardError();
    const scope = currentScope();
    try {
        const dashboard = await api.getDashboard(scope, { signal });
        if (requestId !== dashboardRequestId) return;
        lastDashboardData = dashboard;
        lastSavedPlanId = null;
        planRequestKey = null;
        document.getElementById("exportPlan").classList.add("hidden");
        const coverage = dashboard.coverage || {};
        if (coverage.status === "partial") {
            showDashboardError(
                `预测覆盖不完整：成功 ${coverage.succeeded}/${coverage.requested}，失败 ${coverage.failed} 项`
            );
        }
        KpiCards.render(dashboard.kpi);
        CategoryPieChart.load(dashboard.category_sales);
        TopProductsChart.load(dashboard.top_products);

        const hasData = Boolean(
            (dashboard.top_products && dashboard.top_products.length) ||
            (dashboard.category_sales && dashboard.category_sales.length)
        );
        showEmptyState(hasData ? "" : "当前筛选范围暂无可展示数据");
        document.getElementById("scopeLabel").textContent = scopeText();
        document.getElementById("lastUpdated").textContent =
            `数据更新时间：${dashboard.last_updated || "--"}`;

        const [, inventory] = await Promise.all([loadTrend(), InventoryHeatmap.load(scope)]);
        if (requestId !== dashboardRequestId) return;
        lastInventoryData = inventory || InventoryHeatmap.lastData;
        updatePlanAvailability();
    } catch (e) {
        if (e.name === "AbortError") return;
        console.error("大屏数据加载失败:", e);
        showDashboardError(`数据加载失败: ${e.message}`);
    } finally {
        if (requestId === dashboardRequestId) {
            dashboardController = null;
            setBusy(false);
        }
    }
}

async function loadSystemStatus() {
    const status = document.getElementById("systemStatus");
    status.className = "system-status pending";
    status.textContent = "状态检查中";
    try {
        const [model, quality, metadata] = await Promise.all([
            api.getModelInfo(),
            api.getDataQuality(),
            api.getMetadata()
        ]);
        lastMetadata = metadata;
        DemoUI.setRuntimeContext({
            asOfDate: metadata.as_of_date,
            dataVersion: metadata.data_version,
            modelVersion: metadata.model_version,
            inventoryVersion: metadata.inventory_version,
            inventoryStatus: metadata.inventory_status
        });
        updatePlanAvailability();
        const healthy = model.status === "ready" && quality.status === "healthy" &&
            metadata.inventory_status === "fresh";
        status.className = `system-status ${healthy ? "healthy" : "warning"}`;
        status.textContent = healthy ? "模型与数据正常" : "需要关注";
        const headerStatus = document.getElementById("headerStatus");
        headerStatus.textContent = healthy ? "服务就绪" : "需要关注";
        headerStatus.className = `status-text ${healthy ? "healthy" : "warning"}`;
        status.title = `模型：${model.status}；数据：${quality.status}`;
        document.getElementById("versionSummary").textContent =
            `数据 ${metadata.data_version} · 模型 ${metadata.model_version} · 库存 ${metadata.inventory_status}`;
        const ensembleMape = model.metrics?.ensemble?.mape;
        const baselineMape = model.metrics?.seasonal_naive_7d?.mape;
        const summary = document.getElementById("modelSummary");
        summary.textContent = ensembleMape !== undefined && baselineMape !== undefined
            ? `模型 MAPE ${ensembleMape.toFixed(2)}% · 基线 ${baselineMape.toFixed(2)}%`
            : "模型指标：等待训练报告";
    } catch (e) {
        status.className = "system-status error";
        status.textContent = "状态检查失败";
        const headerStatus = document.getElementById("headerStatus");
        headerStatus.textContent = "状态未知";
        headerStatus.className = "status-text error";
        status.title = e.message;
        console.error("系统状态检查失败:", e);
    }
}

function planItemsReady() {
    const cells = lastInventoryData?.cells || [];
    const requiredFields = [
        "inventory_as_of_date", "inventory_version", "on_hand", "confirmed_inbound",
        "reserved", "lead_time_days", "review_period_days", "safety_stock", "pack_size",
        "minimum_order_quantity"
    ];
    return cells.length > 0 && cells.every(cell => requiredFields.every(field =>
        cell[field] !== null && cell[field] !== undefined && cell[field] !== ""
    ));
}

function updatePlanAvailability() {
    const button = document.getElementById("savePlan");
    if (!button) return;
    const available = lastMetadata?.inventory_status === "fresh" &&
        lastInventoryData?.coverage?.status === "ok" && planItemsReady();
    button.disabled = !available;
    document.getElementById("planStatus").textContent = lastSavedPlanId
        ? `已保存草案：${lastSavedPlanId}`
        : (available ? "预测覆盖完整，可保存当前补货草案" : "需要新鲜库存快照、完整预测覆盖和库存明细后可保存");
}

function makePlanPayload() {
    const cells = lastInventoryData.cells;
    const inventoryDate = cells[0].inventory_as_of_date;
    return {
        name: document.getElementById("planName").value.trim() || "补货草案",
        as_of_date: lastMetadata.as_of_date,
        inventory_as_of_date: inventoryDate,
        data_version: lastMetadata.data_version,
        model_version: lastMetadata.model_version,
        inventory_version: lastMetadata.inventory_version,
        policy_version: "replenishment-v1",
        coverage: lastInventoryData.coverage,
        items: cells.map(cell => ({
            product_id: cell.product_id,
            store_id: cell.store_id,
            product_name: cell.product_name,
            store_name: cell.store_name,
            predicted_sales: cell.predicted_sales,
            suggested_purchase: cell.suggested_purchase,
            risk_level: cell.risk_level,
            on_hand: cell.on_hand,
            confirmed_inbound: cell.confirmed_inbound,
            reserved: cell.reserved,
            lead_time_days: cell.lead_time_days,
            review_period_days: cell.review_period_days,
            safety_stock: cell.safety_stock,
            pack_size: cell.pack_size,
            minimum_order_quantity: cell.minimum_order_quantity,
            inventory_version: cell.inventory_version,
            inventory_as_of_date: cell.inventory_as_of_date,
            window_demand: cell.window_demand,
            net_available: cell.net_available,
            target_stock: cell.target_stock,
            raw_replenishment: cell.raw_replenishment,
            adjustment_quantity: 0,
            adjustment_reason: ""
        })),
        adjustments: []
    };
}

async function savePlanDraft() {
    if (document.getElementById("savePlan").disabled) return;
    const button = document.getElementById("savePlan");
    button.disabled = true;
    document.getElementById("planStatus").textContent = "正在保存草案...";
    planRequestKey = planRequestKey || (window.crypto?.randomUUID?.() || `plan-${Date.now()}`);
    try {
        const saved = await api.createPlan(makePlanPayload(), planRequestKey);
        lastSavedPlanId = saved.plan_id;
        const exportLink = document.getElementById("exportPlan");
        exportLink.href = api.planExportUrl(lastSavedPlanId);
        exportLink.classList.remove("hidden");
        document.getElementById("planStatus").textContent =
            `${saved.created ? "已保存" : "已幂等恢复"}：${saved.plan_id}`;
        planRequestKey = null;
    } catch (e) {
        document.getElementById("planStatus").textContent = `保存失败：${e.message}`;
    } finally {
        updatePlanAvailability();
    }
}

async function refreshAll() {
    await Promise.all([loadDashboard(), loadSystemStatus()]);
}

window.showDashboardError = showDashboardError;
window.showEmptyState = showEmptyState;
window.addEventListener("DOMContentLoaded", init);
