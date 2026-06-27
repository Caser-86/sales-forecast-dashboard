/* 销量折线图：历史 + 预测 + 置信区间 */
const SalesLineChart = {
    chart: null,

    init() {
        this.chart = echarts.init(document.getElementById("salesLine"));
        this.chart.setOption({
            backgroundColor: "transparent",
            grid: { top: 40, right: 70, bottom: 50, left: 60 },
            tooltip: {
                trigger: "axis",
                backgroundColor: "rgba(26, 27, 58, 0.95)",
                borderColor: "#4a4dc4",
                textStyle: { color: "#e0e0ff" }
            },
            legend: {
                data: ["历史销量", "预测销量", "置信区间", "价格"],
                textStyle: { color: "#e0e0ff" },
                top: 5
            },
            xAxis: {
                type: "category",
                data: [],
                axisLine: { lineStyle: { color: "#4a4dc4" } },
                axisLabel: { color: "#8a8db5", fontSize: 10, rotate: 30 }
            },
            yAxis: [
                {
                    type: "value",
                    name: "销量",
                    nameTextStyle: { color: "#8a8db5" },
                    axisLine: { lineStyle: { color: "#4a4dc4" } },
                    axisLabel: { color: "#8a8db5" },
                    splitLine: { lineStyle: { color: "rgba(74, 77, 196, 0.2)" } }
                },
                {
                    type: "value",
                    name: "价格",
                    nameTextStyle: { color: "#8a8db5" },
                    axisLine: { lineStyle: { color: "#4a4dc4" } },
                    axisLabel: { color: "#8a8db5" },
                    splitLine: { show: false }
                }
            ],
            series: [
                {
                    name: "历史销量",
                    type: "line",
                    smooth: true,
                    symbol: "none",
                    data: [],
                    itemStyle: { color: "#6c5ce7" },
                    lineStyle: { width: 2 }
                },
                {
                    name: "预测销量",
                    type: "line",
                    smooth: true,
                    symbol: "none",
                    data: [],
                    itemStyle: { color: "#00e5ff" },
                    lineStyle: { width: 2, type: "dashed" }
                },
                {
                    name: "置信区间",
                    type: "line",
                    smooth: true,
                    symbol: "none",
                    data: [],
                    lineStyle: { opacity: 0 },
                    areaStyle: { color: "rgba(0, 229, 255, 0.12)" },
                    stack: "confidence"
                },
                {
                    name: "价格",
                    type: "line",
                    yAxisIndex: 1,
                    smooth: true,
                    symbol: "none",
                    data: [],
                    itemStyle: { color: "#ffd93d" },
                    lineStyle: { width: 1.5, opacity: 0.6 }
                }
            ]
        });
        window.addEventListener("resize", () => this.chart.resize());
    },

    async load(productId, storeId) {
        try {
            const [sales, forecast] = await Promise.all([
                api.getSales(productId, storeId, 90),
                api.getForecast(productId, storeId)
            ]);

            // 合并日期轴
            const histDates = sales.points.map(p => p.date);
            const foreDates = forecast.forecast.map(p => p.date);
            const allDates = [...histDates, ...foreDates];

            // 历史销量
            const histSales = sales.points.map(p => p.sales);
            // 预测序列：历史段为 null，预测段补齐
            const foreSales = new Array(histDates.length - 1).fill(null)
                .concat([histSales[histSales.length - 1]])
                .concat(forecast.forecast.map(p => p.predicted_sales));
            // 置信区间（上下界）
            const confLow = new Array(histDates.length - 1).fill(null)
                .concat([histSales[histSales.length - 1]])
                .concat(forecast.forecast.map(p => p.confidence_low));
            const confHigh = new Array(histDates.length - 1).fill(null)
                .concat([histSales[histSales.length - 1]])
                .concat(forecast.forecast.map(p => p.confidence_high));
            // 置信带：用 high-low 表示宽度
            const confBand = confHigh.map((h, i) => h === null ? null : (h - confLow[i]));

            // 价格
            const histPrice = sales.points.map(p => p.price);

            this.chart.setOption({
                xAxis: { data: allDates },
                series: [
                    { data: histSales },
                    { data: foreSales },
                    { data: confLow },
                    { data: histPrice.concat(new Array(foreDates.length).fill(null)) }
                ]
            });
        } catch (e) {
            console.error("销量趋势加载失败:", e);
        }
    }
};
