/* 品类销售占比饼图（环形 + 中心总额） */
const CategoryPieChart = {
    chart: null,

    init() {
        this.chart = echarts.init(document.getElementById("categoryPie"));
        this.chart.setOption({
            backgroundColor: "transparent",
            tooltip: {
                trigger: "item",
                backgroundColor: "rgba(26, 27, 58, 0.95)",
                borderColor: "#4a4dc4",
                textStyle: { color: "#e0e0ff" },
                formatter: "{b}: {c} ({d}%)"
            },
            legend: {
                bottom: 5,
                textStyle: { color: "#e0e0ff" },
                icon: "circle"
            },
            series: [{
                type: "pie",
                radius: ["45%", "70%"],
                center: ["50%", "45%"],
                avoidLabelOverlap: false,
                itemStyle: {
                    borderColor: "#0d0e2c",
                    borderWidth: 2
                },
                label: {
                    show: true,
                    color: "#e0e0ff",
                    formatter: "{b}\n{d}%"
                },
                labelLine: { lineStyle: { color: "#4a4dc4" } },
                emphasis: {
                    label: { show: true, fontSize: 16, fontWeight: "bold" }
                },
                data: []
            }],
            graphic: {
                type: "text",
                left: "center",
                top: "40%",
                style: {
                    text: "总销售额\n0",
                    fill: "#00e5ff",
                    font: "bold 16px Microsoft YaHei",
                    textAlign: "center"
                }
            }
        });
        window.addEventListener("resize", () => this.chart.resize());
    },

    async load(categorySales) {
        if (!categorySales || !categorySales.length) {
            this.chart.setOption({
                series: [{ data: [] }],
                graphic: { style: { text: "当前范围\n暂无数据" } }
            });
            return;
        }
        const colors = ["#6c5ce7", "#00e5ff", "#ffd93d", "#6bcf7f", "#ff6b6b"];
        const data = categorySales.map((c, i) => ({
            name: c.category,
            value: c.sales,
            itemStyle: { color: colors[i % colors.length] }
        }));
        const total = categorySales.reduce((s, c) => s + c.sales, 0);

        this.chart.setOption({
            series: [{ data }],
            graphic: {
                style: {
                    text: `总销售额\n${total.toLocaleString()}`
                }
            }
        });
    }
};
