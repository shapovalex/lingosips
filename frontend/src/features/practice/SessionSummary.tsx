/**
 * SessionSummary — shown after all cards in a session have been rated.
 *
 * Displays 3 data points only: cards reviewed, recall rate, next session due.
 * Tone is neutral and factual — no stars, no streaks, no congratulations.
 *
 * Auto-returns to home after 5 seconds; cancelled on unmount.
 *
 * AC: 8
 */
import { useCallback, useEffect } from "react"
import { useNavigate } from "@tanstack/react-router"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"

// ── Utilities ─────────────────────────────────────────────────────────────────

/**
 * Format next due date using Intl.RelativeTimeFormat — no date libraries.
 * Returns:
 *   null → "All caught up!"
 *   in the past or within 1 hour → "Cards due now"
 *   else → "in X hours" / "in X days"
 */
function formatNextDue(nextDue: string | null): string {
  if (!nextDue) return "All caught up!"
  const diff = new Date(nextDue).getTime() - Date.now()
  if (diff <= 3_600_000) return "Cards due now"
  const rtf = new Intl.RelativeTimeFormat("en", { style: "long" })
  const hours = diff / 3_600_000
  if (hours < 24) return rtf.format(Math.round(hours), "hour")
  return rtf.format(Math.round(hours / 24), "day")
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface SessionSummaryProps {
  cardsReviewed: number
  recallRate: number  // 0–1 fraction
  nextDue: string | null
  firstAttemptSuccessRate?: number  // speak mode only — omit for self-assess/write
}

// ── Component ─────────────────────────────────────────────────────────────────

export function SessionSummary({ cardsReviewed, recallRate, nextDue, firstAttemptSuccessRate }: SessionSummaryProps) {
  const navigate = useNavigate()
  const endSession = usePracticeStore((s) => s.endSession)

  // useCallback ensures the auto-return timer captures a stable reference,
  // satisfying react-hooks/exhaustive-deps without a stale closure.
  const handleReturnHome = useCallback(() => {
    endSession()
    void navigate({ to: "/" })
  }, [endSession, navigate])

  // Auto-return after 5 seconds; cancelled on unmount
  useEffect(() => {
    const timer = setTimeout(handleReturnHome, 5000)
    return () => clearTimeout(timer)
  }, [handleReturnHome])

  const recallPercent = Math.round(recallRate * 100)
  const nextDueText = formatNextDue(nextDue)

  return (
    <div
      role="region"
      aria-label="Session summary"
      className="flex flex-col items-center gap-6 p-8 max-w-xl mx-auto"
    >
      {/* Neutral, factual heading */}
      <h2 className="text-xl font-semibold text-zinc-200">Session complete</h2>

      {/* 3 data points — displayed as flat sentences for accessibility and test readability */}
      <ul className="flex flex-col gap-4 w-full text-center list-none" aria-label="Session statistics">
        <li className="text-2xl font-semibold text-zinc-100">
          {cardsReviewed} cards reviewed
        </li>
        <li className="text-2xl font-semibold text-zinc-100">
          {recallPercent}% recall rate
        </li>
        <li className="text-sm text-zinc-400">
          {nextDueText}
        </li>
        {firstAttemptSuccessRate !== undefined && (
          <li className="text-sm text-zinc-400">
            First-attempt success: {Math.round(firstAttemptSuccessRate * 100)}%
          </li>
        )}
      </ul>

      {/* Return to home */}
      <button
        onClick={handleReturnHome}
        className="mt-2 px-6 py-2 rounded-md bg-indigo-500 text-sm font-medium text-white
                   hover:bg-indigo-400 focus:outline-none focus:ring-2
                   focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950
                   transition-colors"
      >
        Return to home
      </button>
    </div>
  )
}
