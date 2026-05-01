/**
 * Shared Playwright fixtures and page object helpers.
 * Full page objects implemented as features are built (Story 1.9+).
 */

import { type Page, expect } from "@playwright/test"

/** Navigate to the home page and wait for it to load. */
export async function gotoHome(page: Page): Promise<void> {
  await page.goto("/")
  await page.waitForLoadState("networkidle")
}

/** Assert the page title is set (non-empty). */
export async function assertTitlePresent(page: Page): Promise<void> {
  const title = await page.title()
  expect(title).toBeTruthy()
}

/** Assert the health endpoint returns OK. */
export async function assertServerHealthy(page: Page): Promise<void> {
  const response = await page.request.get("/health")
  expect(response.status()).toBe(200)
  const body = await response.json()
  expect(body.status).toBe("ok")
}
