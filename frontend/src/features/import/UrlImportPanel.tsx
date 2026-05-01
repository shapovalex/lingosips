/**
 * URL input panel — fetch URL content and extract word candidates.
 */

import { useState } from "react"

interface UrlImportPanelProps {
  onPreviewRequest: (url: string) => void
  isParsing: boolean
  errorMessage?: string | null
}

export function UrlImportPanel({ onPreviewRequest, isParsing, errorMessage }: UrlImportPanelProps) {
  const [url, setUrl] = useState("")

  function handlePreview() {
    if (!url.trim()) return
    onPreviewRequest(url.trim())
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <label htmlFor="url-input" className="text-sm text-zinc-400">
          URL
        </label>
        <input
          id="url-input"
          type="url"
          aria-label="URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handlePreview()}
          placeholder="https://example.com/vocabulary-list"
          className="w-full rounded-lg bg-zinc-900 border border-zinc-700 text-zinc-100 px-3 py-2 text-sm placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {errorMessage && (
        <p className="text-sm text-red-400" role="alert">
          {errorMessage}
        </p>
      )}

      <button
        type="button"
        onClick={handlePreview}
        disabled={isParsing || !url.trim()}
        className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
      >
        {isParsing ? "Fetching..." : "Preview"}
      </button>
    </div>
  )
}
