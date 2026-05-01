/**
 * ImportPage — enum-driven state machine for the import flow.
 *
 * States: "idle" | "parsing" | "preview" | "enriching" | "complete" | "error"
 * Sources: "anki" | "text" | "url"
 *
 * AC1: Three source tabs (Anki, Text, URL)
 * AC2: Anki .apkg file preview
 * AC3: Text/TSV and URL preview
 * AC4: Import start — creates job before enrichment
 * AC5: Progress ring in sidebar (via useAppStore.setActiveImportJobId)
 * AC6: SSE progress via useImportProgress
 */

import { useState } from "react"
import { post } from "@/lib/client"
import { useAppStore } from "@/lib/stores/useAppStore"
import { useImportProgress } from "./useImportProgress"
import { AnkiImportPanel } from "./AnkiImportPanel"
import { TextImportPanel } from "./TextImportPanel"
import { UrlImportPanel } from "./UrlImportPanel"
import { ImportPreview, type ImportPreviewData, type CardPreviewItemData } from "./ImportPreview"

// ── State machine type ──────────────────────────────────────────────────��─────

type ImportState = "idle" | "parsing" | "preview" | "enriching" | "complete" | "error"
type ImportSource = "anki" | "text" | "url"

// ── Component ─────────────────────────────────────────────────────────────────

export function ImportPage() {
  const [importState, setImportState] = useState<ImportState>("idle")
  const [activeSource, setActiveSource] = useState<ImportSource>("anki")
  const [preview, setPreview] = useState<ImportPreviewData | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [completedCount, setCompletedCount] = useState<{ enriched: number; unresolved: number } | null>(null)

  const setActiveImportJobId = useAppStore((s) => s.setActiveImportJobId)
  const activeImportJobId = useAppStore((s) => s.activeImportJobId)
  const importProgress = useImportProgress(activeImportJobId)

  // Derive effective state from SSE progress when in enriching phase.
  // Computed during render (no useEffect) to avoid cascading setState calls.
  let effectiveState = importState
  if (importState === "enriching") {
    if (importProgress.status === "complete") effectiveState = "complete"
    else if (importProgress.status === "error") effectiveState = "error"
  }
  // Derive completedCount and errorMessage from SSE progress (no extra state needed)
  const resolvedCompletedCount =
    effectiveState === "complete"
      ? (completedCount ?? { enriched: importProgress.enriched, unresolved: importProgress.unresolved })
      : completedCount
  const resolvedErrorMessage =
    effectiveState === "error" && importState === "enriching"
      ? (importProgress.errorMessage ?? "Enrichment failed")
      : errorMessage

  // ── Handlers ──────────────────────────────────────────────────────────────

  async function handleAnkiPreview(formData: FormData) {
    setImportState("parsing")
    setErrorMessage(null)
    try {
      // Use fetch directly for multipart — post() sends JSON
      const response = await fetch("/import/preview/anki", {
        method: "POST",
        body: formData,
        // DO NOT set Content-Type — browser sets multipart boundary automatically
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.title ?? "Failed to parse Anki file")
      }
      const data = (await response.json()) as ImportPreviewData
      setPreview(data)
      setImportState("preview")
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to parse Anki file")
      setImportState("error")
    }
  }

  async function handleTextPreview(text: string, format: string) {
    setImportState("parsing")
    setErrorMessage(null)
    try {
      const data = await post<ImportPreviewData>("/import/preview/text", { text, format })
      setPreview(data)
      setImportState("preview")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to parse text"
      setErrorMessage(msg)
      setImportState("error")
    }
  }

  async function handleUrlPreview(url: string) {
    setImportState("parsing")
    setErrorMessage(null)
    try {
      const data = await post<ImportPreviewData>("/import/preview/url", { url })
      setPreview(data)
      setImportState("preview")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not fetch URL"
      setErrorMessage(msg)
      setImportState("error")
    }
  }

  async function handleConfirmImport(selectedCards: CardPreviewItemData[]) {
    if (!preview) return
    setImportState("parsing") // briefly re-use parsing skeleton
    try {
      const result = await post<{ job_id: number; card_count: number }>("/import/start", {
        source_type: preview.source_type,
        cards: selectedCards.map((c) => ({
          target_word: c.target_word,
          translation: c.translation,
          example_sentence: c.example_sentence,
        })),
        target_language: "es", // TODO: read from settings (Story 2.4 uses active_target_language)
        enrich: true,
      })
      setActiveImportJobId(result.job_id)
      setImportState("enriching")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start import"
      setErrorMessage(msg)
      setImportState("error")
    }
  }

  function resetToIdle() {
    setImportState("idle")
    setPreview(null)
    setErrorMessage(null)
    setCompletedCount(null)
    // AC6: clear activeImportJobId so progress ring disappears
    setActiveImportJobId(null)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex-1 overflow-y-auto p-6 pb-24 md:pb-6">
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-50">Import Vocabulary</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Import from Anki decks, plain text, or a web URL. AI enriches missing fields in the
            background.
          </p>
        </div>

        {/* State: parsing — skeleton */}
        {effectiveState === "parsing" && (
          <div className="space-y-3 animate-pulse">
            <div className="h-8 bg-zinc-800 rounded-lg w-3/4" />
            <div className="h-32 bg-zinc-800 rounded-lg" />
            <div className="h-8 bg-zinc-800 rounded-lg w-1/2" />
          </div>
        )}

        {/* State: preview */}
        {effectiveState === "preview" && preview && (
          <ImportPreview
            preview={preview}
            onConfirm={handleConfirmImport}
            onBack={resetToIdle}
          />
        )}

        {/* State: enriching */}
        {effectiveState === "enriching" && (
          <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-6 text-center space-y-4">
            <div className="text-zinc-200 font-medium">Enriching cards…</div>
            {importProgress.total > 0 && (
              <>
                <div className="w-full bg-zinc-800 rounded-full h-2">
                  <div
                    className="bg-indigo-500 h-2 rounded-full transition-all"
                    style={{ width: `${Math.round((importProgress.done / importProgress.total) * 100)}%` }}
                  />
                </div>
                <p className="text-sm text-zinc-400">
                  {importProgress.done} / {importProgress.total}
                  {importProgress.currentItem && ` — ${importProgress.currentItem}`}
                </p>
              </>
            )}
            <p className="text-xs text-zinc-500">
              You can navigate away — enrichment continues in the background.
            </p>
          </div>
        )}

        {/* State: complete */}
        {effectiveState === "complete" && resolvedCompletedCount && (
          <div className="rounded-lg bg-zinc-900 border border-green-700/50 p-6 text-center space-y-4">
            <div className="text-green-400 text-lg font-medium">✓ Import Complete</div>
            <p className="text-zinc-300">
              {resolvedCompletedCount.enriched} cards enriched
              {resolvedCompletedCount.unresolved > 0 &&
                ` · ${resolvedCompletedCount.unresolved} fields could not be resolved`}
            </p>
            <button
              type="button"
              onClick={resetToIdle}
              className="py-2 px-6 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors"
            >
              Import more
            </button>
          </div>
        )}

        {/* State: error */}
        {effectiveState === "error" && (
          <div className="rounded-lg bg-zinc-900 border border-red-700/50 p-6 text-center space-y-4">
            <div className="text-red-400 font-medium">Import failed</div>
            {resolvedErrorMessage && <p className="text-sm text-zinc-300">{resolvedErrorMessage}</p>}
            <button
              type="button"
              onClick={resetToIdle}
              className="py-2 px-6 border border-zinc-700 text-zinc-300 hover:text-zinc-100 rounded-lg font-medium transition-colors"
            >
              Try again
            </button>
          </div>
        )}

        {/* State: idle — show source selector tabs */}
        {effectiveState === "idle" && (
          <div className="space-y-4">
            {/* Source tabs */}
            <div role="tablist" aria-label="Import source" className="flex gap-1 bg-zinc-900 rounded-lg p-1">
              {(["anki", "text", "url"] as ImportSource[]).map((src) => (
                <button
                  key={src}
                  role="tab"
                  aria-selected={activeSource === src}
                  onClick={() => setActiveSource(src)}
                  className={[
                    "flex-1 py-1.5 px-3 rounded-md text-sm font-medium transition-colors capitalize",
                    activeSource === src
                      ? "bg-zinc-700 text-zinc-100"
                      : "text-zinc-400 hover:text-zinc-200",
                  ].join(" ")}
                >
                  {src === "anki" ? "Anki" : src === "text" ? "Text" : "URL"}
                </button>
              ))}
            </div>

            {/* Source panel */}
            {activeSource === "anki" && (
              <AnkiImportPanel onPreviewRequest={handleAnkiPreview} isParsing={false} />
            )}
            {activeSource === "text" && (
              <TextImportPanel onPreviewRequest={handleTextPreview} isParsing={false} />
            )}
            {activeSource === "url" && (
              <UrlImportPanel
                onPreviewRequest={handleUrlPreview}
                isParsing={false}
                errorMessage={null}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
