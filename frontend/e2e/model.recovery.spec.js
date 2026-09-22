const { test, expect } = require("@playwright/test");

test("recovers a real failed training job and activates its isolated candidate", async ({ page }) => {
    test.setTimeout(360_000);
    const pageErrors = [];
    page.on("pageerror", error => pageErrors.push(error.message));
    page.on("dialog", dialog => dialog.accept());

    if (process.env.API_BASE_URL) {
        await page.addInitScript({
            content: `window.API_BASE_URL = ${JSON.stringify(process.env.API_BASE_URL)};`
        });
    }
    await page.goto("/");
    await expect(page.locator("#loading")).toHaveClass(/hidden/);

    await page.locator('.app-nav [data-route="models"]').click();
    await expect(page.locator("#modelCenterPage")).toBeVisible();
    await expect(page.locator("#modelCenterStatus")).not.toHaveText("加载模型清单中");

    await page.locator("#startModelTraining").click();
    await expect(page.locator("#modelTrainingStatus")).toContainText("已提交");
    const submission = await page.locator("#modelTrainingStatus").innerText();
    const jobId = submission.match(/任务 (job-[a-f0-9]+) 已提交/)?.[1];
    expect(jobId).toBeTruthy();

    const jobRow = page.locator("#modelJobsBody tr").filter({ hasText: jobId });
    await expect(jobRow).toContainText("failed", { timeout: 90_000 });
    await expect(jobRow).toContainText("演示故障注入：首次训练失败");
    await expect(jobRow.locator(".model-job-retry")).toBeVisible();

    await jobRow.locator(".model-job-retry").click();
    await expect(jobRow).toContainText("succeeded", { timeout: 240_000 });

    const jobResponse = await page.request.get(`${process.env.API_BASE_URL}/jobs/${jobId}`);
    expect(jobResponse.ok()).toBeTruthy();
    const job = await jobResponse.json();
    const candidateModelId = job.result?.model_id;
    expect(candidateModelId).toBeTruthy();
    const candidateRow = page.locator("#modelVersionsBody tr").filter({ hasText: candidateModelId });
    await expect(candidateRow).toContainText("候选可发布");
    await candidateRow.locator(".model-activate").click();
    await expect(page.locator("#modelTrainingStatus")).toContainText("已激活", { timeout: 30_000 });
    await expect(page.locator("#activeModelSummary")).not.toContainText("legacy");
    expect(pageErrors).toEqual([]);
});
