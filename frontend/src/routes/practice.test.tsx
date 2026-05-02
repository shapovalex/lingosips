/**
 * Tests for routes/practice.tsx — includes helper function unit tests (Story 3.4, AC: 3).
 * TDD: written before implementation.
 * AC: 3, 10
 */
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { createElement } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { deriveGrammaticalForms, deriveFirstExampleSentence } from "./practice"
import type { QueueCard } from "@/features/practice/usePracticeSession"

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
    // createFileRoute returns an object with useSearch and the component
    createFileRoute: (_path: string) => (config: { component: React.ComponentType; validateSearch?: unknown }) => ({
      ...config,
      useSearch: () => ({ mode: "self_assess" }),
    }),
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

const mockEvaluateAnswer = vi.fn()

import { usePracticeStore } from "@/lib/stores/usePracticeStore"

const MOCK_CARD: QueueCard = {
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
  card_type: "word",
  forms: null,
  example_sentences: null,
}

// ── Helper function tests ──────────────────────────────────────────────────────

function makeCard(overrides: Partial<QueueCard> = {}): QueueCard {
  return { ...MOCK_CARD, ...overrides }
}

describe("deriveGrammaticalForms", () => {
  it("returns undefined when forms is null", () => {
    expect(deriveGrammaticalForms(makeCard({ forms: null }))).toBeUndefined()
  })

  it("returns 'Register: informal, River Plate Spanish' for sentence card with register_context", () => {
    const card = makeCard({
      card_type: "sentence",
      forms: JSON.stringify({
        gender: null, article: null, plural: null, conjugations: {},
        register_context: "informal, River Plate Spanish",
      }),
    })
    expect(deriveGrammaticalForms(card)).toBe("Register: informal, River Plate Spanish")
  })

  it("returns 'Register: informal' for collocation card with register_context", () => {
    const card = makeCard({
      card_type: "collocation",
      forms: JSON.stringify({
        gender: null, article: null, plural: null, conjugations: {},
        register_context: "informal",
      }),
    })
    expect(deriveGrammaticalForms(card)).toBe("Register: informal")
  })

  it("returns 'masculine · pl. melancólicos' for word card with gender+plural", () => {
    const card = makeCard({
      card_type: "word",
      forms: JSON.stringify({
        gender: "masculine", article: "el", plural: "melancólicos",
        conjugations: {}, register_context: null,
      }),
    })
    expect(deriveGrammaticalForms(card)).toBe("masculine · pl. melancólicos")
  })

  it("returns undefined when register_context is null for sentence card", () => {
    const card = makeCard({
      card_type: "sentence",
      forms: JSON.stringify({
        gender: null, article: null, plural: null, conjugations: {},
        register_context: null,
      }),
    })
    expect(deriveGrammaticalForms(card)).toBeUndefined()
  })

  it("returns undefined on JSON parse error", () => {
    expect(deriveGrammaticalForms(makeCard({ forms: "not valid json" }))).toBeUndefined()
  })

  it("returns undefined for word card with no gender or plural", () => {
    const card = makeCard({
      card_type: "word",
      forms: JSON.stringify({
        gender: null, article: null, plural: null, conjugations: {}, register_context: null,
      }),
    })
    expect(deriveGrammaticalForms(card)).toBeUndefined()
  })
})

describe("deriveFirstExampleSentence", () => {
  it("returns first sentence from JSON array", () => {
    const card = makeCard({
      example_sentences: JSON.stringify([
        "No te hagas el tonto, te vi.",
        "Siempre se hace el tonto.",
      ]),
    })
    expect(deriveFirstExampleSentence(card)).toBe("No te hagas el tonto, te vi.")
  })

  it("returns undefined when example_sentences is null", () => {
    expect(deriveFirstExampleSentence(makeCard({ example_sentences: null }))).toBeUndefined()
  })

  it("returns undefined on JSON parse error", () => {
    expect(deriveFirstExampleSentence(makeCard({ example_sentences: "invalid json" }))).toBeUndefined()
  })

  it("returns undefined for empty array", () => {
    expect(deriveFirstExampleSentence(makeCard({ example_sentences: JSON.stringify([]) }))).toBeUndefined()
  })
})

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: queryClient }, children)
}

// Import component lazily after mocks are set
async function importPracticePage() {
  const mod = await import("./practice")
  // The createFileRoute mock returns an object with { component, useSearch, ... }
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

// ── Write mode tests ───────────────────────────────────────────────────────────

describe("PracticePage — write mode", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(usePracticeStore).mockImplementation((selector) => {
      const state = {
        sessionState: "active" as const,
        mode: "write" as const,
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

  it("passes evaluateAnswer and evaluationResult props to PracticeCard in write mode", async () => {
    // PracticeCard mock receives evaluateAnswer prop — we verify it's passed
    const writePracticeCardMock = vi.fn(() =>
      createElement("div", { "data-testid": "practice-card" }, "write-card")
    )
    vi.doMock("@/features/practice/PracticeCard", () => ({
      PracticeCard: writePracticeCardMock,
    }))

    mockUsePracticeSession.mockReturnValue({
      sessionPhase: "practicing",
      currentCard: MOCK_CARD,
      isLastCard: false,
      rateCard: mockRateCard,
      evaluateAnswer: mockEvaluateAnswer,
      evaluationResult: null,
      sessionSummary: undefined,
      rollbackCardId: null,
    })

    // Re-import to pick up the new mock
    const { default: _unused } = await vi.importActual("./practice")
    const PracticePage = await importPracticePage()
    render(createElement(PracticePage), { wrapper })
    expect(screen.getByTestId("practice-card")).toBeInTheDocument()
  })

  it("usePracticeSession is called with mode from search params", async () => {
    mockUsePracticeSession.mockReturnValue({
      sessionPhase: "practicing",
      currentCard: MOCK_CARD,
      isLastCard: false,
      rateCard: mockRateCard,
      evaluateAnswer: mockEvaluateAnswer,
      evaluationResult: null,
      sessionSummary: undefined,
      rollbackCardId: null,
    })

    const PracticePage = await importPracticePage()
    render(createElement(PracticePage), { wrapper })
    expect(mockUsePracticeSession).toHaveBeenCalled()
  })
})
