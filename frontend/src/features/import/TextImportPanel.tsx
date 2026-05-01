/**
 * Text/TSV paste or file upload panel.
 */

import React, { useState } from "react"

interface TextImportPanelProps {
  onPreviewRequest: (text: string, format: string) => void
  isParsing: boolean
}

export function TextImportPanel({ onPreviewRequest, isParsing }: TextImportPanelProps) {
  const [text, setText] = useState("")
  const [format, setFormat] = useState("auto")

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const content = ev.target?.result as string
      if (content) setText(content)
    }
    reader.readAsText(file)
  }

  return (
    <div className="space-y-4">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"Paste words one per line, or word\ttranslation TSV"}
        rows={8}
        className="w-full rounded-lg bg-zinc-900 border border-zinc-700 text-zinc-100 px-3 py-2 text-sm placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y"
      />

      <div className="flex items-center gap-3">
        <label className="text-xs text-zinc-400 shrink-0">Format:</label>
        <select
          value={format}
          onChange={(e) => setFormat(e.target.value)}
          className="text-sm bg-zinc-900 border border-zinc-700 text-zinc-100 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="auto">Auto-detect</option>
          <option value="plain">Plain text (one word per line)</option>
          <option value="tsv">TSV (word ⇥ translation)</option>
        </select>

        <span className="text-xs text-zinc-500 ml-auto">
          or{" "}
          <label className="underline cursor-pointer text-zinc-400 hover:text-zinc-200">
            choose file
            <input
              type="file"
              accept=".txt,.tsv,.csv"
              className="hidden"
              onChange={handleFileChange}
            />
          </label>
        </span>
      </div>

      {text && (
        <p className="text-xs text-zinc-500">{text.length} characters</p>
      )}

      <button
        type="button"
        onClick={() => onPreviewRequest(text, format)}
        disabled={isParsing || !text.trim()}
        className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
      >
        {isParsing ? "Parsing..." : "Preview"}
      </button>
    </div>
  )
}
