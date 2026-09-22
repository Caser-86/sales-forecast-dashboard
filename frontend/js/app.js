/* 应用壳：导航、路由和跨页面状态。 */
const ROUTE_ORDER = ["overview", "data", "forecast", "inventory", "plans", "models", "system"];
const ROUTE_COPY = {
    overview: { title: "经营总览", description: "查看当前演示数据的销量、预测、优先级和补货建议。" },
    data: { title: "数据中心", description: "销售与库存 CSV 预检、候选版本和运行快照管理。" },
    forecast: { title: "预测分析", description: "商品与门店预测明细、基线对比和导出将在 M3 开放。" },
    inventory: { title: "库存决策", description: "库存风险清单和补货试算将在 M3 开放。" },
    plans: { title: "计划中心", description: "补货计划审批、版次和审计将在 M3 开放。" },
    models: { title: "模型中心", description: "查看候选模型、训练状态和人工激活动作。" },
    system: { title: "演示系统", description: "场景切换、备份恢复和诊断将在 M4 开放。" }
};

function parsePositiveId(value) {
    const parsed = Number.parseInt(value, 10);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function getRouteState() {
    const rawHash = window.location.hash.slice(1);
    const [routePart, query = ""] = rawHash.split("?");
    const params = new URLSearchParams(query);
    const route = ROUTE_ORDER.includes(routePart.toLowerCase()) ? routePart.toLowerCase() : "overview";
    return {
        route,
        scope: {
            productId: parsePositiveId(params.get("product")),
            storeId: parsePositiveId(params.get("store"))
        }
    };
}

function buildRouteHash(route, scope = {}) {
    const activeRoute = ROUTE_ORDER.includes(route) ? route : "overview";
    const params = new URLSearchParams();
    if (scope.productId) params.set("product", scope.productId);
    if (scope.storeId) params.set("store", scope.storeId);
    const query = params.toString();
    return `#${activeRoute}${query ? `?${query}` : ""}`;
}

function updateNavigationLinks(scope) {
    document.querySelectorAll(".app-nav [data-route]").forEach(link => {
        link.setAttribute("href", buildRouteHash(link.dataset.route, scope));
    });
}

function setRoute(route = getRouteState().route) {
    const state = getRouteState();
    const activeRoute = ROUTE_ORDER.includes(route) ? route : state.route;
    const dashboard = document.querySelector(".dashboard");
    dashboard.dataset.route = activeRoute;
    document.querySelectorAll(".app-nav [data-route]").forEach(link => {
        const isActive = link.dataset.route === activeRoute;
        link.classList.toggle("active", isActive);
        if (isActive) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });
    document.querySelectorAll("[data-overview-only]").forEach(element => {
        element.classList.toggle("hidden", activeRoute !== "overview");
    });
    const dataCenter = document.getElementById("dataCenterPage");
    dataCenter?.classList.toggle("hidden", activeRoute !== "data");
    const modelCenter = document.getElementById("modelCenterPage");
    modelCenter?.classList.toggle("hidden", activeRoute !== "models");
    const forecastAnalysis = document.getElementById("forecastAnalysisPage");
    forecastAnalysis?.classList.toggle("hidden", activeRoute !== "forecast");
    if (activeRoute === "data") {
        window.DataCenterPage?.load();
    }
    if (activeRoute === "models") {
        window.ModelCenterPage?.load();
    }
    if (activeRoute === "forecast") {
        window.ForecastAnalysisPage?.load();
    }
    RoutePlaceholder.render(activeRoute, ROUTE_COPY[activeRoute]);
    RoutePlaceholder.setScope(state.scope);
    updateNavigationLinks(state.scope);
}

function syncScopeToRoute(scope = {}) {
    const state = getRouteState();
    const nextHash = buildRouteHash(state.route, scope);
    if (window.location.hash !== nextHash) {
        window.history.replaceState(null, "", nextHash);
    }
    setRoute(state.route);
}

function initNavigation() {
    const state = getRouteState();
    const normalizedHash = buildRouteHash(state.route, state.scope);
    if (window.location.hash !== normalizedHash) {
        window.history.replaceState(null, "", normalizedHash);
    }
    setRoute(state.route);
    window.addEventListener("hashchange", () => setRoute(window.location.hash.slice(1).toLowerCase()));
}

window.AppNavigation = {
    getRouteState,
    syncScopeToRoute
};
