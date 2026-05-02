/**
 * PracticeCard — the core flashcard component for self-assess practice mode.
 *
 * State machine: "front" | "revealed" | "write-active" | "write-result" | "speak-recording" | "speak-result"
 * All 6 states are defined. Only front/revealed are functional in Story 3.2.
 * Write/Speak states render placeholders implemented in Stories 3.3/3.4.
 *
 * Keyboard: Space flips front→revealed; 1–4 keys submit rating when revealed.
 * Handlers attached to document via useEffect to work without requiring focus.
 *
 * AC: 4, 5, 6, 7
 */
import { useState, useEffect } from "react"
import type { QueueCard } from "./usePracticeSession"

// ── Types ─────────────────────────────────────────────────────────────────────

// Full 6-state machine defined now to avoid refactoring in Stories 3.3/3.4
export type PracticeCardState =
  | "front"
  | "revealed"
  | "write-active"
  | "write-result"
  | "speak-recording"
  | "speak-result"

interface RatingConfig {
  value: number
  label: string
  shortcut: number
  tooltip: string
}

// ── Constants ─────────────────────────────────────────────────────────────────

const RATINGS: RatingConfig[] = [
  { value: 1, label: "Again",  shortcut: 1, tooltip: "Forgot" },
  { value: 2, label: "Hard",   shortcut: 2, tooltip: "Struggled" },
  { value: 3, label: "Good",   shortcut: 3, tooltip: "Recalled" },
  { value: 4, label: "Easy",   shortcut: 4, tooltip: "Instant" },
]

// ── Props ─────────────────────────────────────────────────────────────────────

interface PracticeCardProps {
  card: QueueCard & {
    grammatical_forms?: string
    example_sentence?: string
  }
  onRate: (rating: number) => void
  sessionCount: number
  /** For testing stub states only — defaults to "front" */
  initialState?: PracticeCardState
}

// ── Component ─────────────────────────────────────────────────────────────────

export function PracticeCard({ card, onRate, sessionCount, initialState = "front" }: PracticeCardProps) {
  const [cardState, setCardState] = useState<PracticeCardState>(initialState)

  // ── Keyboard handler — document-level (no focus required) ─────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.code === "Space" && cardState === "front") {
        e.preventDefault()  // prevent page scroll
        setCardState("revealed")
      }
      if (cardState === "revealed") {
        const ratingMap: Record<string, number> = { "1": 1, "2": 2, "3": 3, "4": 4 }
        const rating = ratingMap[e.key]
        if (rating !== undefined) onRate(rating)
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [cardState, onRate])

  // ── Stub states (Stories 3.3/3.4) ─────────────────────────────────────────

  if (cardState === "write-active") {
    return <div data-testid="practice-card-write-active">Story 3.3 placeholder</div>
  }
  if (cardState === "write-result") {
    return <div data-testid="practice-card-write-result">Story 3.3 placeholder</div>
  }
  if (cardState === "speak-recording") {
    return <div data-testid="practice-card-speak-recording">Story 3.4 placeholder</div>
  }
  if (cardState === "speak-result") {
    return <div data-testid="practice-card-speak-result">Story 3.4 placeholder</div>
  }

  // ── Front state ───────────────────────────────────────────────────────────

  if (cardState === "front") {
    return (
      <button
        className="w-full flex flex-col items-center justify-center p-8 cursor-pointer
                   focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-xl"
        aria-label="Flip card"
        onClick={() => setCardState("revealed")}
      >
        <span className="text-4xl font-semibold text-zinc-50">{card.target_word}</span>
        <span className="text-sm text-zinc-500 mt-2">Space to reveal</span>
      </button>
    )
  }

  // ── Revealed state ────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col items-center gap-4 p-8">
      {/* Target word stays visible */}
      <span className="text-4xl font-semibold text-zinc-50">{card.target_word}</span>

      {/* Translation */}
      {card.translation && (
        <span className="text-xl text-zinc-200">{card.translation}</span>
      )}

      {/* Grammatical forms */}
      {"grammatical_forms" in card && card.grammatical_forms && (
        <span className="text-sm text-zinc-400">{card.grammatical_forms}</span>
      )}

      {/* Example sentence */}
      {"example_sentence" in card && card.example_sentence && (
        <span className="italic text-zinc-400 text-sm">{card.example_sentence}</span>
      )}

      {/* FSRS rating row — slides up from below via Tailwind transition */}
      <div
        className="w-full mt-4 transition-transform duration-200 motion-reduce:duration-0
                   translate-y-0"
      >
        <div
          role="group"
          aria-label="Rate your recall"
          className="flex gap-2 justify-center"
        >
          {RATINGS.map(({ value, label, shortcut, tooltip }) => (
            <button
              key={value}
              onClick={() => onRate(value)}
              aria-keyshortcuts={String(shortcut)}
              title={sessionCount >= 3 ? tooltip : undefined}
              className="flex flex-col items-center gap-1 px-4 py-2 rounded-lg
                         bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-medium
                         focus:outline-none focus:ring-2 focus:ring-indigo-500
                         transition-colors min-w-[64px]"
            >
              {label}
              {sessionCount < 3 && (
                <span className="text-xs text-zinc-500">{tooltip}</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
