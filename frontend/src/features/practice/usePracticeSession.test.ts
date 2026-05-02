/**
 * Tests for usePracticeSession hook.
 * TDD: written before implementation.
 * AC: 6, 8, 9
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
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS }) // session/start
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
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: [] }) // empty queue
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
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS }) // session/start
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
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: oneCard }) // session/start
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
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS }) // session/start
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
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: twoCards })
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
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/practice/session/start", undefined)
    })
  })

  it("fires POST /practice/cards/{id}/rate in background after rateCard", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession(),
      { wrapper }
    )

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.rateCard(1, 3) })

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/practice/cards/1/rate", { rating: 3, session_id: 1 })
    })
  })

  it("rateCard error rolls back: sets rollbackCardId and returns to same card", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })  // session/start
    mockPost.mockRejectedValueOnce(new Error("Network")) // rate fails

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))
    expect(result.current.currentCard?.id).toBe(1)

    act(() => { result.current.rateCard(1, 3) })

    // After rollback: still on card 1 with rollbackCardId set
    await waitFor(() => {
      expect(result.current.rollbackCardId).toBe(1)
    })
    expect(result.current.currentCard?.id).toBe(1)
    expect(result.current.sessionPhase).toBe("practicing")
  })

  it("rateCard error on last card restores practicing phase (not complete)", async () => {
    const oneCard = [MOCK_CARDS[0]]
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: oneCard })  // session/start
    mockPost.mockRejectedValueOnce(new Error("Network")) // rate fails

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.rateCard(1, 3) })

    // onMutate transitions to "complete" (last card), but onError restores "practicing"
    await waitFor(() => {
      expect(result.current.sessionPhase).toBe("practicing")
    })
    expect(result.current.rollbackCardId).toBe(1)
  })
})

// ── session_id tracking tests ─────────────────────────────────────────────────

describe("usePracticeSession — session_id tracking", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    usePracticeStore.setState({
      sessionState: "idle",
      mode: null,
      currentCardIndex: 0,
    })
  })

  const MOCK_SESSION_RESPONSE = { session_id: 42, cards: MOCK_CARDS }

  it("extracts session_id from SessionStartResponse", async () => {
    mockPost.mockResolvedValueOnce(MOCK_SESSION_RESPONSE)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))
    expect(result.current.sessionId).toBe(42)
  })

  it("sessionId is null before session starts", () => {
    mockPost.mockReturnValue(new Promise(() => {}))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    expect(result.current.sessionId).toBeNull()
  })

  it("passes session_id to rate card API call", async () => {
    mockPost.mockResolvedValueOnce(MOCK_SESSION_RESPONSE)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.rateCard(1, 3) })

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        "/practice/cards/1/rate",
        { rating: 3, session_id: 42 }
      )
    })
  })

  it("returns sessionId from hook when session started", async () => {
    mockPost.mockResolvedValueOnce(MOCK_SESSION_RESPONSE)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))
    expect(result.current.sessionId).toBe(42)
  })

  it("handles empty cards with session_id correctly", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 99, cards: [] })

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("complete"))
    expect(result.current.sessionId).toBe(99)
  })
})

// ── evaluateAnswer mutation tests ─────────────────────────────────────────────

describe("usePracticeSession — evaluateAnswer", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    usePracticeStore.setState({
      sessionState: "idle",
      mode: null,
      currentCardIndex: 0,
    })
  })

  it("evaluationResult starts as null", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))
    expect(result.current.evaluationResult).toBeNull()
  })

  it("evaluationResult becomes 'pending' when evaluateAnswer is called", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    // evaluateAnswer call never resolves to test pending state
    mockPost.mockReturnValueOnce(new Promise(() => {}))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.evaluateAnswer(1, "helo")
    })

    expect(result.current.evaluationResult).toBe("pending")
  })

  it("evaluationResult becomes EvaluationResult object on successful evaluate", async () => {
    const mockEvalResult = {
      is_correct: false,
      highlighted_chars: [{ char: "h", correct: true }, { char: "e", correct: false }],
      correct_value: "hello",
      explanation: "Missing letter.",
      suggested_rating: 1,
    }
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPost.mockResolvedValueOnce(mockEvalResult)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.evaluateAnswer(1, "helo")
    })

    await waitFor(() => {
      expect(result.current.evaluationResult).toEqual(mockEvalResult)
    })
  })

  it("evaluationResult becomes null on evaluate error", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPost.mockRejectedValueOnce(new Error("Network error"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.evaluateAnswer(1, "helo")
    })

    // After error: evaluationResult should go back to null (not "pending")
    await waitFor(() => {
      expect(result.current.evaluationResult).toBeNull()
    })
  })

  it("evaluationResult resets to null when rateCard is called (card advance)", async () => {
    const mockEvalResult = {
      is_correct: true,
      highlighted_chars: [],
      correct_value: "hello",
      explanation: null,
      suggested_rating: 3,
    }
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPost.mockResolvedValueOnce(mockEvalResult)  // evaluate
    mockPost.mockResolvedValue(MOCK_RATED_CARD)      // rate

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.evaluateAnswer(1, "hello") })
    await waitFor(() => expect(result.current.evaluationResult).toEqual(mockEvalResult))

    act(() => { result.current.rateCard(1, 3) })

    // evaluationResult should reset on card advance
    expect(result.current.evaluationResult).toBeNull()
  })

  it("calls POST /practice/cards/{id}/evaluate with correct payload", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPost.mockResolvedValueOnce({ is_correct: true, highlighted_chars: [], correct_value: "hello", explanation: null, suggested_rating: 3 })
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.evaluateAnswer(1, "hello") })

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/practice/cards/1/evaluate", { answer: "hello" })
    })
  })

  it("hook accepts optional mode param without breaking existing behavior", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    const { wrapper } = createWrapper()
    const { result } = renderHook(
      () => usePracticeSession("write"),
      { wrapper }
    )

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))
    expect(result.current.currentCard).toEqual(MOCK_CARDS[0])
  })

  it("evaluationResult is restored when rateCard fails (write mode rollback)", async () => {
    const mockEvalResult = {
      is_correct: false,
      highlighted_chars: [{ char: "h", correct: true }],
      correct_value: "hello",
      explanation: "Wrong answer.",
      suggested_rating: 1,
    }
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })         // session/start
    mockPost.mockResolvedValueOnce(mockEvalResult)     // evaluate
    mockPost.mockRejectedValueOnce(new Error("Network error"))  // rate fails

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession(), { wrapper })

    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    // Evaluate first to set evaluationResult
    act(() => { result.current.evaluateAnswer(1, "helo") })
    await waitFor(() => expect(result.current.evaluationResult).toEqual(mockEvalResult))

    // Rate (will fail) — evaluationResult cleared in onMutate then restored in onError
    act(() => { result.current.rateCard(1, 1) })

    // After rollback: evaluationResult must be restored so write-result can render
    await waitFor(() => {
      expect(result.current.evaluationResult).toEqual(mockEvalResult)
    })
    // rollbackCardId must be set so PracticeCard gets initialState="write-result"
    expect(result.current.rollbackCardId).toBe(1)
  })
})
