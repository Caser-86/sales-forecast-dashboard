const { test, expect } = require("@playwright/test");

test.beforeEach(async ({}, testInfo) => {
    testInfo.skip(
        process.env.DEMO_AUTH_ENABLED !== "true",
        "requires scripts/verify_offline_demo.ps1 -RunFullReplayE2E"
    );
});

async function login(page, username, password) {
    await expect(page.locator("#demoLogin")).toBeVisible();
    await page.locator("#demoUsername").fill(username);
    await page.locator("#demoPassword").fill(password);
    await page.locator("#demoLoginForm button[type=submit]").click();
    await expect(page.locator("#loading")).toHaveClass(/hidden/);
}

async function openDashboard(page) {
    if (process.env.API_BASE_URL) {
        await page.addInitScript({
            content: `window.API_BASE_URL = ${JSON.stringify(process.env.API_BASE_URL)};`
        });
    }
    await page.goto("/");
    await expect(page.locator("#loading")).toHaveClass(/hidden/);
}

async function openRoute(page, route) {
    await page.locator(`.app-nav [data-route="${route}"]`).click();
}

async function createdPlanId(page) {
    const preview = await page.locator("#replenishmentPreview").textContent();
    const match = preview.match(/草案\s+(\S+)\s+已/);
    expect(match).not.toBeNull();
    return match[1];
}

function planRow(page, planId) {
    return page.locator("#planVersionsBody tr").filter({
        has: page.locator(`button.plan-detail-action[data-plan-id="${planId}"]`)
    }).first();
}

test("replays the complete offline interview workflow in one authenticated session", async ({ page }) => {
    const pageErrors = [];
    page.on("pageerror", error => pageErrors.push(error.message));

    await openDashboard(page);
    await login(page, "analyst", "demo-analyst");

    await openRoute(page, "data");
    await expect(page.locator("#dataCenterPage")).toBeVisible();
    const invalidSales = [
        "date,product_id,store_id,product_name,store_name,category,sales,price",
        "2026-01-01,1,1,P1,S1,食品,-1,12.5",
    ].join("\n");
    await page.locator("#salesDatasetFile").setInputFiles({
        name: "full-replay-invalid.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(invalidSales, "utf8"),
    });
    await page.locator("#previewSalesDataset").click();
    await expect(page.locator("#salesDatasetPreview")).toContainText("第 2 行");
    await expect(page.locator("#uploadSalesDataset")).toBeDisabled();

    const validSales = [
        "date,product_id,store_id,product_name,store_name,category,sales,price",
        "2026-01-01,1,1,P1,S1,食品,10,12.5",
    ].join("\n");
    await page.locator("#salesDatasetFile").setInputFiles({
        name: "full-replay-valid.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(validSales, "utf8"),
    });
    await page.locator("#previewSalesDataset").click();
    await expect(page.locator("#salesDatasetPreview")).toContainText("预检通过");
    await page.locator("#uploadSalesDataset").click();
    await expect(page.locator("#salesDatasetPreview")).toContainText("候选版本已保存");

    await openRoute(page, "forecast");
    await expect(page.locator("#forecastAnalysisStatus")).toHaveText("明细已更新");
    await expect(page.locator("#forecastHistoryBody tr")).toHaveCount(30);
    await expect(page.locator("#forecastFutureBody tr")).toHaveCount(30);

    await openRoute(page, "inventory");
    await expect(page.locator("#inventoryDecisionStatus")).toHaveText("库存清单已更新");
    const firstRow = page.locator("#replenishmentBody tr[data-key]").first();
    await firstRow.locator(".replenishment-select").check();
    await page.locator("#runReplenishmentPreview").click();
    await expect(page.locator("#replenishmentPreview")).toContainText("包装/MOQ 后建议");
    await page.locator("#replenishmentAdjustmentQuantity").fill("1");
    await page.locator("#replenishmentAdjustmentReason").fill("完整离线回放调整");
    await page.locator("#createReplenishmentPlan").click();
    await expect(page.locator("#replenishmentPreview")).toContainText("草案");
    const planId = await createdPlanId(page);

    await openRoute(page, "plans");
    const draft = planRow(page, planId);
    await expect(draft.locator('[data-action="submit"]')).toBeVisible();
    await draft.locator('[data-action="submit"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");

    await page.locator("#demoLogout").click();
    await login(page, "approver", "demo-approver");
    await openRoute(page, "plans");
    const submitted = planRow(page, planId);
    await expect(submitted.locator('[data-action="approve"]')).toBeVisible();
    await submitted.locator('[data-action="approve"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");

    await page.locator("#demoLogout").click();
    await login(page, "admin", "demo-admin");
    await openRoute(page, "plans");
    const approved = planRow(page, planId);
    await approved.locator(".plan-detail-action").click();
    await page.locator('#planWorkflowActions [data-action="events"]').click();
    await expect(page.locator("#planDetailSummary")).toContainText("submit");
    await expect(page.locator("#planDetailSummary")).toContainText("approve");

    await openRoute(page, "system");
    await expect(page.locator("#systemPageStatus")).toHaveText("系统状态已更新");
    await page.locator("#createDemoBackup").click();
    await expect(page.locator("#demoArtifactStatus")).toContainText("备份已创建");
    await expect(page.locator("#demoBackupSelect option")).not.toHaveCount(0);
    const backupStatus = await page.locator("#demoArtifactStatus").textContent();
    const backupName = backupStatus.split("：").pop().trim();
    expect(backupName).toMatch(/^demo-backup-[0-9-]+\.zip$/);

    await page.locator("#demoScenarioSelect").selectOption("stale_inventory");
    page.once("dialog", dialog => dialog.accept());
    await page.locator("#applyDemoScenario").click();
    await expect(page.locator("#demoArtifactStatus")).toContainText("场景已切换");
    await openRoute(page, "inventory");
    await page.locator("#refreshReplenishment").click();
    await expect(page.locator("#inventoryDecisionStatus")).toContainText("过期");

    await openRoute(page, "system");
    await page.locator("#demoBackupSelect").selectOption(backupName);
    page.once("dialog", dialog => dialog.accept());
    await page.locator("#restoreDemoBackup").click();
    await expect(page.locator("#demoArtifactStatus")).toContainText("备份已恢复");
    await page.locator("#createDiagnosticPackage").click();
    await expect(page.locator("#demoArtifactStatus")).toContainText("诊断包已创建");
    expect(pageErrors).toEqual([]);
});
