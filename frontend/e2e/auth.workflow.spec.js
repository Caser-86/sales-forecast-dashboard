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
    const planId = await createdPlanId(page);

    await page.locator('.app-nav [data-route="plans"]').click();
    await expect(page.locator("#planCenterPage")).toBeVisible();
    const draft = planRow(page, planId);
    await expect(draft.locator('[data-action="submit"]')).toBeVisible();
    await draft.locator('[data-action="submit"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");

    await page.locator("#demoLogout").click();
    await expect(page.locator("#demoLogin")).toBeVisible();
    await login(page, "approver", "demo-approver");
    await page.locator('.app-nav [data-route="plans"]').click();
    const submitted = planRow(page, planId);
    await expect(submitted.locator('[data-action="approve"]')).toBeVisible();
    await submitted.locator('[data-action="approve"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");

    await page.locator("#demoLogout").click();
    await login(page, "admin", "demo-admin");
    await page.locator('.app-nav [data-route="plans"]').click();
    const approved = planRow(page, planId);
    await approved.locator(".plan-detail-action").click();
    await page.locator('#planWorkflowActions [data-action="events"]').click();
    await expect(page.locator("#planDetailSummary")).toContainText("submit");
    await expect(page.locator("#planDetailSummary")).toContainText("approve");
    expect(pageErrors).toEqual([]);
});

test("shows an optimistic-lock conflict when two approval tabs race", async ({ page }) => {
    await openDashboard(page);
    await login(page, "analyst", "demo-analyst");

    await page.locator('.app-nav [data-route="inventory"]').click();
    await expect(page.locator("#replenishmentBody tr[data-key]").first()).toBeVisible();
    await page.locator("#replenishmentBody tr[data-key]").first().locator(".replenishment-select").check();
    await page.locator("#replenishmentAdjustmentQuantity").fill("1");
    await page.locator("#replenishmentAdjustmentReason").fill("并发版次测试");
    await page.locator("#createReplenishmentPlan").click();
    await expect(page.locator("#replenishmentPreview")).toContainText("草案");
    const planId = await createdPlanId(page);

    await page.locator('.app-nav [data-route="plans"]').click();
    const draft = planRow(page, planId);
    await draft.locator('[data-action="submit"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");

    await page.locator("#demoLogout").click();
    await expect(page.locator("#demoLogin")).toBeVisible();
    await login(page, "approver", "demo-approver");
    await page.locator('.app-nav [data-route="plans"]').click();
    await expect(planRow(page, planId)).toBeVisible();

    const racingPage = await page.context().newPage();
    await openDashboard(racingPage);
    await racingPage.locator('.app-nav [data-route="plans"]').click();
    const firstApproval = planRow(page, planId);
    const secondApproval = planRow(racingPage, planId);
    await expect(secondApproval).toBeVisible();

    await firstApproval.locator('[data-action="approve"]').click();
    await expect(page.locator("#planCenterStatus")).toContainText("更新");
    racingPage.once("dialog", dialog => dialog.accept("并发操作落后于批准"));
    await secondApproval.locator('[data-action="reject"]').click();
    await expect(racingPage.locator("#planCenterStatus")).toContainText("计划已被其他操作更新");
    await racingPage.close();
});
