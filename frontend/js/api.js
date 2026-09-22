/* 接口请求封装（已清理死代码，统一错误处理） */
function normalizeBase(value) {
    const base = String(value || "").trim().replace(/\/+$/, "");
    if (!base) {
        return "";
    }
    return base.endsWith("/api") ? base : `${base}/api`;
}

function getBase() {
    const host = window.location.hostname;
    const port = window.location.port;
    const protocol = window.location.protocol;

    // 特殊部署或本地开发可在加载 api.js 前设置 window.API_BASE_URL。
    const configuredBase = normalizeBase(window.API_BASE_URL);
    if (configuredBase) {
        return configuredBase;
    }

    // 直接打开 index.html 时没有同源 API，回退到本地后端。
    if (protocol === "file:") {
        return "http://localhost:8000/api";
    }

    // 开发模式：前端 3000/5500 端口访问 → 后端 8000。
    if (port === "3000" || port === "5500") {
        return `${protocol}//${host}:8000/api`;
    }
    // 生产模式：通过 nginx 80 端口反代
    return "/api";
}

function queryString(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
            query.set(key, value);
        }
    });
    const encoded = query.toString();
    return encoded ? `?${encoded}` : "";
}

const BASE = getBase();

const api = {
    async get(path, { signal, timeoutMs = 10000 } = {}) {
        const controller = new AbortController();
        let timedOut = false;
        const timeout = setTimeout(() => {
            timedOut = true;
            controller.abort();
        }, timeoutMs);
        const abortFromCaller = () => controller.abort();
        if (signal) {
            if (signal.aborted) controller.abort();
            signal.addEventListener("abort", abortFromCaller, { once: true });
        }
        try {
            const resp = await fetch(BASE + path, { signal: controller.signal, credentials: "include" });
            if (!resp.ok) {
                let message = `API ${path} 失败: ${resp.status}`;
                try {
                    const body = await resp.json();
                    if (body.error && body.error.message) {
                        message = body.error.message;
                    }
                } catch (_) {
                    // 非 JSON 错误体，保留默认 message
                }
                throw new Error(message);
            }
            return resp.json();
        } catch (e) {
            if (e.name === "AbortError" && timedOut) {
                const timeoutError = new Error(`请求超时: ${path}`);
                timeoutError.name = "TimeoutError";
                throw timeoutError;
            }
            console.error(`请求失败 ${path}:`, e.message);
            throw e;
        } finally {
            clearTimeout(timeout);
            signal?.removeEventListener("abort", abortFromCaller);
        }
    },

    async post(path, body, { signal, timeoutMs = 10000, headers = {} } = {}) {
        const controller = new AbortController();
        let timedOut = false;
        const timeout = setTimeout(() => {
            timedOut = true;
            controller.abort();
        }, timeoutMs);
        const abortFromCaller = () => controller.abort();
        if (signal) {
            if (signal.aborted) controller.abort();
            signal.addEventListener("abort", abortFromCaller, { once: true });
        }
        try {
            const resp = await fetch(BASE + path, {
                method: "POST",
                headers: { "Content-Type": "application/json", ...headers },
                body: JSON.stringify(body),
                signal: controller.signal,
                credentials: "include"
            });
            if (!resp.ok) {
                let message = `API ${path} 失败: ${resp.status}`;
                try {
                    const responseBody = await resp.json();
                    if (responseBody.error && responseBody.error.message) {
                        message = responseBody.error.message;
                    }
                } catch (_) {
                    // 非 JSON 错误体，保留默认 message
                }
                throw new Error(message);
            }
            return resp.json();
        } catch (e) {
            if (e.name === "AbortError" && timedOut) {
                const timeoutError = new Error(`请求超时: ${path}`);
                timeoutError.name = "TimeoutError";
                throw timeoutError;
            }
            console.error(`请求失败 ${path}:`, e.message);
            throw e;
        } finally {
            clearTimeout(timeout);
            signal?.removeEventListener("abort", abortFromCaller);
        }
    },

    async postRaw(path, body, { signal, timeoutMs = 15000, headers = {} } = {}) {
        const controller = new AbortController();
        let timedOut = false;
        const timeout = setTimeout(() => {
            timedOut = true;
            controller.abort();
        }, timeoutMs);
        const abortFromCaller = () => controller.abort();
        if (signal) {
            if (signal.aborted) controller.abort();
            signal.addEventListener("abort", abortFromCaller, { once: true });
        }
        try {
            const resp = await fetch(BASE + path, {
                method: "POST",
                headers,
                body,
                signal: controller.signal,
                credentials: "include"
            });
            if (!resp.ok) {
                let message = `API ${path} 失败: ${resp.status}`;
                try {
                    const responseBody = await resp.json();
                    if (responseBody.error && responseBody.error.message) message = responseBody.error.message;
                } catch (_) {
                    // 非 JSON 错误体，保留默认 message
                }
                throw new Error(message);
            }
            return resp.json();
        } catch (e) {
            if (e.name === "AbortError" && timedOut) {
                const timeoutError = new Error(`请求超时: ${path}`);
                timeoutError.name = "TimeoutError";
                throw timeoutError;
            }
            throw e;
        } finally {
            clearTimeout(timeout);
            signal?.removeEventListener("abort", abortFromCaller);
        }
    },

    getProducts(options) { return this.get("/products", options); },
    getStores(options) { return this.get("/stores", options); },
    getSales(productId, storeId, days = 90, options) {
        return this.get(`/sales?product_id=${productId}&store_id=${storeId}&days=${days}`, options);
    },
    getForecast(productId, storeId, options) {
        return this.get(`/forecast?product_id=${productId}&store_id=${storeId}`, options);
    },
    getDashboard(scope = {}, options) {
        return this.get(`/dashboard${queryString({
            product_id: scope.productId,
            store_id: scope.storeId
        })}`, options);
    },
    getInventory(scope = {}, options) {
        return this.get(`/inventory${queryString({
            product_id: scope.productId,
            store_id: scope.storeId
        })}`, options);
    },
    getKpi(options) { return this.get("/kpi", options); },
    getModelInfo(options) { return this.get("/model-info", options); },
    getDataQuality(options) { return this.get("/data-quality", options); },
    getMetadata(options) { return this.get("/metadata", options); },
    getAuthConfig(options) { return this.get("/auth/config", options); },
    getCurrentUser(options) { return this.get("/auth/me", options); },
    login(username, password, options) { return this.post("/auth/login", { username, password }, options); },
    logout(options) { return this.post("/auth/logout", {}, options); },
    createPlan(payload, idempotencyKey, options = {}) {
        return this.post("/plans", payload, {
            ...options,
            headers: { ...(options.headers || {}), "Idempotency-Key": idempotencyKey }
        });
    },
    submitTraining(payload, idempotencyKey, options = {}) {
        return this.post("/jobs/training", payload, {
            ...options,
            headers: { ...(options.headers || {}), "Idempotency-Key": idempotencyKey }
        });
    },
    getJobs(limit = 50, options) { return this.get(`/jobs?limit=${limit}`, options); },
    getJob(jobId, options) { return this.get(`/jobs/${encodeURIComponent(jobId)}`, options); },
    retryJob(jobId, options) { return this.post(`/jobs/${encodeURIComponent(jobId)}/retry`, {}, options); },
    getModels(options) { return this.get("/models", options); },
    getModel(modelId, options) { return this.get(`/models/${encodeURIComponent(modelId)}`, options); },
    activateModel(modelId, options) {
        return this.post(`/models/${encodeURIComponent(modelId)}/activate`, {}, options);
    },
    previewReplenishment(payload, options) { return this.post("/replenishment/preview", payload, options); },
    getPlans(limit = 50, options) { return this.get(`/plans?limit=${limit}`, options); },
    getPlan(planId, options) { return this.get(`/plans/${encodeURIComponent(planId)}`, options); },
    transitionPlan(planId, payload, options) {
        return this.post(`/plans/${encodeURIComponent(planId)}/transition`, payload, options);
    },
    createPlanRevision(planId, idempotencyKey, options = {}) {
        return this.post(`/plans/${encodeURIComponent(planId)}/revisions`, {}, {
            ...options,
            headers: { ...(options.headers || {}), "Idempotency-Key": idempotencyKey }
        });
    },
    getPlanEvents(planId, options) { return this.get(`/plans/${encodeURIComponent(planId)}/events`, options); },
    getDemoScenarios(options) { return this.get("/demo/scenarios", options); },
    switchDemoScenario(name, confirm = false, options) {
        return this.post(`/demo/scenarios/${encodeURIComponent(name)}`, { confirm }, options);
    },
    getDemoArtifacts(options) { return this.get("/demo/artifacts", options); },
    createDemoBackup(options) { return this.post("/demo/backups", {}, options); },
    restoreDemoBackup(artifactName, options) {
        return this.post("/demo/backups/restore", { artifact_name: artifactName }, options);
    },
    createDiagnosticPackage(options) { return this.post("/demo/diagnostics", {}, options); },
    getDatasets(options) { return this.get("/datasets", options); },
    datasetTemplateUrl(kind) { return `${BASE}/datasets/templates/${encodeURIComponent(kind)}`; },
    previewDataset(kind, text, filename, options = {}) {
        return this.postRaw(`/datasets/${kind}/preview`, text, {
            ...options,
            headers: { "Content-Type": "text/csv", "X-Filename": filename, ...(options.headers || {}) }
        });
    },
    uploadDataset(kind, text, filename, options = {}) {
        return this.postRaw(`/datasets/${kind}`, text, {
            ...options,
            headers: { "Content-Type": "text/csv", "X-Filename": filename, ...(options.headers || {}) }
        });
    },
    publishRuntimeSnapshot(payload, options) { return this.post("/datasets/runtime", payload, options); },
    activateRuntimeSnapshot(snapshotId, options) {
        return this.post(`/datasets/runtime/${encodeURIComponent(snapshotId)}/activate`, {}, options);
    },
    getRuntimeSnapshot(snapshotId, options) {
        return this.get(`/datasets/runtime/${encodeURIComponent(snapshotId)}`, options);
    },
    rollbackRuntimeSnapshot(snapshotId, options) {
        return this.post(`/datasets/runtime/${encodeURIComponent(snapshotId)}/rollback`, {}, options);
    },
    planExportUrl(planId) { return `${BASE}/plans/${encodeURIComponent(planId)}/export`; },
};
