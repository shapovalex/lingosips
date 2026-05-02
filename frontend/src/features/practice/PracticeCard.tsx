/**
 * PracticeCard — the core flashcard component for self-assess and write practice modes.
 *
 * State machine: "front" | "revealed" | "write-active" | "write-result" | "speak-recording" | "speak-result"
 * All 6 states are defined. front/revealed are for self-assess; write-active/write-result for write mode.
 * Speak states render placeholders implemented in Stories 3.4+.
 *
 * Keyboard:
 *   - Self-assess: Space flips front→revealed; 1–4 keys submit rating when revealed.
 *   - Write-active: Enter submits answer; document-level 1–4/Space is guarded off.
 *   - Write-result: Enter confirms pre-selected rating; 1–4 changes selection.
 * Handlers attached to document via useEffect; write mode uses element/component-level events.
 *
 * AC: 4, 5, 6, 7
 */
import { useState, useEffect, useRef } from "react"
import type { QueueCard, EvaluationResult } from "./usePracticeSession"

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
  /** Write mode: called with the user's typed answer */
  onEvaluate?: (answer: string) => void
  /** Write mode: result from POST /practice/cards/{id}/evaluate */
  evaluationResult?: EvaluationResult | "pending" | null
}

// ── WriteResultRatingRow ──────────────────────────────────────────────────────

function WriteResultRatingRow({
  suggestedRating,
  onRate,
}: {
  suggestedRating: number
  onRate: (r: number) => void
}) {
  const [selected, setSelected] = useState(suggestedRating)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        onRate(selected)
        return
      }
      const n = Number(e.key)
      if (n >= 1 && n <= 4) setSelected(n)
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [selected, onRate])

  return (
    <div role="group" aria-label="Rate your recall" className="flex gap-2 justify-center mt-4">
      {RATINGS.map(({ value, label }) => (
        <button
          key={value}
          onClick={() => onRate(value)}
          aria-pressed={selected === value}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors
            focus:outline-none focus:ring-2 focus:ring-indigo-500
            ${selected === value
              ? "bg-indigo-500 text-white"
              : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
            }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export function PracticeCard({
  card,
  onRate,
  sessionCount,
  initialState = "front",
  onEvaluate,
  evaluationResult,
}: PracticeCardProps) {
  const [cardStateBase, setCardState] = useState<PracticeCardState>(initialState)

  // Derive effective card state: transition write-active → write-result during render
  // when the evaluation result arrives. This avoids a synchronous setState in a useEffect
  // and is the React-idiomatic way to handle prop-driven state transitions.
  const cardState: PracticeCardState =
    evaluationResult &&
    evaluationResult !== "pending" &&
    cardStateBase === "write-active"
      ? "write-result"
      : cardStateBase

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [userAnswer, setUserAnswer] = useState<string | null>(null)

  // Card-type-aware font sizing: sentences/collocations use text-2xl; words use text-4xl
  const targetWordSize = card.card_type === "word" ? "text-4xl" : "text-2xl"

  // ── Autofocus textarea in write-active ────────────────────────────────────

  useEffect(() => {
    if (cardState === "write-active") {
      textareaRef.current?.focus()
    }
  }, [cardState])

  // ── Keyboard handler — document-level (no focus required) ─────────────��───

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Guard: write mode states use their own element/component-level handlers
      if (cardState === "write-active" || cardState === "write-result") return

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

  // ── Speak stubs (Stories 3.5+) ────────────────────────────────────────────

  if (cardState === "speak-recording") {
    return <div data-testid="practice-card-speak-recording">Story 3.5 placeholder</div>
  }
  if (cardState === "speak-result") {
    return <div data-testid="practice-card-speak-result">Story 3.5 placeholder</div>
  }

  // ── Write-active state ────────────────────────────────────────────────────

  if (cardState === "write-active") {
    const isEvaluating = evaluationResult === "pending"

    return (
      <div className="flex flex-col items-center gap-6 p-8">
        {/* Target word — same prominence as self-assess front */}
        <span className={`${targetWordSize} font-semibold text-zinc-50`}>{card.target_word}</span>

        {/* Answer input */}
        <div className="w-full max-w-sm flex flex-col gap-2">
          <textarea
            ref={textareaRef}
            rows={1}
            disabled={isEvaluating}
            placeholder="Type the translation…"
            data-testid="write-active-input"
            className="w-full resize-none rounded-lg bg-zinc-800 px-4 py-3 text-zinc-50
                       placeholder:text-zinc-500 focus:outline-none focus:ring-2
                       focus:ring-indigo-500 disabled:opacity-50"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                const val = e.currentTarget.value.trim()
                if (!isEvaluating && val) {
                  setUserAnswer(val)
                  onEvaluate?.(val)
                }
              }
            }}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-500">Enter to submit</span>
            <button
              disabled={isEvaluating}
              onClick={() => {
                const val = textareaRef.current?.value.trim()
                if (val) {
                  setUserAnswer(val)
                  onEvaluate?.(val)
                }
              }}
              className="px-4 py-2 rounded-lg bg-indigo-500 text-sm text-white
                         hover:bg-indigo-400 disabled:opacity-50 transition-colors"
            >
              {isEvaluating ? "Evaluating…" : "Submit"}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Write-result state ────────────────────────────────────────────────────

  if (
    cardState === "write-result" &&
    evaluationResult &&
    evaluationResult !== "pending"
  ) {
    const result = evaluationResult

    return (
      <div className="flex flex-col items-center gap-4 p-8">
        {/* Target word */}
        <span className={`${targetWordSize} font-semibold text-zinc-50`}>{card.target_word}</span>

        {/* User's answer — char-level highlighting for word cards; strikethrough for sentence/collocation */}
        {result.highlighted_chars.length > 0 ? (
          <div className="flex flex-wrap gap-0 text-xl font-mono">
            {result.highlighted_chars.map((hc, i) => (
              <span
                key={i}
                className={
                  hc.correct
                    ? "text-zinc-200"
                    : "text-red-400 underline decoration-red-400"
                }
              >
                {hc.char}
              </span>
            ))}
          </div>
        ) : !result.is_correct && userAnswer ? (
          <span className="text-xl font-mono text-zinc-400 line-through">{userAnswer}</span>
        ) : null}

        {/* Correct value — shown only when wrong */}
        {!result.is_correct && (
          <span className="text-lg text-emerald-500">{result.correct_value}</span>
        )}

        {/* Explanation or fallback */}
        {result.explanation ? (
          <span className="text-sm text-zinc-400 text-center max-w-sm">
            {result.explanation}
          </span>
        ) : !result.is_correct ? (
          <span className="text-sm text-zinc-400 italic">
            Evaluation unavailable — rate manually
          </span>
        ) : null}

        {/* Correct confirmation */}
        {result.is_correct && (
          <span className="text-sm text-emerald-500">✓ Correct</span>
        )}

        {/* FSRS rating row with pre-selected suggested_rating */}
        <WriteResultRatingRow
          suggestedRating={result.suggested_rating}
          onRate={onRate}
        />
      </div>
    )
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
        <span className={`${targetWordSize} font-semibold text-zinc-50`}>{card.target_word}</span>
        <span className="text-sm text-zinc-500 mt-2">Space to reveal</span>
      </button>
    )
  }

  // ── Revealed state ────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col items-center gap-4 p-8">
      {/* Target word stays visible */}
      <span className={`${targetWordSize} font-semibold text-zinc-50`}>{card.target_word}</span>

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
