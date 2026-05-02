/**
 * Tests for usePracticeSession hook.
 * TDD: written before implementation.
 * AC: 6, 9
 */
import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"

// Mock the client module
vi.mock("@/lib/client", () => ({
  post: vi.fn(),
}))

vi.mock("@/lib/stores/useAppStore", () => ({
  useAppStore: {
    getState: () => ({
      addNotification: vi.fn(),
    }),
  },
}))

import { usePracticeSession } from "./usePracticeSession"
import * as clientModule from "@/lib/client"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"

const mockPost = vi.mocked(clientModule.post)

const MOCK_CARDS = [
  {
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
  },
  {
    id: 2,
    target_word: "adios",
    translation: "goodbye",
    target_language: "es",
    due: new Date().toISOString(),
    fsrs_state: "learning",
    stability: 1.0,
    difficulty: 5.0,
    reps: 0,
    lapses: 0,
  },
  {
    id: 3,
    target_word: "gracias",
    translation: "thank you",
    target_language: "es",
    due: new Date().toISOString(),
    fsrs_state: "learning",
    stability: 1.0,
    difficulty: 5.0,
    reps: 0,
    lapses: 0,
  },
]

const MOCK_RATED_CARD = { ...MOCK_CARDS[0], reps: 1, stability: 2.5 }

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const Wrapper = ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
  return { wrapper: Wrapper, queryClient }
}

describe("usePracticeSession", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset practice store
    usePracticeStore.setState({
      sessionState: "idle",
      mode: null,
      currentCardIndex: 0,
    })
  })

  it("starts in loading phase when session cards are not yet fetched", () => {
    // post never resolves — simulates loading
    mockPost.mockReturnValue(new Promise(() => {}))
    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )
    expect(result.current.sessionPhase).toBe("loading")
  })

  it("transitions to practicing phase after session cards are fetched", async () => {
    mockPost.mockResolvedValueOnce(MOCK_CARDS) // session/start
    mockPost.mockResolvedValue(MOCK_RATED_CARD)  // cards/{id}/rate
    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => {
      expect(result.current.sessionPhase).toBe("practicing")
    })
    expect(result.current.currentCard).toEqual(MOCK_CARDS[0])
  })

  it("transitions to complete phase when session starts with 0 cards", async () => {
    mockPost.mockResolvedValueOnce([]) // empty queue
    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => {
      expect(result.current.sessionPhase).toBe("complete")
    })
    expect(result.current.currentCard).toBeUndefined()
  })

  it("rateCard advances to next card immediately (optimistic)", async () => {
    mockPost.mockResolvedValueOnce(MOCK_CARDS) // session/start
    mockPost.mockResolvedValue(MOCK_RATED_CARD)  // cards/{id}/rate

    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))
    expect(result.current.currentCard?.id).toBe(1)

    act(() => {
      result.current.rateCard(1, 3)
    })

    // Card advances immediately (optimistic)
    expect(result.current.currentCard?.id).toBe(2)
  })

  it("rateCard on last card transitions to complete phase", async () => {
    const oneCard = [MOCK_CARDS[0]]
    mockPost.mockResolvedValueOnce(oneCard) // session/start
    mockPost.mockResolvedValue(MOCK_RATED_CARD)  // cards/{id}/rate

    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.rateCard(1, 3)
    })

    // Should transition to complete after rating last card
    expect(result.current.sessionPhase).toBe("complete")
  })

  it("tracks ratings for recall rate calculation", async () => {
    mockPost.mockResolvedValueOnce(MOCK_CARDS) // session/start
    mockPost.mockResolvedValue(MOCK_RATED_CARD)  // cards/{id}/rate

    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    // Rate card 1 and wait for the in-flight mutation to settle before the next rating.
    // This is realistic: the isPending guard prevents double-rating while the API call
    // is in-flight, so each card must resolve before the next can be rated.
    act(() => { result.current.rateCard(1, 3) })  // Good (≥3)
    await waitFor(() => expect(result.current.currentCard?.id).toBe(2))

    act(() => { result.current.rateCard(2, 1) })  // Again (<3)
    await waitFor(() => expect(result.current.currentCard?.id).toBe(3))

    act(() => { result.current.rateCard(3, 4) })  // Easy (≥3)
    await waitFor(() => expect(result.current.sessionPhase).toBe("complete"))

    // 2 out of 3 are ≥3 → 66.7% recall
    const summary = result.current.sessionSummary
    expect(summary).toBeDefined()
    expect(summary?.cardsReviewed).toBe(3)
    expect(summary?.recallRate).toBeCloseTo(2 / 3)
  })

  it("exposes isLastCard correctly", async () => {
    const twoCards = MOCK_CARDS.slice(0, 2)
    mockPost.mockResolvedValueOnce(twoCards)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))
    expect(result.current.isLastCard).toBe(false)

    act(() => { result.current.rateCard(1, 3) })
    expect(result.current.isLastCard).toBe(true)
  })

  it("calls POST /practice/session/start on mount", async () => {
    mockPost.mockResolvedValueOnce(MOCK_CARDS)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/practice/session/start", undefined)
    })
  })

  it("fires POST /practice/cards/{id}/rate in background after rateCard", async () => {
    mockPost.mockResolvedValueOnce(MOCK_CARDS)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.rateCard(1, 3) })

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/practice/cards/1/rate", { rating: 3 })
    })
  })
})
