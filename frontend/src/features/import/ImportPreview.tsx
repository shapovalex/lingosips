/**
 * Shared preview component used by all three source types.
 * Shows card list with checkboxes + import button.
 */

import { useState } from "react"

export interface CardPreviewItemData {
  target_word: string
  translation: string | null
  example_sentence: string | null
  has_audio: boolean
  fields_missing: string[]
  selected: boolean
}

export interface ImportPreviewData {
  source_type: string
  total_cards: number
  fields_present: string[]
  fields_missing_summary: Record<string, number>
  cards: CardPreviewItemData[]
}

interface ImportPreviewProps {
  preview: ImportPreviewData
  onConfirm: (selectedCards: CardPreviewItemData[]) => void
  onBack: () => void
  isSubmitting?: boolean
}

export function ImportPreview({ preview, onConfirm, onBack, isSubmitting }: ImportPreviewProps) {
  const [selected, setSelected] = useState<boolean[]>(() =>
    preview.cards.map((c) => c.selected)
  )

  const selectedCards = preview.cards.filter((_, i) => selected[i])
  const allSelected = selected.every(Boolean)

  function toggleCard(index: number) {
    setSelected((prev) => prev.map((v, i) => (i === index ? !v : v)))
  }

  function toggleAll() {
    setSelected((prev) => prev.map(() => !allSelected))
  }

  // Build fields-present/missing summary string
  const presentStr = preview.fields_present.join(", ")
  const missingSummary = Object.entries(preview.fields_missing_summary)
    .map(([field, count]) => `${field} (${count})`)
    .join(", ")

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-4">
        <p className="text-sm font-medium text-zinc-200">
          {preview.total_cards} cards found
        </p>
        {presentStr && (
          <p className="text-xs text-zinc-400 mt-1">Fields present: {presentStr}</p>
        )}
        {missingSummary && (
          <p className="text-xs text-zinc-500 mt-1">Missing: {missingSummary}</p>
        )}
      </div>

      {/* Select all / deselect all */}
      {preview.cards.length > 0 && (
        <button
          type="button"
          onClick={toggleAll}
          className="text-sm text-indigo-400 hover:text-indigo-300 underline"
        >
          {allSelected ? "Deselect all" : "Select all"}
        </button>
      )}

      {/* Card list */}
      <fieldset>
        <legend className="sr-only">Select cards to import</legend>
        <ul role="list" className="space-y-2 max-h-80 overflow-y-auto">
          {preview.cards.map((card, i) => (
            <li
              key={`${card.target_word}-${i}`}
              className="flex items-start gap-3 rounded-lg bg-zinc-900/50 border border-zinc-800 px-3 py-2"
            >
              <input
                type="checkbox"
                checked={selected[i]}
                onChange={() => toggleCard(i)}
                aria-label={`${card.target_word}${card.fields_missing.length ? ` — ${card.fields_missing.join(", ")}` : ""}`}
                className="mt-0.5 h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-indigo-500 focus:ring-indigo-500"
              />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-zinc-100 text-sm">{card.target_word}</span>
                {card.translation && (
                  <span className="ml-2 text-zinc-400 text-sm">{card.translation}</span>
                )}
                {card.fields_missing.length > 0 && (
                  <p className="text-xs text-amber-500 mt-0.5">
                    Missing: {card.fields_missing.join(", ")}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      </fieldset>

      {/* Action buttons */}
      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onBack}
          className="flex-1 py-2 px-4 border border-zinc-700 text-zinc-300 hover:text-zinc-100 hover:border-zinc-500 rounded-lg font-medium transition-colors"
        >
          Back
        </button>
        <button
          type="button"
          onClick={() => onConfirm(selectedCards)}
          disabled={selectedCards.length === 0 || isSubmitting}
          className="flex-1 py-2 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
        >
          {isSubmitting
            ? "Starting..."
            : `Import & Enrich ${selectedCards.length} card${selectedCards.length !== 1 ? "s" : ""}`}
        </button>
      </div>
    </div>
  )
}
