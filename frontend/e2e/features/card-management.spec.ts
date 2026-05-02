/**
 * Card Management E2E Tests — Story 2.1 (Card Detail, Editing & Notes)
 *
 * Tests run against the real backend on port 7842 (never mocked).
 * Covers ACs: 1–5
 *
 * AC1: CardDetail renders all fields at /cards/{card_id}
 * AC2: Inline editing of AI-generated fields (translation)
 * AC3: Personal note persists on blur
 * AC4: Delete confirmation dialog appears with correct text
 * AC5: Confirmed delete removes card and navigates home
 */

import { test, expect } from "@playwright/test"
import { completeOnboarding, createSeedCard } from "../fixtures/index"

test.describe("Card Management — Card Detail", () => {
  test.beforeEach(async ({ page }) => {
    await completeOnboarding(page)
  })

  // ── AC1: View card detail ─────────────────────────────────────────────────

  test("view card detail via URL navigation (AC1)", async ({ page }) => {
    // Create a seed card via API
    const cardId = await createSeedCard(page.request)

    // Navigate to card detail page
    await page.goto(`/cards/${cardId}`)

    // Target word should be visible as the page heading
    await expect(page.getByRole("heading", { name: "prueba" })).toBeVisible({ timeout: 5000 })

    // Language + card type info: rendered as "es · word" in metadata line
    await expect(page.getByText(/\bes\s*·/)).toBeVisible()

    // FSRS status visible for new card
    await expect(page.getByText("Not yet practiced")).toBeVisible()

    // Translation section should be visible
    await expect(page.getByText(/translation/i)).toBeVisible()
  })

  // ── AC2: Inline translation edit ─────────────────────────────────────────

  test("edit translation inline (AC2)", async ({ page }) => {
    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    // Wait for card to load
    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Find and click the translation display field
    const translationField = page.getByRole("button", { name: /translation/i })
    await translationField.click()

    // Input should appear
    const input = page.getByRole("textbox", { name: /edit translation/i })
    await expect(input).toBeVisible()

    // Clear and type new value
    await input.clear()
    await input.fill("test (edited)")

    // Tab away to trigger blur + PATCH
    await input.press("Tab")

    // Updated value should be reflected
    await expect(page.getByText("test (edited)")).toBeVisible({ timeout: 5000 })
  })

  // ── AC3: Personal note persists ───────────────────────────────────────────

  test("add personal note (AC3)", async ({ page }) => {
    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Click on the personal note area
    const noteField = page.getByRole("button", { name: /personal note/i })
    await noteField.click()

    // Textarea should appear
    const textarea = page.getByRole("textbox", { name: /edit personal note/i })
    await expect(textarea).toBeVisible()

    await textarea.fill("this is my note")

    // Tab away to trigger blur + PATCH
    await textarea.press("Tab")

    // Verify note persists (re-navigate to same card)
    await page.goto(`/cards/${cardId}`)
    await expect(page.getByText("this is my note")).toBeVisible({ timeout: 5000 })
  })

  // ── AC4 & AC5: Delete confirmation + navigation ───────────────────────────

  test("delete card confirms then redirects home (AC4, AC5)", async ({ page }) => {
    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Click Delete card button
    await page.getByRole("button", { name: /delete card/i }).click()

    // Confirmation dialog should appear
    await expect(
      page.getByText(/delete card · this cannot be undone/i)
    ).toBeVisible({ timeout: 3000 })

    // Confirm deletion
    await page.getByRole("button", { name: /^delete$/i }).click()

    // Should redirect to home page
    await expect(page).toHaveURL("/", { timeout: 5000 })

    // Card should no longer be accessible
    const apiResponse = await page.request.get(`http://localhost:7842/cards/${cardId}`)
    expect(apiResponse.status()).toBe(404)
  })

  test("delete cancel does not remove card (AC4)", async ({ page }) => {
    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Click Delete card button
    await page.getByRole("button", { name: /delete card/i }).click()

    // Dialog should appear
    await expect(
      page.getByText(/delete card · this cannot be undone/i)
    ).toBeVisible({ timeout: 3000 })

    // Click Cancel
    await page.getByRole("button", { name: /cancel/i }).click()

    // Dialog should close — card still accessible (heading still visible)
    await expect(page.getByRole("heading", { name: "prueba" })).toBeVisible()

    // Verify card still exists in API
    const apiResponse = await page.request.get(`http://localhost:7842/cards/${cardId}`)
    expect(apiResponse.status()).toBe(200)
  })

  // ── Keyboard navigation ───────────────────────────────────────────────────

  test("keyboard navigation through card detail fields (AC1)", async ({ page }) => {
    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Tab through the page to verify focus ring appears on interactive elements
    await page.keyboard.press("Tab")

    // Verify at least one element has focus (focus ring visible)
    const focusedEl = page.locator(":focus")
    await expect(focusedEl).toBeVisible()
  })
})

// ── Story 2.6: Image section E2E tests ───────────────────────────────────────

test.describe("Card Image — Story 2.6", () => {
  test.beforeEach(async ({ page }) => {
    await completeOnboarding(page)
  })

  test("image section shows 'not configured' text when no image endpoint set (AC4)", async ({ page }) => {
    // By default in test env, no IMAGE_ENDPOINT_URL is configured
    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Image section should show "not configured" text
    await expect(page.getByText(/image endpoint not configured/i)).toBeVisible({ timeout: 3000 })
  })

  test("skip image sets image_skipped state and shows Undo (AC5)", async ({ page }) => {
    // Configure image endpoint for this test via API
    await page.request.post("http://localhost:7842/services/credentials", {
      data: { image_endpoint_url: "http://localhost:9999/nonexistent" },
    })

    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Skip image button should appear when endpoint is configured
    const skipBtn = page.getByRole("button", { name: /skip image/i })
    await skipBtn.waitFor({ timeout: 3000 })
    await skipBtn.click()

    // "Image skipped" state should appear
    await expect(page.getByText(/image skipped/i)).toBeVisible({ timeout: 3000 })
    await expect(page.getByRole("button", { name: /undo/i })).toBeVisible()

    // API should have image_skipped=true
    const apiResponse = await page.request.get(`http://localhost:7842/cards/${cardId}`)
    const cardData = await apiResponse.json()
    expect(cardData.image_skipped).toBe(true)
    expect(cardData.image_url).toBeNull()

    // Clean up: remove image credential
    await page.request.delete("http://localhost:7842/services/credentials/image")
  })

  test("undo skip returns to Add image button (AC5)", async ({ page }) => {
    // Configure image endpoint for this test
    await page.request.post("http://localhost:7842/services/credentials", {
      data: { image_endpoint_url: "http://localhost:9999/nonexistent" },
    })

    const cardId = await createSeedCard(page.request)
    await page.goto(`/cards/${cardId}`)

    await page.getByRole("heading", { name: "prueba" }).waitFor({ timeout: 5000 })

    // Skip first
    const skipBtn = page.getByRole("button", { name: /skip image/i })
    await skipBtn.waitFor({ timeout: 3000 })
    await skipBtn.click()
    await expect(page.getByRole("button", { name: /undo/i })).toBeVisible({ timeout: 3000 })

    // Undo
    await page.getByRole("button", { name: /undo/i }).click()

    // Should show Add image button again
    await expect(page.getByRole("button", { name: /add image/i })).toBeVisible({ timeout: 3000 })

    // API should have image_skipped=false
    const apiResponse = await page.request.get(`http://localhost:7842/cards/${cardId}`)
    const cardData = await apiResponse.json()
    expect(cardData.image_skipped).toBe(false)

    // Clean up
    await page.request.delete("http://localhost:7842/services/credentials/image")
  })
})
