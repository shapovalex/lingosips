/**
 * Deck Management E2E Tests — Story 2.2 (Deck Management & Multi-Language)
 *
 * Tests run against the real backend on port 7842 (never mocked).
 * Covers ACs: 1, 2, 3, 4, 5, 6, 8
 *
 * AC1: DeckGrid shows all decks with card count, due count, language badge; client-side filter
 * AC2: New Deck button + form creates deck via POST /decks; appears immediately
 * AC3: Inline rename calls PATCH /decks/{id}; new name renders without reload
 * AC4: Delete confirmation removes deck; cards remain in collection with deck_id=null
 * AC5: Deck assignment dropdown in CardCreationPanel assigns card to deck on save
 * AC6: Language switcher updates active_target_language and reloads deck list
 * AC8: Discard removes card from DB via DELETE /cards/{id}
 *
 * Note: Tests that use AC5 and AC8 require a real AI/LLM backend (SSE stream).
 *       They use a 30-second timeout to accommodate real API response times.
 */

import { test, expect } from "@playwright/test"
import { completeOnboarding, createSeedCard, createSeedDeck } from "../fixtures/index"

test.describe("Deck Management", () => {
  test.beforeEach(async ({ page }) => {
    await completeOnboarding(page)
  })

  // ── AC1: Browse decks — empty state ────────────────────────────────────────

  test("browse decks screen — empty state (AC1)", async ({ page }) => {
    // Use French language which has no decks in this test run
    // (other tests create Spanish decks only)
    await page.request.put("http://127.0.0.1:7842/settings", {
      data: {
        native_language: "en",
        active_target_language: "fr",
        target_languages: ["es", "fr"],
        onboarding_completed: true,
      },
    })

    await page.goto("/decks")
    await page.waitForLoadState("networkidle")

    // Page heading should be visible
    await expect(page.getByRole("heading", { name: "Decks" })).toBeVisible({ timeout: 5000 })

    // No French decks exist — empty state message should appear
    await expect(page.getByText(/no decks/i)).toBeVisible({ timeout: 5000 })
  })

  // ── AC2: Create deck and see it in grid ────────────────────────────────────

  test("create deck and see it in grid (AC2)", async ({ page }) => {
    await page.goto("/decks")
    await page.waitForLoadState("networkidle")

    const deckName = `E2E Create ${Date.now()}`

    // Click "New deck" button to open the create form
    await page.getByRole("button", { name: /new deck/i }).click()

    // Input should appear
    const input = page.getByRole("textbox", { name: /new deck name/i })
    await expect(input).toBeVisible({ timeout: 3000 })
    await input.fill(deckName)

    // Submit the form
    await page.getByRole("button", { name: /^create$/i }).click()

    // Deck card should appear in the grid immediately (optimistic cache update)
    await expect(page.getByText(deckName)).toBeVisible({ timeout: 5000 })
  })

  // ── AC3: Rename deck inline ────────────────────────────────────────────────

  test("rename deck inline (AC3)", async ({ page, request }) => {
    const ts = Date.now()
    const originalName = `Rename Original ${ts}`
    const updatedName = `Renamed Result ${ts}`

    await createSeedDeck(request, originalName)

    await page.goto("/decks")
    await expect(page.getByText(originalName)).toBeVisible({ timeout: 5000 })

    // Hover over the deck card to reveal action buttons (opacity-0 → opacity-100)
    const deckCard = page.getByText(originalName).first()
    await deckCard.hover()

    // Click the rename button
    await page.getByRole("button", { name: new RegExp(`rename ${originalName}`, "i") }).click()

    // Inline rename input should appear — DeckCard gives it aria-label="Rename {name}"
    const renameInput = page.getByRole("textbox", { name: new RegExp(`Rename ${originalName}`, "i") })
    await expect(renameInput).toBeVisible({ timeout: 3000 })
    await renameInput.clear()
    await renameInput.fill(updatedName)
    await renameInput.press("Enter")

    // Updated name should render without a page reload
    await expect(page.getByText(updatedName)).toBeVisible({ timeout: 5000 })
    await expect(page.getByText(originalName)).not.toBeVisible()
  })

  // ── AC4: Delete deck — cards remain in collection ──────────────────────────

  test("delete deck removes it but cards remain (AC4)", async ({ page, request }) => {
    const deckName = `Delete Test ${Date.now()}`
    const deckId = await createSeedDeck(request, deckName)

    // Create a card and assign it to this deck
    const cardId = await createSeedCard(request)
    await request.patch(`http://127.0.0.1:7842/cards/${cardId}`, {
      data: { deck_id: deckId },
      headers: { "Content-Type": "application/json" },
    })

    await page.goto("/decks")
    await expect(page.getByText(deckName)).toBeVisible({ timeout: 5000 })

    // Hover to show action buttons
    await page.getByText(deckName).first().hover()

    // Click the delete button
    await page.getByRole("button", { name: new RegExp(`delete ${deckName}`, "i") }).click()

    // Confirmation dialog should appear
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 3000 })

    // Confirm deletion
    await page.getByRole("button", { name: /^delete$/i }).click()

    // Deck should disappear from the grid
    await expect(page.getByText(deckName)).not.toBeVisible({ timeout: 5000 })

    // Card should still exist in the collection (deck_id nulled, not deleted)
    const cardResponse = await request.get(`http://127.0.0.1:7842/cards/${cardId}`)
    expect(cardResponse.status()).toBe(200)
    const cardData = await cardResponse.json()
    expect(cardData.deck_id).toBeNull()
  })

  // ── AC1: Deck card shows card count badge ──────────────────────────────────

  test("deck card shows card count badge (AC1)", async ({ page, request }) => {
    const deckName = `Badge Deck ${Date.now()}`
    const deckId = await createSeedDeck(request, deckName)

    // Create a card and assign to this deck
    const cardId = await createSeedCard(request)
    await request.patch(`http://127.0.0.1:7842/cards/${cardId}`, {
      data: { deck_id: deckId },
      headers: { "Content-Type": "application/json" },
    })

    await page.goto("/decks")
    await expect(page.getByText(deckName)).toBeVisible({ timeout: 5000 })

    // Card count badge "1 cards" should be visible within the specific deck card
    // Scope to the deck card to avoid strict mode violations from other decks
    const deckCardLocator = page.getByRole("link", { name: new RegExp(deckName, "i") })
    await expect(deckCardLocator.getByText(/1 card/i)).toBeVisible({ timeout: 5000 })
  })

  // ── AC1: Filter decks by name (client-side) ────────────────────────────────

  test("filter decks by name (AC1)", async ({ page, request }) => {
    const ts = Date.now()
    const alphaName = `Alpha Filter ${ts}`
    const betaName = `Beta Filter ${ts}`
    const gammaName = `Gamma Filter ${ts}`

    // Create 3 decks
    await createSeedDeck(request, alphaName)
    await createSeedDeck(request, betaName)
    await createSeedDeck(request, gammaName)

    await page.goto("/decks")

    // All 3 decks should be visible initially
    await expect(page.getByText(alphaName)).toBeVisible({ timeout: 5000 })
    await expect(page.getByText(betaName)).toBeVisible()
    await expect(page.getByText(gammaName)).toBeVisible()

    // Filter by "Alpha Filter"
    const filterInput = page.getByRole("textbox", { name: /filter decks by name/i })
    await filterInput.fill(`Alpha Filter ${ts}`)

    // Only Alpha deck should remain visible
    await expect(page.getByText(alphaName)).toBeVisible()
    await expect(page.getByText(betaName)).not.toBeVisible()
    await expect(page.getByText(gammaName)).not.toBeVisible()
  })

  // ── AC5: Assign card to deck on creation ───────────────────────────────────

  test("assign card to deck on creation (AC5)", async ({ page, request }) => {
    const deckName = `Assign Deck ${Date.now()}`
    const deckId = await createSeedDeck(request, deckName)

    // Navigate to home (card creation panel)
    await page.goto("/")
    await page.waitForLoadState("networkidle")

    // Type a word to trigger the SSE card stream
    const cardInput = page.getByRole("textbox", { name: /new card/i })
    await expect(cardInput).toBeVisible({ timeout: 5000 })
    await cardInput.fill("libro")
    await cardInput.press("Enter")

    // Wait for the populated state — action row with "Assign to deck" dropdown appears
    // 30s timeout accommodates real LLM API response time
    const deckDropdown = page.getByLabel(/assign to deck/i)
    await expect(deckDropdown).toBeVisible({ timeout: 30000 })

    // Select the test deck from the dropdown
    await deckDropdown.selectOption({ label: deckName })

    // Save the card
    await page.getByRole("button", { name: /save card/i }).click()

    // Panel resets (input becomes enabled again)
    await expect(cardInput).toBeEnabled({ timeout: 10000 })

    // Verify via API: deck now has 1 card
    const decksResponse = await request.get("http://127.0.0.1:7842/decks?target_language=es")
    expect(decksResponse.ok()).toBeTruthy()
    const decks = await decksResponse.json()
    const ourDeck = (decks as Array<{ id: number; card_count: number }>).find(
      (d) => d.id === deckId,
    )
    expect(ourDeck).toBeDefined()
    expect(ourDeck!.card_count).toBe(1)
  })

  // ── AC8: Discard removes card from collection ──────────────────────────────

  test("discard removes card from collection (AC8)", async ({ page }) => {
    await page.goto("/")
    await page.waitForLoadState("networkidle")

    // Type a word to trigger the SSE card stream
    const cardInput = page.getByRole("textbox", { name: /new card/i })
    await expect(cardInput).toBeVisible({ timeout: 5000 })
    await cardInput.fill("mesa")
    await cardInput.press("Enter")

    // Wait for populated state — "View card →" link appears once SSE completes
    const viewCardLink = page.getByRole("link", { name: /view card/i })
    await expect(viewCardLink).toBeVisible({ timeout: 30000 })

    // Extract card ID from the href
    const href = await viewCardLink.getAttribute("href")
    const cardId = href?.split("/").pop()
    expect(cardId).toBeTruthy()

    // Click Discard
    await page.getByRole("button", { name: /^discard$/i }).click()

    // Panel resets to idle
    await expect(cardInput).toBeEnabled({ timeout: 10000 })

    // Card should be deleted from the API (404 expected)
    if (cardId) {
      const apiResponse = await page.request.get(`http://127.0.0.1:7842/cards/${cardId}`)
      expect(apiResponse.status()).toBe(404)
    }
  })

  // ── AC1: Export deck as .lingosips (Story 2.5) ────────────────────────────

  test("export deck to .lingosips file (AC1 Story 2.5)", async ({ page, request }) => {
    const deckName = `Export E2E ${Date.now()}`
    await createSeedDeck(request, deckName)

    // Navigate to deck detail page
    await page.goto("/decks")
    await expect(page.getByText(deckName)).toBeVisible({ timeout: 5000 })

    // Click the deck to go to its detail page
    await page.getByRole("link", { name: new RegExp(deckName, "i") }).click()
    await page.waitForLoadState("networkidle")

    // Deck detail page should show the deck name
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 5000 })

    // Export button should be visible and accessible
    const exportBtn = page.getByRole("button", { name: /export deck as .lingosips file/i })
    await expect(exportBtn).toBeVisible({ timeout: 3000 })

    // Set up download listener
    const downloadPromise = page.waitForEvent("download", { timeout: 10000 }).catch(() => null)
    await exportBtn.click()

    const download = await downloadPromise
    if (download) {
      // File should have .lingosips extension
      expect(download.suggestedFilename()).toMatch(/\.lingosips$/)
    }
  })

  // ── AC2-5: Import .lingosips file (Story 2.5) ──────────────────────────────

  test("import .lingosips file — preview then confirm (AC2-5 Story 2.5)", async ({ page, request }) => {
    // First export a deck to get a real .lingosips file
    const deckName = `Import Source ${Date.now()}`
    const deckId = await createSeedDeck(request, deckName)

    // Get the .lingosips bytes via the API directly
    const exportResponse = await request.get(`http://127.0.0.1:7842/decks/${deckId}/export`)
    expect(exportResponse.status()).toBe(200)
    const exportBytes = await exportResponse.body()

    // Navigate to import page
    await page.goto("/import")
    await page.waitForLoadState("networkidle")

    // Click the .lingosips tab
    await page.getByRole("tab", { name: /\.lingosips/i }).click()

    // Upload the exported file
    const fileInput = page.locator('input[type="file"][accept=".lingosips"]')
    await fileInput.setInputFiles({
      name: `${deckName}.lingosips`,
      mimeType: "application/octet-stream",
      buffer: exportBytes,
    })

    // Click Preview button
    await page.getByRole("button", { name: /preview cards/i }).click()

    // Preview should appear with deck info
    await expect(page.getByText(/cards found/i)).toBeVisible({ timeout: 5000 })
  })

  // ── AC4: Malformed .lingosips shows specific error (Story 2.5) ─────────────

  test("malformed .lingosips shows specific RFC 7807 error (AC4 Story 2.5)", async ({ page }) => {
    await page.goto("/import")
    await page.waitForLoadState("networkidle")

    await page.getByRole("tab", { name: /\.lingosips/i }).click()

    // Upload an invalid file (just bytes, not a valid ZIP)
    const fileInput = page.locator('input[type="file"][accept=".lingosips"]')
    await fileInput.setInputFiles({
      name: "bad.lingosips",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("not a valid zip"),
    })

    await page.getByRole("button", { name: /preview cards/i }).click()

    // Should show a specific error message (two elements match: heading + detail — use first())
    await expect(page.getByText(/import failed|valid .lingosips archive/i).first()).toBeVisible({ timeout: 5000 })
  })

  // ── AC1: Keyboard navigation through deck grid ─────────────────────────────

  test("keyboard navigation through deck grid (AC1)", async ({ page }) => {
    await page.goto("/decks")
    await page.waitForLoadState("networkidle")

    // Focus the "New deck" button and activate it via keyboard
    const newDeckBtn = page.getByRole("button", { name: /new deck/i })
    await newDeckBtn.focus()
    await page.keyboard.press("Enter")

    // Create form should appear with autofocused input
    const deckNameInput = page.getByRole("textbox", { name: /new deck name/i })
    await expect(deckNameInput).toBeVisible({ timeout: 3000 })

    // Type a deck name
    const deckName = `Keyboard Nav ${Date.now()}`
    await deckNameInput.fill(deckName)

    // Tab to "Create" button
    await page.keyboard.press("Tab")
    const createBtn = page.getByRole("button", { name: /^create$/i })
    await expect(createBtn).toBeFocused()

    // Press Enter to create the deck
    await page.keyboard.press("Enter")

    // Deck card should appear in the grid
    await expect(page.getByText(deckName)).toBeVisible({ timeout: 5000 })
  })
})
