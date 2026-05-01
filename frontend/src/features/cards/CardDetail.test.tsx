/**
 * CardDetail component tests — TDD (written before implementation).
 *
 * Tests cover: loading, viewing, error, inline edit (translation + note), delete confirm, cancel.
 * AC: 1–5
 *
 * Strategy: mock @/lib/client (get, patch, del) and @tanstack/react-router.
 * Component receives cardId as a prop (route extracts and converts it).
 */

import React from "react"
import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest"

// ── Mock client module ────────────────────────────────────────────────────────

vi.mock("@/lib/client", () => ({
  get: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    type: string
    title: string
    detail?: string
    constructor(status: number, type: string, title: string, detail?: string) {
      super(title)
      this.name = "ApiError"
      this.status = status
      this.type = type
      this.title = title
      this.detail = detail
    }
  },
}))

// ── Mock TanStack Router ──────────────────────────────────────────────────────

const mockNavigate = vi.fn()
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}))

// ── Import after mocks are set up ─────────────────────────────────────────────

import { get, patch, del } from "@/lib/client"
import { useAppStore } from "@/lib/stores/useAppStore"
import { CardDetail } from "./CardDetail"

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_CARD = {
  id: 1,
  target_word: "melancólico",
  translation: "melancholic",
  forms: { gender: "masculine", article: "el", plural: "melancólicos", conjugations: {} },
  example_sentences: ["Tenía un aire melancólico.", "Era un día melancólico."],
  audio_url: "/cards/1/audio",
  personal_note: null,
  image_url: null,
  image_skipped: false,
  card_type: "word",
  deck_id: null,
  target_language: "es",
  fsrs_state: "New",
  due: "2026-05-01T00:00:00Z",
  stability: 0,
  difficulty: 0,
  reps: 0,
  lapses: 0,
  last_review: null,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
}

// ── Render helper ─────────────────────────────────────────────────────────────

let queryClient: QueryClient

function renderDetail(cardId: number) {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <CardDetail cardId={cardId} />
    </QueryClientProvider>
  )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("CardDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient?.clear()
  })

  // ── Loading state ─────────────────────────────────────────────────────────

  it("shows loading indicator while fetching (AC1)", async () => {
    // never-resolving promise keeps component in loading state
    vi.mocked(get).mockReturnValue(new Promise(() => {}))
    renderDetail(1)
    // Loading skeleton or text should be visible
    await waitFor(() => {
      const loadingEl =
        document.querySelector(".animate-pulse") ?? screen.queryByText(/loading/i)
      expect(loadingEl).not.toBeNull()
    })
  })

  // ── Viewing state ─────────────────────────────────────────────────────────

  it("renders all card fields when loaded (AC1)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    renderDetail(1)

    expect(await screen.findByText("melancólico")).toBeInTheDocument()
    expect(await screen.findByText("melancholic")).toBeInTheDocument()
    // FSRS state "New" → "Not yet practiced"
    expect(await screen.findByText("Not yet practiced")).toBeInTheDocument()
  })

  it("renders audio player when audio_url is present (AC1)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    renderDetail(1)

    await screen.findByText("melancólico")
    const audio = document.querySelector("audio")
    expect(audio).not.toBeNull()
    expect(audio?.getAttribute("src")).toBe("/cards/1/audio")
  })

  // ── Error state ──────────────────────────────────────────────────────────

  it("shows error message on 404 (AC1)", async () => {
    const { ApiError } = await import("@/lib/client")
    vi.mocked(get).mockRejectedValue(
      new ApiError(404, "/errors/card-not-found", "Card not found", "Card 1 does not exist")
    )
    renderDetail(1)

    await waitFor(() => {
      expect(screen.getByText(/card not found/i)).toBeInTheDocument()
    })
  })

  // ── Inline edit — translation ─────────────────────────────────────────────

  it("shows input on translation click and calls patch on blur (AC2)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    vi.mocked(patch).mockResolvedValue({ ...MOCK_CARD, translation: "gloomy" })
    renderDetail(1)

    // Wait for card to load
    const translationEl = await screen.findByText("melancholic")

    // Click to edit
    await userEvent.click(translationEl)

    // Input should appear with aria-label
    const input = screen.getByRole("textbox", { name: /edit translation/i })
    expect(input).toBeInTheDocument()
    expect((input as HTMLInputElement).value).toBe("melancholic")

    // Clear and type new value
    await userEvent.clear(input)
    await userEvent.type(input, "gloomy")

    // Blur triggers patch
    fireEvent.blur(input)

    await waitFor(() => {
      expect(vi.mocked(patch)).toHaveBeenCalledWith("/cards/1", { translation: "gloomy" })
    })
  })

  // ── Inline edit — personal note ───────────────────────────────────────────

  it("adds personal note on click and calls patch on blur (AC3)", async () => {
    vi.mocked(get).mockResolvedValue({ ...MOCK_CARD, personal_note: null })
    vi.mocked(patch).mockResolvedValue({ ...MOCK_CARD, personal_note: "my personal note" })
    renderDetail(1)

    await screen.findByText("melancólico")

    // Find note area — should show "Click to add..." placeholder
    const noteArea = screen.getByRole("button", { name: /personal note/i })
    await userEvent.click(noteArea)

    // Textarea should appear
    const textarea = screen.getByRole("textbox", { name: /edit personal note/i })
    expect(textarea).toBeInTheDocument()

    await userEvent.type(textarea, "my personal note")
    fireEvent.blur(textarea)

    await waitFor(() => {
      expect(vi.mocked(patch)).toHaveBeenCalledWith("/cards/1", {
        personal_note: "my personal note",
      })
    })
  })

  // ── Delete flow ───────────────────────────────────────────────────────────

  it("shows delete confirmation dialog on Delete button click (AC4)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    renderDetail(1)

    await screen.findByText("melancólico")

    const deleteBtn = screen.getByRole("button", { name: /delete card/i })
    await userEvent.click(deleteBtn)

    // Dialog should appear with exact text
    await waitFor(() => {
      expect(
        screen.getByText(/delete card · this cannot be undone/i)
      ).toBeInTheDocument()
    })
  })

  it("calls del and navigates home on delete confirm (AC5)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    vi.mocked(del).mockResolvedValue(undefined)
    renderDetail(1)

    await screen.findByText("melancólico")

    // Click delete
    await userEvent.click(screen.getByRole("button", { name: /delete card/i }))

    // Confirm in dialog
    await waitFor(() => {
      expect(screen.getByText(/delete card · this cannot be undone/i)).toBeInTheDocument()
    })

    const confirmBtn = screen.getByRole("button", { name: /^delete$/i })
    await userEvent.click(confirmBtn)

    await waitFor(() => {
      expect(vi.mocked(del)).toHaveBeenCalledWith("/cards/1")
    })

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: "/" })
    })
  })

  it("does not call del when cancel is clicked (AC4)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    renderDetail(1)

    await screen.findByText("melancólico")

    // Open dialog
    await userEvent.click(screen.getByRole("button", { name: /delete card/i }))

    await waitFor(() => {
      expect(screen.getByText(/delete card · this cannot be undone/i)).toBeInTheDocument()
    })

    // Cancel
    const cancelBtn = screen.getByRole("button", { name: /cancel/i })
    await userEvent.click(cancelBtn)

    expect(vi.mocked(del)).not.toHaveBeenCalled()
  })

  // ── Aria attributes ───────────────────────────────────────────────────────

  it("delete button has aria-label indicating destructive action (AC4)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    renderDetail(1)

    await screen.findByText("melancólico")

    const deleteBtn = screen.getByRole("button", { name: /delete card/i })
    expect(deleteBtn).toBeInTheDocument()
  })

  it("edit fields have aria-labels per field name (AC2)", async () => {
    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    renderDetail(1)

    await screen.findByText("melancólico")

    // Translation field shows in view mode with aria-label
    const translationField = screen.getByRole("button", { name: /translation/i })
    expect(translationField).toBeInTheDocument()
  })

  // ── PATCH onError — notification path (T10.4) ─────────────────────────────

  it("shows error notification when patch fails (T10.4)", async () => {
    // Reset store notifications before test
    useAppStore.setState({ pendingNotifications: [] })

    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    const { ApiError } = await import("@/lib/client")
    vi.mocked(patch).mockRejectedValue(
      new ApiError(500, "/errors/server", "Server error", "Failed to save")
    )
    renderDetail(1)

    // Wait for card to load
    await screen.findByText("melancólico")

    // Click translation to enter edit mode
    const translationEl = screen.getByRole("button", { name: /translation/i })
    await userEvent.click(translationEl)

    // Blur to trigger patch
    const input = screen.getByRole("textbox", { name: /edit translation/i })
    fireEvent.blur(input)

    // Notification should be added to the store
    await waitFor(() => {
      const { pendingNotifications } = useAppStore.getState()
      expect(pendingNotifications.length).toBeGreaterThan(0)
      expect(pendingNotifications[pendingNotifications.length - 1].type).toBe("error")
    })
  })

  // ── DELETE onError — state reset + notification (T10.5) ──────────────────

  it("resets state and shows notification when delete fails (T10.5)", async () => {
    // Reset store notifications before test
    useAppStore.setState({ pendingNotifications: [] })

    vi.mocked(get).mockResolvedValue(MOCK_CARD)
    const { ApiError } = await import("@/lib/client")
    vi.mocked(del).mockRejectedValue(
      new ApiError(500, "/errors/server", "Server error", "Delete failed")
    )
    renderDetail(1)

    await screen.findByText("melancólico")

    // Open delete dialog
    await userEvent.click(screen.getByRole("button", { name: /delete card/i }))
    await waitFor(() => {
      expect(screen.getByText(/delete card · this cannot be undone/i)).toBeInTheDocument()
    })

    // Click confirm delete (will fail)
    const confirmBtn = screen.getByRole("button", { name: /^delete$/i })
    await userEvent.click(confirmBtn)

    // Error notification should be added
    await waitFor(() => {
      const { pendingNotifications } = useAppStore.getState()
      expect(pendingNotifications.length).toBeGreaterThan(0)
      expect(pendingNotifications[pendingNotifications.length - 1].type).toBe("error")
    })

    // Dialog should close (state reset to "viewing")
    await waitFor(() => {
      expect(
        screen.queryByText(/delete card · this cannot be undone/i)
      ).not.toBeInTheDocument()
    })
  })
})
