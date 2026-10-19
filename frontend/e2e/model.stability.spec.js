const { test, expect } = require("@playwright/test");

test.beforeEach(async ({}, testInfo) => {
    testInfo.skip(
        process.env.DEMO_TRAINING_PROFILE !== "full",
        "requires scripts/verify_offline_demo.ps1 -RunModelStabilityE2E"
    );
});

function apiUrl(path) {
    return `${process.env.API_BASE_URL || "http://127.0.0.1:18006/api"}${path}`;
}

function healthUrl() {
    return apiUrl("/../health").replace("/api/../", "/");
}

async function readJson(page, url, label) {
    let lastError;
    for (let attempt = 0; attempt < 4; attempt += 1) {
        try {
            const response = await page.request.get(url);
            expect(response.ok(), `${label} returned HTTP ${response.status()}`).toBeTruthy();
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

async function waitForTrainingWithProbes(page, jobId, initialModel) {
    const observations = [];
    const deadline = Date.now() + 900_000;
    while (Date.now() < deadline) {
        const [job, health, modelInfo, products, inventory, metadata, models] = await Promise.all([
            readJson(page, apiUrl(`/jobs/${encodeURIComponent(jobId)}`), "job status"),
            readJson(page, healthUrl(), "health"),
            readJson(page, apiUrl("/model-info"), "model info"),
            readJson(page, apiUrl("/products"), "products"),
            readJson(page, apiUrl("/inventory"), "inventory"),
            readJson(page, apiUrl("/metadata"), "metadata"),
            readJson(page, apiUrl("/models"), "models"),
        ]);
        expect(health.status).toBe("healthy");
        expect(modelInfo.status).toBe("ready");
        expect(products.products.length).toBeGreaterThan(0);
        expect(inventory.cells.length).toBeGreaterThan(0);
        expect(metadata.model_version).toBe(initialModel);
        expect(models.active_model).toBe(initialModel);
        observations.push({ status: job.status, phase: job.phase });
        if (job.status === "succeeded") return observations;
        if (["failed", "interrupted"].includes(job.status)) {
            throw new Error(`完整训练未成功：${job.error_message || job.status}`);
        }
        await page.waitForTimeout(3000);
    }
    throw new Error(`完整训练超过 900 秒仍未结束，已完成 ${observations.length} 次稳定性探测`);
}

test("keeps serving APIs healthy during normal full training", async ({ page }) => {
    test.setTimeout(960_000);
    await openDashboard(page);
    const initialModels = await readJson(page, apiUrl("/models"), "initial models");
    const initialModel = initialModels.active_model;
    expect(initialModel).toMatch(/^model-[0-9a-f]{16}$/);

    await page.locator('.app-nav [data-route="models"]').click();
    await expect(page.locator("#modelCenterPage")).toBeVisible();
    await page.locator("#startModelTraining").click();
    await expect.poll(async () => page.locator("#modelTrainingStatus").textContent(), {
        timeout: 15_000,
    }).toMatch(/任务\s+\S+\s+已提交/);
    const submitted = await page.locator("#modelTrainingStatus").textContent();
    const jobId = submitted.match(/任务\s+(\S+)\s+已提交/)[1];
    const observations = await waitForTrainingWithProbes(page, jobId, initialModel);

    expect(observations.length).toBeGreaterThanOrEqual(3);
    const statuses = new Set(observations.map(item => item.status));
    expect(statuses.has("running")).toBeTruthy();
    expect(statuses.has("succeeded")).toBeTruthy();
});
