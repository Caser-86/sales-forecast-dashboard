const fs = require("fs");
const os = require("os");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const { chromium } = require(path.join(repoRoot, "frontend", "node_modules", "playwright"));
const baseUrl = process.env.BASE_URL || "http://127.0.0.1:3000";
const stamp = process.env.ZOOM_STAMP || "browser-zoom-200";
const outputDir = process.env.ZOOM_OUTPUT_DIR || path.join(repoRoot, "docs", "evidence");
const chromeCandidates = [
    process.env.CHROME_PATH,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe")
].filter(Boolean);
const chromePath = chromeCandidates.find(candidate => fs.existsSync(candidate));

if (!chromePath) {
    throw new Error("Google Chrome was not found. Set CHROME_PATH to a Chrome executable.");
}

function writePreferences(profileDir, hostname) {
    const defaultDir = path.join(profileDir, "Default");
    fs.mkdirSync(defaultDir, { recursive: true });
    const preferences = {
        partition: {
            per_host_zoom_levels: {
                x: {
                    [hostname]: {
                        last_modified: "13433999999999999",
                        zoom_level: 3.8017840169239308
                    }
                }
            }
        }
    };
    fs.writeFileSync(path.join(defaultDir, "Preferences"), JSON.stringify(preferences));
}

async function main() {
    const url = new URL(baseUrl);
    const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "sales-forecast-zoom-"));
    const screenshotPath = path.join(outputDir, `${stamp}.png`);
    const outputPath = path.join(outputDir, `${stamp}.json`);
    fs.mkdirSync(outputDir, { recursive: true });
    writePreferences(profileDir, url.hostname);

    let browser;
    try {
        browser = await chromium.launchPersistentContext(profileDir, {
            headless: false,
            executablePath: chromePath,
            viewport: { width: 1280, height: 900 },
            args: ["--no-first-run", "--no-default-browser-check", "--disable-popup-blocking"]
        });
        const page = browser.pages()[0] || await browser.newPage();
        const pageErrors = [];
        page.on("pageerror", error => pageErrors.push(error.message));

        await page.goto(baseUrl);
        await page.locator("#loading.hidden").waitFor({ state: "attached", timeout: 30_000 });
        await page.waitForTimeout(700);

        const zoom = await page.evaluate(() => ({
            devicePixelRatio: window.devicePixelRatio,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            bodyZoom: getComputedStyle(document.body).zoom,
            scrollHeight: document.documentElement.scrollHeight,
            viewport: window.innerHeight
        }));
        if (Math.abs(zoom.devicePixelRatio - 2) > 0.01 || zoom.innerWidth !== 640 || zoom.innerHeight !== 450) {
            throw new Error(`Expected real 200% browser zoom, got ${JSON.stringify(zoom)}`);
        }

        const controls = await page.evaluate(() => Object.fromEntries(
            ["refreshDashboard", "planName", "savePlan"].map(id => {
                const element = document.getElementById(id);
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return [id, {
                    visible: style.display !== "none" && style.visibility !== "hidden",
                    inViewport: rect.bottom > 0 && rect.top < window.innerHeight,
                    rect: rect.toJSON()
                }];
            })
        ));

        await page.locator("#scopeProductSelect").selectOption("1");
        await page.locator("#scopeLabel").waitFor({ state: "visible", timeout: 10_000 });
        await page.locator("#savePlan").waitFor({ state: "visible" });
        if (!await page.locator("#savePlan").isEnabled()) {
            throw new Error("Save control did not become enabled at 200% zoom");
        }
        await page.locator("#savePlan").click();
        await page.waitForFunction(
            () => /已保存|已幂等恢复/.test(document.getElementById("planStatus")?.textContent || ""),
            null,
            { timeout: 30_000 }
        );

        const exportHref = await page.locator("#exportPlan").getAttribute("href");
        const exportVisible = await page.locator("#exportPlan").isVisible();
        const status = await page.locator("#planStatus").innerText();
        if (!exportVisible || !exportHref || !/\/api\/plans\/.+\/export/.test(exportHref)) {
            throw new Error("Export link is not reachable at 200% zoom");
        }

        await page.screenshot({ path: screenshotPath, fullPage: true });
        const result = {
            browser: "Google Chrome",
            zoomLevel: "200%",
            zoom,
            controls,
            status,
            exportVisible,
            exportHref,
            pageErrors,
            screenshot: screenshotPath
        };
        fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
        console.log(JSON.stringify(result));
    } finally {
        if (browser) await browser.close();
        fs.rmSync(profileDir, { recursive: true, force: true });
    }
}

main().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
