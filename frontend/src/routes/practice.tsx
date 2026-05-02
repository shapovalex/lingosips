/**
 * routes/practice.tsx — self-assess practice session route.
 *
 * Owns the D4 layout shell (sidebar/right column collapse handled in __root.tsx).
 * Renders PracticeCard or SessionSummary based on session phase from usePracticeSession.
 *
 * AC: 3, 10
 */
import { useEffect } from "react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import { usePracticeSession } from "@/features/practice/usePracticeSession"
import { PracticeCard } from "@/features/practice/PracticeCard"
import { SessionSummary } from "@/features/practice/SessionSummary"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"
import { get } from "@/lib/client"

export const Route = createFileRoute("/practice")({
  component: PracticePage,
})

function PracticePage() {
  const navigate = useNavigate()
  const sessionCount = usePracticeStore((s) => s.sessionCount)
  const startSession = usePracticeStore((s) => s.startSession)
  const { currentCard, rateCard, sessionSummary, sessionPhase, rollbackCardId } = usePracticeSession()

  // AC3: Activate D4 layout (sessionState → "active") on mount so sidebar and
  // right column animate out while the practice session is in progress.
  // endSession() is called by SessionSummary on return/auto-return.
  useEffect(() => {
    startSession("self_assess")
  }, [startSession])

  // AC8: Fetch next-due date when session is complete so SessionSummary can
  // display when the user's next session is scheduled.
  const { data: nextDueData } = useQuery({
    queryKey: ["practice", "next-due"],
    queryFn: () => get<{ next_due: string | null }>("/practice/next-due"),
    enabled: sessionPhase === "complete",
  })

  // ── Loading phase — session cards being fetched ───────────────────────────
  if (sessionPhase === "loading") {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        role="status"
        aria-label="Loading practice session..."
      >
        <div className="flex gap-2">
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce [animation-delay:-0.3s]" />
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce [animation-delay:-0.15s]" />
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" />
        </div>
      </div>
    )
  }

  // ── Complete phase — no cards were due ────────────────────────────────────
  if (sessionPhase === "complete" && !sessionSummary) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-8">
        <p className="text-zinc-300">No cards due — come back later</p>
        <button
          onClick={() => void navigate({ to: "/" })}
          className="px-4 py-2 rounded-md bg-indigo-500 text-sm font-medium text-white
                     hover:bg-indigo-400 focus:outline-none focus:ring-2
                     focus:ring-indigo-500 transition-colors"
        >
          Return home
        </button>
      </div>
    )
  }

  // ── Complete phase — show session summary ─────────────────────────────────
  if (sessionPhase === "complete" && sessionSummary) {
    return (
      <div className="flex items-start justify-center min-h-screen pt-16">
        <SessionSummary
          cardsReviewed={sessionSummary.cardsReviewed}
          recallRate={sessionSummary.recallRate}
          nextDue={nextDueData?.next_due ?? null}
        />
      </div>
    )
  }

  // ── Practicing phase — show current card ──────────────────────────────────
  if (sessionPhase === "practicing" && currentCard) {
    return (
      <div className="flex items-start justify-center min-h-screen pt-16 px-4">
        <div className="max-w-xl mx-auto w-full">
          <PracticeCard
            key={currentCard.id}
            card={currentCard}
            onRate={(rating) => rateCard(currentCard.id, rating)}
            sessionCount={sessionCount}
            initialState={rollbackCardId === currentCard.id ? "revealed" : "front"}
          />
        </div>
      </div>
    )
  }

  // Fallback (shouldn't be reached)
  return null
}
