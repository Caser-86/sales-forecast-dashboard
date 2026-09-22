const { test, expect } = require("@playwright/test");

async function waitForDashboard(page) {
    if (process.env.API_BASE_URL) {
        await page.addInitScript({
            content: `window.API_BASE_URL = ${JSON.stringify(process.env.API_BASE_URL)};`
        });
    }
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

test("navigates with keyboard, survives refresh, and preserves the active scope", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator("#scopeProductSelect").selectOption("1");
    await page.locator('.app-nav [data-route="forecast"]').focus();
    await page.keyboard.press("Enter");

    await expect(page).toHaveURL(/#forecast\?product=1/);
    await expect(page.locator("#routePlaceholderTitle")).toHaveText("预测分析");
    await expect(page.locator("#routeScopeSummary")).toContainText("#1");

    await page.reload();
    await expect(page.locator("#loading")).toHaveClass(/hidden/);
    await expect(page).toHaveURL(/#forecast\?product=1/);
    await expect(page.locator("#routePlaceholderTitle")).toHaveText("预测分析");
    await expect(page.locator(".app-nav [data-route=forecast]")).toHaveAttribute("aria-current", "page");
});

test("keeps the navigation shell usable at desktop acceptance widths", async ({ page }) => {
    for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
        await page.setViewportSize(viewport);
        await waitForDashboard(page);
        await expect(page.locator(".app-nav")).toBeVisible();

        const overflow = await page.evaluate(() => ({
            width: document.documentElement.scrollWidth,
            viewportWidth: window.innerWidth
        }));
        expect(overflow.width).toBeLessThanOrEqual(overflow.viewportWidth);
    }
});
