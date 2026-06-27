/* Top 10 商品销量排行 + 采购建议 */
const TopProductsChart = {
    chart: null,

    init() {
        this.chart = echarts.init(document.getElementById("topProducts"));
        this.chart.setOption({
            backgroundColor: "transparent",
            grid: { top: 20, right: 180, bottom: 20, left: 130 },
            tooltip: {
                trigger: "axis",
                axisPointer: { type: "shadow" },
                backgroundColor: "rgba(26, 27, 58, 0.95)",
                borderColor: "#4a4dc4",
                textStyle: { color: "#e0e0ff" },
                formatter: function (params) {
                    const d = params[0].data.detail;
                    return `${d.product_name}<br/>历史销量: ${d.sales}<br/>预测销量: ${d.predicted}<br/>建议采购: ${d.suggested}<br/>分级: ${d.abc}`;
                }
            },
            xAxis: {
                type: "value",
                axisLine: { lineStyle: { color: "#4a4dc4" } },
                axisLabel: { color: "#8a8db5" },
                splitLine: { lineStyle: { color: "rgba(74, 77, 196, 0.2)" } }
            },
            yAxis: {
                type: "category",
                data: [],
                axisLine: { lineStyle: { color: "#4a4dc4" } },
                axisLabel: { color: "#e0e0ff", fontSize: 11 }
            },
            series: [
                {
                    type: "bar",
                    data: [],
                    barWidth: 14,
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                            { offset: 0, color: "#6c5ce7" },
                            { offset: 1, color: "#00e5ff" }
                        ]),
                        borderRadius: [0, 4, 4, 0]
                    },
                    label: {
                        show: true,
                        position: "right",
                        color: "#00e5ff",
                        fontSize: 11
                    }
                },
                {
                    type: "custom",
                    renderItem: function (params, api) {
                        const idx = api.value(0);
                        return {
                            type: "text",
                            style: {
                                text: api.value(1),
                                x: api.coord([0, idx])[0] + 460,
                                y: api.coord([0, idx])[1],
                                fill: "#ffd93d",
                                font: "12px Microsoft YaHei"
                            }
                        };
                    }
                }
            ]
        });
        window.addEventListener("resize", () => this.chart.resize());
    },

    async load(topProducts) {
        if (!topProducts || !topProducts.length) return;
        // 从小到大排列（ECharts 横向柱状图从下到上）
        const sorted = [...topProducts].sort((a, b) => a.sales - b.sales);
        const names = sorted.map(p => p.product_name.length > 8
            ? p.product_name.slice(0, 8) + "…"
            : p.product_name);
        const data = sorted.map(p => ({
            value: p.sales,
            detail: p
        }));

        this.chart.setOption({
            yAxis: { data: names },
            series: [{ data }]
        });
    }
};
