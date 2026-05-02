/**
 * DeckExportImport — export a deck as a .lingosips file.
 *
 * State machine: "idle" | "exporting" | "error"
 * AC: 1 (export deck to .lingosips file)
 *
 * NOTE: Uses raw fetch() (NOT client.ts) because the response is a binary blob,
 * not JSON. client.ts assumes JSON responses.
 */

import { useState } from "react"
import { useAppStore } from "@/lib/stores/useAppStore"

type ExportState = "idle" | "exporting" | "error"

interface DeckExportImportProps {
  deckId: number
  deckName: string
}

export function DeckExportImport({ deckId, deckName }: DeckExportImportProps) {
  const [state, setState] = useState<ExportState>("idle")
  const addNotification = useAppStore((s) => s.addNotification)

  async function handleExport() {
    setState("exporting")
    try {
      const response = await fetch(`/decks/${deckId}/export`)
      if (!response.ok) {
        throw new Error(`Export failed: ${response.status}`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      // Sanitize filename: mirror backend re.sub(r"[^\w\-. ]", "_", deck_name)
      const safeName = deckName.replace(/[^\w\-. ]/g, "_").trim()
      a.download = `${safeName}.lingosips`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setState("idle")
    } catch {
      setState("error")
      addNotification({ type: "error", message: "Export failed — please try again" })
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        aria-label="Export deck as .lingosips file"
        onClick={handleExport}
        disabled={state === "exporting"}
        className={[
          "py-2 px-4 rounded-lg font-medium text-sm transition-colors",
          state === "exporting"
            ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
            : "bg-indigo-600 hover:bg-indigo-500 text-white",
        ].join(" ")}
      >
        {state === "exporting" ? "Exporting…" : "Export deck"}
      </button>
      {state === "error" && (
        <span className="text-sm text-red-400" role="alert">
          Export failed — please try again
        </span>
      )}
    </div>
  )
}
