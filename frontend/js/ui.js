/* 本地演示版共享 UI 状态：加载、错误重试、空态和运行上下文。 */
(function initDemoUI(global) {
    function get(id) {
        return document.getElementById(id);
    }

    function setLoading(isLoading, message = "正在加载演示数据...") {
        const loading = get("loading");
        if (!loading) return;
        const text = loading.querySelector(".loading-text");
        if (text) text.textContent = message;
        loading.classList.toggle("hidden", !isLoading);
        loading.setAttribute("aria-busy", String(isLoading));
    }

    function showError(message, { retry } = {}) {
        const banner = get("errorBanner");
        if (!banner) return;
        banner.replaceChildren();

        const text = document.createElement("span");
        text.textContent = message;
        banner.appendChild(text);

        if (typeof retry === "function") {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "error-retry";
            button.textContent = "重试";
            button.addEventListener("click", retry, { once: true });
            banner.appendChild(button);
        }
        banner.classList.remove("hidden");
    }

    function clearError() {
        get("errorBanner")?.classList.add("hidden");
    }

    function showEmpty(message = "当前筛选范围暂无可展示数据") {
        const empty = get("emptyState");
        if (!empty) return;
        empty.textContent = message;
        empty.classList.remove("hidden");
    }

    function clearEmpty() {
        get("emptyState")?.classList.add("hidden");
    }

    function setText(id, value) {
        const element = get(id);
        if (element) element.textContent = value;
    }

    function setRuntimeContext({ asOfDate, dataVersion, modelVersion, inventoryVersion, inventoryStatus } = {}) {
        setText("businessDate", `业务日期：${asOfDate || "--"}`);
        setText("routeBusinessDate", `业务日期：${asOfDate || "--"}`);
        setText("routeVersion", dataVersion ? `数据版本：${dataVersion}` : "数据版本：--");
        setText("versionSummary", [
            dataVersion && `数据 ${dataVersion}`,
            modelVersion && `模型 ${modelVersion}`,
            inventoryVersion && `库存 ${inventoryVersion}`,
            inventoryStatus && `状态 ${inventoryStatus}`
        ].filter(Boolean).join(" · ") || "版本：--");
    }

    global.DemoUI = {
        clearEmpty,
        clearError,
        setLoading,
        setRuntimeContext,
        showEmpty,
        showError
    };
})(window);
