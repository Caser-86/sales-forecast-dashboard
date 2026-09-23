/* KPI 卡片：数字滚动动画 */
const KpiCards = {
    animate(elId, target, suffix = "", duration = 1500) {
        const el = document.getElementById(elId);
        if (!el) return;
        const start = 0;
        const startTime = performance.now();
        const isFloat = !Number.isInteger(target);

        function update(now) {
            const t = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - t, 3);
            const val = start + (target - start) * eased;
            if (isFloat) {
                el.textContent = val.toFixed(1) + suffix;
            } else {
                el.textContent = Math.round(val).toLocaleString() + suffix;
            }
            if (t < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    },

    render(kpi) {
        this.animate("kpiTotalSales", kpi.total_sales);
        this.animate("kpiTotalPredicted", kpi.total_predicted);
        this.animate("kpiGrowth", kpi.growth_rate, "%");
        this.animate("kpiMape", kpi.mape, "%");
        this.animate("kpiAlert", kpi.alert_count);
    }
};
