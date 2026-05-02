/**
 * Tests for __root.tsx D4 layout — sidebar and right column hidden during practice session.
 * AC: 3
 */
import { describe, it, expect, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { routeTree } from "@/routeTree.gen"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"

/** Render the full router at a given path with a pre-configured QueryClient. */
function renderWithRouter(path = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(["settings"], {
    id: 1,
    native_language: "en",
    target_languages: '["es"]',
    active_target_language: "es",
    auto_generate_audio: true,
    auto_generate_images: false,
    default_practice_mode: "self_assess",
    cards_per_session: 20,
    onboarding_completed: true,
  })
  const memoryHistory = createMemoryHistory({ initialEntries: [path] })
  const router = createRouter({ routeTree, history: memoryHistory, context: { queryClient } })
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}

describe("RootLayout D4 — sidebar hidden during practice session", () => {
  afterEach(() => {
    // Reset store state after each test
    usePracticeStore.setState({ sessionState: "idle", mode: null, currentCardIndex: 0 })
  })

  it("sidebar wrapper is present when session is idle", async () => {
    renderWithRouter("/")
    // Wait for router to settle
    await screen.findByRole("navigation", { name: "Main navigation" })

    const sidebarWrapper = document.querySelector("[data-testid='sidebar-wrapper']")
    expect(sidebarWrapper).toBeInTheDocument()
    expect(sidebarWrapper?.className).not.toContain("w-0")
  })

  it("sidebar wrapper gets w-0 and overflow-hidden classes when session is active (D4 layout)", async () => {
    // Set store to active state BEFORE rendering
    usePracticeStore.setState({ sessionState: "active", mode: "self_assess" })

    renderWithRouter("/")
    await screen.findByRole("navigation", { name: "Main navigation" })

    const sidebarWrapper = document.querySelector("[data-testid='sidebar-wrapper']")
    expect(sidebarWrapper).toBeInTheDocument()
    expect(sidebarWrapper?.className).toContain("w-0")
    expect(sidebarWrapper?.className).toContain("overflow-hidden")
  })

  it("right column wrapper gets w-0 and overflow-hidden classes when session is active (D4 layout)", async () => {
    // Set store to active state BEFORE rendering
    usePracticeStore.setState({ sessionState: "active", mode: "self_assess" })

    renderWithRouter("/")
    await screen.findByRole("navigation", { name: "Main navigation" })

    const rightColumnWrapper = document.querySelector("[data-testid='right-column-wrapper']")
    expect(rightColumnWrapper).toBeInTheDocument()
    expect(rightColumnWrapper?.className).toContain("w-0")
    expect(rightColumnWrapper?.className).toContain("overflow-hidden")
  })
})
