/* 库存决策：风险清单与服务端补货试算。 */
(function () {
    const state = { cells: [], selected: null, loading: false };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("inventoryDecisionStatus");
        target.textContent = message;
        target.className = `module-status ${tone}`.trim();
    }

    function filteredCells() {
        const query = byId("replenishmentSearch").value.trim().toLowerCase();
        const risk = byId("replenishmentRiskFilter").value;
        return state.cells.filter(cell => {
            const matchesRisk = !risk || cell.risk_level === risk;
            const haystack = `${cell.product_id} ${cell.product_name} ${cell.store_id} ${cell.store_name} ${cell.risk_level}`.toLowerCase();
            return matchesRisk && (!query || haystack.includes(query));
        });
    }

    function render() {
        const body = byId("replenishmentBody");
        body.textContent = "";
        const cells = filteredCells();
        if (!cells.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 7;
            cell.textContent = "当前筛选范围暂无库存风险数据。";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }
        cells.forEach(item => {
            const row = document.createElement("tr");
            row.dataset.key = `${item.product_id}-${item.store_id}`;
            row.className = state.selected && state.selected.product_id === item.product_id && state.selected.store_id === item.store_id ? "selected-row" : "";
            [
                `#${item.product_id} ${item.product_name}`,
                `#${item.store_id} ${item.store_name}`,
                item.abc_class,
                item.risk_level,
                item.window_demand ?? "--",
                item.net_available ?? "--",
                item.suggested_purchase,
            ].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });
            body.appendChild(row);
        });
    }

    function selectCell(cell) {
        state.selected = cell;
        byId("replenishmentForm").classList.remove("hidden");
        byId("replenishmentSelectionTitle").textContent = `${cell.product_name} / ${cell.store_name} · ${cell.risk_level} 风险`;
        byId("replenishmentLeadTime").value = cell.lead_time_days;
        byId("replenishmentReviewPeriod").value = cell.review_period_days;
        byId("replenishmentSafetyStock").value = cell.safety_stock;
        byId("replenishmentPackSize").value = cell.pack_size;
        byId("replenishmentMoq").value = cell.minimum_order_quantity;
        byId("replenishmentPreview").textContent = `当前建议 ${cell.suggested_purchase}，选择参数后可重新试算。`;
        render();
    }

    async function runPreview() {
        if (!state.selected) return;
        const payload = {
            product_id: state.selected.product_id,
            store_id: state.selected.store_id,
            lead_time_days: Number(byId("replenishmentLeadTime").value),
            review_period_days: Number(byId("replenishmentReviewPeriod").value),
            safety_stock: Number(byId("replenishmentSafetyStock").value),
            pack_size: Number(byId("replenishmentPackSize").value),
            minimum_order_quantity: Number(byId("replenishmentMoq").value),
        };
        setStatus("补货试算中");
        try {
            const result = await api.previewReplenishment(payload);
            byId("replenishmentPreview").textContent = `窗口 ${result.window_days} 天：需求 ${result.window_demand}；净可用 ${result.net_available}；目标库存 ${result.target_stock}；原始缺口 ${result.raw_replenishment}；包装/MOQ 后建议 ${result.suggested_quantity}；风险 ${result.risk_level}。来源库存 ${result.inventory_version}，截至 ${result.inventory_as_of_date}。`;
            byId("replenishmentPreview").className = "dataset-preview success";
            setStatus("试算完成", "success");
        } catch (error) {
            byId("replenishmentPreview").textContent = error.message;
            byId("replenishmentPreview").className = "dataset-preview error";
            setStatus(error.message, "error");
        }
    }

    async function load(force = false) {
        if (state.loading || (!force && state.cells.length)) return;
        state.loading = true;
        setStatus("加载库存清单中");
        try {
            const result = await api.getInventory();
            state.cells = result.cells || [];
            byId("replenishmentCoverage").textContent = `覆盖率：${result.coverage.succeeded}/${result.coverage.requested} · ${result.coverage.status}`;
            render();
            setStatus("库存清单已更新", "success");
        } catch (error) {
            state.cells = [];
            render();
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    function init() {
        byId("replenishmentSearch").addEventListener("input", render);
        byId("replenishmentRiskFilter").addEventListener("change", render);
        byId("refreshReplenishment").addEventListener("click", () => load(true));
        byId("runReplenishmentPreview").addEventListener("click", runPreview);
        byId("replenishmentBody").addEventListener("click", event => {
            const row = event.target.closest("tr[data-key]");
            if (!row) return;
            const [productId, storeId] = row.dataset.key.split("-").map(Number);
            selectCell(state.cells.find(item => item.product_id === productId && item.store_id === storeId));
        });
    }

    window.InventoryDecisionPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
