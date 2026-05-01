/**
 * SystemDefaultsSection — system-wide study default settings.
 *
 * Source of truth: GET /settings (TanStack Query ["settings"])
 * Only dirty fields are sent on save (PUT /settings exclude_none semantics).
 *
 * AC6
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { get, put } from "@/lib/client"
import { useAppStore } from "@/lib/stores/useAppStore"

interface SettingsResponse {
  id: number
  native_language: string
  active_target_language: string
  target_languages: string
  auto_generate_audio: boolean
  auto_generate_images: boolean
  default_practice_mode: string
  cards_per_session: number
  onboarding_completed: boolean
}

type PracticeMode = "self_assess" | "write" | "speak"

const PRACTICE_MODES: Record<PracticeMode, string> = {
  self_assess: "Self-assess",
  write: "Write",
  speak: "Speak",
}

export function SystemDefaultsSection() {
  const queryClient = useQueryClient()
  const addNotification = useAppStore((s) => s.addNotification)

  const { data: settings } = useQuery<SettingsResponse>({
    queryKey: ["settings"],
    queryFn: () => get<SettingsResponse>("/settings"),
  })

  // Local form state — initialized from query data
  const [autoGenerateAudio, setAutoGenerateAudio] = useState(true)
  const [autoGenerateImages, setAutoGenerateImages] = useState(false)
  const [defaultPracticeMode, setDefaultPracticeMode] = useState<PracticeMode>("self_assess")
  const [cardsPerSession, setCardsPerSession] = useState(20)

  // Sync local state from query data (reset dirty state on fresh data)
  useEffect(() => {
    if (settings) {
      setAutoGenerateAudio(settings.auto_generate_audio)
      setAutoGenerateImages(settings.auto_generate_images)
      setDefaultPracticeMode(settings.default_practice_mode as PracticeMode)
      setCardsPerSession(settings.cards_per_session)
    }
  }, [settings])

  // Compute dirty fields — only send fields that differ from persisted values
  const dirtyFields = (): Partial<{
    auto_generate_audio: boolean
    auto_generate_images: boolean
    default_practice_mode: string
    cards_per_session: number
  }> => {
    const dirty: Record<string, boolean | string | number> = {}
    if (!settings) {
      return {
        auto_generate_audio: autoGenerateAudio,
        auto_generate_images: autoGenerateImages,
        default_practice_mode: defaultPracticeMode,
        cards_per_session: cardsPerSession,
      }
    }
    if (autoGenerateAudio !== settings.auto_generate_audio)
      dirty.auto_generate_audio = autoGenerateAudio
    if (autoGenerateImages !== settings.auto_generate_images)
      dirty.auto_generate_images = autoGenerateImages
    if (defaultPracticeMode !== settings.default_practice_mode)
      dirty.default_practice_mode = defaultPracticeMode
    if (cardsPerSession !== settings.cards_per_session)
      dirty.cards_per_session = cardsPerSession
    return dirty
  }

  const isDirty = settings != null && Object.keys(dirtyFields()).length > 0

  const saveMutation = useMutation({
    mutationFn: () => put<SettingsResponse>("/settings", dirtyFields()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
    onError: (error: Error & { title?: string }) => {
      addNotification({
        type: "error",
        message: error.title ?? error.message ?? "Failed to save defaults",
      })
    },
  })

  return (
    <div className="space-y-4">
      {/* Auto-generate audio toggle */}
      <div className="flex items-center justify-between">
        <label
          htmlFor="auto-generate-audio"
          className="text-sm font-medium text-zinc-300"
        >
          Auto-generate audio
        </label>
        <input
          id="auto-generate-audio"
          type="checkbox"
          role="switch"
          aria-label="Auto-generate audio"
          checked={autoGenerateAudio}
          onChange={(e) => setAutoGenerateAudio(e.target.checked)}
          className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
        />
      </div>

      {/* Auto-generate images toggle */}
      <div className="flex items-center justify-between">
        <label
          htmlFor="auto-generate-images"
          className="text-sm font-medium text-zinc-300"
        >
          Auto-generate images
        </label>
        <input
          id="auto-generate-images"
          type="checkbox"
          role="switch"
          aria-label="Auto-generate images"
          checked={autoGenerateImages}
          onChange={(e) => setAutoGenerateImages(e.target.checked)}
          className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
        />
      </div>

      {/* Default practice mode */}
      <div>
        <label
          htmlFor="default-practice-mode"
          className="block text-sm font-medium text-zinc-300 mb-1"
        >
          Default practice mode
        </label>
        <select
          id="default-practice-mode"
          value={defaultPracticeMode}
          onChange={(e) => setDefaultPracticeMode(e.target.value as PracticeMode)}
          className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
        >
          {Object.entries(PRACTICE_MODES).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Cards per session */}
      <div>
        <label
          htmlFor="cards-per-session"
          className="block text-sm font-medium text-zinc-300 mb-1"
        >
          Cards per session
        </label>
        <input
          id="cards-per-session"
          type="number"
          min="1"
          max="100"
          value={cardsPerSession}
          onChange={(e) => setCardsPerSession(Number(e.target.value))}
          className="w-32 rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || !isDirty}
          className="rounded bg-zinc-700 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-600 disabled:opacity-50"
        >
          {saveMutation.isPending ? "Saving…" : "Save"}
        </button>
        {isDirty && !saveMutation.isPending && (
          <span className="text-xs text-amber-400">Unsaved changes</span>
        )}
      </div>
    </div>
  )
}
