/**
 * DeckExportImport component tests — TDD (written before implementation).
 *
 * State machine: "idle" | "exporting" | "error"
 * AC: 1 (export deck to .lingosips file)
 *
 * NOTE: URL.createObjectURL is not available in jsdom — do NOT test actual file download.
 * Test that fetch() is called with correct URL, state transitions, and error handling.
 */

import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi, describe, it, expect, beforeEach } from "vitest"

// ── Mock stores ────────────────────────────────────────────────────────────────

const mockAddNotification = vi.fn()

vi.mock("@/lib/stores/useAppStore", () => ({
  useAppStore: vi.fn((selector: (s: unknown) => unknown) => {
    const state = {
      addNotification: mockAddNotification,
      pendingNotifications: [],
      activeImportJobId: null,
      setActiveImportJobId: vi.fn(),
    }
    return selector(state)
  }),
}))

// ── Import component AFTER mocks ──────────────────────────────────────────────

import { DeckExportImport } from "./DeckExportImport"

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderComponent(props?: { deckId?: number; deckName?: string }) {
  return render(
    <DeckExportImport deckId={props?.deckId ?? 1} deckName={props?.deckName ?? "Spanish Vocab"} />
  )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("DeckExportImport — idle state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: fetch succeeds with a blob response
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(["fake zip"], { type: "application/zip" })),
    }))
    // URL.createObjectURL / revokeObjectURL are not in jsdom — stub them
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue("blob:fake-url"),
      revokeObjectURL: vi.fn(),
    })
  })

  it("renders Export deck button in idle state", () => {
    renderComponent()
    expect(screen.getByRole("button", { name: /export deck as .lingosips file/i })).toBeInTheDocument()
  })

  it("button has correct aria-label", () => {
    renderComponent()
    const btn = screen.getByRole("button", { name: /export deck as .lingosips file/i })
    expect(btn).toHaveAttribute("aria-label", "Export deck as .lingosips file")
  })

  it("button is focusable (keyboard accessible)", () => {
    renderComponent()
    const btn = screen.getByRole("button", { name: /export deck as .lingosips file/i })
    btn.focus()
    expect(document.activeElement).toBe(btn)
  })
})

describe("DeckExportImport — exporting state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue("blob:fake-url"),
      revokeObjectURL: vi.fn(),
    })
  })

  it("calls fetch with correct export URL on button click", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(["data"], { type: "application/zip" })),
    })
    vi.stubGlobal("fetch", mockFetch)

    renderComponent({ deckId: 42, deckName: "My Deck" })
    const btn = screen.getByRole("button", { name: /export deck/i })
    await userEvent.click(btn)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/decks/42/export")
    })
  })

  it("button is disabled while exporting", async () => {
    // fetch that never resolves → stays in exporting state
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))

    renderComponent()
    const btn = screen.getByRole("button", { name: /export deck/i })
    await userEvent.click(btn)

    await waitFor(() => {
      expect(btn).toBeDisabled()
    })
  })

  it("uses sanitized filename for download (replaces invalid chars with underscore)", async () => {
    // Selectively mock document.createElement — only intercept "a" tag creation
    // to avoid breaking React's DOM setup which also calls createElement("div")
    const originalCreateElement = document.createElement.bind(document)
    let capturedDownload = ""
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      if (tagName === "a") {
        const anchor = originalCreateElement("a")
        Object.defineProperty(anchor, "download", {
          set: (v: string) => { capturedDownload = v },
          get: () => capturedDownload,
          configurable: true,
        })
        return anchor
      }
      return originalCreateElement(tagName)
    })

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(["data"], { type: "application/zip" })),
    }))

    // Deck name with special chars that should be sanitized (: and / are invalid)
    renderComponent({ deckId: 1, deckName: "My Deck: Special/Chars" })
    await userEvent.click(screen.getByRole("button", { name: /export deck/i }))

    await waitFor(() => {
      expect(capturedDownload).toBe("My Deck_ Special_Chars.lingosips")
    })

    vi.restoreAllMocks()
  })

  it("returns to idle state after successful export", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(["data"], { type: "application/zip" })),
    }))

    renderComponent()
    const btn = screen.getByRole("button", { name: /export deck/i })
    await userEvent.click(btn)

    await waitFor(() => {
      const updatedBtn = screen.getByRole("button", { name: /export deck as .lingosips file/i })
      expect(updatedBtn).not.toBeDisabled()
    })
  })
})

describe("DeckExportImport — error state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue("blob:fake-url"),
      revokeObjectURL: vi.fn(),
    })
  })

  it("shows error notification when fetch returns non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }))

    renderComponent()
    const btn = screen.getByRole("button", { name: /export deck/i })
    await userEvent.click(btn)

    await waitFor(() => {
      expect(mockAddNotification).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" })
      )
    })
  })

  it("shows error notification when fetch throws (network error)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")))

    renderComponent()
    const btn = screen.getByRole("button", { name: /export deck/i })
    await userEvent.click(btn)

    await waitFor(() => {
      expect(mockAddNotification).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" })
      )
    })
  })
})
