const { test, expect } = require("@playwright/test");

test.beforeEach(async ({}, testInfo) => {
    testInfo.skip(
        process.env.DEMO_AUTH_ENABLED !== "true",
        "requires scripts/start_demo.ps1 -WithAuth"
    );
});

async function login(page, username, password) {
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
}

test("completes analyst approval and admin audit workflow", async ({ page }) => {
    const pageErrors = [];
    page.on("pageerror", error => pageErrors.push(error.message));

    await openDashboard(page);
    await login(page, "analyst", "demo-analyst");

    await page.locator('.app-nav [data-route="inventory"]').click();
    await expect(page.locator("#inventoryDecisionPage")).toBeVisible();
    const firstRow = page.locator("#replenishmentBody tr[data-key]").first();
    await expect(firstRow).toBeVisible();
    await firstRow.locator(".replenishment-select").check();
    await page.locator("#replenishmentAdjustmentQuantity").fill("1");
    await page.locator("#replenishmentAdjustmentReason").fill("审批流程 E2E");
    await page.locator("#createReplenishmentPlan").click();
    await expect(page.locator("#replenishmentPreview")).toContainText("草案");

    await page.locator('.app-nav [data-route="plans"]').click();
    await expect(page.locator("#planCenterPage")).toBeVisible();
    const draft = page.locator("#planVersionsBody tr").filter({ hasText: "草案" }).first();
    await expect(draft.locator('[data-action="submit"]')).toBeVisible();
    await draft.locator('[data-action="submit"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");

    await page.locator("#demoLogout").click();
    await expect(page.locator("#demoLogin")).toBeVisible();
    await login(page, "approver", "demo-approver");
    await page.locator('.app-nav [data-route="plans"]').click();
    const submitted = page.locator("#planVersionsBody tr").filter({ hasText: "待审批" }).first();
    await expect(submitted.locator('[data-action="approve"]')).toBeVisible();
    await submitted.locator('[data-action="approve"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");

    await page.locator("#demoLogout").click();
    await login(page, "admin", "demo-admin");
    await page.locator('.app-nav [data-route="plans"]').click();
    const approved = page.locator("#planVersionsBody tr").filter({ hasText: "已批准" }).first();
    await approved.locator(".plan-detail-action").click();
    await page.locator('#planWorkflowActions [data-action="events"]').click();
    await expect(page.locator("#planDetailSummary")).toContainText("submit");
    await expect(page.locator("#planDetailSummary")).toContainText("approve");
    expect(pageErrors).toEqual([]);
});
