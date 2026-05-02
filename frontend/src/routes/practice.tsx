/**
 * routes/practice.tsx — practice session route (self-assess, write, and speak mode).
 *
 * Owns the D4 layout shell (sidebar/right column collapse handled in __root.tsx).
 * D5 layout activates for speak mode (items-center, no pt-16).
 * Renders PracticeCard or SessionSummary based on session phase from usePracticeSession.
 *
 * AC: 1, 2, 3, 4, 7, 8, 10
 */
import { useEffect, useCallback, useRef, useState } from "react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import { usePracticeSession } from "@/features/practice/usePracticeSession"
import { PracticeCard } from "@/features/practice/PracticeCard"
import { SessionSummary } from "@/features/practice/SessionSummary"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"
import { useAppStore } from "@/lib/stores/useAppStore"
import { get } from "@/lib/client"
import type { PracticeMode } from "@/lib/stores/usePracticeStore"
import type { PracticeCardState } from "@/features/practice/PracticeCard"
import type { QueueCard } from "@/features/practice/usePracticeSession"
import type { SyllableFeedbackState } from "@/features/practice/SyllableFeedback"

const VALID_PRACTICE_MODES: readonly PracticeMode[] = ["self_assess", "write", "speak"]

// ── Module-level display helpers ──────────────────────────────────────────────

/** Parse `forms` JSON and produce a display string for the grammatical forms / register context. */
export function deriveGrammaticalForms(card: QueueCard): string | undefined {
  if (!card.forms) return undefined
  try {
    const forms = JSON.parse(card.forms) as Record<string, unknown>
    if (card.card_type === "sentence" || card.card_type === "collocation") {
      const registerContext = forms.register_context as string | null | undefined
      return registerContext ? `Register: ${registerContext}` : undefined
    }
    // Word cards: build "masculine · pl. melancólicos" style string
    const parts: string[] = []
    if (forms.gender && typeof forms.gender === "string") parts.push(forms.gender)
    if (forms.plural && typeof forms.plural === "string") parts.push(`pl. ${forms.plural}`)
    return parts.length > 0 ? parts.join(" · ") : undefined
  } catch {
    return undefined
  }
}

/** Return the first example sentence from the `example_sentences` JSON array. */
export function deriveFirstExampleSentence(card: QueueCard): string | undefined {
  if (!card.example_sentences) return undefined
  try {
    const sentences = JSON.parse(card.example_sentences) as string[]
    return sentences[0] ?? undefined
  } catch {
    return undefined
  }
}

export const Route = createFileRoute("/practice")({
  validateSearch: (search: Record<string, unknown>) => {
    const requested = search.mode as string
    // Runtime guard: unknown mode values fall back to self_assess instead of
    // being cast blindly through as PracticeMode
    const mode: PracticeMode = VALID_PRACTICE_MODES.includes(requested as PracticeMode)
      ? (requested as PracticeMode)
      : "self_assess"
    return { mode }
  },
  component: PracticePage,
})

function PracticePage() {
  const navigate = useNavigate()
  const { mode } = Route.useSearch()
  const sessionCount = usePracticeStore((s) => s.sessionCount)
  const startSession = usePracticeStore((s) => s.startSession)
  const {
    currentCard,
    rateCard,
    evaluateAnswer,
    evaluationResult,
    sessionSummary,
    sessionPhase,
    rollbackCardId,
    evaluateSpeech,
    speechResult,
    skipCard,
    showFallbackNotice,
  } = usePracticeSession(mode)

  // ── Speak mode: MediaRecorder refs and state ──────────────────────────────
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const isUnmountedRef = useRef(false)
  const [isRecording, setIsRecording] = useState(false)

  // AC3: Activate D4 layout (sessionState → "active") on mount so sidebar and
  // right column animate out while the practice session is in progress.
  // endSession() is called by SessionSummary on return/auto-return.
  useEffect(() => {
    startSession(mode)
  }, [startSession, mode])

  // ── Speak mode: handleSpeak — MediaRecorder tap-to-record ─────────────────
  // Tap once to start recording, tap again to stop and submit.
  const handleSpeak = useCallback(async () => {
    // Guard: don't start a new recording while evaluation is in-flight (race condition)
    if (speechResult === "pending") return

    if (mediaRecorderRef.current?.state === "recording") {
      // Already recording: stop (release → submit)
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      return
    }
    // Start new recording
    audioChunksRef.current = []
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)  // no mimeType — use browser default
      recorder.ondataavailable = (e) => { audioChunksRef.current.push(e.data) }
      recorder.onstop = () => {
        const audio = new Blob(audioChunksRef.current, { type: recorder.mimeType })
        stream.getTracks().forEach((t) => t.stop())
        setIsRecording(false)
        // Guard: don't call evaluateSpeech after component has unmounted
        if (!isUnmountedRef.current && currentCard) evaluateSpeech(currentCard.id, audio)
      }
      recorder.start()
      setIsRecording(true)
      mediaRecorderRef.current = recorder
    } catch {
      useAppStore.getState().addNotification({
        type: "error",
        message: "Microphone access denied — grant permission and try again",
      })
    }
  }, [currentCard, evaluateSpeech, speechResult])

  // ── Speak mode: cleanup MediaRecorder on unmount to release mic (P3) ──────
  useEffect(() => {
    return () => {
      isUnmountedRef.current = true
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

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
          firstAttemptSuccessRate={sessionSummary.firstAttemptSuccessRate}
        />
      </div>
    )
  }

  // ── Practicing phase — show current card ──────────────────────────────────
  if (sessionPhase === "practicing" && currentCard) {
    // Determine initial state for the card based on mode and rollback
    let initialState: PracticeCardState = "front"
    if (mode === "write") {
      initialState = rollbackCardId === currentCard.id ? "write-result" : "write-active"
    } else if (mode === "speak") {
      initialState = rollbackCardId === currentCard.id ? "speak-result" : "speak-recording"
    } else if (rollbackCardId === currentCard.id) {
      initialState = "revealed"
    }

    // Derive SyllableFeedbackState from speechResult (AC4: fallback-notice for local Whisper)
    const syllableFeedbackState: SyllableFeedbackState = (() => {
      if (!speechResult) return "awaiting"
      if (speechResult === "pending") return "evaluating"
      // TypeScript narrows speechResult to SpeechEvaluationResult here — no cast needed
      if (showFallbackNotice) return "fallback-notice"
      return speechResult.overall_correct ? "result-correct" : "result-partial"
    })()

    const speechResultData = speechResult !== null && speechResult !== "pending"
      ? speechResult
      : undefined

    // D5 layout for speak mode; D4 for self-assess and write
    const outerClassName = mode === "speak"
      ? "flex items-center justify-center min-h-screen px-4"
      : "flex items-start justify-center min-h-screen pt-16 px-4"

    return (
      <div className={outerClassName}>
        <div className="max-w-xl mx-auto w-full">
          <PracticeCard
            key={currentCard.id}
            card={{
              ...currentCard,
              grammatical_forms: deriveGrammaticalForms(currentCard),
              example_sentence: deriveFirstExampleSentence(currentCard),
            }}
            onRate={(rating) => rateCard(currentCard.id, rating)}
            onEvaluate={(answer) => evaluateAnswer(currentCard.id, answer)}
            evaluationResult={evaluationResult}
            sessionCount={sessionCount}
            initialState={initialState}
            onSpeak={handleSpeak}
            onSkip={skipCard}
            isRecording={isRecording}
            syllableFeedbackState={syllableFeedbackState}
            speechSyllables={speechResultData?.syllables}
            speechCorrectionMessage={speechResultData?.correction_message}
            speechProviderUsed={speechResultData?.provider_used}
          />
        </div>
      </div>
    )
  }

  // Fallback (shouldn't be reached)
  return null
}
