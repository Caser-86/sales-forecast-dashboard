/* 演示系统：只读运行上下文、版本和数据质量。 */
(function () {
    const state = { loaded: false, loading: false };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("systemPageStatus");
        target.textContent = message;
        target.className = `module-status ${tone}`.trim();
    }

    function addSummary(label, value, tone = "") {
        const item = document.createElement("div");
        item.className = "system-summary-item";
        const name = document.createElement("span");
        name.textContent = label;
        const result = document.createElement("strong");
        result.textContent = value;
        result.className = tone;
        item.append(name, result);
        byId("systemSummary").appendChild(item);
    }

    function render(data) {
        byId("systemSummary").textContent = "";
        addSummary("数据状态", data.metadata.data_status, data.metadata.data_status === "ready" ? "healthy" : "warning");
        addSummary("模型状态", data.metadata.model_status, data.metadata.model_status === "ready" ? "healthy" : "warning");
        addSummary("库存状态", data.metadata.inventory_status, data.metadata.inventory_status === "fresh" ? "healthy" : "warning");
        addSummary("质量状态", data.quality.status, data.quality.status === "healthy" ? "healthy" : "warning");
        addSummary("活动快照", data.datasets.active_runtime?.snapshot_id || "未启用");

        const runtimeBody = byId("systemRuntimeBody");
        runtimeBody.textContent = "";
        const runtime = data.datasets.active_runtime;
        const runtimeRows = runtime
            ? [["销售数据", runtime.data_version], ["模型", runtime.model_version], ["库存", runtime.inventory_version], ["策略", runtime.policy_version]]
            : [["销售数据", data.metadata.data_version], ["模型", data.metadata.model_version], ["库存", data.metadata.inventory_version]];
        runtimeRows.forEach(values => {
            const row = document.createElement("tr");
            values.forEach(value => { const cell = document.createElement("td"); cell.textContent = value; row.appendChild(cell); });
            runtimeBody.appendChild(row);
        });

        const qualityBody = byId("systemQualityBody");
        qualityBody.textContent = "";
        [
            ["来源", data.quality.source],
            ["数据行数", data.quality.rows],
            ["日期范围", `${data.quality.date_start || "--"} 至 ${data.quality.date_end || "--"}`],
            ["重复键行", data.quality.duplicate_rows],
            ["缺失值", Object.values(data.quality.missing_values || {}).reduce((sum, value) => sum + value, 0)],
            ["问题", (data.quality.issues || []).join("；") || "无"],
        ].forEach(values => {
            const row = document.createElement("tr");
            values.forEach(value => { const cell = document.createElement("td"); cell.textContent = value; row.appendChild(cell); });
            qualityBody.appendChild(row);
        });
    }

    async function load(force = false) {
        if (state.loading || (state.loaded && !force)) return;
        state.loading = true;
        setStatus("加载系统状态中");
        try {
            const [metadata, quality, datasets] = await Promise.all([api.getMetadata(), api.getDataQuality(), api.getDatasets()]);
            render({ metadata, quality, datasets });
            state.loaded = true;
            setStatus("系统状态已更新", "success");
        } catch (error) {
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    function init() { byId("refreshSystemPage").addEventListener("click", () => load(true)); }

    window.SystemPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
