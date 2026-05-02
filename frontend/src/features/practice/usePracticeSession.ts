/**
 * usePracticeSession — orchestrates a single practice session (self-assess or write mode).
 *
 * Session cards are local state (snapshot fetched once at session start via
 * POST /practice/session/start). They are NOT stored in Zustand or TanStack Query cache.
 *
 * Rating is optimistic — advances to the next card immediately without a spinner.
 * API call fires in the background; on error → toast + allow retry.
 *
 * AC: 6, 8, 9
 */
import { useState, useEffect, useCallback } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { post } from "@/lib/client"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"
import { useAppStore } from "@/lib/stores/useAppStore"
import type { PracticeMode } from "@/lib/stores/usePracticeStore"

// ── Types ─────────────────────────────────────────────────────────────────────

// Internal type for session start response shape (Story 3.5)
type SessionStartApiResponse = {
  session_id: number
  cards: QueueCard[]
}

export type QueueCard = {
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
  card_type: "word" | "sentence" | "collocation"
  forms: string | null       // JSON string — contains register_context for sentence/collocation
  example_sentences: string | null  // JSON string
}

type RatedCardResponse = QueueCard & { last_review: string | null }

export type SessionPhase = "loading" | "practicing" | "complete"

export interface SessionSummary {
  cardsReviewed: number
  recallRate: number  // 0–1 fraction
}

export interface EvaluationResult {
  is_correct: boolean
  highlighted_chars: Array<{ char: string; correct: boolean }>
  correct_value: string
  explanation: string | null
  suggested_rating: number
}

export interface UsePracticeSessionReturn {
  currentCard: QueueCard | undefined
  isLastCard: boolean
  rateCard: (cardId: number, rating: number) => void
  sessionSummary: SessionSummary | undefined
  sessionPhase: SessionPhase
  /** When non-null, a rating for this card failed — remount PracticeCard for retry */
  rollbackCardId: number | null
  evaluateAnswer: (cardId: number, answer: string) => void
  evaluationResult: EvaluationResult | "pending" | null
  sessionId: number | null  // for linking session to progress page (Story 3.5)
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function usePracticeSession(_mode?: PracticeMode): UsePracticeSessionReturn {
  const queryClient = useQueryClient()
  const { currentCardIndex, nextCard, prevCard } = usePracticeStore()
  const [sessionCards, setSessionCards] = useState<QueueCard[]>([])
  const [ratings, setRatings] = useState<number[]>([])
  const [sessionPhase, setSessionPhase] = useState<SessionPhase>("loading")
  const [rollbackCardId, setRollbackCardId] = useState<number | null>(null)
  const [pendingCardId, setPendingCardId] = useState<number | null>(null)
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResult | "pending" | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)

  // ── Fetch session cards on mount ─────────────────────────────────────────

  const startMutation = useMutation<SessionStartApiResponse, Error>({
    mutationFn: () => post<SessionStartApiResponse>("/practice/session/start", undefined),
    onSuccess: (data) => {
      setSessionId(data.session_id)
      setSessionCards(data.cards)
      if (data.cards.length === 0) {
        setSessionPhase("complete")
      } else {
        setSessionPhase("practicing")
      }
    },
  })

  // TanStack Query v5 guarantees `mutate` is a stable function reference
  // (wrapped in useCallback internally), so it is safe to list as a dep.
  // This runs exactly once on mount.
  useEffect(() => {
    startMutation.mutate()
  }, [startMutation.mutate])  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Rating mutation ───────────────────────────────────────────────────────

  const rateCardMutation = useMutation<
    RatedCardResponse,
    Error,
    { cardId: number; rating: number; cardIndex: number; sessionId: number | null },
    { previousEvaluationResult: EvaluationResult | "pending" | null }
  >({
    mutationFn: ({ cardId, rating, sessionId: sid }) =>
      post<RatedCardResponse>(`/practice/cards/${cardId}/rate`, { rating, session_id: sid }),
    onMutate: ({ cardId, cardIndex, rating }) => {
      // Optimistic: advance immediately — 60fps, no spinner
      // Capture evaluation result BEFORE clearing so it can be restored on rollback.
      const previousEvaluationResult = evaluationResult
      setRollbackCardId(null)
      setPendingCardId(cardId)
      setRatings((prev) => [...prev, rating])
      // Clear evaluationResult so the next card starts fresh
      setEvaluationResult(null)
      if (cardIndex >= sessionCards.length - 1) {
        setSessionPhase("complete")
      } else {
        nextCard()
      }
      return { previousEvaluationResult }
    },
    onError: (_error, { cardId, cardIndex }, context) => {
      // Roll back: go back to the card that failed; track its id so PracticeCard
      // can remount in write-result (or revealed) state for retry.
      setPendingCardId(null)
      setRollbackCardId(cardId)
      // Restore evaluation result so write-result state can re-render on rollback
      setEvaluationResult(context?.previousEvaluationResult ?? null)
      if (cardIndex < sessionCards.length - 1) {
        prevCard()
      } else {
        setSessionPhase("practicing")
      }
      setRatings((prev) => prev.slice(0, -1))
      useAppStore.getState().addNotification({
        type: "error",
        message: "Rating failed — please try again",
      })
    },
    onSettled: (_data, _error, { cardId }) => {
      setPendingCardId((prev) => (prev === cardId ? null : prev))
      // Invalidate queue so QueueWidget status bar count stays accurate
      // (deferred fix from Story 3.1 code review)
      void queryClient.invalidateQueries({ queryKey: ["practice", "queue"] })
    },
  })

  // ── Evaluate mutation ─────────────────────────────────────────────────────

  const evaluateAnswerMutation = useMutation<
    EvaluationResult,
    Error,
    { cardId: number; answer: string }
  >({
    mutationFn: ({ cardId, answer }) =>
      post<EvaluationResult>(`/practice/cards/${cardId}/evaluate`, { answer }),
    onMutate: () => setEvaluationResult("pending"),
    onSuccess: (data, variables) => {
      // Guard against a stale response arriving after the user has already rated
      // and advanced to the next card. If the evaluated card is no longer current,
      // discard the result rather than clobbering the new card's state.
      const currentCard = sessionCards[currentCardIndex]
      if (currentCard?.id === variables.cardId) {
        setEvaluationResult(data)
      }
    },
    onError: () => {
      setEvaluationResult(null)
      useAppStore.getState().addNotification({
        type: "error",
        message: "Evaluation failed — rate manually",
      })
    },
  })

  // ── Public API ────────────────────────────────────────────────────────────

  const rateCard = useCallback(
    (cardId: number, rating: number) => {
      // Guard against double-rating the SAME card (rapid key presses).
      // Only block if THIS card is already being rated — a different card can be
      // rated while the previous API call is still in-flight (optimistic advance
      // already moved currentCardIndex forward).
      if (pendingCardId === cardId) return
      rateCardMutation.mutate({ cardId, rating, cardIndex: currentCardIndex, sessionId })
    },
    [rateCardMutation, currentCardIndex, pendingCardId, sessionId]
  )

  const evaluateAnswer = useCallback(
    (cardId: number, answer: string) => {
      evaluateAnswerMutation.mutate({ cardId, answer })
    },
    [evaluateAnswerMutation]
  )

  const currentCard = sessionCards[currentCardIndex]
  const isLastCard = sessionCards.length > 0 && currentCardIndex === sessionCards.length - 1

  const sessionSummary: SessionSummary | undefined =
    sessionPhase === "complete" && sessionCards.length > 0
      ? {
          cardsReviewed: ratings.length,
          recallRate: ratings.length > 0
            ? ratings.filter((r) => r >= 3).length / ratings.length
            : 0,
        }
      : undefined

  return {
    currentCard,
    isLastCard,
    rateCard,
    sessionSummary,
    sessionPhase,
    rollbackCardId,
    evaluateAnswer,
    evaluationResult,
    sessionId,
  }
}
