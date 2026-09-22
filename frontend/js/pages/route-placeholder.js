/* V2 页面骨架：未开放模块必须明确说明状态。 */
window.RoutePlaceholder = {
    render(activeRoute, copy) {
        const placeholder = document.getElementById("routePlaceholder");
        placeholder.classList.toggle("hidden", activeRoute === "overview");
        document.getElementById("routePlaceholderTitle").textContent = copy.title;
        document.getElementById("routePlaceholderDescription").textContent = copy.description;
    }
};
