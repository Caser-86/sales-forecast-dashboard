/* 计划中心：不可变草案列表、明细和导出。 */
(function () {
    const state = { plans: [], loaded: false, loading: false };

    function byId(id) { return document.getElementById(id); }

    function setStatus(message, tone = "") {
        const target = byId("planCenterStatus");
        target.textContent = message;
        target.className = `module-status ${tone}`.trim();
    }

    function statusLabel(status) {
        return { draft: "草案", submitted: "待审批", approved: "已批准", rejected: "已驳回", cancelled: "已取消" }[status] || status || "草案";
    }

    function appendAction(host, planId, action, label) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dataset-table-action plan-workflow-action";
        button.dataset.planId = planId;
        button.dataset.action = action;
        button.textContent = label;
        host.appendChild(button);
    }

    function renderPlans() {
        const body = byId("planVersionsBody");
        body.textContent = "";
        if (!state.plans.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 9;
            cell.textContent = "暂无已保存草案；可从总览保存当前补货建议。";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }
        state.plans.forEach(plan => {
            const row = document.createElement("tr");
            [plan.name, statusLabel(plan.status), plan.version, plan.item_count, plan.data_version, plan.model_version, plan.inventory_version, plan.created_at].forEach(value => {
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
            if (plan.status === "draft") appendAction(action, plan.plan_id, "submit", "提交审批");
            if (plan.status === "submitted") {
                appendAction(action, plan.plan_id, "approve", "批准");
                appendAction(action, plan.plan_id, "reject", "驳回");
            }
            if (["draft", "submitted"].includes(plan.status)) appendAction(action, plan.plan_id, "cancel", "取消");
            if (plan.status === "rejected") appendAction(action, plan.plan_id, "revision", "创建修订版");
            row.appendChild(action);
            body.appendChild(row);
        });
    }

    function renderDetail(plan) {
        byId("planDetail").classList.remove("hidden");
        byId("planDetailTitle").textContent = `${plan.name} · ${plan.plan_id}`;
        byId("planDetailSource").textContent = `状态 ${statusLabel(plan.status)} · 第 ${plan.version} 版 · 创建于 ${plan.created_at} · 数据 ${plan.data_version} · 模型 ${plan.model_version} · 库存 ${plan.inventory_version}`;
        byId("planDetailSummary").textContent = `策略 ${plan.policy_version} · 覆盖 ${plan.snapshot.coverage.succeeded}/${plan.snapshot.coverage.requested} · 条目 ${plan.snapshot.items.length}`;
        const actionHost = byId("planWorkflowActions");
        actionHost.textContent = "";
        const exportLink = document.createElement("a");
        exportLink.id = "planDetailExport";
        exportLink.className = "refresh-button plan-link";
        exportLink.href = api.planExportUrl(plan.plan_id);
        exportLink.download = "";
        exportLink.textContent = "导出 CSV";
        if (plan.status === "draft") appendAction(actionHost, plan.plan_id, "submit", "提交审批");
        if (plan.status === "submitted") {
            appendAction(actionHost, plan.plan_id, "approve", "批准");
            appendAction(actionHost, plan.plan_id, "reject", "驳回");
        }
        if (["draft", "submitted"].includes(plan.status)) appendAction(actionHost, plan.plan_id, "cancel", "取消");
        if (plan.status === "rejected") appendAction(actionHost, plan.plan_id, "revision", "创建修订版");
        if (DemoAuth.getUser()?.role === "admin") appendAction(actionHost, plan.plan_id, "events", "查看审计");
        actionHost.appendChild(exportLink);
        const body = byId("planDetailItemsBody");
        body.textContent = "";
        plan.snapshot.items.forEach(item => {
            const row = document.createElement("tr");
            [
                `#${item.product_id} ${item.product_name}`,
                `#${item.store_id} ${item.store_name}`,
                item.risk_level,
                item.predicted_sales,
                item.original_suggested_purchase ?? item.suggested_purchase,
                item.suggested_purchase,
                item.adjustment_quantity,
                item.adjustment_reason || "--",
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

    async function workflowAction(planId, action) {
        if (action === "events") {
            try {
                const events = await api.getPlanEvents(planId);
                byId("planDetailSummary").textContent = events.length
                    ? events.map(event => `${event.action} ${event.from_status}->${event.to_status} · ${event.actor_username} · ${event.reason || "无原因"}`).join(" | ")
                    : "暂无审计事件";
            } catch (error) { setStatus(error.message, "error"); }
            return;
        }
        const plan = state.plans.find(item => item.plan_id === planId);
        if (!plan) return;
        if (action === "revision") {
            setStatus("正在创建修订版");
            try {
                const result = await api.createPlanRevision(planId, `revision-${Date.now()}-${Math.random().toString(16).slice(2)}`);
                await load(true);
                await showDetail(result.plan_id);
            } catch (error) { setStatus(error.message, "error"); }
            return;
        }
        const reason = action === "reject" ? window.prompt("请输入驳回原因") : "";
        if (action === "reject" && !reason) return;
        setStatus("正在更新计划状态");
        try {
            await api.transitionPlan(planId, { action, expected_version: plan.version, reason });
            await load(true);
            await showDetail(planId);
        } catch (error) { setStatus(error.message, "error"); }
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
            const workflowButton = event.target.closest(".plan-workflow-action");
            if (workflowButton) workflowAction(workflowButton.dataset.planId, workflowButton.dataset.action);
        });
        byId("planWorkflowActions").addEventListener("click", event => {
            const workflowButton = event.target.closest(".plan-workflow-action");
            if (workflowButton) workflowAction(workflowButton.dataset.planId, workflowButton.dataset.action);
        });
    }

    window.PlansPage = { init, load };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
