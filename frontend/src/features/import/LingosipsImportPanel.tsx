/**
 * Drag-and-drop .lingosips import panel.
 * Follows the same pattern as AnkiImportPanel.tsx.
 * State: "idle" | "dragging"
 *
 * AC: 2 — show file picker for .lingosips files.
 */

import React, { useRef, useState } from "react"

interface LingosipsImportPanelProps {
  onFileSelected: (file: File) => void
  isParsing: boolean
}

type PanelState = "idle" | "dragging"

export function LingosipsImportPanel({ onFileSelected, isParsing }: LingosipsImportPanelProps) {
  const [state, setState] = useState<PanelState>("idle")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFile(file: File) {
    if (!file.name.endsWith(".lingosips")) {
      setFileError("Only .lingosips files are accepted. Please select a valid archive.")
      setSelectedFile(null)
      return
    }
    setFileError(null)
    setSelectedFile(file)
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setState("dragging")
  }

  function handleDragLeave() {
    setState("idle")
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setState("idle")
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      fileInputRef.current?.click()
    }
  }

  function handlePreview() {
    if (!selectedFile) return
    onFileSelected(selectedFile)
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <button
        type="button"
        aria-label="Upload .lingosips file"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={handleKeyDown}
        className={[
          "w-full min-h-32 border-2 border-dashed rounded-lg flex flex-col items-center justify-center gap-2",
          "text-zinc-400 cursor-pointer transition-colors",
          state === "dragging"
            ? "border-indigo-500 bg-indigo-500/10 text-indigo-400"
            : "border-zinc-700 hover:border-zinc-500 hover:text-zinc-300",
        ].join(" ")}
      >
        <svg
          aria-hidden="true"
          className="w-10 h-10"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>
        {selectedFile ? (
          <span className="text-sm text-zinc-200">
            {selectedFile.name} ({(selectedFile.size / 1024).toFixed(0)} KB)
          </span>
        ) : (
          <>
            <span className="text-sm font-medium">
              {state === "dragging"
                ? "Drop .lingosips file here"
                : "Drop .lingosips here or click to browse"}
            </span>
            <span className="text-xs">LingoSips deck archive (.lingosips)</span>
          </>
        )}
      </button>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".lingosips"
        className="hidden"
        onChange={handleFileChange}
        aria-hidden="true"
      />

      {fileError && (
        <p role="alert" className="text-sm text-red-400">
          {fileError}
        </p>
      )}

      {selectedFile && (
        <button
          type="button"
          onClick={handlePreview}
          disabled={isParsing}
          className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
        >
          {isParsing ? "Parsing..." : "Preview Cards"}
        </button>
      )}
    </div>
  )
}
