/* 数据中心：真实 CSV 预检、候选版本和运行快照操作。 */
(function () {
    const state = {
        sales: { file: null, preview: null },
        inventory: { file: null, preview: null },
        catalog: null,
        loaded: false,
        loading: false,
    };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const element = byId("dataCenterStatus");
        element.textContent = message;
        element.className = `module-status ${tone}`.trim();
    }

    function renderPreview(kind, result) {
        const target = byId(`${kind}DatasetPreview`);
        const upload = byId(`upload${kind[0].toUpperCase()}${kind.slice(1)}Dataset`);
        upload.disabled = !result.valid;
        if (result.valid) {
            const summary = result.summary || {};
            target.textContent = `预检通过：${result.row_count} 行，日期 ${summary.date_start || summary.as_of_date || "--"} 至 ${summary.date_end || summary.as_of_date || "--"}`;
            target.className = "dataset-preview success";
            return;
        }
        const details = result.errors.slice(0, 8).map(item =>
            `第 ${item.row} 行${item.column ? ` [${item.column}]` : ""}：${item.message}`
        );
        target.textContent = `预检失败：${result.error_count} 个问题${result.truncated ? "（已限制展示数量）" : ""}。 ${details.join("；")}`;
        target.className = "dataset-preview error";
    }

    async function preview(kind) {
        const item = state[kind];
        if (!item.file) {
            renderPreview(kind, { valid: false, error_count: 1, truncated: false, errors: [{ row: 1, column: "", message: "请先选择 CSV 文件" }] });
            return;
        }
        setStatus(`${kind === "sales" ? "销售" : "库存"}文件预检中`);
        try {
            const text = await item.file.text();
            item.preview = { text, result: await api.previewDataset(kind, text, item.file.name) };
            renderPreview(kind, item.preview.result);
            setStatus(item.preview.result.valid ? "预检通过，可保存候选" : "预检未通过，请修正文件", item.preview.result.valid ? "success" : "error");
        } catch (error) {
            setStatus(error.message, "error");
        }
    }

    async function upload(kind) {
        const item = state[kind];
        if (!item.file || !item.preview?.result?.valid) return;
        setStatus(`${kind === "sales" ? "销售" : "库存"}候选版本保存中`);
        try {
            const result = await api.uploadDataset(kind, item.preview.text, item.file.name);
            const target = byId(`${kind}DatasetPreview`);
            target.textContent = `候选版本已保存：${result.dataset_id || result.inventory_id}。当前活动版本未改变。`;
            target.className = "dataset-preview success";
            item.preview = null;
            byId(`upload${kind[0].toUpperCase()}${kind.slice(1)}Dataset`).disabled = true;
            await load(true);
        } catch (error) {
            setStatus(error.message, "error");
        }
    }

    function addOption(select, value, label) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.appendChild(option);
    }

    function renderSelectors(catalog) {
        const active = catalog.active || {};
        const dataSelect = byId("runtimeDataVersion");
        const modelSelect = byId("runtimeModelVersion");
        const inventorySelect = byId("runtimeInventoryVersion");
        [dataSelect, modelSelect, inventorySelect].forEach(select => { select.textContent = ""; });
        addOption(dataSelect, active.data_version || "legacy", `当前：${active.data_version || "legacy"}`);
        (catalog.sales || []).forEach(item => addOption(dataSelect, item.dataset_id, item.dataset_id));
        addOption(modelSelect, active.model_version || "legacy", `当前：${active.model_version || "legacy"}`);
        (catalog.models || []).forEach(item => addOption(modelSelect, item.model_id, item.model_id));
        addOption(inventorySelect, active.inventory_version || "legacy", `当前：${active.inventory_version || "legacy"}`);
        (catalog.inventory || []).forEach(item => addOption(inventorySelect, item.inventory_id, item.inventory_id));
        [dataSelect, modelSelect, inventorySelect].forEach(select => {
            const values = [...select.options].map(option => option.value);
            select.value = values[0];
        });
    }

    function renderVersions(catalog) {
        const body = byId("datasetVersionsBody");
        body.textContent = "";
        const active = catalog.active || {};
        const rows = [
            ...(catalog.sales || []).map(item => ({ type: "销售", id: item.dataset_id, range: `${item.date_start} 至 ${item.date_end}`, created: item.created_at_utc, active: item.dataset_id === active.data_version })),
            ...(catalog.inventory || []).map(item => ({ type: "库存", id: item.inventory_id, range: `截至 ${item.as_of_date}`, created: item.created_at_utc, active: item.inventory_id === active.inventory_version })),
            ...(catalog.models || []).map(item => ({ type: "模型", id: item.model_id, range: `数据 ${item.data_version}`, created: item.created_at_utc, active: item.model_id === active.model_version })),
            ...(catalog.runtime_snapshots || []).map(item => ({ type: "运行快照", id: item.snapshot_id, range: `${item.data_version} / ${item.model_version}`, created: item.created_at_utc, active: item.active })),
        ];
        if (!rows.length) {
            const empty = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 5;
            cell.textContent = "暂无候选版本；可先下载模板并上传。";
            empty.appendChild(cell);
            body.appendChild(empty);
            return;
        }
        rows.forEach(row => {
            const tr = document.createElement("tr");
            [row.type, row.id, row.range, row.created || "--", row.active ? "活动" : "候选"].forEach(value => {
                const td = document.createElement("td");
                td.textContent = value || "--";
                tr.appendChild(td);
            });
            body.appendChild(tr);
        });
    }

    async function publishSnapshot() {
        const payload = {
            data_version: byId("runtimeDataVersion").value,
            model_version: byId("runtimeModelVersion").value,
            inventory_version: byId("runtimeInventoryVersion").value,
            policy_version: "policy-v1",
        };
        setStatus("运行快照兼容性校验中");
        try {
            const snapshot = await api.publishRuntimeSnapshot(payload);
            const activate = window.confirm(`候选快照 ${snapshot.snapshot_id} 已生成。现在激活吗？`);
            if (activate) {
                await api.activateRuntimeSnapshot(snapshot.snapshot_id);
                byId("runtimeSnapshotPreview").textContent = `已激活 ${snapshot.snapshot_id}，页面将按同一快照读取。`;
            } else {
                byId("runtimeSnapshotPreview").textContent = `候选快照 ${snapshot.snapshot_id} 已生成，当前活动版本未改变。`;
            }
            byId("runtimeSnapshotPreview").className = "dataset-preview success";
            await load(true);
        } catch (error) {
            byId("runtimeSnapshotPreview").textContent = error.message;
            byId("runtimeSnapshotPreview").className = "dataset-preview error";
            setStatus(error.message, "error");
        }
    }

    async function load(force = false) {
        if (state.loading || (state.loaded && !force)) return;
        state.loading = true;
        try {
            state.catalog = await api.getDatasets();
            state.loaded = true;
            renderSelectors(state.catalog);
            renderVersions(state.catalog);
            setStatus("版本清单已更新", "success");
        } catch (error) {
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    function init() {
        document.querySelectorAll("[data-template-kind]").forEach(link => {
            link.href = api.datasetTemplateUrl(link.dataset.templateKind);
        });
        ["sales", "inventory"].forEach(kind => {
            const input = byId(`${kind}DatasetFile`);
            input.addEventListener("change", () => {
                state[kind].file = input.files[0] || null;
                byId(`${kind}DatasetFileName`).textContent = state[kind].file?.name || "尚未选择文件";
                state[kind].preview = null;
                byId(`upload${kind[0].toUpperCase()}${kind.slice(1)}Dataset`).disabled = true;
            });
            byId(`preview${kind[0].toUpperCase()}${kind.slice(1)}Dataset`).addEventListener("click", () => preview(kind));
            byId(`upload${kind[0].toUpperCase()}${kind.slice(1)}Dataset`).addEventListener("click", () => upload(kind));
        });
        byId("publishRuntimeSnapshot").addEventListener("click", publishSnapshot);
        byId("refreshDatasetCatalog").addEventListener("click", () => load(true));
    }

    window.DataCenterPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
