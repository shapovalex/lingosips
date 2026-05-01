/**
 * First Launch → Card Creation Journey
 *
 * Stub test for Story 1.1 — verifies the app loads and page title is present.
 * Full card creation journey implemented in Story 1.9.
 *
 * Updated in Story 1.4: completeOnboarding() called in beforeEach so these
 * tests bypass the first-run wizard and land directly on the home dashboard.
 */

import { test, expect } from "@playwright/test"
import {
  gotoHome,
  assertTitlePresent,
  assertServerHealthy,
  completeOnboarding,
} from "../fixtures/index"

test.describe("First Launch", () => {
  test.beforeEach(async ({ page }) => {
    // Story 1.4: complete onboarding before navigating so wizard doesn't block tests
    await completeOnboarding(page)
  })

  test("page loads and title is present", async ({ page }) => {
    await gotoHome(page)
    await assertTitlePresent(page)
  })

  test("server health endpoint returns ok", async ({ page }) => {
    await assertServerHealthy(page)
  })

  test("home page renders without errors", async ({ page }) => {
    await gotoHome(page)
    // No console errors
    const errors: string[] = []
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text())
    })
    await page.waitForTimeout(500)
    expect(errors).toHaveLength(0)
  })
})
