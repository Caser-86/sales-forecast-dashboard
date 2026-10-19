/* Escape API-provided labels before ECharts interprets formatter output as HTML. */
window.escapeHtml = function (value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
};
