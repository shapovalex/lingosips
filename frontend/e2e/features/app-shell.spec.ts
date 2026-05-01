import { test, expect } from "@playwright/test"

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
 */

// ─── Desktop layout ───────────────────────────────────────────────────────────
test.describe("App Shell — Desktop (1280×800)", () => {
  test.use({ viewport: { width: 1280, height: 800 } })

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

  test("AC1: Icon sidebar has 5 navigation items", async ({ page }) => {
    await page.goto("/")
    const mainNav = page.getByRole("navigation", { name: "Main navigation" })
    await expect(mainNav.getByRole("link")).toHaveCount(5)
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

  test("AC7: Skip link is the first focusable element", async ({ page }) => {
    await page.goto("/")

    // Tab once — should land on skip link
    await page.keyboard.press("Tab")
    const focusedText = await page.evaluate(() => document.activeElement?.textContent)
    expect(focusedText).toContain("Skip to main content")
  })

  test("AC7: Second Tab from skip link lands in main content navigation", async ({
    page,
  }) => {
    await page.goto("/")
    await page.keyboard.press("Tab") // Skip link
    await page.keyboard.press("Tab") // First nav item in icon sidebar or main
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName)
    // Should be an anchor (Link) in the navigation
    expect(["A", "BUTTON"]).toContain(focusedTag)
  })

  test("AC5: Focus ring is visible on focused element — indigo-500 outline", async ({
    page,
  }) => {
    await page.goto("/")

    // Tab to skip link (first focusable element)
    await page.keyboard.press("Tab")

    // Check computed style of the focused element
    const outlineColor = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement
      return window.getComputedStyle(el).outlineColor
    })

    // indigo-500 = #6366f1 = rgb(99, 102, 241)
    // CSS computed color may return rgb() format
    expect(outlineColor).toMatch(/rgb\(99,\s*102,\s*241\)/)
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

  test("AC4: Bottom nav replaces icon sidebar on mobile", async ({ page }) => {
    await page.goto("/")

    // Icon sidebar (Main navigation) should NOT be visible on mobile
    const mainNav = page.getByRole("navigation", { name: "Main navigation" })
    await expect(mainNav).not.toBeVisible()

    // Bottom nav SHOULD be visible on mobile
    const bottomNav = page.getByRole("navigation", { name: "Bottom navigation" })
    await expect(bottomNav).toBeVisible()
  })

  test("AC4: Bottom nav has 5 navigation items with text labels", async ({ page }) => {
    await page.goto("/")
    const bottomNav = page.getByRole("navigation", { name: "Bottom navigation" })
    await expect(bottomNav).toBeVisible()
    await expect(bottomNav.getByRole("link")).toHaveCount(5)
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

  test("AC7: Skip link is first focusable element on mobile too", async ({ page }) => {
    await page.goto("/")
    await page.keyboard.press("Tab")
    const focusedText = await page.evaluate(() => document.activeElement?.textContent)
    expect(focusedText).toContain("Skip to main content")
  })
})
