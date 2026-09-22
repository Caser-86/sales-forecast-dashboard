/* V2 页面骨架：未开放模块必须明确说明状态。 */
window.RoutePlaceholder = {
    render(activeRoute, copy) {
        const placeholder = document.getElementById("routePlaceholder");
        placeholder.classList.toggle(
            "hidden",
            ["overview", "data", "models", "forecast"].includes(activeRoute)
        );
        document.getElementById("routePlaceholderTitle").textContent = copy.title;
        document.getElementById("routePlaceholderDescription").textContent = copy.description;
    },

    setScope(scope) {
        const product = scope.productId ? `#${scope.productId}` : "全部商品";
        const store = scope.storeId ? `#${scope.storeId}` : "全部门店";
        document.getElementById("routeScopeSummary").textContent =
            `筛选范围：${product} · ${store}`;
    }
};
