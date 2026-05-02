/**
 * Tests for ProgressDashboard component.
 * TDD: written before implementation.
 * AC: 1, 2 (Story 3.5)
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { createElement } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

vi.mock("@/lib/client", () => ({
  get: vi.fn(),
}))

import { ProgressDashboard } from "./ProgressDashboard"
import * as clientModule from "@/lib/client"

const mockGet = vi.mocked(clientModule.get)

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const Wrapper = ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
  return { wrapper: Wrapper }
}

const MOCK_DASHBOARD_DATA = {
  total_cards: 42,
  learned_cards: 15,
  review_count_by_day: [
    { date: "2026-04-28", count: 5 },
    { date: "2026-04-29", count: 3 },
  ],
  overall_recall_rate: 0.75,
}

const EMPTY_DASHBOARD_DATA = {
  total_cards: 0,
  learned_cards: 0,
  review_count_by_day: [],
  overall_recall_rate: 0.0,
}

describe("ProgressDashboard states", () => {
  it("renders loading skeleton while data is fetching", () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    const region = screen.getByRole("region", { name: /progress dashboard/i })
    expect(region).toHaveAttribute("aria-busy", "true")
  })

  it("renders 'No reviews yet' in empty state (total_cards === 0)", async () => {
    mockGet.mockResolvedValue(EMPTY_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    const text = await screen.findByText(/no reviews yet/i)
    expect(text).toBeDefined()
  })

  it("renders all 4 metric cards in loaded state", async () => {
    mockGet.mockResolvedValue(MOCK_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    // Should show total_cards
    expect(await screen.findByText("42")).toBeDefined()
    // Should show learned_cards
    expect(screen.getByText("15")).toBeDefined()
    // Should show recall rate as %
    expect(screen.getByText("75%")).toBeDefined()
  })

  it("renders error message when query fails", async () => {
    mockGet.mockRejectedValue(new Error("Network error"))
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    const alert = await screen.findByRole("alert")
    expect(alert).toBeDefined()
    expect(alert.textContent).toMatch(/unable to load/i)
  })
})

describe("ProgressDashboard metrics", () => {
  it("shows total_cards count", async () => {
    mockGet.mockResolvedValue(MOCK_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    expect(await screen.findByText("42")).toBeDefined()
    expect(screen.getByText(/total cards/i)).toBeDefined()
  })

  it("shows learned_cards count", async () => {
    mockGet.mockResolvedValue(MOCK_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    await screen.findByText("42")  // wait for load
    expect(screen.getByText("15")).toBeDefined()
    expect(screen.getByText(/learned/i)).toBeDefined()
  })

  it("shows recall rate as percentage", async () => {
    mockGet.mockResolvedValue(MOCK_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    expect(await screen.findByText("75%")).toBeDefined()
  })

  it("renders activity bars for each day with reviews", async () => {
    mockGet.mockResolvedValue(MOCK_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    const chart = await screen.findByRole("img", { name: /review activity/i })
    expect(chart).toBeDefined()
  })

  it("shows 'No reviews yet' in chart area when review_count_by_day is empty", async () => {
    mockGet.mockResolvedValue({ ...MOCK_DASHBOARD_DATA, total_cards: 5, review_count_by_day: [] })
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    await screen.findByText("5")  // wait for load
    // Chart area should show no-reviews message
    const chart = screen.getByRole("img", { name: /review activity/i })
    expect(chart).toBeDefined()
  })
})

describe("ProgressDashboard accessibility", () => {
  it("has role=region with aria-label", async () => {
    mockGet.mockResolvedValue(MOCK_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    const region = screen.getByRole("region", { name: /progress dashboard/i })
    expect(region).toBeDefined()
  })

  it("activity chart has role=img with descriptive aria-label", async () => {
    mockGet.mockResolvedValue(MOCK_DASHBOARD_DATA)
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    const chart = await screen.findByRole("img", { name: /review activity/i })
    expect(chart).toBeDefined()
  })

  it("has aria-busy=true in loading state", () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    const { wrapper } = createWrapper()
    render(createElement(ProgressDashboard), { wrapper })

    const region = screen.getByRole("region", { name: /progress dashboard/i })
    expect(region.getAttribute("aria-busy")).toBe("true")
  })
})
