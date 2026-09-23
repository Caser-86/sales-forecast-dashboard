/* 库存决策：风险清单与服务端补货试算。 */
(function () {
    const state = {
        cells: [],
        selected: null,
        selectedKeys: new Set(),
        metadata: null,
        datasets: null,
        coverage: null,
        loading: false,
        inventoryPage: 1,
        inventoryPageSize: 20,
    };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("inventoryDecisionStatus");
        target.textContent = message;
        target.className = `module-status ${tone}`.trim();
    }

    function cellKey(cell) { return `${cell.product_id}-${cell.store_id}`; }

    function updatePlanButtons() {
        const enabled = state.selectedKeys.size > 0;
        byId("createReplenishmentPlan").disabled = !enabled;
        byId("addReplenishmentPlan").disabled = !enabled;
    }

    function filteredCells() {
        const query = byId("replenishmentSearch").value.trim().toLowerCase();
        const abc = byId("replenishmentAbcFilter").value;
        const risk = byId("replenishmentRiskFilter").value;
        return state.cells.filter(cell => {
            const matchesAbc = !abc || cell.abc_class === abc;
            const matchesRisk = !risk || cell.risk_level === risk;
            const haystack = `${cell.product_id} ${cell.product_name} ${cell.store_id} ${cell.store_name} ${cell.abc_class} ${cell.risk_level}`.toLowerCase();
            return matchesAbc && matchesRisk && (!query || haystack.includes(query));
        });
    }

    function render() {
        const body = byId("replenishmentBody");
        body.textContent = "";
        const cells = filteredCells();
        const pageCount = Math.max(1, Math.ceil(cells.length / state.inventoryPageSize));
        if (state.inventoryPage > pageCount) {
            state.inventoryPage = pageCount;
            return render();
        }
        const start = cells.length ? (state.inventoryPage - 1) * state.inventoryPageSize + 1 : 0;
        const end = Math.min(state.inventoryPage * state.inventoryPageSize, cells.length);
        byId("replenishmentSummary").textContent =
            `库存 ${start}-${end}/${cells.length} · 第 ${state.inventoryPage}/${pageCount} 页`;
        byId("replenishmentPrev").disabled = state.inventoryPage <= 1;
        byId("replenishmentNext").disabled = state.inventoryPage >= pageCount;
        if (!cells.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 8;
            cell.textContent = "当前筛选范围暂无库存风险数据。";
            row.appendChild(cell);
            body.appendChild(row);
            updatePlanButtons();
            return;
        }
        cells.slice(start - 1, end).forEach(item => {
            const key = cellKey(item);
            const row = document.createElement("tr");
            row.dataset.key = key;
            row.className = state.selected && cellKey(state.selected) === key ? "selected-row" : "";
            const selectorCell = document.createElement("td");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "replenishment-select";
            checkbox.dataset.key = key;
            checkbox.checked = state.selectedKeys.has(key);
            checkbox.setAttribute("aria-label", `选择 ${item.product_name} ${item.store_name}`);
            selectorCell.appendChild(checkbox);
            row.appendChild(selectorCell);
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
        updatePlanButtons();
    }

    function selectCell(cell) {
        if (!cell) return;
        state.selected = cell;
        state.selectedKeys.add(cellKey(cell));
        byId("replenishmentForm").classList.remove("hidden");
        byId("replenishmentSelectionTitle").textContent = `${cell.product_name} / ${cell.store_name} · ${cell.risk_level} 风险`;
        byId("replenishmentLeadTime").value = cell.lead_time_days;
        byId("replenishmentReviewPeriod").value = cell.review_period_days;
        byId("replenishmentSafetyStock").value = cell.safety_stock;
        byId("replenishmentPackSize").value = cell.pack_size;
        byId("replenishmentMoq").value = cell.minimum_order_quantity;
        byId("replenishmentAdjustmentQuantity").value = 0;
        byId("replenishmentAdjustmentReason").value = "";
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

    function buildPlanPayload() {
        if (!state.metadata || !state.coverage) throw new Error("运行上下文尚未加载完成");
        const selected = state.cells.filter(cell => state.selectedKeys.has(cellKey(cell)));
        if (!selected.length) throw new Error("请至少选择一条库存明细");
        const current = state.selected;
        const manualAdjustment = Number(byId("replenishmentAdjustmentQuantity").value || 0);
        if (!Number.isInteger(manualAdjustment)) throw new Error("人工调整数量必须是整数");
        const reason = byId("replenishmentAdjustmentReason").value.trim();
        if (manualAdjustment !== 0 && !reason) throw new Error("填写人工调整数量时必须填写原因");
        const items = selected.map(cell => {
            const adjustment = current && cellKey(current) === cellKey(cell) ? manualAdjustment : 0;
            const adjustmentReason = current && cellKey(current) === cellKey(cell) ? reason : "";
            if (cell.suggested_purchase + adjustment < 0) {
                throw new Error(`${cell.product_name} 的调整后数量不能为负数`);
            }
            return {
                ...cell,
                original_suggested_purchase: cell.suggested_purchase,
                adjustment_quantity: adjustment,
                adjustment_reason: adjustmentReason,
            };
        });
        return {
            name: `库存补货草案-${new Date().toISOString().slice(0, 10)}`,
            as_of_date: state.metadata.as_of_date,
            inventory_as_of_date: state.metadata.inventory_as_of_date,
            data_version: state.metadata.data_version,
            model_version: state.metadata.model_version,
            inventory_version: state.metadata.inventory_version,
            policy_version: state.datasets?.active_runtime?.policy_version || "replenishment-v1",
            coverage: state.coverage,
            items,
            adjustments: items.filter(item => item.adjustment_quantity !== 0).map(item => ({
                product_id: item.product_id,
                store_id: item.store_id,
                quantity: item.adjustment_quantity,
                reason: item.adjustment_reason,
            })),
        };
    }

    async function createPlan() {
        if (!state.metadata || !state.coverage) return;
        if (state.metadata.inventory_status !== "fresh") {
            setStatus("库存快照已过期，不能生成新草案", "error");
            return;
        }
        if (state.coverage.status !== "ok" || state.coverage.failed !== 0) {
            setStatus("预测覆盖不完整，不能生成新草案", "error");
            return;
        }
        const button = byId("addReplenishmentPlan");
        button.disabled = true;
        setStatus("正在保存补货草案");
        try {
            const payload = buildPlanPayload();
            const key = window.crypto?.randomUUID?.() || `inventory-plan-${Date.now()}`;
            const result = await api.createPlan(payload, key);
            byId("replenishmentPreview").textContent = `草案 ${result.plan_id} 已${result.created ? "保存" : "幂等恢复"}，包含 ${payload.items.length} 条明细。`;
            byId("replenishmentPreview").className = "dataset-preview success";
            setStatus("补货草案已保存", "success");
        } catch (error) {
            byId("replenishmentPreview").textContent = error.message;
            byId("replenishmentPreview").className = "dataset-preview error";
            setStatus(error.message, "error");
        } finally {
            updatePlanButtons();
        }
    }

    async function load(force = false) {
        if (state.loading || (!force && state.cells.length)) return;
        state.loading = true;
        if (force) state.inventoryPage = 1;
        setStatus("加载库存清单中");
        try {
            const [result, metadata, datasets] = await Promise.all([
                api.getInventory(),
                api.getMetadata(),
                api.getDatasets(),
            ]);
            state.cells = result.cells || [];
            state.coverage = result.coverage;
            state.metadata = metadata;
            state.datasets = datasets;
            byId("inventorySourceSummary").textContent =
                `来源版本：数据 ${metadata.data_version} · 模型 ${metadata.model_version} · 库存 ${metadata.inventory_version}`;
            const validKeys = new Set(state.cells.map(cellKey));
            state.selectedKeys = new Set([...state.selectedKeys].filter(key => validKeys.has(key)));
            byId("replenishmentCoverage").textContent = `覆盖率：${result.coverage.succeeded}/${result.coverage.requested} · ${result.coverage.status}`;
            render();
            setStatus("库存清单已更新", "success");
        } catch (error) {
            state.cells = [];
            state.coverage = null;
            render();
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    function init() {
        const resetPageAndRender = () => {
            state.inventoryPage = 1;
            render();
        };
        byId("replenishmentSearch").addEventListener("input", resetPageAndRender);
        byId("replenishmentAbcFilter").addEventListener("change", resetPageAndRender);
        byId("replenishmentRiskFilter").addEventListener("change", resetPageAndRender);
        byId("refreshReplenishment").addEventListener("click", () => load(true));
        byId("replenishmentPrev").addEventListener("click", () => {
            state.inventoryPage = Math.max(1, state.inventoryPage - 1);
            render();
        });
        byId("replenishmentNext").addEventListener("click", () => {
            state.inventoryPage += 1;
            render();
        });
        byId("runReplenishmentPreview").addEventListener("click", runPreview);
        byId("createReplenishmentPlan").addEventListener("click", createPlan);
        byId("addReplenishmentPlan").addEventListener("click", createPlan);
        byId("replenishmentBody").addEventListener("click", event => {
            const checkbox = event.target.closest(".replenishment-select");
            if (checkbox) {
                const cell = state.cells.find(item => cellKey(item) === checkbox.dataset.key);
                if (checkbox.checked) {
                    selectCell(cell);
                } else {
                    state.selectedKeys.delete(checkbox.dataset.key);
                    if (state.selected && cellKey(state.selected) === checkbox.dataset.key) {
                        state.selected = null;
                        byId("replenishmentForm").classList.add("hidden");
                    }
                    render();
                }
                return;
            }
            const row = event.target.closest("tr[data-key]");
            if (!row) return;
            selectCell(state.cells.find(item => cellKey(item) === row.dataset.key));
        });
    }

    window.InventoryDecisionPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
