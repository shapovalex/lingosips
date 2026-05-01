/**
 * Shared Playwright fixtures and page object helpers.
 * Full page objects implemented as features are built (Story 1.9+).
 */

import { type APIRequestContext, type Page, expect } from "@playwright/test"


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

/**
 * Complete onboarding via API so tests that need the main app shell can bypass
 * the first-run wizard (Story 1.4).
 *
 * Call in beforeEach for any test that navigates to "/" and expects the app
 * shell (sidebar, bottom nav, etc.) to be visible.
 */
export async function completeOnboarding(page: Page): Promise<void> {
  await page.request.put("http://localhost:7842/settings", {
    data: {
      native_language: "en",
      active_target_language: "es",
      onboarding_completed: true,
    },
  })
}

/**
 * Create a seed card via POST /cards/stream and extract the card_id from
 * the SSE complete event.
 *
 * Returns the card_id of the created card.
 */
export async function createSeedCard(request: APIRequestContext): Promise<number> {
  const response = await request.fetch("http://localhost:7842/cards/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    data: JSON.stringify({ target_word: "prueba" }),
  })
  const body = await response.text()
  // Parse SSE events to find card_id from complete event
  const match = body.match(/"card_id":\s*(\d+)/)
  if (!match) throw new Error(`No card_id in SSE response. Body: ${body.slice(0, 200)}`)
  return Number(match[1])
}

/**
 * Create a seed deck via POST /decks.
 *
 * Returns the id of the created deck.
 * Used by deck management E2E tests (Story 2.2).
 */
export async function createSeedDeck(
  request: APIRequestContext,
  name: string,
  lang = "es",
): Promise<number> {
  const response = await request.post("http://localhost:7842/decks", {
    data: { name, target_language: lang },
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  })
  if (!response.ok()) {
    const body = await response.text()
    throw new Error(`createSeedDeck failed (${response.status()}): ${body.slice(0, 200)}`)
  }
  const body = await response.json()
  return body.id as number
}
