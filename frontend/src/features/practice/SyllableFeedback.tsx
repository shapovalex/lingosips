/**
 * SyllableFeedback component — displays syllable-by-syllable pronunciation feedback.
 *
 * This is a standalone, isolated component (Story 4.2).
 * It does NOT integrate into the full speak mode practice flow — that is Story 4.3.
 * All data is accepted as props; events emitted via callbacks.
 *
 * AC: 1–7
 */

// ── Types ─────────────────────────────────────────────────────────────────────

/**
 * The display state of the SyllableFeedback component.
 * Enum-driven state machine — never boolean flags.
 *
 * - "awaiting"       — pre-recording; chips neutral, mic ready
 * - "evaluating"     — evaluation in flight; chips pulse, "Evaluating..." label
 * - "result-correct" — all syllables correct; emerald header tint
 * - "result-partial" — some wrong; amber chips, correction text, Try again/Move on
 * - "fallback-notice"— whisper fallback detected; amber badge + pulsing chips
 */
export type SyllableFeedbackState =
  | "awaiting"
  | "evaluating"
  | "result-correct"
  | "result-partial"
  | "fallback-notice"

/** Per-chip visual state derived from the component state + syllable correctness. */
type ChipState = "neutral" | "correct" | "wrong" | "pending"

interface SyllableFeedbackProps {
  /** The target word being practiced (shown in header) */
  targetWord: string
  /** Current component display state */
  state: SyllableFeedbackState
  /** Syllable breakdown from API — null when awaiting or evaluating */
  syllables?: Array<{ syllable: string; correct: boolean; score: number }>
  /** Correction message from API — null/undefined when all correct */
  correctionMessage?: string | null
  /** Provider used — triggers fallback-notice when "local_whisper" */
  providerUsed?: string
  /** Called when user taps "Try again" in result-partial state */
  onRetry?: () => void
  /** Called when user taps "Move on" in result-partial state */
  onMoveOn?: () => void
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Derive per-chip visual state from component state and syllable correctness.
 * Uses the state machine defined in the story's Dev Notes.
 */
function deriveChipState(
  componentState: SyllableFeedbackState,
  syllableCorrect: boolean
): ChipState {
  if (componentState === "awaiting") return "neutral"
  if (componentState === "evaluating" || componentState === "fallback-notice") return "pending"
  if (componentState === "result-correct") return "correct"
  if (componentState === "result-partial") return syllableCorrect ? "correct" : "wrong"
  return "neutral"
}

/**
 * Map a ChipState to Tailwind CSS classes.
 * Design tokens from story Dev Notes:
 *   neutral  → zinc-900 bg, zinc-800 border
 *   correct  → emerald-950 bg, emerald-800 border, emerald-300 text
 *   wrong    → amber-950 bg, amber-400 border, amber-300 text  (AMBER — never red)
 *   pending  → zinc-900 bg, zinc-800 border + animate-pulse
 */
function chipClasses(chipState: ChipState): string {
  const base = "inline-flex items-center justify-center px-3 py-1 rounded-md text-sm font-medium"
  switch (chipState) {
    case "neutral":
      return `${base} bg-zinc-900 border border-zinc-800 text-zinc-400`
    case "correct":
      return `${base} bg-emerald-950 border border-emerald-800 text-emerald-300`
    case "wrong":
      return `${base} bg-amber-950 border border-amber-400 text-amber-300`
    case "pending":
      return `${base} bg-zinc-900 border border-zinc-800 text-zinc-400 animate-pulse`
    default: {
      const _exhaustive: never = chipState
      return base
    }
  }
}

/**
 * Build per-chip aria-label — syllable + status text (AC6).
 * Uses "correct" or "incorrect" — never color-only (AC7).
 */
function chipAriaLabel(syllable: string, chipState: ChipState): string {
  if (chipState === "wrong") return `${syllable} — incorrect`
  if (chipState === "correct") return `${syllable} — correct`
  // neutral / pending states — still label chip with its text for screen readers
  return `${syllable}`
}

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * SyllableFeedback renders syllable chips with per-chip color feedback,
 * an aria-live correction message, and action buttons for partial results.
 */
export function SyllableFeedback({
  targetWord,
  state,
  syllables,
  correctionMessage,
  providerUsed: _providerUsed,
  onRetry,
  onMoveOn,
}: SyllableFeedbackProps) {
  // ── Derived values ──────────────────────────────────────────────────────────

  const isResultCorrect = state === "result-correct"
  const isResultPartial = state === "result-partial"
  const isEvaluating = state === "evaluating"
  const isFallbackNotice = state === "fallback-notice"

  // Header background — emerald tint only when all correct (AC3)
  const headerClasses = isResultCorrect
    ? "flex items-center justify-between px-4 py-3 rounded-t-lg bg-emerald-950/30"
    : "flex items-center justify-between px-4 py-3 rounded-t-lg"

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden">
      {/* Header — target word */}
      <div
        data-testid="syllable-feedback-header"
        className={headerClasses}
      >
        <span className="text-base font-semibold text-zinc-100">{targetWord}</span>
      </div>

      {/* Body */}
      <div className="px-4 pb-4 space-y-3">
        {/* Fallback-notice badge (AC5) — amber, visible but not alarming */}
        {isFallbackNotice && (
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/20 border border-amber-500 text-amber-300 text-xs font-medium">
              Using local Whisper · ~3s
            </span>
          </div>
        )}

        {/* Chip row */}
        {syllables && syllables.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {syllables.map((s, i) => {
              const chipState = deriveChipState(state, s.correct)
              return (
                <span
                  key={`${s.syllable}-${i}`}
                  role="img"
                  aria-label={chipAriaLabel(s.syllable, chipState)}
                  className={chipClasses(chipState)}
                >
                  {s.syllable}
                </span>
              )
            })}
          </div>
        )}

        {/* Evaluating label (AC2) — evaluating state only; fallback-notice shows badge+chips only */}
        {isEvaluating && (
          <p className="text-sm text-zinc-400">Evaluating...</p>
        )}

        {/* Correction text — aria-live assertive (AC6) */}
        <div aria-live="assertive" aria-atomic="true">
          {isResultPartial && correctionMessage && (
            <p className="text-sm text-zinc-400">{correctionMessage}</p>
          )}
        </div>

        {/* Action buttons — only in result-partial (AC4) */}
        {isResultPartial && (
          <div className="flex gap-3 mt-2">
            <button
              type="button"
              onClick={() => onRetry?.()}
              className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-500 hover:bg-indigo-400 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => onMoveOn?.()}
              className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              Move on
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
