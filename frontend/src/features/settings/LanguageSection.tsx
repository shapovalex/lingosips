/**
 * LanguageSection — native language + target languages configuration.
 *
 * Source of truth: GET /settings (TanStack Query ["settings"])
 * target_languages is a JSON string in SQLite — always use safeParseLanguages() to parse.
 *
 * AC5
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { get, put } from "@/lib/client"
import { useAppStore } from "@/lib/stores/useAppStore"

interface SettingsResponse {
  id: number
  native_language: string
  active_target_language: string
  target_languages: string  // JSON string: '["es", "fr"]'
  auto_generate_audio: boolean
  auto_generate_images: boolean
  default_practice_mode: string
  cards_per_session: number
  onboarding_completed: boolean
}

// Authoritative language list — mirrors core/settings.py SUPPORTED_LANGUAGES
const SUPPORTED_LANGUAGES: Record<string, string> = {
  en: "English",
  es: "Spanish",
  fr: "French",
  de: "German",
  it: "Italian",
  pt: "Portuguese",
  nl: "Dutch",
  pl: "Polish",
  ru: "Russian",
  ja: "Japanese",
  zh: "Chinese (Simplified)",
  ko: "Korean",
  ar: "Arabic",
  tr: "Turkish",
  sv: "Swedish",
  da: "Danish",
  no: "Norwegian",
  cs: "Czech",
  uk: "Ukrainian",
}

/**
 * Safe JSON parse for target_languages string column.
 * NEVER use raw JSON.parse() — crashes on malformed data (Story 2.2 code review finding).
 */
function safeParseLanguages(raw: string | undefined): string[] {
  if (!raw) return ["es"]
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : ["es"]
  } catch {
    return ["es"]
  }
}

export function LanguageSection() {
  const queryClient = useQueryClient()
  const addNotification = useAppStore((s) => s.addNotification)

  const { data: settings } = useQuery<SettingsResponse>({
    queryKey: ["settings"],
    queryFn: () => get<SettingsResponse>("/settings"),
  })

  // Local form state — initialized from query data
  const [nativeLanguage, setNativeLanguage] = useState("en")
  const [activeTargetLanguage, setActiveTargetLanguage] = useState("es")
  const [targetLanguages, setTargetLanguages] = useState<string[]>(["es"])

  // Sync local state from query data (initialize form fields when server data arrives).
  // Pattern: external store sync via useEffect is intentional here — the form needs
  // editable local copies of server values. This is a legitimate use of setState in effect.
  useEffect(() => {
    if (settings) {
      setNativeLanguage(settings.native_language) // eslint-disable-line react-hooks/set-state-in-effect
      setActiveTargetLanguage(settings.active_target_language)
      setTargetLanguages(safeParseLanguages(settings.target_languages))
    }
  }, [settings])

  const saveMutation = useMutation({
    mutationFn: () =>
      put<SettingsResponse>("/settings", {
        native_language: nativeLanguage,
        active_target_language: activeTargetLanguage,
        target_languages: targetLanguages,
      }),
    onSuccess: () => {
      // Invalidate settings AND decks (deck browser re-renders for new language)
      queryClient.invalidateQueries({ queryKey: ["settings"] })
      queryClient.invalidateQueries({ queryKey: ["decks"] })
    },
    onError: (error: Error) => {
      addNotification({
        type: "error",
        message: error.message ?? "Failed to save language settings",
      })
    },
  })

  function handleRemoveLanguage(code: string) {
    // Cannot remove the active language or the last language
    if (targetLanguages.length <= 1 || code === activeTargetLanguage) return
    setTargetLanguages((prev) => prev.filter((l) => l !== code))
  }

  function handleAddLanguage(code: string) {
    if (!code || targetLanguages.includes(code)) return
    setTargetLanguages((prev) => [...prev, code])
  }

  const availableToAdd = Object.keys(SUPPORTED_LANGUAGES).filter(
    (code) => !targetLanguages.includes(code)
  )

  return (
    <div className="space-y-4">
      {/* Native language */}
      <div>
        <label
          htmlFor="native-language"
          className="block text-sm font-medium text-zinc-300 mb-1"
        >
          Native language
        </label>
        <select
          id="native-language"
          value={nativeLanguage}
          onChange={(e) => setNativeLanguage(e.target.value)}
          className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
        >
          {Object.entries(SUPPORTED_LANGUAGES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
      </div>

      {/* Active target language */}
      <div>
        <label
          htmlFor="active-target-language"
          className="block text-sm font-medium text-zinc-300 mb-1"
        >
          Active target language
        </label>
        <select
          id="active-target-language"
          value={activeTargetLanguage}
          onChange={(e) => setActiveTargetLanguage(e.target.value)}
          className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
        >
          {targetLanguages.map((code) => (
            <option key={code} value={code}>
              {SUPPORTED_LANGUAGES[code] ?? code}
            </option>
          ))}
        </select>
      </div>

      {/* Target languages list */}
      <div>
        <p className="block text-sm font-medium text-zinc-300 mb-2">
          Target languages
        </p>
        <div className="flex flex-wrap gap-2 mb-2">
          {targetLanguages.map((code) => {
            const isLast = targetLanguages.length <= 1
            const isActive = code === activeTargetLanguage
            const cantRemove = isLast || isActive
            return (
              <span
                key={code}
                className="inline-flex items-center gap-1 rounded-full bg-zinc-800 px-3 py-1 text-sm text-zinc-200"
              >
                {SUPPORTED_LANGUAGES[code] ?? code}
                <button
                  type="button"
                  disabled={cantRemove}
                  onClick={() => handleRemoveLanguage(code)}
                  className="ml-1 text-zinc-500 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-30"
                  aria-label={`Remove ${SUPPORTED_LANGUAGES[code] ?? code}`}
                >
                  ×
                </button>
              </span>
            )
          })}
        </div>

        {/* Add language */}
        {availableToAdd.length > 0 && (
          <select
            aria-label="Add target language"
            onChange={(e) => {
              if (e.target.value) {
                handleAddLanguage(e.target.value)
                e.target.value = ""
              }
            }}
            defaultValue=""
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
          >
            <option value="">Add language…</option>
            {availableToAdd.map((code) => (
              <option key={code} value={code}>
                {SUPPORTED_LANGUAGES[code]}
              </option>
            ))}
          </select>
        )}
      </div>

      <button
        type="button"
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
        className="rounded bg-zinc-700 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-600 disabled:opacity-50"
      >
        {saveMutation.isPending ? "Saving…" : "Save"}
      </button>
    </div>
  )
}
