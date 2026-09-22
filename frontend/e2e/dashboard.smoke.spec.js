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

test("opens the data center and shows real CSV preflight errors", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="data"]').click();
    await expect(page.locator("#dataCenterPage")).toBeVisible();
    await expect(page.locator("#dataCenterStatus")).not.toHaveText("加载版本清单中");
    await expect(page.locator("#dataCenterPage .dataset-table")).toBeVisible();

    const invalidSales = [
        "date,product_id,store_id,product_name,store_name,category,sales,price",
        "2026-01-01,1,1,P1,S1,食品,-1,12.5",
    ].join("\n");
    await page.locator("#salesDatasetFile").setInputFiles({
        name: "invalid-sales.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(invalidSales, "utf8"),
    });
    await page.locator("#previewSalesDataset").click();
    await expect(page.locator("#salesDatasetPreview")).toContainText("第 2 行");
    await expect(page.locator("#uploadSalesDataset")).toBeDisabled();
});

test("opens the model center and shows the persistent training surface", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="models"]').click();
    await expect(page.locator("#modelCenterPage")).toBeVisible();
    await expect(page.locator("#startModelTraining")).toBeVisible();
    await expect(page.locator("#modelVersionsBody")).toBeAttached();
    await expect(page.locator("#modelCenterStatus")).not.toHaveText("加载模型清单中");
});

test("opens forecast analysis and exposes source-traceable detail", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="forecast"]').click();
    await expect(page.locator("#forecastAnalysisPage")).toBeVisible();
    await expect(page.locator("#forecastAnalysisStatus")).not.toHaveText("加载目录中");
    await expect(page.locator("#forecastSourceSummary")).toContainText("有效历史样本");
    await expect(page.locator("#exportForecastCsv")).toBeEnabled();
});

test("shows complete forecast detail and downloads a safe CSV", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="forecast"]').click();
    await expect(page.locator("#forecastAnalysisStatus")).toHaveText("明细已更新");
    await expect(page.locator("#forecastHistoryBody tr")).toHaveCount(30);
    await expect(page.locator("#forecastFutureBody tr")).toHaveCount(30);
    await expect(page.locator("#forecastMetricSummary")).toContainText("MAPE");

    const download = page.waitForEvent("download");
    await page.locator("#exportForecastCsv").click();
    expect((await download).suggestedFilename()).toMatch(/^forecast-\d+-\d+\.csv$/);
});

test("opens inventory decision and exposes server-side what-if controls", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="inventory"]').click();
    await expect(page.locator("#inventoryDecisionPage")).toBeVisible();
    await expect(page.locator("#inventoryDecisionStatus")).not.toHaveText("加载库存清单中");
    await expect(page.locator("#replenishmentBody")).toBeAttached();
    await expect(page.locator("#replenishmentRiskFilter")).toBeVisible();
});

test("filters inventory risk and renders the server-side replenishment formula", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="inventory"]').click();
    await expect(page.locator("#inventoryDecisionStatus")).toHaveText("库存清单已更新");
    const unfilteredRow = page.locator("#replenishmentBody tr[data-key]").first();
    await expect(unfilteredRow).toBeVisible();
    const risk = (await unfilteredRow.locator("td").nth(4).textContent()).trim();
    await page.locator("#replenishmentRiskFilter").selectOption(risk);
    const firstRow = page.locator("#replenishmentBody tr[data-key]").first();
    await expect(firstRow).toBeVisible();
    await firstRow.locator(".replenishment-select").check();
    await page.locator("#replenishmentPackSize").fill("10");
    await page.locator("#replenishmentMoq").fill("30");
    await page.locator("#runReplenishmentPreview").click();
    await expect(page.locator("#replenishmentPreview")).toContainText("包装/MOQ 后建议");
    await expect(page.locator("#replenishmentPreview")).toContainText("来源库存");
});

test("creates a batch replenishment draft from selected inventory rows", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="inventory"]').click();
    await expect(page.locator("#inventoryDecisionPage")).toBeVisible();
    const firstRow = page.locator("#replenishmentBody tr[data-key]").first();
    await expect(firstRow).toBeVisible();
    await firstRow.locator(".replenishment-select").check();
    await expect(page.locator("#createReplenishmentPlan")).toBeEnabled();

    await page.locator("#replenishmentAdjustmentQuantity").fill("1");
    await page.locator("#replenishmentAdjustmentReason").fill("面试演示调整");
    await page.locator("#createReplenishmentPlan").click();
    await expect(page.locator("#replenishmentPreview")).toContainText("草案");
});

test("opens plan center with immutable draft history surface", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="plans"]').click();
    await expect(page.locator("#planCenterPage")).toBeVisible();
    await expect(page.locator("#planVersionsBody")).toBeAttached();
    await expect(page.locator("#planCenterStatus")).not.toHaveText("加载草案中");
});

test("opens system status and shows runtime diagnostics", async ({ page }) => {
    await waitForDashboard(page);

    await page.locator('.app-nav [data-route="system"]').click();
    await expect(page.locator("#systemPage")).toBeVisible();
    await expect(page.locator("#systemPageStatus")).not.toHaveText("加载系统状态中");
    await expect(page.locator("#systemRuntimeBody")).toBeAttached();
    await expect(page.locator("#demoScenarioSelect")).toBeVisible();
    await expect(page.locator("#createDiagnosticPackage")).toBeVisible();
});
