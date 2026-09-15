/* 大屏主逻辑：初始化、筛选、刷新与可见状态反馈 */
let productsCache = [];
let storesCache = [];

async function init() {
    SalesLineChart.init();
    InventoryHeatmap.init();
    CategoryPieChart.init();
    TopProductsChart.init();

    updateClock();
    setInterval(updateClock, 1000);

    try {
        await loadSelectors();
        await Promise.all([loadSystemStatus(), loadDashboard()]);
    } catch (e) {
        showDashboardError(`初始化失败: ${e.message}`);
    } finally {
        document.getElementById("loading").classList.add("hidden");
    }

    setInterval(loadDashboard, 5 * 60 * 1000);
}

function updateClock() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    document.getElementById("currentDate").textContent =
        `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
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
    const [products, inv] = await Promise.all([
        api.getProducts(),
        api.getInventory()
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

    const storeMap = {};
    (inv.cells || []).forEach(c => { storeMap[c.store_id] = c.store_name; });
    storesCache = Object.keys(storeMap).map(id => ({
        store_id: Number(id),
        store_name: storeMap[id]
    })).sort((a, b) => a.store_id - b.store_id);
    populateSelect("storeSelect", storesCache, "store_id", s => s.store_name);
    populateSelect(
        "scopeStoreSelect",
        storesCache,
        "store_id",
        s => `#${s.store_id} ${s.store_name}`,
        "全部门店"
    );

    document.getElementById("productSelect").addEventListener("change", loadTrend);
    document.getElementById("storeSelect").addEventListener("change", loadTrend);
    document.getElementById("scopeProductSelect").addEventListener("change", loadDashboard);
    document.getElementById("scopeStoreSelect").addEventListener("change", loadDashboard);
    document.getElementById("refreshDashboard").addEventListener("click", refreshAll);
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
    const errorBanner = document.getElementById("errorBanner");
    errorBanner.textContent = `${message}。请检查后端服务 (http://localhost:8000/health)`;
    errorBanner.classList.remove("hidden");
}

function clearDashboardError() {
    document.getElementById("errorBanner").classList.add("hidden");
}

function showEmptyState(message = "") {
    const emptyState = document.getElementById("emptyState");
    emptyState.textContent = message || "当前筛选范围暂无可展示数据";
    emptyState.classList.toggle("hidden", !message);
}

async function loadDashboard() {
    setBusy(true);
    clearDashboardError();
    const scope = currentScope();
    try {
        const dashboard = await api.getDashboard(scope);
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

        await Promise.all([loadTrend(), InventoryHeatmap.load(scope)]);
    } catch (e) {
        console.error("大屏数据加载失败:", e);
        showDashboardError(`数据加载失败: ${e.message}`);
    } finally {
        setBusy(false);
    }
}

async function loadSystemStatus() {
    const status = document.getElementById("systemStatus");
    status.className = "system-status pending";
    status.textContent = "状态检查中";
    try {
        const [model, quality] = await Promise.all([
            api.getModelInfo(),
            api.getDataQuality()
        ]);
        const healthy = model.status === "ready" && quality.status === "healthy";
        status.className = `system-status ${healthy ? "healthy" : "warning"}`;
        status.textContent = healthy ? "模型与数据正常" : "需要关注";
        status.title = `模型：${model.status}；数据：${quality.status}`;
        const ensembleMape = model.metrics?.ensemble?.mape;
        const baselineMape = model.metrics?.seasonal_naive_7d?.mape;
        const summary = document.getElementById("modelSummary");
        summary.textContent = ensembleMape !== undefined && baselineMape !== undefined
            ? `模型 MAPE ${ensembleMape.toFixed(2)}% · 基线 ${baselineMape.toFixed(2)}%`
            : "模型指标：等待训练报告";
    } catch (e) {
        status.className = "system-status error";
        status.textContent = "状态检查失败";
        status.title = e.message;
        console.error("系统状态检查失败:", e);
    }
}

async function refreshAll() {
    await Promise.all([loadDashboard(), loadSystemStatus()]);
}

window.showDashboardError = showDashboardError;
window.showEmptyState = showEmptyState;
window.addEventListener("DOMContentLoaded", init);
