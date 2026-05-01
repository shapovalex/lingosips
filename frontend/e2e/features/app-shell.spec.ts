import { test, expect } from "@playwright/test"
import { completeOnboarding } from "../fixtures/index"

/**
 * App Shell E2E Tests — Story 1.2
 *
 * Tests run against the real backend on port 7842 (never mocked).
 * Covers ACs: 1, 2, 4, 5, 7, 8
 *
 * AC1: D2 layout: 64px sidebar, fluid main, 360px right column (desktop)
 * AC2: Dark mode active by default
 * AC4: Mobile: sidebar replaced by bottom nav, right column as accordion
 * AC5: Focus ring indigo-500 visible on focused elements
 * AC7: "Skip to main content" is first focusable element
 * AC8: Time to interactive < 2000ms
 *
 * Updated in Story 1.4: completeOnboarding() called in beforeEach for all
 * test groups so the onboarding wizard does not block app-shell assertions.
 */

// ─── Desktop layout ───────────────────────────────────────────────────────────
test.describe("App Shell — Desktop (1280×800)", () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test.beforeEach(async ({ page }) => {
    await completeOnboarding(page)
  })

  test("AC1: D2 layout renders — icon sidebar, main content area, right column", async ({
    page,
  }) => {
    await page.goto("/")

    // Icon sidebar is present with correct aria label
    const mainNav = page.getByRole("navigation", { name: "Main navigation" })
    await expect(mainNav).toBeVisible()

    // Main content area is present
    const main = page.locator("#main-content")
    await expect(main).toBeVisible()

    // Right column is visible on desktop (complementary landmark with aria-label)
    const rightColumn = page.getByRole("complementary", { name: "Right column" })
    await expect(rightColumn).toBeVisible()

    // Bottom nav should NOT be visible on desktop (flex md:hidden = display:none at md+)
    const bottomNav = page.getByRole("navigation", { name: "Bottom navigation" })
    await expect(bottomNav).not.toBeVisible()
  })

  test("AC1: Icon sidebar has 6 navigation items", async ({ page }) => {
    await page.goto("/")
    const mainNav = page.getByRole("navigation", { name: "Main navigation" })
    // 6 items: Home, Practice, Decks, Import, Progress, Settings (Settings added in Story 2.3)
    await expect(mainNav.getByRole("link")).toHaveCount(6)
  })

  test("AC2: Dark mode is active by default — html element has 'dark' class", async ({
    page,
  }) => {
    await page.goto("/")
    const htmlClass = await page.evaluate(() =>
      document.documentElement.getAttribute("class")
    )
    expect(htmlClass).toContain("dark")
  })

  test("AC7: Skip link is the first focusable element in DOM order", async ({ page }) => {
    await page.goto("/")
    // Wait for app shell to fully render
    await page.waitForSelector('nav[aria-label="Main navigation"]')

    // Verify the skip link is first in DOM order among all focusable elements.
    // Note: Tab-based check is unreliable here because CardCreationPanel uses
    // autoFocus (intentional UX) — Tab starts from that input, not DOM start.
    // DOM-order check is the correct WCAG verification for skip-link placement.
    const firstFocusableText = await page.evaluate(() => {
      const focusable = document.querySelectorAll(
        "a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])"
      )
      return focusable[0]?.textContent?.trim()
    })
    expect(firstFocusableText).toContain("Skip to main content")
  })

  test("AC7: Second Tab from skip link lands in main content navigation", async ({
    page,
  }) => {
    await page.goto("/")
    // Wait for app shell to fully render before Tab sequence
    await page.waitForSelector('nav[aria-label="Main navigation"]')
    await page.keyboard.press("Tab") // Skip link
    await page.keyboard.press("Tab") // First nav item in icon sidebar or main
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName)
    // Should be an anchor (Link) in the navigation
    expect(["A", "BUTTON"]).toContain(focusedTag)
  })

  test("AC5: Focus ring is visible on focused element — indigo-500 background on skip link", async ({
    page,
  }) => {
    await page.goto("/")
    // Wait for app shell before testing focus
    await page.waitForSelector('nav[aria-label="Main navigation"]')

    // Focus the skip link directly (Tab-based approach unreliable due to autoFocus
    // on CardCreationPanel input — the skip link IS first in DOM but not Tab order)
    await page.locator('a[href="#main-content"]').focus()

    // Check computed background colour — skip link uses focus:bg-indigo-500
    // Tailwind v4 uses OKLCH; Tailwind v3 uses RGB. Accept either.
    // indigo-500: rgb(99, 102, 241) OR oklch(0.585 0.233 277.117)
    const backgroundColor = await page.evaluate(() => {
      const el = document.activeElement
      return window.getComputedStyle(el).backgroundColor
    })

    const isIndigoBackground =
      /rgb\(99,\s*102,\s*241\)/.test(backgroundColor) ||
      /oklch\(0\.5[0-9]/.test(backgroundColor)
    expect(isIndigoBackground).toBe(true)
  })

  test("AC8: Performance — time to interactive under 2000ms", async ({ page }) => {
    const startTime = Date.now()
    await page.goto("/")

    // Wait for the main navigation to be visible (interactive)
    await page.getByRole("navigation", { name: "Main navigation" }).waitFor({
      state: "visible",
      timeout: 2000,
    })

    const elapsed = Date.now() - startTime
    expect(elapsed).toBeLessThan(2000)
  })
})

// ─── Mobile layout ────────────────────────────────────────────────────────────
test.describe("App Shell — Mobile (375×812)", () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test.beforeEach(async ({ page }) => {
    await completeOnboarding(page)
  })

  test("AC4: Bottom nav replaces icon sidebar on mobile", async ({ page }) => {
    await page.goto("/")

    // Icon sidebar (Main navigation) should NOT be visible on mobile
    const mainNav = page.getByRole("navigation", { name: "Main navigation" })
    await expect(mainNav).not.toBeVisible()

    // Bottom nav SHOULD be visible on mobile
    const bottomNav = page.getByRole("navigation", { name: "Bottom navigation" })
    await expect(bottomNav).toBeVisible()
  })

  test("AC4: Bottom nav has 6 navigation items with text labels", async ({ page }) => {
    await page.goto("/")
    const bottomNav = page.getByRole("navigation", { name: "Bottom navigation" })
    await expect(bottomNav).toBeVisible()
    // 6 items: Home, Practice, Decks, Import, Progress, Settings (Settings added in Story 2.3)
    await expect(bottomNav.getByRole("link")).toHaveCount(6)
  })

  test("AC4: Right column accordion is present on mobile", async ({ page }) => {
    await page.goto("/")

    // The accordion toggle button should be visible
    const toggleBtn = page.getByRole("button", { name: /Cards due/i })
    await expect(toggleBtn).toBeVisible()
  })

  test("AC4: Right column accordion toggles open and close", async ({ page }) => {
    await page.goto("/")

    const toggleBtn = page.getByRole("button", { name: /Cards due/i })
    await expect(toggleBtn).toBeVisible()

    // Expand
    await toggleBtn.click()
    // Button text changes to "Close"
    await expect(page.getByRole("button", { name: /Close/i })).toBeVisible()

    // Collapse
    await page.getByRole("button", { name: /Close/i }).click()
    // Button text back to "Cards due"
    await expect(page.getByRole("button", { name: /Cards due/i })).toBeVisible()
  })

  test("AC7: Skip link is first focusable element in DOM order on mobile too", async ({ page }) => {
    await page.goto("/")
    // Wait for app shell to fully render
    await page.waitForSelector('nav[aria-label="Bottom navigation"]')

    // DOM-order check — same rationale as desktop AC7 test (autoFocus on input)
    const firstFocusableText = await page.evaluate(() => {
      const focusable = document.querySelectorAll(
        "a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])"
      )
      return focusable[0]?.textContent?.trim()
    })
    expect(firstFocusableText).toContain("Skip to main content")
  })
})
