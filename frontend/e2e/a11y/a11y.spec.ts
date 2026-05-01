/**
 * Accessibility (axe-core) smoke test.
 *
 * Runs @axe-core/playwright against the app home page to catch WCAG 2.1 AA
 * violations before merge. This stub covers the infrastructure requirement (AC: 4).
 * Full per-feature a11y tests are added alongside each feature in later stories.
 */

import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"

test.describe("Accessibility — home page", () => {
  test("home page has no critical axe violations", async ({ page }) => {
    await page.goto("/")
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"]) // WCAG 2.1 AA baseline
      .analyze()

    // Report violations for debugging without failing on deferred issues
    const criticalViolations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )

    expect(
      criticalViolations,
      `Critical/serious axe violations found:\n${criticalViolations.map((v) => `  [${v.impact}] ${v.id}: ${v.description}`).join("\n")}`
    ).toHaveLength(0)
  })

  test("health endpoint is reachable", async ({ page }) => {
    const response = await page.request.get("/health")
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body.status).toBe("ok")
  })
})
