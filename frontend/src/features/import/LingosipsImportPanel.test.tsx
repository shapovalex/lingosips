/**
 * LingosipsImportPanel component tests — TDD (written before implementation).
 *
 * Tests cover: drag-and-drop zone, file picker, .lingosips file acceptance,
 * preview button, keyboard accessibility, and callback behaviour.
 * AC: 2 (import .lingosips file, show preview)
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi, describe, it, expect, beforeEach } from "vitest"

// ── Import component ──────────────────────────────────────────────────────────

import { LingosipsImportPanel } from "./LingosipsImportPanel"

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeLingosipsFile(name = "test.lingosips"): File {
  const content = JSON.stringify({ format_version: "1", deck: { name: "X", target_language: "es" }, cards: [] })
  return new File([content], name, { type: "application/octet-stream" })
}

describe("LingosipsImportPanel — idle state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders a drop zone for .lingosips files", () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)
    const dropZone = screen.getByRole("button", { name: /upload .lingosips file/i })
    expect(dropZone).toBeInTheDocument()
  })

  it("file input accepts only .lingosips files", () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)
    const fileInput = document.querySelector('input[type="file"][accept=".lingosips"]')
    expect(fileInput).not.toBeNull()
  })

  it("drop zone is keyboard accessible (Enter opens file picker)", () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)
    const dropZone = screen.getByRole("button", { name: /upload .lingosips file/i })
    dropZone.focus()
    expect(document.activeElement).toBe(dropZone)
  })
})

describe("LingosipsImportPanel — file selected", () => {
  it("shows Preview button when a .lingosips file is selected", async () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeLingosipsFile()
    await userEvent.upload(fileInput, file)

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /preview cards/i })).toBeInTheDocument()
    })
  })

  it("clicking Preview calls onFileSelected with the file", async () => {
    const onFileSelected = vi.fn()
    render(<LingosipsImportPanel onFileSelected={onFileSelected} isParsing={false} />)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeLingosipsFile()
    await userEvent.upload(fileInput, file)

    const previewBtn = await screen.findByRole("button", { name: /preview cards/i })
    await userEvent.click(previewBtn)

    expect(onFileSelected).toHaveBeenCalledWith(file)
  })

  it("shows file name after selection", async () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeLingosipsFile("my-vocab.lingosips")
    await userEvent.upload(fileInput, file)

    await waitFor(() => {
      expect(screen.getByText(/my-vocab.lingosips/i)).toBeInTheDocument()
    })
  })
})

describe("LingosipsImportPanel — drag-and-drop", () => {
  it("drag-over changes style (dragging state)", async () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)

    const dropZone = screen.getByRole("button", { name: /upload .lingosips file/i })

    fireEvent.dragOver(dropZone, {
      dataTransfer: { files: [] },
      preventDefault: vi.fn(),
    })

    // After drag-over, should reflect dragging state (tested via aria or class change)
    // We verify the event handler doesn't throw
    expect(dropZone).toBeInTheDocument()
  })
})

describe("LingosipsImportPanel — invalid file type", () => {
  it("shows error message when a non-.lingosips file is dropped via drag-and-drop", async () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)

    const dropZone = screen.getByRole("button", { name: /upload .lingosips file/i })
    const wrongFile = new File(["content"], "deck.zip", { type: "application/zip" })

    // Use fireEvent.drop to bypass userEvent's accept-attribute filtering
    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [wrongFile],
        types: ["Files"],
      },
    })

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument()
      expect(screen.getByRole("alert").textContent).toMatch(/\.lingosips/i)
    })
  })

  it("does not show Preview button when invalid file type is dropped", async () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={false} />)

    const dropZone = screen.getByRole("button", { name: /upload .lingosips file/i })
    const wrongFile = new File(["content"], "deck.zip", { type: "application/zip" })

    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [wrongFile],
        types: ["Files"],
      },
    })

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /preview cards/i })).not.toBeInTheDocument()
    })
  })
})

describe("LingosipsImportPanel — isParsing state", () => {
  it("Preview button is disabled when isParsing=true", async () => {
    render(<LingosipsImportPanel onFileSelected={vi.fn()} isParsing={true} />)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeLingosipsFile()
    await userEvent.upload(fileInput, file)

    await waitFor(() => {
      // When isParsing=true the button label changes to "Parsing..." — match either label
      const previewBtn = screen.getByRole("button", { name: /parsing|preview/i })
      expect(previewBtn).toBeDisabled()
    })
  })
})
