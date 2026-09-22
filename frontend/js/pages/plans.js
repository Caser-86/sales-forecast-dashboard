/* 计划中心：不可变草案列表、明细和导出。 */
(function () {
    const state = { plans: [], loaded: false, loading: false };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("planCenterStatus");
        target.textContent = message;
        target.className = `module-status ${tone}`.trim();
    }

    function renderPlans() {
        const body = byId("planVersionsBody");
        body.textContent = "";
        if (!state.plans.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 7;
            cell.textContent = "暂无已保存草案；可从总览保存当前补货建议。";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }
        state.plans.forEach(plan => {
            const row = document.createElement("tr");
            [plan.name, plan.item_count, plan.data_version, plan.model_version, plan.inventory_version, plan.created_at].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value ?? "--";
                row.appendChild(cell);
            });
            const action = document.createElement("td");
            const button = document.createElement("button");
            button.type = "button";
            button.className = "dataset-table-action plan-detail-action";
            button.dataset.planId = plan.plan_id;
            button.textContent = "查看明细";
            action.appendChild(button);
            row.appendChild(action);
            body.appendChild(row);
        });
    }

    function renderDetail(plan) {
        byId("planDetail").classList.remove("hidden");
        byId("planDetailTitle").textContent = `${plan.name} · ${plan.plan_id}`;
        byId("planDetailSource").textContent = `创建于 ${plan.created_at} · 数据 ${plan.data_version} · 模型 ${plan.model_version} · 库存 ${plan.inventory_version}`;
        byId("planDetailSummary").textContent = `策略 ${plan.policy_version} · 覆盖 ${plan.snapshot.coverage.succeeded}/${plan.snapshot.coverage.requested} · 条目 ${plan.snapshot.items.length}`;
        const exportLink = byId("planDetailExport");
        exportLink.href = api.planExportUrl(plan.plan_id);
        const body = byId("planDetailItemsBody");
        body.textContent = "";
        plan.snapshot.items.forEach(item => {
            const row = document.createElement("tr");
            [
                `#${item.product_id} ${item.product_name}`,
                `#${item.store_id} ${item.store_name}`,
                item.risk_level,
                item.predicted_sales,
                item.suggested_purchase,
                item.adjustment_quantity,
            ].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value ?? "--";
                row.appendChild(cell);
            });
            body.appendChild(row);
        });
    }

    async function showDetail(planId) {
        setStatus("加载草案详情");
        try {
            renderDetail(await api.getPlan(planId));
            setStatus("草案详情已更新", "success");
        } catch (error) {
            setStatus(error.message, "error");
        }
    }

    async function load(force = false) {
        if (state.loading || (state.loaded && !force)) return;
        state.loading = true;
        try {
            state.plans = await api.getPlans();
            state.loaded = true;
            renderPlans();
            setStatus("草案列表已更新", "success");
        } catch (error) {
            setStatus(error.message, "error");
        } finally {
            state.loading = false;
        }
    }

    function init() {
        byId("refreshPlans").addEventListener("click", () => load(true));
        byId("planVersionsBody").addEventListener("click", event => {
            const button = event.target.closest(".plan-detail-action");
            if (button) showDetail(button.dataset.planId);
        });
    }

    window.PlansPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
