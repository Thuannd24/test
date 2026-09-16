import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration.
 *
 * Prerequisites:
 *   1. Start the full stack: docker-compose up --build
 *   2. Install Playwright: cd e2e && npm install && npx playwright install
 *   3. Run tests: npx playwright test
 *
 * Run headed: npx playwright test --headed
 * Run specific test: npx playwright test todo-journey
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false, // run sequentially to avoid port conflicts on local
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [["html", { outputFolder: "playwright-report" }], ["list"]],

  use: {
    /** Base URL of the running frontend */
    baseURL: process.env.FRONTEND_URL || "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
  ],

  /** Timeout per test */
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
});
