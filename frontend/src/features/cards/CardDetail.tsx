/**
 * CardDetail — full card detail view with inline field editing and delete.
 *
 * State machine: "viewing" | "confirm-delete" | "deleting"
 * Loading / error are derived from TanStack Query (isLoading, isError) — not local state.
 *
 * Architecture:
 * - TanStack Query owns card data via ["cards", cardId] key
 * - Zustand (useAppStore) receives error notifications only
 * - del/patch/get from @/lib/client — never fetch() directly
 */

import { useState } from "react"
import { useNavigate, Link } from "@tanstack/react-router"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { get, patch, del, ApiError } from "@/lib/client"
import { useAppStore } from "@/lib/stores/useAppStore"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"

// ── Types ─────────────────────────────────────────────────────────────────────

interface CardFormsData {
  gender: string | null
  article: string | null
  plural: string | null
  conjugations: Record<string, string>
}

interface CardResponse {
  id: number
  target_word: string
  translation: string | null
  forms: CardFormsData | null
  example_sentences: string[]
  audio_url: string | null
  personal_note: string | null
  image_url: string | null
  image_skipped: boolean
  card_type: string
  deck_id: number | null
  target_language: string
  fsrs_state: string
  due: string
  stability: number
  difficulty: number
  reps: number
  lapses: number
  last_review: string | null
  created_at: string
  updated_at: string
}

type CardUpdatePayload = {
  translation?: string | null
  forms?: CardFormsData | null
  example_sentences?: string[] | null
  personal_note?: string | null
  deck_id?: number | null
}

type CardDetailState = "viewing" | "confirm-delete" | "deleting"

// ── FSRS display helper ────────────────────────────────────────────────────────

function getFsrsStatus(fsrsState: string, due: string): string {
  if (fsrsState === "New") return "Not yet practiced"
  const dueDate = new Date(due)
  const now = new Date()
  if (dueDate <= now) return "Due now"
  const diffMs = dueDate.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return `Due in ${diffDays} day${diffDays === 1 ? "" : "s"}`
}

// ── EditableField ─────────────────────────────────────────────────────────────

interface EditableFieldProps {
  fieldName: string
  displayValue: string
  multiline?: boolean
  ariaLabel: string
  editingField: string | null
  fieldDraft: string
  onStartEdit: (fieldName: string, currentValue: string) => void
  onChangeField: (value: string) => void
  onBlur: (fieldName: string) => void
}

function EditableField({
  fieldName,
  displayValue,
  multiline = false,
  ariaLabel,
  editingField,
  fieldDraft,
  onStartEdit,
  onChangeField,
  onBlur,
}: EditableFieldProps) {
  if (editingField === fieldName) {
    if (multiline) {
      return (
        <textarea
          className="w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-zinc-50 focus:border-indigo-500 focus:outline-none"
          value={fieldDraft}
          autoFocus
          onChange={(e) => onChangeField(e.target.value)}
          onBlur={() => onBlur(fieldName)}
          aria-label={`Edit ${ariaLabel}`}
        />
      )
    }
    return (
      <input
        className="w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-zinc-50 focus:border-indigo-500 focus:outline-none"
        value={fieldDraft}
        autoFocus
        onChange={(e) => onChangeField(e.target.value)}
        onBlur={() => onBlur(fieldName)}
        aria-label={`Edit ${ariaLabel}`}
      />
    )
  }
  return (
    <div
      role="button"
      tabIndex={0}
      className="cursor-text rounded px-2 py-1 hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      onClick={() => onStartEdit(fieldName, displayValue)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onStartEdit(fieldName, displayValue)
      }}
      aria-label={`${ariaLabel}: ${displayValue || "empty — click to add"}`}
    >
      {displayValue || <span className="text-zinc-500 italic">Click to add...</span>}
    </div>
  )
}

// ── CardDetail ─────────────────────────────────────────────────────────────────

interface CardDetailProps {
  cardId: number
}

export function CardDetail({ cardId }: CardDetailProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [state, setState] = useState<CardDetailState>("viewing")
  const [editingField, setEditingField] = useState<string | null>(null)
  const [fieldDraft, setFieldDraft] = useState<string>("")

  // ── Server data ────────────────────────────────────────────────────────────

  const { data: card, isLoading, isError, error } = useQuery<CardResponse>({
    queryKey: ["cards", cardId],
    queryFn: () => get<CardResponse>(`/cards/${cardId}`),
  })

  // ── PATCH mutation ─────────────────────────────────────────────────────────

  const updateField = useMutation({
    mutationFn: (update: CardUpdatePayload) =>
      patch<CardResponse>(`/cards/${cardId}`, update),
    onSuccess: (updated) => {
      queryClient.setQueryData(["cards", cardId], updated)
    },
    onError: (err: unknown) => {
      const message =
        err instanceof ApiError ? (err.detail ?? "Failed to save") : "Failed to save"
      useAppStore.getState().addNotification({ type: "error", message })
    },
  })

  // ── DELETE mutation ────────────────────────────────────────────────────────

  const deleteCard = useMutation({
    mutationFn: () => del(`/cards/${cardId}`),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["cards", cardId] })
      queryClient.invalidateQueries({ queryKey: ["practice", "queue"] })
      navigate({ to: "/" })
    },
    onError: (err: unknown) => {
      const message =
        err instanceof ApiError ? (err.detail ?? err.title) : "Delete failed"
      useAppStore.getState().addNotification({ type: "error", message })
      setState("viewing")
    },
  })

  // ── Inline edit handlers ───────────────────────────────────────────────────

  function startEdit(fieldName: string, currentValue: string) {
    setEditingField(fieldName)
    setFieldDraft(currentValue)
  }

  function commitEdit(fieldName: string) {
    if (editingField !== fieldName) return
    setEditingField(null)

    if (fieldName === "translation") {
      updateField.mutate({ translation: fieldDraft })
    } else if (fieldName === "personal_note") {
      updateField.mutate({ personal_note: fieldDraft || null })
    } else if (fieldName === "example_sentences") {
      const lines = fieldDraft
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
      updateField.mutate({ example_sentences: lines })
    } else if (fieldName === "forms") {
      try {
        const parsed = JSON.parse(fieldDraft)
        updateField.mutate({ forms: parsed })
      } catch {
        useAppStore.getState().addNotification({
          type: "error",
          message: "Forms field contains invalid JSON — edit not saved",
        })
      }
    }
  }

  // ── Loading state ──────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 max-w-2xl mx-auto">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
        <div className="flex flex-col gap-3 mt-4">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
    )
  }

  // ── Error state ────────────────────────────────────────────────────────────

  if (isError || !card) {
    const errMessage =
      error instanceof ApiError ? error.title : "Failed to load card"
    return (
      <div className="flex flex-col gap-4 max-w-2xl mx-auto">
        <p className="text-red-400">{errMessage}</p>
        <Link to="/" className="text-zinc-400 hover:text-zinc-200 text-sm underline">
          ← Back to home
        </Link>
      </div>
    )
  }

  // ── Viewing / editing state ────────────────────────────────────────────────

  const fsrsStatus = getFsrsStatus(card.fsrs_state, card.due)
  const formsDraft = card.forms ? JSON.stringify(card.forms, null, 2) : "{}"
  const examplesDraft = card.example_sentences.join("\n")
  const noteDraft = card.personal_note ?? ""

  return (
    <div className="flex flex-col gap-0 max-w-2xl mx-auto">
      {/* Header row */}
      <div className="flex items-center justify-between pb-4">
        <Link to="/" className="text-zinc-400 hover:text-zinc-200 text-sm underline">
          ← Back to home
        </Link>
        <Button
          variant="destructive"
          size="sm"
          onClick={() => setState("confirm-delete")}
          aria-label="Delete card"
        >
          Delete card
        </Button>
      </div>

      {/* Target word (non-editable) */}
      <div className="border-b border-zinc-800 pb-4 mb-4">
        <h1 className="text-2xl font-bold text-zinc-50">{card.target_word}</h1>
        <p className="text-sm text-zinc-400">
          {card.target_language} · {card.card_type}
        </p>
      </div>

      {/* Translation + FSRS */}
      <div className="border-b border-zinc-800 pb-4 mb-4">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-sm font-medium text-zinc-300 uppercase tracking-wide">
            Translation
          </h2>
          <span className="text-xs text-zinc-500">{fsrsStatus}</span>
        </div>
        <EditableField
          fieldName="translation"
          displayValue={card.translation ?? ""}
          ariaLabel="translation"
          editingField={editingField}
          fieldDraft={fieldDraft}
          onStartEdit={startEdit}
          onChangeField={setFieldDraft}
          onBlur={commitEdit}
        />
      </div>

      {/* Grammatical Forms */}
      <div className="border-b border-zinc-800 pb-4 mb-4">
        <h2 className="text-sm font-medium text-zinc-300 uppercase tracking-wide mb-1">
          Grammatical Forms
        </h2>
        <EditableField
          fieldName="forms"
          displayValue={
            card.forms
              ? [card.forms.article, card.forms.gender, card.forms.plural]
                  .filter(Boolean)
                  .join(" · ")
              : ""
          }
          multiline
          ariaLabel="grammatical forms"
          editingField={editingField}
          fieldDraft={editingField === "forms" ? fieldDraft : formsDraft}
          onStartEdit={(name, _currentValue) => startEdit(name, formsDraft)}
          onChangeField={setFieldDraft}
          onBlur={commitEdit}
        />
      </div>

      {/* Example Sentences */}
      <div className="border-b border-zinc-800 pb-4 mb-4">
        <h2 className="text-sm font-medium text-zinc-300 uppercase tracking-wide mb-1">
          Example Sentences
        </h2>
        <EditableField
          fieldName="example_sentences"
          displayValue={card.example_sentences.join("\n")}
          multiline
          ariaLabel="example sentences"
          editingField={editingField}
          fieldDraft={editingField === "example_sentences" ? fieldDraft : examplesDraft}
          onStartEdit={(name, _currentValue) => startEdit(name, examplesDraft)}
          onChangeField={setFieldDraft}
          onBlur={commitEdit}
        />
      </div>

      {/* Audio */}
      {card.audio_url && (
        <div className="border-b border-zinc-800 pb-4 mb-4">
          <h2 className="text-sm font-medium text-zinc-300 uppercase tracking-wide mb-1">
            Audio
          </h2>
          <audio
            controls
            src={card.audio_url}
            className="h-8 w-full"
            aria-label={`Pronunciation audio for ${card.target_word}`}
          />
        </div>
      )}

      {/* Personal Note */}
      <div className="pb-4 mb-4">
        <h2 className="text-sm font-medium text-zinc-300 uppercase tracking-wide mb-1">
          Personal Note
        </h2>
        <EditableField
          fieldName="personal_note"
          displayValue={noteDraft}
          multiline
          ariaLabel="personal note"
          editingField={editingField}
          fieldDraft={editingField === "personal_note" ? fieldDraft : noteDraft}
          onStartEdit={(name, _currentValue) => startEdit(name, noteDraft)}
          onChangeField={setFieldDraft}
          onBlur={commitEdit}
        />
      </div>

      {/* Delete confirmation dialog */}
      <Dialog
        open={state === "confirm-delete" || state === "deleting"}
        onOpenChange={(open) => {
          if (!open && state !== "deleting") setState("viewing")
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete card · This cannot be undone</DialogTitle>
            <DialogDescription className="sr-only">
              Permanently deletes this card from all decks and the practice queue.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setState("viewing")}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setState("deleting")
                deleteCard.mutate()
              }}
              disabled={state === "deleting"}
            >
              {state === "deleting" ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
