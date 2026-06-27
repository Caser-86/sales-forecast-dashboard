/* 接口请求封装（已清理死代码，统一错误处理） */
function getBase() {
    const host = window.location.hostname;
    const port = window.location.port;
    // 开发模式：前端 3000/5500 端口访问 → 后端 8000
    if (port === "3000" || port === "5500") {
        return `http://${host}:8000/api`;
    }
    // 生产模式：通过 nginx 80 端口反代
    return "/api";
}

const BASE = getBase();

const api = {
    async get(path) {
        try {
            const resp = await fetch(BASE + path);
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
            console.error(`请求失败 ${path}:`, e.message);
            throw e;
        }
    },

    getProducts() { return this.get("/products"); },
    getSales(productId, storeId, days = 90) {
        return this.get(`/sales?product_id=${productId}&store_id=${storeId}&days=${days}`);
    },
    getForecast(productId, storeId) {
        return this.get(`/forecast?product_id=${productId}&store_id=${storeId}`);
    },
    getDashboard() { return this.get("/dashboard"); },
    getInventory() { return this.get("/inventory"); },
    getKpi() { return this.get("/kpi"); },
};
