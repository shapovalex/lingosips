/**
 * useCardStream — hook that drives the CardCreationPanel state machine.
 *
 * State machine:
 *   idle → loading → populated → saving → idle
 *   idle → loading → error → idle (via reset/discard)
 *
 * Architecture rules followed:
 * - fetch() is NOT called here — only streamPost() from lib/client
 * - TanStack Query owns card list invalidation
 * - Zustand is NOT used (streaming state is local to this component tree)
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { streamPost, ApiError } from "../../lib/client"

export type CardCreationState = "idle" | "loading" | "populated" | "saving" | "error"

export interface CardFieldData {
  translation?: string
  forms?: {
    gender: string | null
    article: string | null
    plural: string | null
    conjugations: Record<string, string>
  }
  example_sentences?: string[]
  audio?: string
  card_id?: number
}

export function useCardStream() {
  const [state, setState] = useState<CardCreationState>("idle")
  const [fields, setFields] = useState<CardFieldData>({})
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const queryClient = useQueryClient()

  // Cleanup on unmount — abort in-flight stream and cancel any pending save reset
  useEffect(
    () => () => {
      abortRef.current?.abort()
      if (saveTimeoutRef.current !== null) clearTimeout(saveTimeoutRef.current)
    },
    []
  )

  const startStream = useCallback(async (targetWord: string) => {
    // Abort any in-flight request
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    // Cancel any pending saveCard state reset to prevent it from clobbering this new stream
    if (saveTimeoutRef.current !== null) {
      clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = null
    }

    const { signal } = abortRef.current

    setState("loading")
    setFields({})
    setErrorMessage(null)

    try {
      for await (const event of streamPost("/cards/stream", { target_word: targetWord }, signal)) {
        if (signal.aborted) return

        if (event.event === "field_update") {
          const { field, value } = event.data as { field: string; value: unknown }
          setFields((prev) => ({ ...prev, [field]: value }))
        } else if (event.event === "complete") {
          const { card_id } = event.data as { card_id: number }
          setFields((prev) => ({ ...prev, card_id }))
          setState("populated")
        } else if (event.event === "error") {
          const { message } = event.data as { message: string }
          setErrorMessage(message)
          setState("error")
        }
      }
    } catch (err) {
      if (signal.aborted) return
      // Prefer ApiError.title (backend-specific message), then err.message, then generic fallback
      setErrorMessage(
        err instanceof ApiError
          ? err.title
          : err instanceof Error
            ? err.message
            : "Connection failed"
      )
      setState("error")
    }
  }, [])

  const saveCard = useCallback(() => {
    setState("saving")
    // Card is already persisted in DB — just invalidate the cache so card list refreshes
    queryClient.invalidateQueries({ queryKey: ["cards"] })
    // Rapid-click guard: cancel any existing reset timer before scheduling a new one
    if (saveTimeoutRef.current !== null) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(() => {
      saveTimeoutRef.current = null
      setState("idle")
      setFields({})
      setErrorMessage(null)
    }, 300)
  }, [queryClient])

  const discard = useCallback(() => {
    // TODO Story 2.1: call DELETE /cards/${fields.card_id} to actually remove the card
    // Card remains in DB as an unlisted card until DELETE is implemented
    abortRef.current?.abort()
    // Cancel any pending saveCard state reset
    if (saveTimeoutRef.current !== null) {
      clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = null
    }
    setState("idle")
    setFields({})
    setErrorMessage(null)
  }, [])

  // reset is an alias for discard — used from error state for retry setup
  const reset = discard

  return { state, fields, errorMessage, startStream, saveCard, discard, reset }
}
