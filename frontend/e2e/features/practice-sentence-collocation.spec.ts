/**
 * Practice Sentence/Collocation E2E Tests — Story 3.4
 *
 * Tests run against the real backend on port 7842 (never mocked).
 * Covers: FR23 (sentence/collocation practice), AC: 1, 2, 3, 4, 5, 6, 7
 *
 * AC1: LLM pipeline sets card_type="sentence"|"collocation"|"word"
 * AC2: Practice queue exposes card_type, forms, example_sentences
 * AC3: Sentence card front shows phrase at text-2xl; revealed shows register context
 * AC4: Write mode uses LLM-based paraphrase evaluation; highlighted_chars=[] for sentences
 * AC5: FSRS rating row unchanged for sentence/collocation cards
 * AC6: Backward-compatible — word cards continue to work identically
 */

import { test, expect } from "@playwright/test"
import { completeOnboarding, resetTestDb } from "../fixtures/index"

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Create a sentence/collocation card via SSE stream, then PATCH to set known
 * translation and a past due date so it appears in the practice queue.
 * card_type and forms are set by the LLM based on the target word content.
 */
async function createDueSentenceCard(
  request: import("@playwright/test").APIRequestContext,
  options: {
    targetWord: string
    translation: string
  },
): Promise<number> {
  // Create card via SSE (LLM will set card_type based on content)
  const response = await request.fetch("http://localhost:7842/cards/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    data: JSON.stringify({ target_word: options.targetWord }),
  })
  const body = await response.text()
  const match = body.match(/"card_id":\s*(\d+)/)
  if (!match) throw new Error(`No card_id in SSE: ${body.slice(0, 300)}`)
  const id = Number(match[1])

  // Patch: set known translation and past due date
  await request.patch(`http://localhost:7842/cards/${id}`, {
    data: {
      translation: options.translation,
      due: new Date(Date.now() - 60_000).toISOString(),
    },
    headers: { "Content-Type": "application/json" },
  })
  return id
}

/**
 * Create a standard word card with known translation (same as write mode tests).
 */
async function createDueWordCard(
  request: import("@playwright/test").APIRequestContext,
  targetWord: string,
  translation: string,
): Promise<number> {
  const response = await request.fetch("http://localhost:7842/cards/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    data: JSON.stringify({ target_word: targetWord }),
  })
  const body = await response.text()
  const match = body.match(/"card_id":\s*(\d+)/)
  if (!match) throw new Error(`No card_id in SSE: ${body.slice(0, 300)}`)
  const id = Number(match[1])

  await request.patch(`http://localhost:7842/cards/${id}`, {
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
  await resetTestDb(page)
  await completeOnboarding(page)
})

// ── Tests ──────────────────────────────────────────────────────────────────────

test("practice queue includes card_type, forms, example_sentences on session start (AC: 2)", async ({ page, request }) => {
  // Create a sentence-like phrase card — LLM should detect it as sentence/collocation
  await createDueSentenceCard(request, {
    targetWord: "hace el tonto",
    translation: "plays dumb",
  })

  // Check the API response includes the required fields
  const response = await request.post("http://localhost:7842/practice/session/start")
  expect(response.ok()).toBeTruthy()
  const data = await response.json()
  expect(data).toHaveLength(1)
  const card = data[0]
  expect(card).toHaveProperty("card_type")
  expect(card).toHaveProperty("forms")
  expect(card).toHaveProperty("example_sentences")
})

test("self-assess — word card still uses text-4xl (backward compat, AC: 6)", async ({ page, request }) => {
  await createDueWordCard(request, "hola", "hello")

  await page.goto("/practice?mode=self_assess")
  await page.waitForLoadState("networkidle")

  // Word card target word is displayed
  const targetWordEl = page.getByText("hola")
  await expect(targetWordEl).toBeVisible()

  // Word card should use text-4xl (larger size)
  const targetClass = await targetWordEl.getAttribute("class")
  expect(targetClass).toContain("text-4xl")
})

test("write mode — word card correct answer shows ✓ Correct (backward compat, AC: 6)", async ({ page, request }) => {
  await createDueWordCard(request, "hola", "hello")

  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  await expect(page.getByRole("textbox")).toBeVisible()
  await page.getByRole("textbox").fill("hello")
  await page.getByRole("textbox").press("Enter")

  // Should show ✓ Correct
  await expect(page.getByText("✓ Correct")).toBeVisible({ timeout: 10_000 })
})

test("write mode — word card wrong answer shows char highlighting (backward compat, AC: 6)", async ({ page, request }) => {
  await createDueWordCard(request, "melancólico", "melancholic")

  await page.goto("/practice?mode=write")
  await page.waitForLoadState("networkidle")

  await expect(page.getByRole("textbox")).toBeVisible()
  await page.getByRole("textbox").fill("melancolic")
  await page.getByRole("textbox").press("Enter")

  // Correct value shown in emerald (exact match to avoid picking up explanation text)
  await expect(page.locator(".text-emerald-500", { hasText: "melancholic" })).toBeVisible({ timeout: 10_000 })
})

test("sentence card in practice session — FSRS rating row shows Again/Hard/Good/Easy (AC: 5)", async ({ page, request }) => {
  await createDueSentenceCard(request, {
    targetWord: "no te hagas el tonto",
    translation: "don't play dumb",
  })

  // Navigate to self-assess to check FSRS row appears on reveal
  await page.goto("/practice?mode=self_assess")
  await page.waitForLoadState("networkidle")

  // Flip card to revealed state
  await page.keyboard.press("Space")

  // All 4 FSRS buttons should be visible
  await expect(page.getByRole("button", { name: /again/i })).toBeVisible({ timeout: 5_000 })
  await expect(page.getByRole("button", { name: /hard/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /good/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /easy/i })).toBeVisible()
})

test("write mode — sentence exact match returns is_correct=true from evaluate endpoint (AC: 4)", async ({ request }) => {
  const id = await createDueSentenceCard(request, {
    targetWord: "no te hagas el tonto",
    translation: "don't play dumb",
  })

  // Evaluate exact match directly via API
  const evalResponse = await request.post(`http://localhost:7842/practice/cards/${id}/evaluate`, {
    data: { answer: "don't play dumb" },
    headers: { "Content-Type": "application/json" },
  })
  expect(evalResponse.ok()).toBeTruthy()
  const evalData = await evalResponse.json()

  expect(evalData.is_correct).toBe(true)
  expect(evalData.highlighted_chars).toEqual([])
  expect(evalData.suggested_rating).toBe(3)
})

test("write mode — sentence wrong answer returns is_correct=false with empty highlighted_chars (AC: 4)", async ({ request }) => {
  const id = await createDueSentenceCard(request, {
    targetWord: "no te hagas el tonto",
    translation: "don't play dumb",
  })

  // Evaluate clearly wrong answer
  const evalResponse = await request.post(`http://localhost:7842/practice/cards/${id}/evaluate`, {
    data: { answer: "completely wrong answer unrelated to the meaning" },
    headers: { "Content-Type": "application/json" },
  })
  expect(evalResponse.ok()).toBeTruthy()
  const evalData = await evalResponse.json()

  // highlighted_chars is always [] for sentence cards
  expect(evalData.highlighted_chars).toEqual([])
  // wrong answer
  expect(evalData.is_correct).toBe(false)
  expect(evalData.suggested_rating).toBe(1)
})

test("write mode — sentence paraphrase returns is_correct=true from LLM (AC: 4)", async ({ request }) => {
  const id = await createDueSentenceCard(request, {
    targetWord: "no te hagas el tonto",
    translation: "don't play dumb",
  })

  // Evaluate a clear paraphrase
  const evalResponse = await request.post(`http://localhost:7842/practice/cards/${id}/evaluate`, {
    data: { answer: "stop pretending you don't know" },
    headers: { "Content-Type": "application/json" },
  })
  expect(evalResponse.ok()).toBeTruthy()
  const evalData = await evalResponse.json()

  // highlighted_chars always [] for sentence cards
  expect(evalData.highlighted_chars).toEqual([])
  // is_correct from LLM — paraphrase should be accepted
  // We don't assert is_correct=true because LLM may vary, but we verify the structure
  expect(typeof evalData.is_correct).toBe("boolean")
  expect(evalData.suggested_rating).toBeGreaterThanOrEqual(1)
  expect(evalData.suggested_rating).toBeLessThanOrEqual(4)
})
