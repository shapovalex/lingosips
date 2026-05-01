import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router"
import { QueryClient } from "@tanstack/react-query"
import { routeTree } from "@/routeTree.gen"

/**
 * Renders the full router to get the RootLayout which contains BottomNav.
 * Provides a mock QueryClient for the RouterContext required by __root.tsx.
 * Uses findByRole (async) since TanStack Router has async state initialization.
 */
function renderWithRouter(path = "/") {
  const queryClient = new QueryClient()
  const memoryHistory = createMemoryHistory({ initialEntries: [path] })
  const router = createRouter({ routeTree, history: memoryHistory, context: { queryClient } })
  return render(<RouterProvider router={router} />)
}

describe("BottomNav", () => {
  it("renders a nav landmark with aria-label 'Bottom navigation'", async () => {
    renderWithRouter("/")
    const nav = await screen.findByRole("navigation", { name: "Bottom navigation" })
    expect(nav).toBeInTheDocument()
  })

  it("renders all 5 navigation items with text labels", async () => {
    renderWithRouter("/")
    const bottomNav = await screen.findByRole("navigation", { name: "Bottom navigation" })
    expect(bottomNav).toHaveTextContent("Home")
    expect(bottomNav).toHaveTextContent("Practice")
    expect(bottomNav).toHaveTextContent("Import")
    expect(bottomNav).toHaveTextContent("Progress")
    expect(bottomNav).toHaveTextContent("Settings")
  })

  it("each nav item has the correct aria-label", async () => {
    renderWithRouter("/")
    const bottomNav = await screen.findByRole("navigation", { name: "Bottom navigation" })
    const links = bottomNav.querySelectorAll("a")
    expect(links).toHaveLength(5)
    const ariaLabels = Array.from(links).map((l) => l.getAttribute("aria-label"))
    expect(ariaLabels).toContain("Home — card creation")
    expect(ariaLabels).toContain("Practice")
    expect(ariaLabels).toContain("Import")
    expect(ariaLabels).toContain("Progress")
    expect(ariaLabels).toContain("Settings")
  })

  it("active item has text-indigo-500 class on '/' route", async () => {
    renderWithRouter("/")
    const bottomNav = await screen.findByRole("navigation", { name: "Bottom navigation" })
    const homeLink = bottomNav.querySelector('a[aria-label="Home — card creation"]')
    expect(homeLink).not.toBeNull()
    expect(homeLink!.className).toContain("text-indigo-500")
  })
})
