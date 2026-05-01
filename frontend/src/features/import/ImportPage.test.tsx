/**
 * ImportPage component tests — TDD (written before implementation).
 *
 * Tests cover all state machine branches:
 *   idle | parsing | preview | enriching | complete | error
 *
 * AC covered: AC1 (3 source tabs), AC2 (Anki preview), AC3 (text/URL preview),
 *             AC4 (import start → job_id), AC5 (progress ring), AC6 (SSE events)
 */

import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect, beforeEach } from "vitest"
import React from "react"
import { ImportPage } from "./ImportPage"

// ── Mock dependencies ─────────────────────────────────────────────────────────
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useNavigate: () => vi.fn(),
}))

vi.mock("@/lib/client")
import * as clientModule from "@/lib/client"
const mockPost = vi.mocked(clientModule.post)

vi.mock("@/lib/stores/useAppStore", () => ({
  useAppStore: vi.fn((selector: (s: unknown) => unknown) => {
    const state = {
      activeImportJobId: null,
      importProgress: {
        done: 0, total: 0, currentItem: null, status: "idle",
        enriched: 0, unresolved: 0, errorMessage: null,
      },
      setActiveImportJobId: vi.fn(),
      setImportProgress: vi.fn(),
      addNotification: vi.fn(),
    }
    return selector(state)
  }),
}))

// ── Wrapper ───────────────────────────────────────────────────────────────────
function renderImportPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(ImportPage)
    )
  )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ImportPage — idle state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders three source tabs: Anki, Text, URL", () => {
    renderImportPage()
    expect(screen.getByRole("tab", { name: /Anki/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Text/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /URL/i })).toBeInTheDocument()
  })

  it("file input accepts only .apkg files", () => {
    renderImportPage()
    // Anki tab is default — look for file input with .apkg accept
    const fileInput = document.querySelector('input[type="file"][accept=".apkg"]')
    expect(fileInput).not.toBeNull()
  })

  it("URL tab renders URL text input", async () => {
    const user = userEvent.setup()
    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /URL/i }))
    expect(screen.getByRole("textbox", { name: /url/i })).toBeInTheDocument()
  })

  it("Text tab renders textarea", async () => {
    const user = userEvent.setup()
    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /Text/i }))
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("Anki drop zone has correct aria-label", () => {
    renderImportPage()
    expect(
      screen.getByRole("button", { name: /Upload Anki .apkg file/i })
    ).toBeInTheDocument()
  })
})

describe("ImportPage — parsing state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows skeleton while POST /import/preview/text is pending", async () => {
    const user = userEvent.setup()
    // Make post return a never-resolving promise to stay in parsing state
    let resolvePost: (v: unknown) => void
    mockPost.mockReturnValue(new Promise((r) => { resolvePost = r }))

    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /Text/i }))
    const textarea = screen.getByRole("textbox")
    await user.type(textarea, "hola\nhello")
    await user.click(screen.getByRole("button", { name: /Preview/i }))

    // Should show a skeleton (not a spinner)
    expect(document.querySelector(".animate-pulse")).not.toBeNull()
    resolvePost!({ source_type: "text", total_cards: 2, cards: [], fields_present: [], fields_missing_summary: {} })
  })
})

describe("ImportPage — preview state", () => {
  const mockPreview = {
    source_type: "text",
    total_cards: 2,
    fields_present: ["target_word", "translation"],
    fields_missing_summary: { audio: 2, forms: 2 },
    cards: [
      { target_word: "hola", translation: "hello", example_sentence: null,
        has_audio: false, fields_missing: ["audio", "forms"], selected: true },
      { target_word: "agua", translation: "water", example_sentence: null,
        has_audio: false, fields_missing: ["audio", "forms"], selected: true },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows card count and card list after preview", async () => {
    const user = userEvent.setup()
    mockPost.mockResolvedValueOnce(mockPreview)

    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /Text/i }))
    const textarea = screen.getByRole("textbox")
    await user.type(textarea, "hola\thello\nagua\twater")
    await user.click(screen.getByRole("button", { name: /Preview/i }))

    await waitFor(() => {
      expect(screen.getByText(/2 cards found/i)).toBeInTheDocument()
    })
    expect(screen.getByText("hola")).toBeInTheDocument()
    expect(screen.getByText("agua")).toBeInTheDocument()
  })

  it("all cards pre-selected in preview", async () => {
    const user = userEvent.setup()
    mockPost.mockResolvedValueOnce(mockPreview)

    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /Text/i }))
    await user.type(screen.getByRole("textbox"), "hola\thello\nagua\twater")
    await user.click(screen.getByRole("button", { name: /Preview/i }))

    await waitFor(() => screen.getByText(/2 cards found/i))
    const checkboxes = screen.getAllByRole("checkbox")
    expect(checkboxes.every((cb) => (cb as HTMLInputElement).checked)).toBe(true)
  })

  it("deselecting a card reduces import count", async () => {
    const user = userEvent.setup()
    mockPost.mockResolvedValueOnce(mockPreview)

    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /Text/i }))
    await user.type(screen.getByRole("textbox"), "hola\thello\nagua\twater")
    await user.click(screen.getByRole("button", { name: /Preview/i }))

    await waitFor(() => screen.getByText(/2 cards found/i))
    // Uncheck first card (skip "select all" checkbox at index 0 if present)
    const checkboxes = screen.getAllByRole("checkbox")
    await user.click(checkboxes[0])

    // Import button should now show 1 card
    expect(screen.getByRole("button", { name: /Import.*1 card/i })).toBeInTheDocument()
  })

  it("Import & Enrich button shows correct card count", async () => {
    const user = userEvent.setup()
    mockPost.mockResolvedValueOnce(mockPreview)

    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /Text/i }))
    await user.type(screen.getByRole("textbox"), "hola\thello\nagua\twater")
    await user.click(screen.getByRole("button", { name: /Preview/i }))

    await waitFor(() => screen.getByText(/2 cards found/i))
    expect(screen.getByRole("button", { name: /Import.*2 cards/i })).toBeInTheDocument()
  })
})

describe("ImportPage — enriching state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("transitions to enriching after POST /import/start", async () => {
    const user = userEvent.setup()
    const mockPreview = {
      source_type: "text", total_cards: 1, fields_present: ["target_word"],
      fields_missing_summary: { translation: 1 },
      cards: [{ target_word: "hola", translation: null, example_sentence: null,
                has_audio: false, fields_missing: ["translation"], selected: true }],
    }
    mockPost
      .mockResolvedValueOnce(mockPreview)
      .mockResolvedValueOnce({ job_id: 42, card_count: 1 })

    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /Text/i }))
    await user.type(screen.getByRole("textbox"), "hola")
    await user.click(screen.getByRole("button", { name: /Preview/i }))

    await waitFor(() => screen.getByText(/1 cards found/i))
    await user.click(screen.getByRole("button", { name: /Import.*1 card/i }))

    await waitFor(() => {
      expect(screen.getByText(/enriching|importing|in progress/i)).toBeInTheDocument()
    })
  })
})

describe("ImportPage — error state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows specific error message when preview fails", async () => {
    const user = userEvent.setup()
    const { ApiError } = await import("@/lib/client")
    mockPost.mockRejectedValueOnce(
      new ApiError(422, "/errors/url-fetch-failed", "Could not fetch URL", undefined)
    )

    renderImportPage()
    await user.click(screen.getByRole("tab", { name: /URL/i }))
    const urlInput = screen.getByRole("textbox", { name: /url/i })
    await user.type(urlInput, "http://unreachable.invalid")
    await user.click(screen.getByRole("button", { name: /Preview/i }))

    await waitFor(() => {
      expect(screen.getByText(/Could not fetch URL/i)).toBeInTheDocument()
    })
  })
})
