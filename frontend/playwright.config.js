const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
    testDir: "./e2e",
    timeout: 30_000,
    expect: {
        timeout: 10_000
    },
    reporter: process.env.CI
        ? [["line"], ["html", { outputFolder: "playwright-report", open: "never" }]]
        : "list",
    use: {
        baseURL: process.env.BASE_URL || "http://127.0.0.1:3000",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
        video: "retain-on-failure"
    }
});
