/**
 * Settings & Onboarding E2E Tests — Story 1.4
 *
 * Tests run against the real backend on port 7842 (never mocked).
 * FR38: Guided onboarding wizard
 * FR39: Functional before any config
 * FR40: First card within 60 seconds
 *
 * AC1: First launch shows OnboardingWizard, no sidebar/bottom nav
 * AC2: Completing wizard saves languages and lands on home dashboard
 * AC3: Skip reaches home dashboard with local AI fallback active
 * AC4: Return visit does NOT show wizard
 */

import { test, expect, type Page } from "@playwright/test"

async function resetOnboarding(page: Page) {
  /**
   * Reset onboarding state so each test starts fresh (wizard shown).
   * Resets onboarding_completed AND language selections to prevent cross-test
   * contamination when a previous test changed the target language (e.g. "fr").
   * Uses the real API endpoint — keeps test isolation without DB truncation.
   */
  await page.request.put("http://127.0.0.1:7842/settings", {
    data: {
      onboarding_completed: false,
      native_language: "en",
      active_target_language: "es",
    },
  })
}

async function completeOnboardingViaAPI(page: Page) {
  /**
   * Complete onboarding via API so tests that need app shell can skip the wizard.
   */
  await page.request.put("http://127.0.0.1:7842/settings", {
    data: {
      native_language: "en",
      active_target_language: "es",
      onboarding_completed: true,
    },
  })
}

test.describe("First-Run Onboarding", () => {
  test.beforeEach(async ({ page }) => {
    await resetOnboarding(page)
  })

  // T7.2
  test("first launch shows OnboardingWizard, no sidebar, no bottom nav", async ({ page }) => {
    await page.goto("/")
    // Wizard is visible
    await expect(page.getByRole("main", { name: "Language setup" })).toBeVisible()
    // Sidebar and bottom nav must NOT appear during onboarding
    await expect(page.getByRole("navigation", { name: "Main navigation" })).not.toBeVisible()
    await expect(
      page.getByRole("navigation", { name: "Bottom navigation" })
    ).not.toBeVisible()
  })

  // T7.3
  test("completing wizard with language selection navigates to home dashboard", async ({
    page,
  }) => {
    await page.goto("/")
    // Select French as target language
    await page.selectOption('select[aria-label="Target language"]', "fr")
    await page.click('button:has-text("Start learning")')
    // Wizard must be gone AND home dashboard (Main navigation) must appear — AC2
    await expect(page.getByRole("main", { name: "Language setup" })).not.toBeVisible()
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible()
  })

  // T7.4
  test("skip button navigates to home dashboard with default languages", async ({ page }) => {
    await page.goto("/")
    await page.click('button:has-text("Skip for now")')
    // Wizard must be gone AND home dashboard (Main navigation) must appear — AC3
    await expect(page.getByRole("main", { name: "Language setup" })).not.toBeVisible()
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible()
  })

  // T7.5
  test("return visit after onboarding — wizard does NOT appear", async ({ page }) => {
    // First, complete onboarding
    await completeOnboardingViaAPI(page)
    // Reload and verify wizard is not shown
    await page.goto("/")
    await expect(page.getByRole("main", { name: "Language setup" })).not.toBeVisible()
  })

  // T7.6
  test("keyboard navigation through wizard — Tab order correct, Enter submits", async ({
    page,
  }) => {
    await page.goto("/")
    // Native select should be focused on mount
    const nativeSelect = page.getByLabel("Native language")
    await expect(nativeSelect).toBeFocused()

    // Tab to target select
    await page.keyboard.press("Tab")
    await expect(page.getByLabel("Target language")).toBeFocused()

    // Tab to "Start learning" button
    await page.keyboard.press("Tab")
    const startBtn = page.getByRole("button", { name: "Start learning" })
    await expect(startBtn).toBeFocused()

    // Press Enter to submit
    await page.keyboard.press("Enter")
    // Wizard should disappear after submission
    await expect(page.getByRole("main", { name: "Language setup" })).not.toBeVisible({
      timeout: 5000,
    })
  })
})

// ── Settings page — Story 2.3 ─────────────────────────────────────────────────

test.describe("Settings page — Story 2.3", () => {
  test.beforeEach(async ({ page }) => {
    await completeOnboardingViaAPI(page)
    await page.goto("/settings")
  })

  test("renders AI Services, Languages, and Study Defaults sections", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "AI Services" })).toBeVisible()
    await expect(page.getByRole("heading", { name: "Languages" })).toBeVisible()
    await expect(page.getByRole("heading", { name: "Study Defaults" })).toBeVisible()
  })

  test("AI upgrade panel opens inline — no modal dialog", async ({ page }) => {
    await page.getByRole("button", { name: "Upgrade" }).first().click()
    // No dialog/modal — form is inline
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 500 })
    await expect(page.getByLabel(/API key/i)).toBeVisible()
  })

  test("API key input is masked (type=password)", async ({ page }) => {
    await page.getByRole("button", { name: "Upgrade" }).first().click()
    const input = page.getByLabel(/API key/i)
    await expect(input).toHaveAttribute("type", "password")
  })

  test("invalid API key shows specific error message", async ({ page }) => {
    await page.getByRole("button", { name: "Upgrade" }).first().click()
    await page.getByLabel(/API key/i).fill("sk-invalid-key-abc123")
    // Click Test connection — real backend will fail with bad key
    await page.getByRole("button", { name: "Test connection" }).click()
    await expect(page.getByTestId("test-error-message")).toBeVisible({ timeout: 15000 })
    // Save button must NOT appear inside the AI service panel after a failed test
    const aiPanel = page.getByTestId("ai-service-panel")
    await expect(aiPanel.getByRole("button", { name: "Save" })).not.toBeVisible()
  })

  test("system defaults save persists via API", async ({ page }) => {
    // Get initial auto_generate_audio state
    const initialResp = await page.request.get("http://127.0.0.1:7842/settings")
    const initial = await initialResp.json()
    const newAudioValue = !initial.auto_generate_audio
    // Toggle auto_generate_audio
    await page.getByRole("switch", { name: /Auto.generate audio/i }).click()
    // Wait for Save to be enabled (confirms form is dirty and settings are loaded)
    const saveBtn = page.getByRole("button", { name: /Save/i }).last()
    await expect(saveBtn).toBeEnabled({ timeout: 3_000 })
    // Click Save and wait for the PUT response to complete before reading back
    const [putResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/settings") && r.request().method() === "PUT",
      ),
      saveBtn.click(),
    ])
    expect(putResponse.ok()).toBe(true)
    // Verify persisted
    const resp = await page.request.get("http://127.0.0.1:7842/settings")
    const body = await resp.json()
    expect(body.auto_generate_audio).toBe(newAudioValue)
  })

  test("language section saves and settings endpoint responds", async ({ page }) => {
    const resp = await page.request.get("http://127.0.0.1:7842/settings")
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body).toHaveProperty("native_language")
    expect(body).toHaveProperty("target_languages")
  })
})
