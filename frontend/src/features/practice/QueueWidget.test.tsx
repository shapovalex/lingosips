/**
 * QueueWidget component tests — TDD (written before implementation).
 *
 * Tests cover all 3 state machine branches:
 *   "due" | "empty" | "in-session"
 *
 * Strategy: mock TanStack Query useQuery and usePracticeStore,
 * focus on render / accessibility / state machine behaviour.
 *
 * AC covered: AC4 — 3-state widget, aria-label, aria-live, mode selector radiogroup
 */

import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect, beforeEach } from "vitest"
import React from "react"

// ── Mock TanStack Router ─────────────────────────────────────────────────────
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}))

// ── Mock TanStack Query useQuery ─────────────────────────────────────────────
vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>()
  return {
    ...actual,
    useQuery: vi.fn(),
  }
})
import { useQuery } from "@tanstack/react-query"
const mockUseQuery = vi.mocked(useQuery)

// ── Mock usePracticeStore ────────────────────────────────────────────────────
vi.mock("@/lib/stores/usePracticeStore")
import { usePracticeStore } from "@/lib/stores/usePracticeStore"
const mockUsePracticeStore = vi.mocked(usePracticeStore)

// ── Import component after mocks ─────────────────────────────────────────────
import { QueueWidget } from "./QueueWidget"

// ── Helpers ──────────────────────────────────────────────────────────────────

type QueueCard = {
  id: number
  target_word: string
  translation: string | null
  target_language: string
  due: string
  fsrs_state: string
  stability: number
  difficulty: number
  reps: number
  lapses: number
}

function makeCard(overrides: Partial<QueueCard> = {}): QueueCard {
  return {
    id: 1,
    target_word: "hola",
    translation: "hello",
    target_language: "es",
    due: new Date(Date.now() - 60_000).toISOString(),
    fsrs_state: "New",
    stability: 0,
    difficulty: 0,
    reps: 0,
    lapses: 0,
    ...overrides,
  }
}

const mockStartSession = vi.fn()

type StoreState = {
  sessionState: "idle" | "active" | "complete"
  mode: "self_assess" | "write" | "speak" | null
  currentCardIndex: number
  sessionCount: number
  startSession: (mode: "self_assess" | "write" | "speak") => void
  endSession: () => void
  nextCard: () => void
  prevCard: () => void
}

/**
 * usePracticeStore supports selector calls: usePracticeStore((s) => s.sessionState)
 * The mock must handle the selector function argument.
 */
function mockStoreWith(state: StoreState) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  mockUsePracticeStore.mockImplementation((selector?: (s: StoreState) => any) => {
    if (typeof selector === "function") return selector(state)
    return state
  })
}

function mockIdleStore() {
  mockStoreWith({
    sessionState: "idle",
    mode: null,
    currentCardIndex: 0,
    sessionCount: 0,
    startSession: mockStartSession,
    endSession: vi.fn(),
    nextCard: vi.fn(),
    prevCard: vi.fn(),
  })
}

function mockActiveStore() {
  mockStoreWith({
    sessionState: "active",
    mode: "self_assess",
    currentCardIndex: 0,
    sessionCount: 0,
    startSession: mockStartSession,
    endSession: vi.fn(),
    nextCard: vi.fn(),
    prevCard: vi.fn(),
  })
}

function renderWidget() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(QueueWidget)
    )
  )
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("QueueWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── "due" state (T3.1) ────────────────────────────────────────────────────

  describe("due state — N > 0 cards", () => {
    beforeEach(() => {
      mockIdleStore()
      mockUseQuery.mockReturnValue({
        data: [makeCard({ id: 1 }), makeCard({ id: 2, target_word: "adios" })],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useQuery>)
    })

    it("shows count with correct aria-label (AC4)", () => {
      renderWidget()
      // The count span has aria-label="N cards due for review"
      const countEl = screen.getByLabelText("2 cards due for review")
      expect(countEl).toBeTruthy()
      expect(countEl.textContent).toBe("2")
    })

    it("shows Practice button (AC4)", () => {
      renderWidget()
      expect(screen.getByRole("button", { name: /practice/i })).toBeTruthy()
    })

    it("shows mode selector radiogroup with two options (T3.4, AC4)", () => {
      renderWidget()
      const radiogroup = screen.getByRole("radiogroup")
      expect(radiogroup).toBeTruthy()
      const radios = screen.getAllByRole("radio")
      expect(radios).toHaveLength(2)
    })

    it("mode selector has Self-assess and Write options (AC4)", () => {
      renderWidget()
      expect(screen.getByRole("radio", { name: /self-assess/i })).toBeTruthy()
      expect(screen.getByRole("radio", { name: /write/i })).toBeTruthy()
    })

    it("has aria-live polite region for screen readers (AC4)", () => {
      renderWidget()
      const liveRegion = document.querySelector("[aria-live='polite']")
      expect(liveRegion).toBeTruthy()
    })
  })

  // ── "empty" state (T3.2) ──────────────────────────────────────────────────

  describe("empty state — 0 cards due", () => {
    beforeEach(() => {
      mockIdleStore()
      mockUseQuery.mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useQuery>)
    })

    it("shows 'All caught up' text (AC4)", () => {
      renderWidget()
      expect(screen.getByText(/all caught up/i)).toBeTruthy()
    })

    it("does not show Practice button (AC4)", () => {
      renderWidget()
      expect(screen.queryByRole("button", { name: /practice/i })).toBeNull()
    })
  })

  // ── "in-session" state (T3.3) ─────────────────────────────────────────────

  describe("in-session state — session active", () => {
    beforeEach(() => {
      mockActiveStore()
      mockUseQuery.mockReturnValue({
        data: [makeCard()],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useQuery>)
    })

    it("collapses to status bar with 'Session active' (AC4)", () => {
      renderWidget()
      expect(screen.getByText(/session active/i)).toBeTruthy()
    })

    it("does not show Practice button in session (AC4)", () => {
      renderWidget()
      expect(screen.queryByRole("button", { name: /practice/i })).toBeNull()
    })
  })

  // ── Loading state ─────────────────────────────────────────────────────────

  describe("loading state", () => {
    beforeEach(() => {
      mockIdleStore()
      mockUseQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
      } as ReturnType<typeof useQuery>)
    })

    it("renders loading indicator — not 'All caught up'", () => {
      renderWidget()
      expect(screen.getByTestId("queue-widget-loading")).toBeTruthy()
      expect(screen.queryByText(/all caught up/i)).toBeNull()
    })
  })

  // ── Error state ───────────────────────────────────────────────────────────

  describe("error state — query failed", () => {
    beforeEach(() => {
      mockIdleStore()
      mockUseQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
      } as ReturnType<typeof useQuery>)
    })

    it("shows error message — not 'All caught up'", () => {
      renderWidget()
      expect(screen.getByTestId("queue-widget-error")).toBeTruthy()
      expect(screen.queryByText(/all caught up/i)).toBeNull()
    })
  })
})
