import { defineConfig, devices } from "@playwright/test"

/**
 * Playwright configuration for lingosips E2E tests.
 *
 * Tests run against a REAL backend (never mocked) on port 7842.
 * Start the test server with: make test-server
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:7842",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "cd .. && make test-server",
    url: "http://localhost:7842/health",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
