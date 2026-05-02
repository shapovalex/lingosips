/**
 * Practice Self-Assess Mode E2E Tests — Story 3.2
 *
 * Tests run against the real backend on port 7842 (never mocked).
 * Covers: FR17–18, FR24–25
 *
 * AC1: POST /practice/session/start returns due card queue
 * AC2: GET /practice/next-due returns earliest due date
 * AC3: D4 layout — sidebar and right column animate out during session
 * AC4: PracticeCard front state shows target word + "Space to reveal"
 * AC5: PracticeCard revealed state shows translation + FSRS rating row
 * AC6: Rating is optimistic — next card loads immediately
 * AC7: Tooltip labels shown for first 3 sessions only
 * AC8: SessionSummary shown after last card rated
 * AC9: QueueWidget count live-updates after each card is rated
 * AC10: /practice route fully implemented
 */

import { test, expect } from "@playwright/test"
import { completeOnboarding } from "../fixtures/index"

// ── Helpers ────────────────────────────────────────────────────────────────────

/** Create a card that is due NOW via API (sets due to past) */
async function createDueCard(
  request: import("@playwright/test").APIRequestContext,
  targetWord: string,
  cardId?: number,
): Promise<number> {
  if (cardId) {
    // Update existing card's due date to past
    await request.patch(`http://localhost:7842/cards/${cardId}`, {
      data: { due: new Date(Date.now() - 60_000).toISOString() },
      headers: { "Content-Type": "application/json" },
    })
    return cardId
  }

  // Create via SSE stream
  const response = await request.fetch("http://localhost:7842/cards/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    data: JSON.stringify({ target_word: targetWord }),
  })
  const body = await response.text()
  const match = body.match(/"card_id":\s*(\d+)/)
  if (!match) throw new Error(`No card_id in SSE: ${body.slice(0, 200)}`)
  const id = Number(match[1])

  // Set due to past so it appears in queue
  await request.patch(`http://localhost:7842/cards/${id}`, {
    data: { due: new Date(Date.now() - 60_000).toISOString() },
    headers: { "Content-Type": "application/json" },
  })
  return id
}

/** Seed N due cards and return their IDs */
async function seedDueCards(
  request: import("@playwright/test").APIRequestContext,
  count: number,
): Promise<number[]> {
  const ids: number[] = []
  for (let i = 0; i < count; i++) {
    const id = await createDueCard(request, `seed_word_${i}_${Date.now()}`)
    ids.push(id)
  }
  return ids
}

/** Delete cards by ID via API */
async function deleteCards(
  request: import("@playwright/test").APIRequestContext,
  ids: number[],
): Promise<void> {
  for (const id of ids) {
    await request.delete(`http://localhost:7842/cards/${id}`)
  }
}

// ── Test suite ────────────────────────────────────────────────────────────────

test.describe("Practice Self-Assess Mode", () => {
  test.beforeEach(async ({ page }) => {
    await completeOnboarding(page)
  })

  // ── AC1: POST /practice/session/start works ─────────────────────────────────

  test("POST /practice/session/start returns due cards (AC1)", async ({ request }) => {
    const ids = await seedDueCards(request, 2)
    try {
      const response = await request.post("http://localhost:7842/practice/session/start")
      expect(response.status()).toBe(200)
      const data = await response.json()
      expect(Array.isArray(data)).toBe(true)
      // Should have at least 2 cards (the ones we seeded)
      expect(data.length).toBeGreaterThanOrEqual(2)
      // Verify QueueCard shape
      for (const card of data) {
        expect(card).toHaveProperty("id")
        expect(card).toHaveProperty("target_word")
        expect(card).toHaveProperty("fsrs_state")
      }
    } finally {
      await deleteCards(request, ids)
    }
  })

  // ── AC2: GET /practice/next-due works ─────────────────────────────────────

  test("GET /practice/next-due returns earliest due date (AC2)", async ({ request }) => {
    const response = await request.get("http://localhost:7842/practice/next-due")
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty("next_due")
    // next_due can be null (no cards) or a datetime string
    if (data.next_due !== null) {
      expect(() => new Date(data.next_due)).not.toThrow()
    }
  })

  test("GET /practice/next-due returns null when no cards exist", async ({ request }) => {
    // Set active language to a test language unlikely to have cards
    await request.put("http://localhost:7842/settings", {
      data: { native_language: "en", active_target_language: "ja", onboarding_completed: true },
      headers: { "Content-Type": "application/json" },
    })
    const response = await request.get("http://localhost:7842/practice/next-due")
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data.next_due).toBeNull()

    // Reset back to es
    await request.put("http://localhost:7842/settings", {
      data: { native_language: "en", active_target_language: "es", onboarding_completed: true },
      headers: { "Content-Type": "application/json" },
    })
  })

  // ── AC3: D4 layout ─────────────────────────────────────────────────────────

  test("D4 layout: sidebar hidden when session is active (AC3)", async ({ page, request }) => {
    const ids = await seedDueCards(request, 1)
    try {
      await page.goto("/")
      await page.waitForLoadState("networkidle")

      // Sidebar should be visible before session starts
      const sidebarWrapper = page.locator("[data-testid='sidebar-wrapper']")
      await expect(sidebarWrapper).toBeVisible()
      const initialClass = await sidebarWrapper.getAttribute("class")
      expect(initialClass).not.toContain("w-0")

      // Start a practice session
      await page.click("[aria-label='Practice']")
      // TanStack Router's validateSearch appends ?mode=... — use wildcard to match either form
      await page.waitForURL(/.*\/practice.*/)

      // After navigating, session starts — sidebar should collapse
      // Wait for the D4 transition
      await page.waitForFunction(() => {
        const sidebar = document.querySelector("[data-testid='sidebar-wrapper']")
        return sidebar?.className?.includes("w-0")
      }, { timeout: 3000 })

      const sessionClass = await sidebarWrapper.getAttribute("class")
      expect(sessionClass).toContain("w-0")
    } finally {
      await deleteCards(request, ids)
    }
  })

  // ── AC4: PracticeCard front state ──────────────────────────────────────────

  test("PracticeCard front state: shows target word and Space hint (AC4)", async ({ page, request }) => {
    const ids = await seedDueCards(request, 1)
    try {
      await page.goto("/practice")
      await page.waitForLoadState("networkidle")

      // Wait for the practice card to load
      const wordEl = page.locator(".text-4xl").first()
      await expect(wordEl).toBeVisible({ timeout: 5000 })

      // Should show "Space to reveal" hint
      await expect(page.getByText(/space to reveal/i)).toBeVisible()
    } finally {
      await deleteCards(request, ids)
    }
  })

  // ── AC5: PracticeCard revealed state ──────────────────────────────────────

  test("PracticeCard revealed state: shows translation and FSRS rating row on Space (AC5)", async ({ page, request }) => {
    const ids = await seedDueCards(request, 1)
    try {
      await page.goto("/practice")
      await page.waitForLoadState("networkidle")

      // Wait for card to load
      await expect(page.getByText(/space to reveal/i)).toBeVisible({ timeout: 5000 })

      // Press Space to flip
      await page.keyboard.press("Space")

      // FSRS rating row should appear
      await expect(page.getByRole("group", { name: /rate your recall/i })).toBeVisible({ timeout: 3000 })
      await expect(page.getByRole("button", { name: /again/i })).toBeVisible()
      await expect(page.getByRole("button", { name: /good/i })).toBeVisible()
    } finally {
      await deleteCards(request, ids)
    }
  })

  // ── AC6: Optimistic rating ─────────────────────────────────────────────────

  test("full self-assess session: flip × N → SessionSummary → home (AC6, AC8)", async ({ page, request }) => {
    // Use isolated language ("uk" / Ukrainian) + cards_per_session=3 to guarantee
    // exactly 3 cards. The shared test DB accumulates cards across runs; "uk" is
    // otherwise empty in the test DB, and cards_per_session cap prevents residual
    // cards from past failures from bloating the session beyond 3.
    // Note: "zz" was previously used but is not in SUPPORTED_LANGUAGES (→ 422),
    //       so the settings change silently failed, leaving 149 "es" cards in scope.
    await request.put("http://localhost:7842/settings", {
      data: {
        native_language: "en",
        active_target_language: "uk",
        onboarding_completed: true,
        cards_per_session: 3,
      },
      headers: { "Content-Type": "application/json" },
    })
    const ids = await seedDueCards(request, 3)
    try {
      await page.goto("/practice")
      await page.waitForLoadState("networkidle")

      // Flip and rate all 3 cards — use button clicks for rating reliability
      // (keyboard key test is covered by "keyboard navigation" test)
      for (let i = 0; i < 3; i++) {
        // Wait for front state
        await expect(page.getByText(/space to reveal/i)).toBeVisible({ timeout: 5000 })
        // Flip with Space key
        await page.keyboard.press("Space")
        // Wait for rating row
        await expect(page.getByRole("group", { name: /rate your recall/i })).toBeVisible({ timeout: 3000 })
        // Click "Good" button directly — reliable regardless of keyboard focus state.
        // name: /good/i (no anchors) handles "Good Recalled" tooltip text appended when sessionCount < 3.
        await page.getByRole("button", { name: /good/i }).click()
        // Rating row must disappear (card advanced) before starting next iteration
        await expect(page.getByRole("group", { name: /rate your recall/i })).not.toBeVisible({ timeout: 5000 })
      }

      // After all 3 cards rated, SessionSummary should appear
      await expect(page.getByText(/cards reviewed/i)).toBeVisible({ timeout: 5000 })
      await expect(page.getByText(/recall rate/i)).toBeVisible()

      // Click Return to home
      await page.getByRole("button", { name: /return to home/i }).click()
      await page.waitForURL("**/")
    } finally {
      await deleteCards(request, ids)
      // Reset language to "es" and restore default cards_per_session (20)
      await request.put("http://localhost:7842/settings", {
        data: {
          native_language: "en",
          active_target_language: "es",
          onboarding_completed: true,
          cards_per_session: 20,
        },
        headers: { "Content-Type": "application/json" },
      })
    }
  })

  // ── AC8: Empty queue message ───────────────────────────────────────────────

  test("session with empty queue shows no-cards message (AC8)", async ({ page, request }) => {
    // Use a language with no due cards
    await request.put("http://localhost:7842/settings", {
      data: { native_language: "en", active_target_language: "de", onboarding_completed: true },
      headers: { "Content-Type": "application/json" },
    })

    try {
      await page.goto("/practice")
      await page.waitForLoadState("networkidle")

      await expect(page.getByText(/no cards due/i)).toBeVisible({ timeout: 5000 })
      await expect(page.getByRole("button", { name: /return home/i })).toBeVisible()
    } finally {
      // Reset to es
      await request.put("http://localhost:7842/settings", {
        data: { native_language: "en", active_target_language: "es", onboarding_completed: true },
        headers: { "Content-Type": "application/json" },
      })
    }
  })

  // ── AC6: Keyboard navigation ───────────────────────────────────────────────

  test("keyboard navigation: 1–4 rating keys work (AC6)", async ({ page, request }) => {
    const ids = await seedDueCards(request, 1)
    try {
      await page.goto("/practice")
      await page.waitForLoadState("networkidle")

      // Flip card
      await expect(page.getByText(/space to reveal/i)).toBeVisible({ timeout: 5000 })
      await page.keyboard.press("Space")
      await expect(page.getByRole("group", { name: /rate your recall/i })).toBeVisible({ timeout: 3000 })

      // Rate with keyboard key 4 (Easy)
      await page.keyboard.press("4")

      // Rating row must disappear — card advanced (next front state or session complete)
      // Note: "Space to reveal" may still be visible if there are more cards in the session;
      // checking the rating group is gone is the reliable signal that the key press worked.
      await expect(page.getByRole("group", { name: /rate your recall/i })).not.toBeVisible({ timeout: 3000 })
    } finally {
      await deleteCards(request, ids)
    }
  })

  // ── AC6: Failed rating shows notification and allows retry ─────────────────

  test("failed rating shows toast notification and allows retry (AC6)", async ({ page, request }) => {
    const ids = await seedDueCards(request, 1)
    try {
      await page.goto("/practice")
      await page.waitForLoadState("networkidle")

      // Wait for card to load and flip it
      await expect(page.getByText(/space to reveal/i)).toBeVisible({ timeout: 5000 })
      await page.keyboard.press("Space")
      await expect(page.getByRole("group", { name: /rate your recall/i })).toBeVisible({ timeout: 3000 })

      // Intercept the rate API call and force a 500 error
      await page.route("**/practice/cards/*/rate", (route) => {
        void route.fulfill({ status: 500, body: '{"detail":"Internal Server Error"}' })
      })

      // Submit a rating — optimistic advance fires, then rollback on 500
      await page.keyboard.press("3")

      // Notification toast should appear with error message
      await expect(page.getByText(/rating failed/i)).toBeVisible({ timeout: 5000 })

      // Card should be back (rolled back) — rating row still visible for retry
      await expect(page.getByRole("group", { name: /rate your recall/i })).toBeVisible({ timeout: 3000 })

      // Unintercept so retry can succeed
      await page.unroute("**/practice/cards/*/rate")

      // Retry — this time the real API is called
      await page.keyboard.press("3")

      // Session should advance after successful retry
      await expect(page.getByText(/cards reviewed|space to reveal/i)).toBeVisible({ timeout: 5000 })
    } finally {
      await deleteCards(request, ids)
    }
  })
})
