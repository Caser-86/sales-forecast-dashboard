/* 应用壳：导航、路由和跨页面状态。 */
const ROUTE_ORDER = ["overview", "data", "forecast", "inventory", "plans", "models", "system"];
const ROUTE_COPY = {
    overview: { title: "经营总览", description: "查看当前演示数据的销量、预测、优先级和补货建议。" },
    data: { title: "数据中心", description: "数据上传、质量检查、版本激活和回滚将在 M2 开放。" },
    forecast: { title: "预测分析", description: "商品与门店预测明细、基线对比和导出将在 M3 开放。" },
    inventory: { title: "库存决策", description: "库存风险清单和补货试算将在 M3 开放。" },
    plans: { title: "计划中心", description: "补货计划审批、版次和审计将在 M3 开放。" },
    models: { title: "模型中心", description: "训练任务、评估、发布和回滚将在 M2 开放。" },
    system: { title: "演示系统", description: "场景切换、备份恢复和诊断将在 M4 开放。" }
};

function setRoute(route) {
    const activeRoute = ROUTE_ORDER.includes(route) ? route : "overview";
    const dashboard = document.querySelector(".dashboard");
    dashboard.dataset.route = activeRoute;
    document.querySelectorAll("[data-route]").forEach(link => {
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
    RoutePlaceholder.render(activeRoute, ROUTE_COPY[activeRoute]);
}

function initNavigation() {
    const requestedRoute = window.location.hash.slice(1).toLowerCase();
    const activeRoute = ROUTE_ORDER.includes(requestedRoute) ? requestedRoute : "overview";
    if (window.location.hash.slice(1).toLowerCase() !== activeRoute) {
        window.history.replaceState(null, "", `#${activeRoute}`);
    }
    setRoute(activeRoute);
    window.addEventListener("hashchange", () => setRoute(window.location.hash.slice(1).toLowerCase()));
}
