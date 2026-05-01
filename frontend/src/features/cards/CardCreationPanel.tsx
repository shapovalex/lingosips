/**
 * CardCreationPanel — primary card creation UI component.
 *
 * State machine: idle | loading | populated | saving | error
 * - Delegates all streaming state to useCardStream()
 * - Owns only the input's local controlled value
 *
 * Accessibility:
 * - Input: aria-label="New card — type a word or phrase", autoFocus
 * - Field slots: aria-live="polite" — card container is ALWAYS in the DOM (sr-only when
 *   not in a card state) so screen readers register the live regions before content arrives
 * - Loading container: aria-busy="true"
 *
 * Animation (AC3, AC6):
 * - tailwindcss-animate: animate-in fade-in-0 slide-in-from-bottom-1 on each content element
 * - animationDelay staggers fields by 150ms (translation 0ms → forms 150ms → example 300ms → audio 450ms)
 * - motion-safe: prefix disables all animations when prefers-reduced-motion: reduce (AC6)
 */

import { useEffect, useRef, useState } from "react"
import { Link } from "@tanstack/react-router"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useCardStream } from "./useCardStream"

// Shared animation classes applied to each field content element on mount.
// motion-safe: ensures no animation fires under prefers-reduced-motion: reduce.
const FIELD_ANIM =
  "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-300"

export function CardCreationPanel() {
  const [inputValue, setInputValue] = useState("")
  const [completedCardId, setCompletedCardId] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const hasPlayedRef = useRef(false) // prevent audio from replaying on re-render

  const { state, fields, errorMessage, startStream, saveCard, discard, reset } = useCardStream()

  // Track completedCardId from the SSE complete event
  useEffect(() => {
    if (state === "populated" && fields.card_id != null) {
      setCompletedCardId(fields.card_id)
    }
    if (state === "idle") {
      setCompletedCardId(null)
    }
  }, [state, fields.card_id])

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && inputValue.trim() && state === "idle") {
      startStream(inputValue.trim())
      setInputValue("")
    }
    if (e.key === "Escape") {
      reset()
      setInputValue("")
    }
  }

  // Refocus input after save completes (state returns to idle)
  // Also reset audio play flag for next card
  useEffect(() => {
    if (state === "idle") {
      hasPlayedRef.current = false
      inputRef.current?.focus()
    }
  }, [state])

  // Input is disabled only during loading, saving, and populated (not error — user can edit before retry)
  const inputDisabled = state === "loading" || state === "saving" || state === "populated"
  const showCardPreview = state === "loading" || state === "populated" || state === "saving"
  const showActionRow = state === "populated"
  const showSkeletons = state === "loading"

  const hasTranslation = Boolean(fields.translation)
  const hasForms = Boolean(fields.forms)
  const hasExamples = Boolean(fields.example_sentences && fields.example_sentences.length > 0)
  const hasAudio = Boolean(fields.audio)

  return (
    <div className="flex flex-col gap-4 w-full max-w-2xl mx-auto p-4">
      {/* Input area */}
      <div className="flex flex-col gap-2">
        <Input
          ref={inputRef}
          autoFocus
          type="text"
          aria-label="New card — type a word or phrase"
          placeholder="Type a word or phrase…"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={inputDisabled}
          className="text-base"
        />

        {/* Error message (AC5) */}
        {state === "error" && errorMessage && (
          <div className="flex items-center gap-3">
            <p className="text-red-400 text-sm flex-1">{errorMessage}</p>
            <Button variant="outline" size="sm" onClick={reset}>
              Try again
            </Button>
          </div>
        )}
      </div>

      {/* Card preview — always rendered so aria-live regions stay registered in the DOM.
          Visually hidden (sr-only) when not in a card state (idle / error).
          Uses sr-only (not display:none / visibility:hidden) so screen readers still register
          the live regions and don't miss the first field announcement. */}
      <div
        aria-busy={state === "loading" ? true : undefined}
        className={cn(
          showCardPreview
            ? cn(
                "rounded-lg border border-zinc-800 bg-zinc-900 p-4 flex flex-col gap-3",
                state === "saving" && "ring-1 ring-emerald-500"
              )
            : "sr-only"
        )}
      >
        {/* Translation slot — stagger delay 0ms */}
        <div aria-live="polite">
          {showSkeletons ? (
            <Skeleton className="h-5 w-3/4" />
          ) : hasTranslation ? (
            <p
              className={cn("text-lg font-semibold text-zinc-50", FIELD_ANIM)}
              style={{ animationDelay: "0ms" }}
            >
              {fields.translation}
            </p>
          ) : null}
        </div>

        {/* Forms slot — stagger delay 150ms */}
        <div aria-live="polite">
          {showSkeletons ? (
            <Skeleton className="h-4 w-1/2" />
          ) : hasForms ? (
            <p
              className={cn("text-sm text-zinc-400", FIELD_ANIM)}
              style={{ animationDelay: "150ms" }}
            >
              {[fields.forms?.article, fields.forms?.plural].filter(Boolean).join(" · ") || null}
            </p>
          ) : null}
        </div>

        {/* Example sentences slot — stagger delay 300ms */}
        <div aria-live="polite">
          {showSkeletons ? (
            <Skeleton className="h-4 w-full" />
          ) : hasExamples ? (
            <ul
              className={cn(
                "list-disc list-inside text-sm text-zinc-300 space-y-1",
                FIELD_ANIM
              )}
              style={{ animationDelay: "300ms" }}
            >
              {fields.example_sentences!.map((sentence, i) => (
                <li key={i}>{sentence}</li>
              ))}
            </ul>
          ) : null}
        </div>

        {/* Audio slot — stagger delay 450ms */}
        <div aria-live="polite">
          {showSkeletons ? (
            <Skeleton className="h-8 w-full" />
          ) : hasAudio ? (
            // Wrap audio in animated div — animationDelay on the wrapper, not the audio element itself
            <div className={FIELD_ANIM} style={{ animationDelay: "450ms" }}>
              <audio
                ref={audioRef}
                src={fields.audio}
                controls
                preload="auto"
                className="w-full"
                onCanPlay={() => {
                  if (!hasPlayedRef.current && audioRef.current) {
                    hasPlayedRef.current = true
                    audioRef.current.play().catch(() => {
                      // Autoplay blocked by browser policy — user can click controls manually
                    })
                  }
                }}
              />
            </div>
          ) : showCardPreview ? (
            // No audio after complete event — audio field_update was silently skipped (TTS failed)
            // Only shown in populated/saving state, not in idle/error (which use sr-only container)
            <p
              className={cn("text-zinc-400 text-sm", FIELD_ANIM)}
              style={{ animationDelay: "450ms" }}
            >
              Not available
            </p>
          ) : null}
        </div>
      </div>

      {/* Save / Discard action row (AC4) — visible only in populated state */}
      {showActionRow && (
        <div className="flex gap-2 items-center justify-end">
          <Button variant="ghost" onClick={discard}>
            Discard
          </Button>
          {completedCardId != null && (
            <Link
              to="/cards/$cardId"
              params={{ cardId: String(completedCardId) }}
              className="text-sm text-zinc-400 hover:text-zinc-200 underline"
            >
              View card →
            </Link>
          )}
          <Button onClick={saveCard}>Save card</Button>
        </div>
      )}
    </div>
  )
}
