/**
 * usePracticeSession — orchestrates a single self-assess practice session.
 *
 * Session cards are local state (snapshot fetched once at session start via
 * POST /practice/session/start). They are NOT stored in Zustand or TanStack Query cache.
 *
 * Rating is optimistic — advances to the next card immediately without a spinner.
 * API call fires in the background; on error → toast + allow retry.
 *
 * AC: 6, 9
 */
import { useState, useEffect, useCallback } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { post } from "@/lib/client"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"
import { useAppStore } from "@/lib/stores/useAppStore"

// ── Types ─────────────────────────────────────────────────────────────────────

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
}

type RatedCardResponse = QueueCard & { last_review: string | null }

export type SessionPhase = "loading" | "practicing" | "complete"

export interface SessionSummary {
  cardsReviewed: number
  recallRate: number  // 0–1 fraction
}

export interface UsePracticeSessionReturn {
  currentCard: QueueCard | undefined
  isLastCard: boolean
  rateCard: (cardId: number, rating: number) => void
  sessionSummary: SessionSummary | undefined
  sessionPhase: SessionPhase
  /** When non-null, a rating for this card failed — remount PracticeCard in "revealed" state for retry */
  rollbackCardId: number | null
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function usePracticeSession(): UsePracticeSessionReturn {
  const queryClient = useQueryClient()
  const { currentCardIndex, nextCard, prevCard } = usePracticeStore()
  const [sessionCards, setSessionCards] = useState<QueueCard[]>([])
  const [ratings, setRatings] = useState<number[]>([])
  const [sessionPhase, setSessionPhase] = useState<SessionPhase>("loading")
  const [rollbackCardId, setRollbackCardId] = useState<number | null>(null)
  const [pendingCardId, setPendingCardId] = useState<number | null>(null)

  // ── Fetch session cards on mount ─────────────────────────────────────────

  const startMutation = useMutation<QueueCard[], Error>({
    mutationFn: () => post<QueueCard[]>("/practice/session/start", undefined),
    onSuccess: (cards) => {
      setSessionCards(cards)
      if (cards.length === 0) {
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
    { cardId: number; rating: number; cardIndex: number }
  >({
    mutationFn: ({ cardId, rating }) =>
      post<RatedCardResponse>(`/practice/cards/${cardId}/rate`, { rating }),
    onMutate: ({ cardId, cardIndex, rating }) => {
      // Optimistic: advance immediately — 60fps, no spinner
      // Clear any previous rollback state before submitting a new rating
      setRollbackCardId(null)
      setPendingCardId(cardId)
      setRatings((prev) => [...prev, rating])
      if (cardIndex >= sessionCards.length - 1) {
        setSessionPhase("complete")
      } else {
        nextCard()
      }
    },
    onError: (_error, { cardId, cardIndex }) => {
      // Roll back: go back to the card that failed; track its id so PracticeCard
      // can remount in "revealed" state (rating row visible) for retry.
      setPendingCardId(null)
      setRollbackCardId(cardId)
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

  // ── Public API ────────────────────────────────────────────────────────────

  const rateCard = useCallback(
    (cardId: number, rating: number) => {
      // Guard against double-rating the SAME card (rapid key presses).
      // Only block if THIS card is already being rated — a different card can be
      // rated while the previous API call is still in-flight (optimistic advance
      // already moved currentCardIndex forward).
      if (pendingCardId === cardId) return
      rateCardMutation.mutate({ cardId, rating, cardIndex: currentCardIndex })
    },
    [rateCardMutation, currentCardIndex, pendingCardId]
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
  }
}
