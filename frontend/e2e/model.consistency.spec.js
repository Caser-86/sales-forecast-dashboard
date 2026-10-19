const { test, expect } = require("@playwright/test");

test.beforeEach(async ({}, testInfo) => {
    testInfo.skip(
        process.env.DEMO_TRAINING_PROFILE !== "full",
        "requires scripts/verify_offline_demo.ps1 -RunModelConsistencyE2E"
    );
});

function apiUrl(path) {
    return `${process.env.API_BASE_URL || "http://127.0.0.1:18006/api"}${path}`;
}

async function readJson(page, path) {
    let lastError;
    for (let attempt = 0; attempt < 4; attempt += 1) {
        try {
            const response = await page.request.get(apiUrl(path));
            expect(response.ok()).toBeTruthy();
            return response.json();
        } catch (error) {
            lastError = error;
            await page.waitForTimeout(250 * (attempt + 1));
        }
    }
    throw lastError;
}

async function openDashboard(page) {
    if (process.env.API_BASE_URL) {
        await page.addInitScript({
            content: `window.API_BASE_URL = ${JSON.stringify(process.env.API_BASE_URL)}`
        });
    }
    await page.goto("/");
    await expect(page.locator("#loading")).toHaveClass(/hidden/);
}

async function waitForTraining(page, jobId) {
    return expect.poll(async () => {
        let job;
        try {
            job = await readJson(page, `/jobs/${encodeURIComponent(jobId)}`);
        } catch (_) {
            // A single connection reset must not abort a long-running local job poll.
            return "temporarily_unavailable";
        }
        if (job.status === "failed" || job.status === "interrupted") {
            throw new Error(`普通完整训练未成功：${job.error_message || job.status}`);
        }
        return job.status;
    }, {
        timeout: 600_000,
        intervals: [3000, 5000, 10000]
    }).toBe("succeeded");
}

test("keeps the normal training model version consistent across serving pages", async ({ page }) => {
    test.setTimeout(900_000);
    const pageErrors = [];
    page.on("pageerror", error => pageErrors.push(error.message));

    await openDashboard(page);
    await page.locator('.app-nav [data-route="models"]').click();
    await expect(page.locator("#modelCenterPage")).toBeVisible();
    await expect(page.locator("#modelCenterStatus")).not.toHaveText("加载模型清单中");

    await page.locator("#startModelTraining").click();
    await expect.poll(async () => page.locator("#modelTrainingStatus").textContent(), {
        timeout: 15_000
    }).toMatch(/任务\s+\S+\s+已提交/);
    const submitted = await page.locator("#modelTrainingStatus").textContent();
    const jobId = submitted.match(/任务\s+(\S+)\s+已提交/)[1];
    // Leave the polling-heavy model page while the real worker trains in the background.
    await page.goto("about:blank");
    await waitForTraining(page, jobId);

    const job = await readJson(page, `/jobs/${encodeURIComponent(jobId)}`);
    const modelId = job.result?.model_id;
    expect(modelId).toMatch(/^model-[0-9a-f]{16}$/);

    await openDashboard(page);
    await page.locator('.app-nav [data-route="models"]').click();
    const candidateRow = page.locator("#modelVersionsBody tr").filter({ hasText: modelId });
    await expect(candidateRow).toContainText("候选可发布");
    await expect(candidateRow.locator(".model-activate")).toBeVisible();
    page.once("dialog", dialog => dialog.accept());
    await candidateRow.locator(".model-activate").click();
    await expect(page.locator("#modelTrainingStatus")).toContainText(modelId);

    await expect.poll(async () => (await readJson(page, "/models")).active_model, {
        timeout: 15_000
    }).toBe(modelId);

    const metadata = await readJson(page, "/metadata");
    const modelInfo = await readJson(page, "/model-info");
    expect(metadata.model_version).toBe(modelId);
    expect(modelInfo.status).toBe("ready");

    await page.locator('.app-nav [data-route="overview"]').click();
    await expect(page.locator("#versionSummary")).toContainText(modelId);

    await page.locator('.app-nav [data-route="data"]').click();
    await expect(page.locator("#dataCenterStatus")).toContainText("版本清单已更新");
    await expect(page.locator("#datasetVersionsBody")).toContainText(modelId);

    await page.locator('.app-nav [data-route="forecast"]').click();
    await expect(page.locator("#forecastAnalysisStatus")).toContainText("明细已更新");
    await expect(page.locator("#forecastSourceSummary")).toContainText(modelId);

    await page.locator('.app-nav [data-route="inventory"]').click();
    await expect(page.locator("#inventorySourceSummary")).toContainText(modelId);

    await page.locator('.app-nav [data-route="system"]').click();
    await expect(page.locator("#systemRuntimeBody")).toContainText(modelId);
    expect(pageErrors).toEqual([]);
});
