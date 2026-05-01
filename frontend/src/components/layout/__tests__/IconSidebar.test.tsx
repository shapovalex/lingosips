import { describe, it, expect } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { routeTree } from "@/routeTree.gen"

/**
 * Renders the full router to get the RootLayout which contains IconSidebar.
 * Provides a mock QueryClient for the RouterContext required by __root.tsx.
 * Uses findByRole (async) since TanStack Router has async state initialization.
 *
 * Pre-seeds the ["settings"] cache with onboarding_completed=true so the
 * onboarding gate (Story 1.4) passes and the normal app shell renders.
 */
function renderWithRouter(path = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // Bypass onboarding gate — tests assume settings are complete
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

describe("IconSidebar", () => {
  it("renders a nav landmark with aria-label 'Main navigation'", async () => {
    renderWithRouter("/")
    const nav = await screen.findByRole("navigation", { name: "Main navigation" })
    expect(nav).toBeInTheDocument()
  })

  it("renders all navigation items scoped within Main navigation", async () => {
    renderWithRouter("/")
    const nav = await screen.findByRole("navigation", { name: "Main navigation" })
    const { getByLabelText } = within(nav)

    expect(getByLabelText("Home — card creation")).toBeInTheDocument()
    expect(getByLabelText("Practice")).toBeInTheDocument()
    expect(getByLabelText("Decks — vocabulary organization")).toBeInTheDocument()
    expect(getByLabelText("Import")).toBeInTheDocument()
    expect(getByLabelText("Progress")).toBeInTheDocument()
    expect(getByLabelText("Settings")).toBeInTheDocument()
  })

  it("each nav link has the correct aria-label", async () => {
    renderWithRouter("/")
    const nav = await screen.findByRole("navigation", { name: "Main navigation" })
    const { getByLabelText } = within(nav)

    const navLabels = [
      "Home — card creation",
      "Practice",
      "Decks — vocabulary organization",
      "Import",
      "Progress",
      "Settings",
    ]
    navLabels.forEach((label) => {
      expect(getByLabelText(label)).toBeInTheDocument()
    })
  })

  it("all nav items have minimum 44px touch targets", async () => {
    renderWithRouter("/")
    const nav = await screen.findByRole("navigation", { name: "Main navigation" })
    const homeLink = within(nav).getByLabelText("Home — card creation")
    expect(homeLink.className).toContain("min-h-[44px]")
    expect(homeLink.className).toContain("min-w-[44px]")
  })

  it("active route link gets bg-indigo-500 class on '/' route", async () => {
    renderWithRouter("/")
    const nav = await screen.findByRole("navigation", { name: "Main navigation" })
    const homeLink = within(nav).getByLabelText("Home — card creation")
    // TanStack Router applies activeProps — active class bg-indigo-500 on current route
    expect(homeLink).toBeInTheDocument()
    expect(homeLink.className).toContain("bg-indigo-500")
  })
})
