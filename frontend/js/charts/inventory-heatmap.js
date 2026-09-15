/* 库存热力图：商品 × 门店，按风险等级着色 */
const InventoryHeatmap = {
    chart: null,
    requestId: 0,
    controller: null,

    init() {
        this.chart = echarts.init(document.getElementById("inventoryHeatmap"));
        this.chart.setOption({
            backgroundColor: "transparent",
            grid: { top: 30, right: 30, bottom: 60, left: 120 },
            tooltip: {
                position: "top",
                backgroundColor: "rgba(26, 27, 58, 0.95)",
                borderColor: "#4a4dc4",
                textStyle: { color: "#e0e0ff" },
                formatter: function (p) {
                    const d = p.data;
                    return `${escapeHtml(d.product_name)}<br/>${escapeHtml(d.store_name)}<br/>预测销量: ${d.predicted}<br/>建议采购: ${d.suggested}<br/>分级: ${escapeHtml(d.abc)}`;
                }
            },
            xAxis: {
                type: "category",
                data: [],
                axisLabel: { color: "#8a8db5", fontSize: 10, rotate: 40 },
                axisLine: { lineStyle: { color: "#4a4dc4" } },
                splitArea: { show: false }
            },
            yAxis: {
                type: "category",
                data: [],
                axisLabel: { color: "#8a8db5" },
                axisLine: { lineStyle: { color: "#4a4dc4" } },
                splitArea: { show: false }
            },
            visualMap: {
                min: 0,
                max: 2,
                show: true,
                orient: "horizontal",
                left: "center",
                bottom: 5,
                textStyle: { color: "#e0e0ff" },
                inRange: {
                    color: ["#6bcf7f", "#ffd93d", "#ff6b6b"]
                },
                text: ["高风险", "低风险"],
                textStyle: { color: "#e0e0ff" }
            },
            series: [{
                type: "heatmap",
                data: [],
                label: { show: false },
                emphasis: {
                    itemStyle: { shadowBlur: 10, shadowColor: "rgba(0, 229, 255, 0.5)" }
                }
            }]
        });
        window.addEventListener("resize", () => this.chart.resize());
    },

    async load(scope = {}) {
        const requestId = ++this.requestId;
        this.controller?.abort();
        this.controller = new AbortController();
        const signal = this.controller.signal;
        try {
            const inv = await api.getInventory(scope, { signal });
            if (requestId !== this.requestId) return;
            const cells = inv.cells;
            if (!cells.length) {
                this.chart.setOption({
                    xAxis: { data: [] },
                    yAxis: { data: [] },
                    series: [{ data: [] }]
                });
                return;
            }

            const products = [...new Set(cells.map(c => c.product_id))].sort((a, b) => a - b);
            const stores = [...new Set(cells.map(c => c.store_id))].sort((a, b) => a - b);
            const productName = {};
            const storeName = {};
            cells.forEach(c => {
                productName[c.product_id] = c.product_name;
                storeName[c.store_id] = c.store_name;
            });

            // 风险等级数值：high=2, medium=1, low=0
            const riskMap = { high: 2, medium: 1, low: 0 };
            const data = cells.map(c => ({
                value: [products.indexOf(c.product_id), stores.indexOf(c.store_id), riskMap[c.risk_level]],
                product_name: c.product_name,
                store_name: c.store_name,
                predicted: c.predicted_sales,
                suggested: c.suggested_purchase,
                abc: c.abc_class
            }));

            this.chart.setOption({
                xAxis: { data: products.map(p => `#${p} ${productName[p].slice(0, 6)}`) },
                yAxis: { data: stores.map(s => storeName[s]) },
                series: [{ data }]
            });
        } catch (e) {
            if (e.name === "AbortError") return;
            console.error("库存热力图加载失败:", e);
            window.showDashboardError?.(`库存热力图加载失败: ${e.message}`);
            throw e;
        } finally {
            if (requestId === this.requestId) this.controller = null;
        }
    }
};
