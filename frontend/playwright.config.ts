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
  // All E2E tests share a real SQLite DB — parallel execution causes state
  // interference between completeOnboarding() and resetOnboarding() calls.
  // Use 1 worker to serialize tests in both CI and local environments.
  workers: 1,
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
