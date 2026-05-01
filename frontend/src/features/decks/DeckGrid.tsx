/**
 * DeckGrid — deck browser with create, rename, delete, and language-switch.
 *
 * State:
 * - TanStack Query owns all deck and settings data
 * - createState: "hidden" | "open" — local UI state for the create form
 * - filterText — local client-side name filter
 *
 * Cache update strategy (setQueryData, NOT invalidateQueries):
 * - Create: optimistic insert + sort
 * - Rename: optimistic replace + sort
 * - Delete: optimistic remove
 * - Language switch: query key changes → TanStack Query auto-fetches new language's decks
 */

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { get, post, patch, del, put, ApiError } from "@/lib/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useAppStore } from "@/lib/stores/useAppStore"
import { DeckCard, type DeckResponse } from "./DeckCard"

export type { DeckResponse }

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Safely parse a JSON string into string[]. Returns fallback on any parse error. */
function parseLanguages(raw: string, fallback: string[]): string[] {
  try {
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) && parsed.every((x) => typeof x === "string")
      ? (parsed as string[])
      : fallback
  } catch {
    return fallback
  }
}

// ── Types ──────────────────────────────────────────────────────────────────────

interface SettingsResponse {
  id: number
  native_language: string
  active_target_language: string
  target_languages: string // JSON string
  onboarding_completed: boolean
  auto_generate_audio: boolean
  auto_generate_images: boolean
  default_practice_mode: string
  cards_per_session: number
}

type CreateState = "hidden" | "open"

// ── CreateDeckForm (internal component) ──────────────────────────────────────

interface CreateDeckFormProps {
  onSubmit: (name: string) => void
  onCancel: () => void
  isPending: boolean
}

function CreateDeckForm({ onSubmit, onCancel, isPending }: CreateDeckFormProps) {
  const [name, setName] = useState("")
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (name.trim()) onSubmit(name.trim())
      }}
      className="flex gap-2 items-center max-w-sm border border-zinc-700 rounded-lg p-3"
    >
      <Input
        autoFocus
        placeholder="Deck name..."
        aria-label="New deck name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={200}
      />
      <Button type="submit" disabled={!name.trim() || isPending} size="sm">
        {isPending ? "Creating..." : "Create"}
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
        Cancel
      </Button>
    </form>
  )
}

// ── DeckGridSkeleton ──────────────────────────────────────────────────────────

function DeckGridSkeleton() {
  return (
    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-lg border border-zinc-800 p-4 flex flex-col gap-2">
          <Skeleton data-slot="skeleton" className="h-5 w-3/4" />
          <Skeleton data-slot="skeleton" className="h-4 w-1/2" />
        </div>
      ))}
    </div>
  )
}

// ── EmptyDecksState ──────────────────────────────────────────────────────────

function EmptyDecksState({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-zinc-400">
      {hasFilter ? (
        <p>No decks match your filter.</p>
      ) : (
        <p>No decks yet — create your first deck above.</p>
      )}
    </div>
  )
}

// ── DeckGrid ──────────────────────────────────────────────────────────────────

export function DeckGrid() {
  const queryClient = useQueryClient()
  const [createState, setCreateState] = useState<CreateState>("hidden")
  const [filterText, setFilterText] = useState("")

  // Fetch settings to get active_target_language + available languages
  const { data: settings, isLoading: settingsLoading } = useQuery<SettingsResponse>({
    queryKey: ["settings"],
    queryFn: () => get<SettingsResponse>("/settings"),
  })

  const activeLanguage = settings?.active_target_language ?? "es"
  const availableLanguages: string[] = settings
    ? parseLanguages(settings.target_languages, [activeLanguage])
    : [activeLanguage]

  // Fetch decks for the active language — only when settings have loaded
  const {
    data: decks,
    isLoading,
    isError,
  } = useQuery<DeckResponse[]>({
    queryKey: ["decks", activeLanguage],
    queryFn: () => get<DeckResponse[]>(`/decks?target_language=${activeLanguage}`),
    enabled: !!settings,
  })

  // Client-side name filter
  const filteredDecks = (decks ?? []).filter((d) =>
    d.name.toLowerCase().includes(filterText.toLowerCase())
  )

  // ── Mutations ──────────────────────────────────────────────────────────────

  const createDeck = useMutation({
    mutationFn: (name: string) =>
      post<DeckResponse>("/decks", { name, target_language: activeLanguage }),
    onSuccess: (newDeck) => {
      queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
        old
          ? [...old, newDeck].sort((a, b) => a.name.localeCompare(b.name))
          : [newDeck]
      )
      setCreateState("hidden")
    },
    onError: (error: ApiError) => {
      // For 409, error.detail already contains the full RFC 7807 message from the backend
      // (e.g. "A deck named 'X' already exists for language 'Y'") — use it directly.
      const message =
        error.status === 409
          ? (error.detail ?? error.title ?? "A deck with that name already exists")
          : (error.detail ?? "Failed to create deck")
      useAppStore.getState().addNotification({ type: "error", message })
    },
  })

  const renameDeck = useMutation({
    mutationFn: ({ deckId, name }: { deckId: number; name: string }) =>
      patch<DeckResponse>(`/decks/${deckId}`, { name }),
    onSuccess: (updated) => {
      queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
        old
          ? old
              .map((d) => (d.id === updated.id ? updated : d))
              .sort((a, b) => a.name.localeCompare(b.name))
          : [updated]
      )
    },
    onError: (error: ApiError) => {
      useAppStore.getState().addNotification({
        type: "error",
        message: error.status === 409 ? "Deck name already exists" : (error.detail ?? "Failed to rename"),
      })
    },
  })

  const deleteDeck = useMutation({
    mutationFn: (deckId: number) => del(`/decks/${deckId}`),
    onSuccess: (_, deckId) => {
      queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
        old ? old.filter((d) => d.id !== deckId) : []
      )
    },
    onError: (error: ApiError) => {
      useAppStore.getState().addNotification({
        type: "error",
        message: error.detail ?? "Failed to delete deck",
      })
    },
  })

  const switchLanguage = useMutation({
    mutationFn: (langCode: string) =>
      put<SettingsResponse>("/settings", { active_target_language: langCode }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["settings"], updated)
      // Deck list auto-refetches because activeLanguage changes (query key changes)
    },
    onError: (error: ApiError) => {
      useAppStore.getState().addNotification({
        type: "error",
        message: error.detail ?? "Failed to switch language",
      })
    },
  })

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="p-4 md:p-8 flex flex-col gap-6">
      {/* Header: title + language switcher + new deck button */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-semibold text-zinc-50">Decks</h1>
        <div className="flex items-center gap-3">
          {/* Language selector — only shown if > 1 language */}
          {availableLanguages.length > 1 && (
            <select
              aria-label="Active target language"
              value={activeLanguage}
              onChange={(e) => switchLanguage.mutate(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-50"
            >
              {availableLanguages.map((lang) => (
                <option key={lang} value={lang}>
                  {lang.toUpperCase()}
                </option>
              ))}
            </select>
          )}
          <Button onClick={() => setCreateState("open")}>New deck</Button>
        </div>
      </div>

      {/* Search filter */}
      <Input
        placeholder="Filter decks by name..."
        aria-label="Filter decks by name"
        value={filterText}
        onChange={(e) => setFilterText(e.target.value)}
        className="max-w-sm"
      />

      {/* Create deck inline form */}
      {createState === "open" && (
        <CreateDeckForm
          onSubmit={(name) => createDeck.mutate(name)}
          onCancel={() => setCreateState("hidden")}
          isPending={createDeck.isPending}
        />
      )}

      {/* Deck grid */}
      {(isLoading || settingsLoading) && <DeckGridSkeleton />}
      {isError && <p className="text-red-400">Failed to load decks</p>}
      {!isLoading && !isError && filteredDecks.length === 0 && (
        <EmptyDecksState hasFilter={!!filterText} />
      )}
      {!isLoading && !isError && filteredDecks.length > 0 && (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {filteredDecks.map((deck) => (
            <DeckCard
              key={deck.id}
              deck={deck}
              onRename={(name) => renameDeck.mutate({ deckId: deck.id, name })}
              onDelete={() => deleteDeck.mutate(deck.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
