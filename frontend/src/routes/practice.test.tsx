/**
 * Tests for routes/practice.tsx.
 * TDD: written before implementation.
 * AC: 3, 10
 */
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { createElement } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

// Mock API client — prevents real HTTP calls from useQuery in PracticePage
vi.mock("@/lib/client", () => ({
  get: vi.fn().mockResolvedValue({ next_due: null }),
  post: vi.fn(),
}))

// Mock the practice session hook
const mockRateCard = vi.fn()
const mockUsePracticeSession = vi.fn()

vi.mock("@/features/practice/usePracticeSession", () => ({
  usePracticeSession: () => mockUsePracticeSession(),
}))

// Mock PracticeCard
vi.mock("@/features/practice/PracticeCard", () => ({
  PracticeCard: ({ card, onRate }: { card: { target_word: string }; onRate: (r: number) => void }) =>
    createElement("div", {
      "data-testid": "practice-card",
      onClick: () => onRate(3),
    }, card.target_word),
}))

// Mock SessionSummary
vi.mock("@/features/practice/SessionSummary", () => ({
  SessionSummary: ({ cardsReviewed, recallRate }: { cardsReviewed: number; recallRate: number }) =>
    createElement("div", { "data-testid": "session-summary" },
      `${cardsReviewed} cards, ${Math.round(recallRate * 100)}% recall`
    ),
}))

// Mock the router
const mockNavigate = vi.fn()
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>()
  return {
    ...actual,
    // createFileRoute("/path") returns a function that accepts { component } config
    createFileRoute: (_path: string) => (config: { component: React.ComponentType }) => config,
    useNavigate: () => mockNavigate,
  }
})

// Mock usePracticeStore
vi.mock("@/lib/stores/usePracticeStore", () => ({
  usePracticeStore: vi.fn((selector) => {
    const state = {
      sessionState: "idle" as const,
      mode: "self_assess" as const,
      currentCardIndex: 0,
      sessionCount: 0,
      startSession: vi.fn(),
      endSession: vi.fn(),
      nextCard: vi.fn(),
      prevCard: vi.fn(),
    }
    return selector(state)
  }),
}))

import { usePracticeStore } from "@/lib/stores/usePracticeStore"

const MOCK_CARD = {
  id: 1,
  target_word: "hola",
  translation: "hello",
  target_language: "es",
  due: new Date().toISOString(),
  fsrs_state: "learning",
  stability: 1.0,
  difficulty: 5.0,
  reps: 0,
  lapses: 0,
}

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: queryClient }, children)
}

// Import component lazily after mocks are set
async function importPracticePage() {
  const mod = await import("./practice")
  // The createFileRoute wrapper returns the component
  return (mod.Route as unknown as { component: React.ComponentType }).component
}

describe("PracticePage (routes/practice.tsx)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(usePracticeStore).mockImplementation((selector) => {
      const state = {
        sessionState: "active" as const,
        mode: "self_assess" as const,
        currentCardIndex: 0,
        sessionCount: 0,
        startSession: vi.fn(),
        endSession: vi.fn(),
        nextCard: vi.fn(),
        prevCard: vi.fn(),
      }
      return selector(state)
    })
  })

  it("shows loading skeleton while session is loading", async () => {
    mockUsePracticeSession.mockReturnValue({
      sessionPhase: "loading",
      currentCard: undefined,
      isLastCard: false,
      rateCard: mockRateCard,
      sessionSummary: undefined,
    })

    const PracticePage = await importPracticePage()
    render(createElement(PracticePage), { wrapper })
    expect(screen.getByRole("status")).toBeInTheDocument()
  })

  it("renders PracticeCard in practicing phase", async () => {
    mockUsePracticeSession.mockReturnValue({
      sessionPhase: "practicing",
      currentCard: MOCK_CARD,
      isLastCard: false,
      rateCard: mockRateCard,
      sessionSummary: undefined,
    })

    const PracticePage = await importPracticePage()
    render(createElement(PracticePage), { wrapper })
    expect(screen.getByTestId("practice-card")).toBeInTheDocument()
    expect(screen.getByText("hola")).toBeInTheDocument()
  })

  it("renders SessionSummary in complete phase", async () => {
    mockUsePracticeSession.mockReturnValue({
      sessionPhase: "complete",
      currentCard: undefined,
      isLastCard: false,
      rateCard: mockRateCard,
      sessionSummary: { cardsReviewed: 5, recallRate: 0.8 },
    })

    const PracticePage = await importPracticePage()
    render(createElement(PracticePage), { wrapper })
    expect(screen.getByTestId("session-summary")).toBeInTheDocument()
  })

  it("shows 'No cards due' message when session is complete with 0 cards reviewed", async () => {
    mockUsePracticeSession.mockReturnValue({
      sessionPhase: "complete",
      currentCard: undefined,
      isLastCard: false,
      rateCard: mockRateCard,
      sessionSummary: undefined,  // no summary when 0 cards
    })

    const PracticePage = await importPracticePage()
    render(createElement(PracticePage), { wrapper })
    expect(screen.getByText(/no cards due/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /return home/i })).toBeInTheDocument()
  })

  it("PracticeCard is centered with max-w-xl mx-auto", async () => {
    mockUsePracticeSession.mockReturnValue({
      sessionPhase: "practicing",
      currentCard: MOCK_CARD,
      isLastCard: false,
      rateCard: mockRateCard,
      sessionSummary: undefined,
    })

    const PracticePage = await importPracticePage()
    render(createElement(PracticePage), { wrapper })
    const container = screen.getByTestId("practice-card").closest("[class*='max-w-xl']")
    expect(container).toBeInTheDocument()
    expect(container?.className).toContain("mx-auto")
  })
})
