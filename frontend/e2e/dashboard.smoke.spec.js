const { test, expect } = require("@playwright/test");

async function waitForDashboard(page) {
    await page.goto("/");
    await expect(page.locator("#loading")).toHaveClass(/hidden/);
}

test("loads live dashboard data and saves an exportable draft", async ({ page }) => {
    const pageErrors = [];
    page.on("pageerror", error => pageErrors.push(error.message));

    await waitForDashboard(page);

    await expect(page.locator("#errorBanner")).toBeHidden();
    await expect(page.locator("#lastUpdated")).not.toHaveText("数据更新时间：--");
    await expect(page.locator("#scopeProductSelect option")).not.toHaveCount(1);
    await expect(page.locator("#refreshDashboard")).toBeEnabled();

    await page.locator("#scopeProductSelect").selectOption("1");
    await expect(page.locator("#scopeLabel")).toContainText("#1");
    await expect(page.locator("#savePlan")).toBeEnabled();

    await page.locator("#savePlan").click();
    await expect(page.locator("#planStatus")).toHaveText(/已保存|已幂等恢复/);
    await expect(page.locator("#exportPlan")).toBeVisible();
    await expect(page.locator("#exportPlan")).toHaveAttribute("href", /\/api\/plans\/.+\/export/);
    expect(pageErrors).toEqual([]);
});

test("keeps primary actions reachable at the narrow viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await waitForDashboard(page);

    await expect(page.locator("#refreshDashboard")).toBeVisible();
    await expect(page.locator("#planName")).toBeVisible();
    await expect(page.locator("#savePlan")).toBeVisible();

    const pageSize = await page.evaluate(() => ({
        height: document.documentElement.scrollHeight,
        viewport: window.innerHeight
    }));
    expect(pageSize.height).toBeGreaterThan(pageSize.viewport);

    await page.locator("#refreshDashboard").focus();
    await expect(page.locator("#refreshDashboard")).toBeFocused();
});
