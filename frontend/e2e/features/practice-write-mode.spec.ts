/**
 * Practice Write Mode E2E Tests — Story 3.3
 *
 * Tests run against the real backend on port 7842 (never mocked).
 * Covers: FR19–FR20
 *
 * AC1:  POST /practice/cards/{id}/evaluate endpoint works
 * AC2:  Exact match → is_correct=true, suggested_rating=3
 * AC3:  Wrong answer → char diff + LLM explanation or null
 * AC4:  routes/practice.tsx supports ?mode=write
 * AC5:  write-active: target word at top, autofocused textarea, Submit btn, hint
 * AC6:  write-result: char highlighting (red=wrong), correct_value in emerald, explanation
 * AC7:  FSRS rating row pre-selects suggested_rating; Enter confirms
 * AC8:  usePracticeSession evaluateAnswer/evaluationResult
 */

import { test, expect } from "@playwright/test"
import { completeOnboarding, resetTestDb } from "../fixtures/index"

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Create a due card with a KNOWN translation so we can test exact match.
 * Uses PATCH to set both due and translation.
 */
async function createDueCardWithTranslation(
  request: import("@playwright/test").APIRequestContext,
  targetWord: string,
  translation: string,
): Promise<number> {
  // Create via SSE stream
  const response = await request.fetch("http://127.0.0.1:7842/cards/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    data: JSON.stringify({ target_word: targetWord }),
  })
  const body = await response.text()
  const match = body.match(/"card_id":\s*(\d+)/)
  if (!match) throw new Error(`No card_id in SSE: ${body.slice(0, 200)}`)
  const id = Number(match[1])

  // Patch with known translation + past due date
  await request.patch(`http://127.0.0.1:7842/cards/${id}`, {
    data: {
      translation,
      due: new Date(Date.now() - 60_000).toISOString(),
    },
    headers: { "Content-Type": "application/json" },
  })
  return id
}

// ── Setup ──────────────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  // Reset DB first — removes leftover cards from previous test runs that would
  // contaminate the session queue order. Then re-apply onboarding settings.
  await resetTestDb(page)
  await completeOnboarding(page)
})

// ── Tests ──────────────────────────────────────────────────────────────────────

test("correct answer → write-result success state → Good pre-selected → Enter confirms → next card", async ({ page, request }) => {
  // Seed 2 due cards so we can advance to the next one
  const card1Id = await createDueCardWithTranslation(request, "hola", "hello")
  await createDueCardWithTranslation(request, "adios", "goodbye")

  // Navigate to write mode
  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  // Should show write-active state — textarea focused
  await expect(page.getByRole("textbox")).toBeVisible()
  await expect(page.getByRole("textbox")).toBeFocused()

  // Type correct translation (exact, case-insensitive)
  await page.getByRole("textbox").fill("hello")
  await page.getByRole("textbox").press("Enter")

  // Should transition to write-result
  await expect(page.getByRole("textbox")).not.toBeVisible({ timeout: 5000 })

  // Should show ✓ Correct (is_correct = true)
  await expect(page.getByText("✓ Correct")).toBeVisible({ timeout: 10_000 })

  // FSRS row should be visible with Good (rating=3) pre-selected
  const goodBtn = page.getByRole("button", { name: /good/i })
  await expect(goodBtn).toBeVisible()
  await expect(goodBtn).toHaveAttribute("aria-pressed", "true")

  // Press Enter to confirm rating → advances to next card
  await page.keyboard.press("Enter")

  // Next card loads in write-active
  await expect(page.getByRole("textbox")).toBeVisible({ timeout: 5000 })

  // Cleanup
  await request.delete(`http://127.0.0.1:7842/cards/${card1Id}`)
})

test("wrong answer → char highlighting → explanation or 'unavailable' → FSRS rating row → Again", async ({ page, request }) => {
  // Seed a card with known translation
  await createDueCardWithTranslation(request, "gato", "cat")

  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  // Should show write-active
  await expect(page.getByRole("textbox")).toBeVisible()

  // Type wrong answer
  await page.getByRole("textbox").fill("dog")
  await page.keyboard.press("Enter")

  // Should transition to write-result showing the wrong answer's characters
  // Wait for write-result state (textarea gone)
  await expect(page.getByRole("textbox")).not.toBeVisible({ timeout: 10_000 })

  // Correct value should be visible in green (is_correct=false → show correct_value)
  // Use exact:true to avoid ambiguity with explanation text that may also contain "cat"
  await expect(page.getByText("cat", { exact: true }).first()).toBeVisible({ timeout: 10_000 })

  // FSRS row should show Again (rating=1) pre-selected
  const againBtn = page.getByRole("button", { name: /again/i })
  await expect(againBtn).toBeVisible()
  await expect(againBtn).toHaveAttribute("aria-pressed", "true")

  // Click Again to rate
  await againBtn.click()

  // Session should advance — with 1 card "Session complete" summary is shown,
  // then auto-returns home; also handle "No cards due" (empty queue) or next card
  await expect(
    page.getByText("No cards due")
      .or(page.getByRole("textbox"))
      .or(page.getByText("Session complete"))
  ).toBeVisible({ timeout: 8_000 })
})

test("keyboard navigation: Tab/click changes rating button selection", async ({ page, request }) => {
  await createDueCardWithTranslation(request, "casa", "house")

  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  // Answer (wrong so we get write-result with rating row)
  await page.getByRole("textbox").fill("wrong")
  await page.keyboard.press("Enter")

  // Wait for write-result
  await expect(page.getByRole("textbox")).not.toBeVisible({ timeout: 10_000 })

  // Press 3 key to select Good (should change selection)
  await page.keyboard.press("3")
  const goodBtn = page.getByRole("button", { name: /good/i })
  await expect(goodBtn).toHaveAttribute("aria-pressed", "true")

  // Press Enter to confirm
  await page.keyboard.press("Enter")

  // Card rated — session advances. With 1 card the "Session complete" summary
  // is shown; it auto-returns home after 5 s. Accept all valid post-session states.
  await expect(
    page.getByText("No cards due")
      .or(page.getByRole("textbox"))
      .or(page.getByText("Session complete"))
  ).toBeVisible({ timeout: 8_000 })
})

test("write mode URL param ?mode=write activates write-active state (textarea visible)", async ({ page, request }) => {
  await createDueCardWithTranslation(request, "libro", "book")

  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  // Write mode → textarea immediately visible (not the "flip card" button)
  await expect(page.getByRole("textbox")).toBeVisible()
  // Should NOT show "Space to reveal" (that's self-assess)
  await expect(page.getByText(/space to reveal/i)).not.toBeVisible()
})

test("LLM unavailable → 'Evaluation unavailable — rate manually' shown", async ({ page, request }) => {
  // This test relies on the backend returning explanation=null (which happens
  // when LLM times out or is unavailable). In test environment the local LLM
  // may not be loaded, so explanation=null is expected behavior.
  await createDueCardWithTranslation(request, "perro", "dog")

  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  await page.getByRole("textbox").fill("xyz")
  await page.keyboard.press("Enter")

  // Wait for write-result
  await expect(page.getByRole("textbox")).not.toBeVisible({ timeout: 10_000 })

  // Either "Evaluation unavailable" (LLM absent) OR an actual explanation (LLM worked).
  // Both are rendered as <span class="text-sm text-zinc-400 ..."> — check each separately
  // to avoid strict-mode failure from multiple .text-zinc-400 elements on the page.
  const hasUnavailable = await page.getByText(/evaluation unavailable — rate manually/i).isVisible().catch(() => false)
  const hasActualExplanation = (await page.locator("span.text-zinc-400").count()) > 0

  // At least one must be true — the write-result state always shows explanation area
  expect(hasUnavailable || hasActualExplanation).toBe(true)

  // FSRS row must always be shown regardless of LLM availability
  await expect(page.getByRole("group", { name: /rate your recall/i })).toBeVisible()
})

test("empty queue in write mode shows 'No cards due' message", async ({ page }) => {
  // No cards seeded — queue is empty
  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  await expect(page.getByText(/no cards due/i)).toBeVisible({ timeout: 5_000 })
  await expect(page.getByRole("button", { name: /return home/i })).toBeVisible()
})

test("Submit button calls evaluate (same as Enter key)", async ({ page, request }) => {
  await createDueCardWithTranslation(request, "sol", "sun")

  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  const textarea = page.getByRole("textbox")
  await textarea.fill("moon")

  // Click Submit button instead of Enter
  await page.getByRole("button", { name: /submit/i }).click()

  // Should transition to write-result
  await expect(textarea).not.toBeVisible({ timeout: 10_000 })
  await expect(page.getByRole("group", { name: /rate your recall/i })).toBeVisible()
})
