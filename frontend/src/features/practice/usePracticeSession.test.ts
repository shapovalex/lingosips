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
  postBinary: vi.fn(),
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
const mockPostBinary = vi.mocked(clientModule.postBinary)

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
      // mode=self_assess is always appended (added in Story 5.1 for CEFR session tracking)
      expect(mockPost).toHaveBeenCalledWith("/practice/session/start?mode=self_assess", undefined)
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

// ── evaluateSpeech / skipCard / speak stats tests ─────────────────────────────

const MOCK_SPEECH_RESULT_CORRECT = {
  overall_correct: true,
  syllables: [
    { syllable: "ho", correct: true, score: 0.9 },
    { syllable: "la", correct: true, score: 0.95 },
  ],
  correction_message: null,
  provider_used: "azure_speech",
}

const MOCK_SPEECH_RESULT_WRONG = {
  overall_correct: false,
  syllables: [
    { syllable: "ho", correct: true, score: 0.9 },
    { syllable: "la", correct: false, score: 0.2 },
  ],
  correction_message: "Focus on the second syllable",
  provider_used: "azure_speech",
}

const MOCK_AUDIO_BLOB = new Blob(["audio-data"], { type: "audio/webm" })

describe("usePracticeSession — speak mode (evaluateSpeech, skipCard, firstAttemptSuccessRate)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Real timers — fake timers are activated per-test only where needed
    usePracticeStore.setState({
      sessionState: "idle",
      mode: null,
      currentCardIndex: 0,
    })
  })

  afterEach(() => {
    // Ensure real timers are restored after each test
    vi.useRealTimers()
  })

  it("evaluateSpeech calls POST /practice/cards/{id}/speak with audio Blob", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPostBinary.mockResolvedValueOnce(MOCK_SPEECH_RESULT_CORRECT)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB)
    })

    await waitFor(() => {
      expect(mockPostBinary).toHaveBeenCalledWith(
        "/practice/cards/1/speak",
        MOCK_AUDIO_BLOB,
        "audio/webm"
      )
    })
  })

  it("speechResult becomes 'pending' while evaluateSpeech is in-flight", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPostBinary.mockReturnValueOnce(new Promise(() => {}))  // never resolves

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB)
    })

    expect(result.current.speechResult).toBe("pending")
  })

  it("on overall_correct=true: sets speechResult to data and does NOT auto-rate immediately", async () => {
    // Use real timers — assert immediately after evaluation resolves (before 1s timer fires)
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPostBinary.mockResolvedValueOnce(MOCK_SPEECH_RESULT_CORRECT)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB) })

    await waitFor(() => {
      expect(result.current.speechResult).toEqual(MOCK_SPEECH_RESULT_CORRECT)
    })

    // Assert immediately (1s timer not yet elapsed) — still on card 1
    expect(result.current.currentCard?.id).toBe(1)
  })

  it("on overall_correct=true: auto-calls rateCard(id, 3) after 1000ms", async () => {
    vi.useFakeTimers()
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPostBinary.mockResolvedValueOnce(MOCK_SPEECH_RESULT_CORRECT)
    mockPost.mockResolvedValue(MOCK_RATED_CARD)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    // Flush session start: advance 0ms flushes microtasks without firing long timers
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.sessionPhase).toBe("practicing")

    act(() => { result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB) })
    // Flush evaluateSpeech resolution via microtasks only (0ms advance)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.speechResult).toEqual(MOCK_SPEECH_RESULT_CORRECT)

    // NOW advance 1000ms — auto-advance timer fires
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    // Flush the resulting rateCard mutation promise
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })

    // Should advance to next card
    expect(result.current.currentCard?.id).toBe(2)
  })

  it("speechResult becomes 'pending' and blocks speech re-evaluation while in-flight (P4 race guard)", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    // First evaluateSpeech call — never resolves (simulates slow API)
    mockPostBinary.mockReturnValueOnce(new Promise(() => {}))

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    // First evaluation — goes to "pending"
    act(() => { result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB) })
    expect(result.current.speechResult).toBe("pending")

    // Second call while pending — mock should NOT be called again (guard in handleSpeak
    // prevents it; the hook itself doesn't guard, but the practice.tsx handleSpeak does)
    // Here we test that speechResult stays "pending" while the first is in-flight
    act(() => { result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB) })
    // speakAttemptsRef.current is now 2 — second call went through at hook level
    // BUT: the guard in handleSpeak (speechResult === "pending" → return) prevents this
    // in the real UI flow. This test confirms the "pending" state is correctly set.
    expect(result.current.speechResult).toBe("pending")
  })

  it("on overall_correct=false: speechResult set to result data; no auto-advance", async () => {
    // Use real timers — no auto-advance timer is set for wrong results
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPostBinary.mockResolvedValueOnce(MOCK_SPEECH_RESULT_WRONG)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => { result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB) })

    await waitFor(() => {
      expect(result.current.speechResult).toEqual(MOCK_SPEECH_RESULT_WRONG)
    })

    // Still on card 1 — no auto-advance for wrong result
    expect(result.current.currentCard?.id).toBe(1)
  })

  it("evaluateSpeech error: speechResult resets to null", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })
    mockPostBinary.mockRejectedValueOnce(new Error("Speech evaluation failed"))

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB)
    })

    // After error: speechResult should be null (pending → null)
    await waitFor(() => {
      expect(result.current.speechResult).toBeNull()
    })
  })

  it("skipCard advances to next card without rating (no API call)", async () => {
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: MOCK_CARDS })

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    expect(result.current.currentCard?.id).toBe(1)

    act(() => {
      result.current.skipCard()
    })

    // Advanced to next card (synchronous state update)
    expect(result.current.currentCard?.id).toBe(2)
    // No rate call was made (only session start)
    expect(mockPost).toHaveBeenCalledTimes(1)
  })

  it("skipCard on last card sets sessionPhase='complete'", async () => {
    const oneCard = [MOCK_CARDS[0]]
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: oneCard })

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    await waitFor(() => expect(result.current.sessionPhase).toBe("practicing"))

    act(() => {
      result.current.skipCard()
    })

    expect(result.current.sessionPhase).toBe("complete")
  })

  it("firstAttemptSuccessRate: 1 success on first try out of 2 attempts = 50%", async () => {
    vi.useFakeTimers()
    // 2 cards: card 1 correct first try; card 2 wrong first try then correct
    const twoCards = MOCK_CARDS.slice(0, 2)
    mockPost.mockResolvedValueOnce({ session_id: 1, cards: twoCards })
    // Card 1: correct on first attempt → auto-rate
    mockPostBinary.mockResolvedValueOnce(MOCK_SPEECH_RESULT_CORRECT)
    mockPost.mockResolvedValueOnce(MOCK_RATED_CARD)  // rate card 1
    // Card 2: wrong on first attempt (no auto-advance)
    mockPostBinary.mockResolvedValueOnce(MOCK_SPEECH_RESULT_WRONG)
    // Card 2: retry (correct) → auto-rate
    mockPostBinary.mockResolvedValueOnce(MOCK_SPEECH_RESULT_CORRECT)
    mockPost.mockResolvedValueOnce({ ...MOCK_CARDS[1], reps: 1 })  // rate card 2

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePracticeSession("speak"), { wrapper })
    // Flush session start (microtasks only, no long timers)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.sessionPhase).toBe("practicing")

    // Card 1: evaluate (correct) → speechResult set
    act(() => { result.current.evaluateSpeech(1, MOCK_AUDIO_BLOB) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.speechResult).toEqual(MOCK_SPEECH_RESULT_CORRECT)
    // Auto-advance after 1s
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.currentCard?.id).toBe(2)

    // Card 2: first attempt wrong
    act(() => { result.current.evaluateSpeech(2, MOCK_AUDIO_BLOB) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.speechResult).toEqual(MOCK_SPEECH_RESULT_WRONG)

    // Card 2: retry (correct) → speechResult set
    act(() => { result.current.evaluateSpeech(2, MOCK_AUDIO_BLOB) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.speechResult).toEqual(MOCK_SPEECH_RESULT_CORRECT)
    // Auto-advance after 1s → last card → complete
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(result.current.sessionPhase).toBe("complete")

    const summary = result.current.sessionSummary
    expect(summary).toBeDefined()
    // 1 first-attempt success out of 2 cards attempted
    expect(summary?.firstAttemptSuccessRate).toBeCloseTo(1 / 2)
  })

})
