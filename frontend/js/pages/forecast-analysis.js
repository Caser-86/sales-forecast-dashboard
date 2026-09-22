/* 预测分析：目录下钻、来源版本、历史/未来表格和安全 CSV 导出。 */
(function () {
    const state = {
        products: [],
        stores: [],
        detail: null,
        chart: null,
        loaded: false,
        loading: false,
    };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("forecastAnalysisStatus");
        target.textContent = message;
        target.className = `module-status ${tone}`.trim();
    }

    function fillSelect(selectId, items, valueKey, labelBuilder) {
        const select = byId(selectId);
        select.textContent = "";
        items.forEach(item => {
            const option = document.createElement("option");
            option.value = item[valueKey];
            option.textContent = labelBuilder(item);
            select.appendChild(option);
        });
    }

    function renderProducts() {
        const page = CatalogUtils.filterAndPage(state.products, byId("forecastCatalogSearch").value, 1, 1000);
        fillSelect("forecastProductSelect", page.items, "product_id", item => `#${item.product_id} ${item.product_name}`);
        const routeProduct = AppNavigation.getRouteState().scope.productId;
        if (routeProduct && page.items.some(item => item.product_id === routeProduct)) {
            byId("forecastProductSelect").value = String(routeProduct);
        }
    }

    function renderHistory(points) {
        const body = byId("forecastHistoryBody");
        body.textContent = "";
        points.slice(-30).forEach(point => {
            const row = document.createElement("tr");
            [point.date, point.sales, point.price, point.is_promotion ? "是" : "否"].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });
            body.appendChild(row);
        });
    }

    function renderForecast(points) {
        const body = byId("forecastFutureBody");
        body.textContent = "";
        points.forEach(point => {
            const row = document.createElement("tr");
            [point.date, point.predicted_sales, point.confidence_low, point.confidence_high].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });
            body.appendChild(row);
        });
    }

    function renderChart(history, forecast) {
        if (!state.chart) state.chart = echarts.init(byId("forecastAnalysisChart"));
        const dates = [...history.map(item => item.date), ...forecast.map(item => item.date)];
        state.chart.setOption({
            backgroundColor: "transparent",
            grid: { top: 30, right: 20, bottom: 45, left: 50 },
            tooltip: { trigger: "axis" },
            legend: { data: ["历史销量", "预测销量"], textStyle: { color: "#e0e0ff" } },
            xAxis: { type: "category", data: dates, axisLabel: { color: "#8a8db5", rotate: 30 } },
            yAxis: { type: "value", axisLabel: { color: "#8a8db5" } },
            series: [
                { name: "历史销量", type: "line", smooth: true, data: history.map(item => item.sales).concat(new Array(forecast.length).fill(null)) },
                { name: "预测销量", type: "line", smooth: true, data: new Array(Math.max(history.length - 1, 0)).fill(null).concat(history.length ? [history[history.length - 1].sales] : []).concat(forecast.map(item => item.predicted_sales)) },
            ],
        });
    }

    function renderDetail(detail) {
        const metadata = detail.metadata;
        const model = detail.model;
        const history = detail.sales.points || [];
        const forecast = detail.forecast.forecast || [];
        const baseline = model.metrics?.seasonal_naive_7d;
        const selected = model.metrics?.ensemble;
        const metricSamples = selected?.samples
            ?? selected?.mape_samples
            ?? model.backtest?.selected?.metrics?.samples
            ?? "--";
        byId("forecastSourceSummary").textContent = `来源：数据 ${metadata.data_version} · 模型 ${metadata.model_version} · 商品 #${detail.sales.product_id} · 门店 #${detail.sales.store_id} · 有效历史样本 ${history.length}，未来预测 ${forecast.length} 天。`;
        byId("forecastMetricSummary").textContent = `评估窗口：${model.split?.validation_days || "--"} 天验证；有效回测样本 ${metricSamples}；MAPE 只统计实际销量大于 0 的样本；当前策略 ${model.selected_model || "ensemble"}；基线 MAPE ${baseline?.mape?.toFixed(2) || "--"}%；当前模型 MAPE ${selected?.mape?.toFixed(2) || "--"}%。`;
        renderHistory(history);
        renderForecast(forecast);
        renderChart(history, forecast);
        byId("exportForecastCsv").disabled = false;
    }

    function csvCell(value) {
        let text = String(value ?? "");
        if (/^[=+\-@]/.test(text)) text = `'${text}`;
        return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
    }

    function downloadForecastCsv() {
        if (!state.detail) return;
        const rows = [["type", "date", "actual_sales", "predicted_sales", "confidence_low", "confidence_high", "price"]];
        state.detail.sales.points.forEach(point => rows.push(["history", point.date, point.sales, "", "", "", point.price]));
        state.detail.forecast.forecast.forEach(point => rows.push(["forecast", point.date, "", point.predicted_sales, point.confidence_low, point.confidence_high, ""]));
        const blob = new Blob(["\ufeff" + rows.map(row => row.map(csvCell).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `forecast-${state.detail.sales.product_id}-${state.detail.sales.store_id}.csv`;
        anchor.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
    }

    async function loadDetail() {
        const productId = Number(byId("forecastProductSelect").value);
        const storeId = Number(byId("forecastStoreSelect").value);
        if (!productId || !storeId) return;
        setStatus("明细加载中");
        byId("exportForecastCsv").disabled = true;
        try {
            const [sales, forecast, metadata, model] = await Promise.all([
                api.getSales(productId, storeId, 90),
                api.getForecast(productId, storeId),
                api.getMetadata(),
                api.getModelInfo(),
            ]);
            state.detail = { sales, forecast, metadata, model };
            renderDetail(state.detail);
            setStatus("明细已更新", "success");
        } catch (error) {
            state.detail = null;
            setStatus(error.message, "error");
            byId("forecastSourceSummary").textContent = "未知商品、门店或历史样本不足时不显示伪造的零值。";
        }
    }

    async function load(force = false) {
        if (state.loading || (state.loaded && !force)) return;
        state.loading = true;
        try {
            const [products, stores] = await Promise.all([api.getProducts(), api.getStores()]);
            state.products = products.products || [];
            state.stores = stores || [];
            renderProducts();
            fillSelect("forecastStoreSelect", state.stores, "store_id", item => `#${item.store_id} ${item.store_name}`);
            const routeStore = AppNavigation.getRouteState().scope.storeId;
            if (routeStore && state.stores.some(item => item.store_id === routeStore)) byId("forecastStoreSelect").value = String(routeStore);
            state.loaded = true;
            setStatus("目录已加载", "success");
            if (byId("forecastProductSelect").value && byId("forecastStoreSelect").value) await loadDetail();
        } catch (error) {
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    function init() {
        byId("forecastCatalogSearch").addEventListener("input", renderProducts);
        byId("loadForecastDetail").addEventListener("click", loadDetail);
        byId("exportForecastCsv").addEventListener("click", downloadForecastCsv);
        window.addEventListener("resize", () => state.chart?.resize());
    }

    window.ForecastAnalysisPage = { init, load, downloadForecastCsv };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
