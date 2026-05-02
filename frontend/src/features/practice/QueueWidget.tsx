/**
 * QueueWidget — displays due cards count and practice mode selector.
 *
 * Enum-driven 3-state machine: "due" | "empty" | "in-session"
 * State is derived from TanStack Query + usePracticeStore — never stored separately.
 *
 * AC: 4
 */

import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { useCallback, useState } from "react"
import { get } from "@/lib/client"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"

// ── Types ────────────────────────────────────────────────────────────────────

type QueueWidgetState = "due" | "empty" | "in-session"

type PracticeMode = "self_assess" | "write"

type QueueCard = {
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

// ── Component ────────────────────────────────────────────────────────────────

export function QueueWidget() {
  const navigate = useNavigate()
  const [selectedMode, setSelectedMode] = useState<PracticeMode>("self_assess")

  const sessionState = usePracticeStore((s) => s.sessionState)
  const startSession = usePracticeStore((s) => s.startSession)

  const { data: queue = [], isLoading, isError } = useQuery<QueueCard[]>({
    queryKey: ["practice", "queue"],
    queryFn: () => get<QueueCard[]>("/practice/queue"),
  })

  // handlePractice defined unconditionally — safe for React's render model.
  const handlePractice = useCallback(() => {
    startSession(selectedMode)
    void navigate({ to: "/practice", search: { mode: selectedMode } })
  }, [startSession, selectedMode, navigate])

  // ── Loading: initial fetch with no cached data ────────────────────────────
  if (isLoading) {
    return (
      <div
        className="flex flex-col items-center gap-2 p-6 text-center"
        data-testid="queue-widget-loading"
      >
        <span className="text-sm text-zinc-500">Loading...</span>
      </div>
    )
  }

  // ── Error: queue fetch failed ─────────────────────────────────────────────
  if (isError) {
    return (
      <div
        className="flex flex-col items-center gap-2 p-6 text-center"
        data-testid="queue-widget-error"
      >
        <span className="text-sm text-zinc-400">Unable to load practice queue</span>
      </div>
    )
  }

  // Derive widget state — never store this separately
  const widgetState: QueueWidgetState =
    sessionState === "active"
      ? "in-session"
      : queue.length > 0
        ? "due"
        : "empty"

  // ── In-session: thin status bar ──────────────────────────────────────────
  if (widgetState === "in-session") {
    return (
      <div
        className="flex items-center justify-between px-4 py-2 bg-indigo-950 border-b border-indigo-800 text-sm text-indigo-200"
        data-testid="queue-widget-session-bar"
      >
        <span>Session active</span>
        <span className="text-indigo-400">{queue.length} remaining</span>
      </div>
    )
  }

  // ── Due: cards ready to practice ─────────────────────────────────────────
  if (widgetState === "due") {
    const count = queue.length

    return (
      <div className="flex flex-col gap-4 p-4" data-testid="queue-widget-due">
        {/* Count region — aria-live for screen reader announcements */}
        <div aria-live="polite" aria-atomic="true" className="flex flex-col items-center gap-1">
          <span
            aria-label={`${count} cards due for review`}
            className="text-4xl font-bold text-zinc-50 tabular-nums"
          >
            {count}
          </span>
          <span className="text-sm text-zinc-400">cards due for review</span>
        </div>

        {/* Mode selector — role="radiogroup" for accessibility */}
        <div
          role="radiogroup"
          aria-label="Practice mode"
          className="flex gap-2"
        >
          <ModeChip
            label="Self-assess"
            value="self_assess"
            selected={selectedMode === "self_assess"}
            onChange={setSelectedMode}
          />
          <ModeChip
            label="Write"
            value="write"
            selected={selectedMode === "write"}
            onChange={setSelectedMode}
          />
        </div>

        {/* Practice button */}
        <button
          onClick={handlePractice}
          className="w-full rounded-md bg-indigo-500 px-4 py-2 text-sm font-medium
                     text-white hover:bg-indigo-400 focus:outline-none focus:ring-2
                     focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950
                     transition-colors"
          aria-label="Practice"
        >
          Practice
        </button>
      </div>
    )
  }

  // ── Empty: all caught up ──────────────────────────────────────────────────
  return (
    <div
      className="flex flex-col items-center gap-2 p-6 text-center"
      data-testid="queue-widget-empty"
    >
      <span className="text-zinc-300 font-medium">All caught up</span>
      <span className="text-sm text-zinc-400">Check back later</span>
    </div>
  )
}

// ── Mode chip sub-component ───────────────────────────────────────────────────

interface ModeChipProps {
  label: string
  value: PracticeMode
  selected: boolean
  onChange: (mode: PracticeMode) => void
}

function ModeChip({ label, value, selected, onChange }: ModeChipProps) {
  return (
    <label
      className={`
        flex-1 flex items-center justify-center px-3 py-1.5 rounded-full text-sm font-medium
        cursor-pointer transition-colors select-none
        ${selected
          ? "bg-indigo-500 text-white"
          : "bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700"
        }
      `}
    >
      {/* input[type=radio] already has implicit role="radio" — no explicit role needed.
          Accessible name comes from the wrapping <label> text — no aria-label on input. */}
      <input
        type="radio"
        name="practice-mode"
        value={value}
        checked={selected}
        onChange={() => onChange(value)}
        className="sr-only"
      />
      {label}
    </label>
  )
}
