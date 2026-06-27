/* 大屏主逻辑：初始化、加载、刷新 */
let storesCache = [];

async function init() {
    // 初始化所有图表
    SalesLineChart.init();
    InventoryHeatmap.init();
    CategoryPieChart.init();
    TopProductsChart.init();

    // 时钟
    updateClock();
    setInterval(updateClock, 1000);

    // 加载下拉框
    await loadSelectors();

    // 加载大屏数据
    await loadDashboard();

    // 隐藏加载遮罩
    document.getElementById("loading").classList.add("hidden");

    // 每 5 分钟刷新一次
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

async function loadSelectors() {
    try {
        const products = await api.getProducts();
        const productSel = document.getElementById("productSelect");
        productSel.innerHTML = products.products.map(p =>
            `<option value="${p.product_id}">${p.product_name}</option>`
        ).join("");

        // 门店列表从大屏接口获取（通过 inventory 间接获得）
        const inv = await api.getInventory();
        const storeMap = {};
        inv.cells.forEach(c => storeMap[c.store_id] = c.store_name);
        storesCache = Object.keys(storeMap).map(k => ({
            store_id: parseInt(k),
            store_name: storeMap[k]
        })).sort((a, b) => a.store_id - b.store_id);

        const storeSel = document.getElementById("storeSelect");
        storeSel.innerHTML = storesCache.map(s =>
            `<option value="${s.store_id}">${s.store_name}</option>`
        ).join("");

        // 切换商品/门店时刷新折线图
        productSel.addEventListener("change", () => {
            SalesLineChart.load(parseInt(productSel.value), parseInt(storeSel.value));
        });
        storeSel.addEventListener("change", () => {
            SalesLineChart.load(parseInt(productSel.value), parseInt(storeSel.value));
        });
    } catch (e) {
        console.error("加载下拉框失败:", e);
    }
}

async function loadDashboard() {
    const errorBanner = document.getElementById("errorBanner");
    errorBanner.classList.add("hidden");
    try {
        const dashboard = await api.getDashboard();
        // KPI
        KpiCards.render(dashboard.kpi);
        // 品类饼图
        CategoryPieChart.load(dashboard.category_sales);
        // Top 10
        TopProductsChart.load(dashboard.top_products);
        // 默认加载第一个商品的折线图
        const productSel = document.getElementById("productSelect");
        const storeSel = document.getElementById("storeSelect");
        if (productSel.value && storeSel.value) {
            SalesLineChart.load(parseInt(productSel.value), parseInt(storeSel.value));
        }
        // 库存热力图
        InventoryHeatmap.load();
    } catch (e) {
        console.error("大屏数据加载失败:", e);
        errorBanner.textContent = `数据加载失败: ${e.message}。请检查后端服务 (http://localhost:8000/health)`;
        errorBanner.classList.remove("hidden");
    }
}

window.addEventListener("DOMContentLoaded", init);
