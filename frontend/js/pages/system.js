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

    function renderScenario(data) {
        const select = byId("demoScenarioSelect");
        select.textContent = "";
        const scenarios = data.scenarios?.scenarios || [];
        scenarios.forEach(scenario => {
            const option = document.createElement("option");
            option.value = scenario.name;
            option.textContent = scenario.label;
            select.appendChild(option);
        });
        const active = data.scenarios?.active;
        if (active) select.value = active;
        const current = data.scenarios?.scenario;
        byId("demoScenarioDescription").textContent = current
            ? `${current.label}：${current.description} 预期状态：${current.expected_status}`
            : "当前服务未绑定独立 DEMO_ROOT，场景控制不可用。";
        const enabled = Boolean(active && DemoAuth.getUser()?.role === "admin");
        ["demoScenarioSelect", "applyDemoScenario", "createDemoBackup", "createDiagnosticPackage", "demoBackupSelect", "restoreDemoBackup"]
            .forEach(id => { byId(id).disabled = !enabled; });
    }

    function renderArtifacts(artifacts) {
        const select = byId("demoBackupSelect");
        select.textContent = "";
        (artifacts?.backups || []).forEach(name => {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            select.appendChild(option);
        });
        byId("restoreDemoBackup").disabled = !select.options.length || DemoAuth.getUser()?.role !== "admin";
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
        renderScenario(data);
        renderArtifacts(data.artifacts);
    }

    async function load(force = false) {
        if (state.loading || (state.loaded && !force)) return;
        state.loading = true;
        setStatus("加载系统状态中");
        try {
            const [metadata, quality, datasets] = await Promise.all([api.getMetadata(), api.getDataQuality(), api.getDatasets()]);
            let scenarios = null;
            let artifacts = { backups: [], diagnostics: [] };
            try {
                [scenarios, artifacts] = await Promise.all([api.getDemoScenarios(), api.getDemoArtifacts()]);
                byId("demoScenarioStatus").textContent = "本地演示可用";
            } catch (_) {
                byId("demoScenarioStatus").textContent = "仅只读模式";
            }
            render({ metadata, quality, datasets, scenarios, artifacts });
            state.loaded = true;
            setStatus("系统状态已更新", "success");
        } catch (error) {
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    function setArtifactStatus(message, tone = "") {
        const target = byId("demoArtifactStatus");
        target.textContent = message;
        target.className = `dataset-preview ${tone}`.trim();
    }

    async function refreshArtifacts() {
        try { renderArtifacts(await api.getDemoArtifacts()); } catch (error) { setArtifactStatus(error.message, "error"); }
    }

    function init() {
        byId("refreshSystemPage").addEventListener("click", () => load(true));
        byId("applyDemoScenario").addEventListener("click", async () => {
            const name = byId("demoScenarioSelect").value;
            if (!name || !window.confirm("切换场景会更新活动运行快照，是否继续？")) return;
            setArtifactStatus("正在切换演示场景");
            try { await api.switchDemoScenario(name, true); setArtifactStatus("场景已切换", "success"); await load(true); }
            catch (error) { setArtifactStatus(error.message, "error"); }
        });
        byId("createDemoBackup").addEventListener("click", async () => {
            setArtifactStatus("正在创建备份");
            try { const result = await api.createDemoBackup(); setArtifactStatus(`备份已创建：${result.artifact_name}`, "success"); await refreshArtifacts(); }
            catch (error) { setArtifactStatus(error.message, "error"); }
        });
        byId("createDiagnosticPackage").addEventListener("click", async () => {
            setArtifactStatus("正在生成脱敏诊断包");
            try { const result = await api.createDiagnosticPackage(); setArtifactStatus(`诊断包已创建：${result.artifact_name}`, "success"); await refreshArtifacts(); }
            catch (error) { setArtifactStatus(error.message, "error"); }
        });
        byId("restoreDemoBackup").addEventListener("click", async () => {
            const name = byId("demoBackupSelect").value;
            if (!name || !window.confirm("恢复备份会覆盖当前演示状态，是否继续？")) return;
            setArtifactStatus("正在恢复演示备份");
            try { await api.restoreDemoBackup(name); setArtifactStatus("备份已恢复，请刷新系统状态", "success"); await load(true); }
            catch (error) { setArtifactStatus(error.message, "error"); }
        });
    }

    window.SystemPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
