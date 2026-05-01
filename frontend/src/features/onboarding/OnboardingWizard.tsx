/**
 * OnboardingWizard — first-run language selection (Story 1.4).
 *
 * State machine: "idle" | "submitting" | "error"
 * - idle:       Form visible, selects enabled, both buttons active.
 * - submitting: Spinner on button, selects disabled, Skip hidden.
 * - error:      Error message in aria-live region, "Try again" resets to idle.
 *
 * On success: invalidates ["settings"] → RootLayout re-fetches → wizard unmounts.
 * Anti-pattern avoided: no Zustand, no window.location.href navigation.
 */

import { useState, useRef, useEffect } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { put } from "@/lib/client"

// Mirrors backend SUPPORTED_LANGUAGES (keep in sync manually until api.d.ts regenerated in T8)
const SUPPORTED_LANGUAGES: Array<{ code: string; label: string }> = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "it", label: "Italian" },
  { code: "pt", label: "Portuguese" },
  { code: "nl", label: "Dutch" },
  { code: "pl", label: "Polish" },
  { code: "ru", label: "Russian" },
  { code: "ja", label: "Japanese" },
  { code: "zh", label: "Chinese (Simplified)" },
  { code: "ko", label: "Korean" },
  { code: "ar", label: "Arabic" },
  { code: "tr", label: "Turkish" },
  { code: "sv", label: "Swedish" },
  { code: "da", label: "Danish" },
  { code: "no", label: "Norwegian" },
  { code: "cs", label: "Czech" },
  { code: "uk", label: "Ukrainian" },
]

interface SettingsUpdateRequest {
  native_language?: string
  active_target_language?: string
  onboarding_completed?: boolean
}

// Enum-driven state machine (project-context.md: never boolean flags)
type WizardState = "idle" | "submitting" | "error"

export function OnboardingWizard() {
  const queryClient = useQueryClient()
  const [wizardState, setWizardState] = useState<WizardState>("idle")
  const [nativeLang, setNativeLang] = useState("en")
  const [targetLang, setTargetLang] = useState("es")
  const [errorMessage, setErrorMessage] = useState("")
  const nativeSelectRef = useRef<HTMLSelectElement>(null)

  // T5.11: Focus native language select on mount (FR40: reach creation in <60s)
  useEffect(() => {
    nativeSelectRef.current?.focus()
  }, [])

  const mutation = useMutation({
    mutationFn: (data: SettingsUpdateRequest) => put<unknown>("/settings", data),
    onMutate: () => {
      setWizardState("submitting")
      setErrorMessage("")
    },
    onSuccess: () => {
      // Transition to idle per state machine, then invalidate — RootLayout re-fetches
      // → onboarding_completed=true → wizard unmounts. The idle transition ensures
      // the form is briefly re-enabled if the refetch is slow, preventing a
      // permanently disabled wizard stuck in "submitting" state.
      setWizardState("idle")
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
    onError: (error: Error) => {
      setWizardState("error")
      setErrorMessage(
        `Settings could not be saved. ${error.message}. Please try again or check your connection.`
      )
    },
  })

  function handleStartLearning() {
    mutation.mutate({
      native_language: nativeLang,
      active_target_language: targetLang,
      onboarding_completed: true,
    })
  }

  // T5.8: Skip → same mutation with defaults + onboarding_completed: true
  function handleSkip() {
    mutation.mutate({
      native_language: "en",
      active_target_language: "es",
      onboarding_completed: true,
    })
  }

  function handleRetry() {
    setWizardState("idle")
  }

  const isSubmitting = wizardState === "submitting"

  return (
    // T5.10: role="main", aria-label="Language setup"
    <div
      className="flex h-screen flex-col items-center justify-center bg-zinc-950 p-8"
      role="main"
      aria-label="Language setup"
    >
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-semibold text-zinc-50">Welcome to lingosips</h1>
          <p className="mt-3 text-zinc-400">
            Choose your languages to get started. You can change these anytime in Settings.
          </p>
        </div>

        {/* T5.10: aria-live="polite" on error region for screen readers */}
        <div aria-live="polite" aria-atomic="true">
          {wizardState === "error" && (
            <div
              role="alert"
              className="rounded-md border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-400"
            >
              {errorMessage}
            </div>
          )}
        </div>

        <div className="space-y-6">
          {/* T5.6: Native language selector — default "en" */}
          <div className="space-y-2">
            <label
              htmlFor="native-language"
              className="text-sm font-medium text-zinc-300"
            >
              I speak (native language)
            </label>
            <select
              id="native-language"
              ref={nativeSelectRef}
              value={nativeLang}
              onChange={(e) => setNativeLang(e.target.value)}
              disabled={isSubmitting}
              aria-label="Native language"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2
                         text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500
                         focus:ring-offset-2 focus:ring-offset-zinc-950 disabled:opacity-50"
            >
              {SUPPORTED_LANGUAGES.map(({ code, label }) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* T5.6: Target language selector — default "es" */}
          <div className="space-y-2">
            <label
              htmlFor="target-language"
              className="text-sm font-medium text-zinc-300"
            >
              I'm learning (target language)
            </label>
            <select
              id="target-language"
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              disabled={isSubmitting}
              aria-label="Target language"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2
                         text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500
                         focus:ring-offset-2 focus:ring-offset-zinc-950 disabled:opacity-50"
            >
              {SUPPORTED_LANGUAGES.map(({ code, label }) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* T5.10: Tab order: native select → target select → "Start learning" → "Skip for now" */}
        <div className="space-y-3">
          {wizardState === "error" ? (
            <button
              onClick={handleRetry}
              className="w-full rounded-md bg-indigo-500 px-4 py-3 font-medium
                         text-white hover:bg-indigo-400 focus:outline-none focus:ring-2
                         focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950"
            >
              Try again
            </button>
          ) : (
            <button
              onClick={handleStartLearning}
              disabled={isSubmitting}
              className="w-full rounded-md bg-indigo-500 px-4 py-3 font-medium
                         text-white hover:bg-indigo-400 focus:outline-none focus:ring-2
                         focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950
                         disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Starting..." : "Start learning"}
            </button>
          )}

          {/* T5.8: Skip for now — hidden during submitting state */}
          {wizardState !== "submitting" && (
            <button
              onClick={handleSkip}
              className="w-full rounded-md px-4 py-2 text-sm text-zinc-400
                         hover:text-zinc-300 focus:outline-none focus:ring-2
                         focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950"
            >
              Skip for now
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
