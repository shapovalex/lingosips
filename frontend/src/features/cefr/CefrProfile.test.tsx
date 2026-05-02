/**
 * Tests for CefrProfile component.
 * TDD: written before implementation.
 * AC: 7 (Story 5.2)
 *
 * Covers all five states of the CefrProfileState machine:
 *   null-level | loaded | loaded-no-speak-data | loading | error
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { createElement } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

vi.mock("@/lib/client", () => ({
  get: vi.fn(),
}))

// Mock TanStack Router Link so tests don't need a router context
vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children }: { to: string; children: React.ReactNode }) =>
    createElement("a", { href: to }, children),
}))

import { CefrProfile } from "./CefrProfile"
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

const MOCK_SETTINGS = { active_target_language: "es" }

const MOCK_PROFILE_B1 = {
  level: "B1",
  vocabulary_breadth: 520,
  grammar_coverage: 12,
  recall_rate_by_card_type: {
    self_assess: 0.85,
    write: 0.65,
    speak: 0.72,
  },
  active_passive_ratio: 0.45,
  explanation: "You have demonstrated B1 vocabulary and grammar coverage.",
}

const MOCK_PROFILE_B1_NO_SPEAK = {
  level: "B1",
  vocabulary_breadth: 520,
  grammar_coverage: 12,
  recall_rate_by_card_type: {
    self_assess: 0.85,
    write: 0.65,
    // no "speak" key
  },
  active_passive_ratio: null,
  explanation: "You have demonstrated B1 vocabulary and grammar coverage.",
}

const MOCK_PROFILE_NULL_LEVEL = {
  level: null,
  vocabulary_breadth: 0,
  grammar_coverage: 0,
  recall_rate_by_card_type: {},
  active_passive_ratio: null,
  explanation: "Practice more cards to generate your profile",
}

// ─── Null level state ────────────────────────────────────────────────────────

describe("CefrProfile — null level state", () => {
  it("renders 'Keep practicing' message when level is null", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_NULL_LEVEL)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    const msg = await screen.findByText(/keep practicing/i)
    expect(msg).toBeDefined()
  })

  it("renders link to /practice", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_NULL_LEVEL)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText(/keep practicing/i)
    const link = screen.getByRole("link", { name: /go to practice/i })
    expect(link).toBeDefined()
  })

  it("does NOT render breakdown rows when level is null", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_NULL_LEVEL)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText(/keep practicing/i)
    expect(screen.queryByText(/vocabulary size/i)).toBeNull()
    expect(screen.queryByText(/grammar coverage/i)).toBeNull()
    expect(screen.queryByText(/pronunciation accuracy/i)).toBeNull()
    expect(screen.queryByText(/active vs. passive/i)).toBeNull()
  })
})

// ─── Loaded state ─────────────────────────────────────────────────────────────

describe("CefrProfile — loaded state", () => {
  it("renders level badge at text-2xl with correct level value", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_B1)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    const badge = await screen.findByText("B1")
    expect(badge).toBeDefined()
    expect(badge.className).toContain("text-2xl")
  })

  it("renders 'What you demonstrate confidently' section", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_B1)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText("B1")
    expect(screen.getByText(/what you demonstrate confidently/i)).toBeDefined()
  })

  it("renders 'Areas for development' section", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_B1)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText("B1")
    expect(screen.getByText(/areas for development/i)).toBeDefined()
  })

  it("renders 'Gap to the next level' section", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_B1)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText("B1")
    expect(screen.getByText(/gap to the next level/i)).toBeDefined()
  })

  it("renders all four breakdown rows", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_B1)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText("B1")
    // Use getAllByText because "grammar coverage" also appears in the explanation text
    expect(screen.getByText(/vocabulary size/i)).toBeDefined()
    expect(screen.getAllByText(/grammar coverage/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/pronunciation accuracy/i)).toBeDefined()
    expect(screen.getByText(/active vs\. passive recall/i)).toBeDefined()
  })
})

// ─── Pronunciation row with no speak data ─────────────────────────────────────

describe("CefrProfile — pronunciation row with no speak data", () => {
  it("shows 'No speak mode data yet' when speak key absent from recall_rate_by_card_type", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_B1_NO_SPEAK)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText("B1")
    const noSpeakTexts = screen.getAllByText(/no speak mode data yet/i)
    expect(noSpeakTexts.length).toBeGreaterThanOrEqual(1)
  })

  it("shows 'No speak mode data yet' when active_passive_ratio is null", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.resolve(MOCK_PROFILE_B1_NO_SPEAK)
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    await screen.findByText("B1")
    // active_passive_ratio is null → "No speak mode data yet"
    // Both the pronunciation row and the active/passive row show this text
    const noSpeakTexts = screen.getAllByText(/no speak mode data yet/i)
    expect(noSpeakTexts.length).toBeGreaterThanOrEqual(2)
  })
})

// ─── Loading and error ─────────────────────────────────────────────────────────

describe("CefrProfile — loading and error", () => {
  it("renders skeleton while loading", () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    const region = screen.getByRole("region", { name: /cefr profile/i })
    expect(region).toHaveAttribute("aria-busy", "true")
  })

  it("renders error message when query fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (url.startsWith("/cefr/profile")) return Promise.reject(new Error("Network error"))
      return Promise.reject(new Error("unexpected url: " + url))
    })
    const { wrapper } = createWrapper()
    render(createElement(CefrProfile), { wrapper })

    const alert = await screen.findByRole("alert")
    expect(alert).toBeDefined()
    expect(alert.textContent).toMatch(/unable to load cefr profile/i)
  })
})
