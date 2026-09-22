const { test, expect } = require("@playwright/test");

test.beforeEach(async ({}, testInfo) => {
    testInfo.skip(
        process.env.DEMO_RUNTIME_ROLLBACK_E2E !== "true",
        "requires scripts/verify_offline_demo.ps1 -RunRuntimeRollbackE2E"
    );
});

async function openDashboard(page) {
    if (process.env.API_BASE_URL) {
        await page.addInitScript({
            content: `window.API_BASE_URL = ${JSON.stringify(process.env.API_BASE_URL)};`
        });
    }
    await page.goto("/");
    await expect(page.locator("#loading")).toHaveClass(/hidden/);
}

async function runtimeCatalog(page) {
    const response = await page.request.get(`${process.env.API_BASE_URL}/datasets`);
    expect(response.ok()).toBeTruthy();
    return response.json();
}

async function activeRuntime(page) {
    const catalog = await runtimeCatalog(page);
    expect(catalog.active_runtime?.snapshot_id).toBeTruthy();
    return catalog.active_runtime;
}

test("publishes, activates twice, and rolls back a runtime snapshot from the data center", async ({ page }) => {
    page.on("dialog", dialog => dialog.accept());
    await openDashboard(page);

    await page.locator('.app-nav [data-route="data"]').click();
    await expect(page.locator("#dataCenterPage")).toBeVisible();
    await expect(page.locator("#dataCenterStatus")).toHaveText("版本清单已更新");

    const initialCatalog = await runtimeCatalog(page);
    const seed = initialCatalog.active_runtime || {
        data_version: initialCatalog.active.data_version,
        model_version: initialCatalog.active.model_version,
        inventory_version: initialCatalog.active.inventory_version,
    };
    await page.locator("#runtimeDataVersion").selectOption(seed.data_version);
    await page.locator("#runtimeModelVersion").selectOption(seed.model_version);
    await page.locator("#runtimeInventoryVersion").selectOption(seed.inventory_version);
    await page.locator("#publishRuntimeSnapshot").click();
    await expect(page.locator("#runtimeSnapshotPreview")).toContainText("已激活");
    const firstActive = await activeRuntime(page);

    const candidateResponse = await page.request.post(`${process.env.API_BASE_URL}/datasets/runtime`, {
        data: {
            data_version: firstActive.data_version,
            model_version: firstActive.model_version,
            inventory_version: firstActive.inventory_version,
            policy_version: `policy-e2e-${Date.now()}`,
        },
    });
    expect(candidateResponse.ok()).toBeTruthy();
    const candidate = await candidateResponse.json();
    expect(candidate.snapshot_id).not.toBe(firstActive.snapshot_id);
    await page.locator("#refreshDatasetCatalog").click();
    await expect(page.locator("#dataCenterStatus")).toHaveText("版本清单已更新");

    const rollbackButton = page.locator(
        `#datasetVersionsBody button.snapshot-rollback[data-snapshot-id="${candidate.snapshot_id}"]`
    );
    await expect(rollbackButton).toBeVisible();
    await rollbackButton.click();
    await expect(page.locator("#runtimeSnapshotPreview")).toContainText(
        `已从 ${firstActive.snapshot_id} 回滚到 ${candidate.snapshot_id}`
    );
    expect((await activeRuntime(page)).snapshot_id).toBe(candidate.snapshot_id);

    const restoreButton = page.locator(
        `#datasetVersionsBody button.snapshot-rollback[data-snapshot-id="${firstActive.snapshot_id}"]`
    );
    await expect(restoreButton).toBeVisible();
    await restoreButton.click();
    await expect(page.locator("#runtimeSnapshotPreview")).toContainText(
        `已从 ${candidate.snapshot_id} 回滚到 ${firstActive.snapshot_id}`
    );
    expect((await activeRuntime(page)).snapshot_id).toBe(firstActive.snapshot_id);

    await page.locator('.app-nav [data-route="overview"]').click();
    await expect(page.locator("#versionSummary")).toContainText(`模型 ${firstActive.model_version}`);
    await page.locator('.app-nav [data-route="forecast"]').click();
    await expect(page.locator("#forecastSourceSummary")).toContainText(`模型 ${firstActive.model_version}`);
    await page.locator('.app-nav [data-route="inventory"]').click();
    await expect(page.locator("#inventorySourceSummary")).toContainText(`模型 ${firstActive.model_version}`);
    await page.locator('.app-nav [data-route="system"]').click();
    await expect(page.locator("#systemRuntimeBody")).toContainText(firstActive.model_version);
});
