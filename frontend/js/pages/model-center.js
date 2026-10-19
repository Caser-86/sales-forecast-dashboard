/* 模型中心：候选模型、持久化训练任务和人工激活。 */
(function () {
    const state = {
        catalog: null,
        loaded: false,
        loading: false,
        pollTimer: null,
        modelPage: 1,
        modelPageSize: 10,
        jobPage: 1,
        jobPageSize: 10,
    };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("modelCenterStatus");
        target.textContent = message;
        target.className = `module-status ${tone}`.trim();
    }

    function formatMetric(metrics) {
        if (!metrics || typeof metrics !== "object") return "--";
        const selected = metrics.ensemble || metrics.lightgbm || metrics.lstm || Object.values(metrics)[0];
        if (!selected) return "--";
        return `MAPE ${Number(selected.mape).toFixed(2)}% / RMSE ${Number(selected.rmse).toFixed(2)}`;
    }

    function renderModels(catalog) {
        const body = byId("modelVersionsBody");
        body.textContent = "";
        const models = catalog.models || [];
        const pageCount = Math.max(1, Math.ceil(models.length / state.modelPageSize));
        if (state.modelPage > pageCount) {
            state.modelPage = pageCount;
            return renderModels(catalog);
        }
        const start = models.length ? (state.modelPage - 1) * state.modelPageSize + 1 : 0;
        const end = Math.min(state.modelPage * state.modelPageSize, models.length);
        byId("modelVersionSummary").textContent =
            `模型 ${start}-${end}/${models.length} · 第 ${state.modelPage}/${pageCount} 页`;
        byId("modelVersionPrev").disabled = state.modelPage <= 1;
        byId("modelVersionNext").disabled = state.modelPage >= pageCount;
        if (!models.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 7;
            cell.textContent = "暂无通过校验的模型包；可先发起候选训练。";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }
        models.slice(start - 1, end).forEach(model => {
            const row = document.createElement("tr");
            [
                model.model_id,
                model.data_version || "legacy",
                model.selected_strategy || "--",
                formatMetric(model.metrics),
                `${model.artifact_count || 0} 个产物 / ${(model.package_checksum || "--").slice(0, 12)}`,
                model.active ? "活动" : (model.publishable ? "候选可发布" : "数据不兼容"),
            ].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });
            const action = document.createElement("td");
            if (!model.active && model.publishable) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "dataset-table-action model-activate";
                button.dataset.modelId = model.model_id;
                button.textContent = "人工激活";
                action.appendChild(button);
            } else {
                action.textContent = model.active ? "当前活动" : "不可发布";
            }
            row.appendChild(action);
            body.appendChild(row);
        });
    }

    function renderJobs(catalog) {
        const body = byId("modelJobsBody");
        body.textContent = "";
        const jobs = catalog.jobs || [];
        const pageCount = Math.max(1, Math.ceil(jobs.length / state.jobPageSize));
        if (state.jobPage > pageCount) {
            state.jobPage = pageCount;
            return renderJobs(catalog);
        }
        const start = jobs.length ? (state.jobPage - 1) * state.jobPageSize + 1 : 0;
        const end = Math.min(state.jobPage * state.jobPageSize, jobs.length);
        byId("modelJobSummary").textContent =
            `任务 ${start}-${end}/${jobs.length} · 第 ${state.jobPage}/${pageCount} 页`;
        byId("modelJobPrev").disabled = state.jobPage <= 1;
        byId("modelJobNext").disabled = state.jobPage >= pageCount;
        if (!jobs.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 7;
            cell.textContent = "暂无训练任务。";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }
        jobs.slice(start - 1, end).forEach(job => {
            const row = document.createElement("tr");
            [
                job.job_id,
                job.phase,
                `${job.input_data_version} / ${job.input_model_version}`,
                job.created_at || "--",
                job.status,
                job.error_message || "--",
            ].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });
            const action = document.createElement("td");
            if (["failed", "interrupted"].includes(job.status)) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "dataset-table-action model-job-retry";
                button.dataset.jobId = job.job_id;
                button.textContent = "重试任务";
                action.appendChild(button);
            } else if (["queued", "running"].includes(job.status)) {
                action.textContent = "处理中";
            } else {
                action.textContent = job.status === "succeeded" ? "已完成" : "--";
            }
            row.appendChild(action);
            body.appendChild(row);
        });
    }

    function schedulePoll(catalog) {
        window.clearTimeout(state.pollTimer);
        if ((catalog.jobs || []).some(job => ["queued", "running"].includes(job.status))) {
            state.pollTimer = window.setTimeout(() => load(true), 3000);
        }
    }

    async function load(force = false) {
        if (state.loading || (state.loaded && !force)) return;
        state.loading = true;
        if (force) {
            state.modelPage = 1;
            state.jobPage = 1;
        }
        try {
            state.catalog = await api.getModels();
            state.loaded = true;
            const runtime = state.catalog.active_runtime;
            byId("activeModelSummary").textContent = `模型版本：${state.catalog.active_model || "legacy"}`;
            byId("activeModelRuntimeSummary").textContent = `运行快照：${runtime?.snapshot_id || "未启用统一快照"} · 数据 ${state.catalog.active_data_version || "legacy"}`;
            renderModels(state.catalog);
            renderJobs(state.catalog);
            setStatus("模型清单已更新", "success");
            schedulePoll(state.catalog);
        } catch (error) {
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    async function startTraining() {
        const key = `model-training-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        setStatus("候选训练任务提交中");
        try {
            const job = await api.submitTraining({}, key);
            byId("modelTrainingStatus").textContent = `任务 ${job.job_id} 已提交，训练输出只写入候选目录。`;
            byId("modelTrainingStatus").className = "dataset-preview success";
            await load(true);
        } catch (error) {
            byId("modelTrainingStatus").textContent = error.message;
            byId("modelTrainingStatus").className = "dataset-preview error";
            setStatus(error.message, "error");
        }
    }

    async function activateModel(modelId) {
        if (!window.confirm(`确认人工激活模型 ${modelId} 吗？系统会先校验数据版本并创建运行快照。`)) return;
        setStatus(`正在激活 ${modelId}`);
        try {
            const result = await api.activateModel(modelId);
            byId("modelTrainingStatus").textContent = `模型 ${result.model_id} 已激活${result.runtime_snapshot ? `，运行快照为 ${result.runtime_snapshot.snapshot_id}` : ""}。`;
            byId("modelTrainingStatus").className = "dataset-preview success";
            await load(true);
        } catch (error) {
            byId("modelTrainingStatus").textContent = error.message;
            byId("modelTrainingStatus").className = "dataset-preview error";
            setStatus(error.message, "error");
        }
    }

    async function retryJob(jobId) {
        if (!window.confirm(`确认重试任务 ${jobId} 吗？本次重试会使用新的候选目录，不会覆盖活动模型。`)) return;
        setStatus(`正在重试 ${jobId}`);
        try {
            const job = await api.retryJob(jobId);
            byId("modelTrainingStatus").textContent = `任务 ${job.job_id} 已重新排队，第 ${job.attempt} 次尝试。`;
            byId("modelTrainingStatus").className = "dataset-preview success";
            await load(true);
        } catch (error) {
            byId("modelTrainingStatus").textContent = error.message;
            byId("modelTrainingStatus").className = "dataset-preview error";
            setStatus(error.message, "error");
        }
    }

    function init() {
        byId("startModelTraining").addEventListener("click", startTraining);
        byId("refreshModelCatalog").addEventListener("click", () => load(true));
        byId("modelVersionPrev").addEventListener("click", () => {
            state.modelPage = Math.max(1, state.modelPage - 1);
            renderModels(state.catalog);
        });
        byId("modelVersionNext").addEventListener("click", () => {
            state.modelPage += 1;
            renderModels(state.catalog);
        });
        byId("modelJobPrev").addEventListener("click", () => {
            state.jobPage = Math.max(1, state.jobPage - 1);
            renderJobs(state.catalog);
        });
        byId("modelJobNext").addEventListener("click", () => {
            state.jobPage += 1;
            renderJobs(state.catalog);
        });
        byId("modelVersionsBody").addEventListener("click", event => {
            const button = event.target.closest(".model-activate");
            if (button) activateModel(button.dataset.modelId);
        });
        byId("modelJobsBody").addEventListener("click", event => {
            const button = event.target.closest(".model-job-retry");
            if (button) retryJob(button.dataset.jobId);
        });
    }

    window.ModelCenterPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
