/* 可复用的前端目录过滤与分页，不改变服务端数据口径。 */
window.CatalogUtils = {
    filterAndPage(items, query = "", page = 1, pageSize = 50) {
        const normalized = String(query).trim().toLowerCase();
        const filtered = normalized
            ? items.filter(item => Object.values(item).some(value => String(value).toLowerCase().includes(normalized)))
            : [...items];
        const start = Math.max(0, page - 1) * pageSize;
        return {
            total: filtered.length,
            page,
            pageSize,
            items: filtered.slice(start, start + pageSize),
        };
    },
};
