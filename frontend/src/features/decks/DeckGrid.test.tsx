/**
 * DeckGrid component tests — TDD (written before implementation).
 *
 * Tests cover: loading, empty state, deck list render, filter, create, rename, delete,
 *              language switcher, deck card navigation link, aria labels.
 * AC: 1, 2, 3, 4, 6
 *
 * Strategy: mock @/lib/client and @tanstack/react-router; wrap in QueryClientProvider.
 */

import React from "react"
import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest"

// ── Mock client module ────────────────────────────────────────────────────────

vi.mock("@/lib/client", () => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
  put: vi.fn(),
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

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children, to, params }: { children: React.ReactNode; to: string; params?: Record<string, string> }) => {
    const href = params ? to.replace(/\$(\w+)/g, (_, k) => params[k] ?? k) : to
    return <a href={href}>{children}</a>
  },
}))

// ── Imports after mocks ───────────────────────────────────────────────────────

import { get, post, patch, del, put, ApiError } from "@/lib/client"
import { useAppStore } from "@/lib/stores/useAppStore"
import { DeckGrid } from "./DeckGrid"

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_SETTINGS = {
  id: 1,
  native_language: "en",
  active_target_language: "es",
  target_languages: '["es","fr"]',
  onboarding_completed: true,
  auto_generate_audio: true,
  auto_generate_images: false,
  default_practice_mode: "self_assess",
  cards_per_session: 20,
}

const MOCK_DECK: {
  id: number
  name: string
  target_language: string
  card_count: number
  due_card_count: number
  created_at: string
  updated_at: string
} = {
  id: 1,
  name: "Spanish Vocab",
  target_language: "es",
  card_count: 5,
  due_card_count: 2,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
}

const MOCK_DECK_2 = {
  id: 2,
  name: "Travel Phrases",
  target_language: "es",
  card_count: 3,
  due_card_count: 0,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
}

// ── Test setup ────────────────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

function renderWithQueryClient(ui: React.ReactElement, queryClient?: QueryClient) {
  const qc = queryClient ?? makeQueryClient()
  return {
    ...render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>),
    queryClient: qc,
  }
}

describe("DeckGrid", () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = makeQueryClient()
    vi.clearAllMocks()
    // Reset Zustand store
    useAppStore.setState({ pendingNotifications: [] })
  })

  afterEach(() => {
    queryClient.clear()
  })

  // ── Loading state ─────────────────────────────────────────────────────────

  it("shows loading skeleton while fetching settings", async () => {
    // Settings query is pending — never resolves during this test
    vi.mocked(get).mockImplementation(() => new Promise(() => {}))

    renderWithQueryClient(<DeckGrid />, queryClient)

    // There should be skeleton elements present
    const skeletons = document.querySelectorAll("[data-slot='skeleton']")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  // ── Empty state ───────────────────────────────────────────────────────────

  it("renders empty state when no decks exist", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await waitFor(() => {
      expect(screen.getByText(/no decks/i)).toBeInTheDocument()
    })
  })

  // ── Deck list rendering ───────────────────────────────────────────────────

  it("renders deck list with name, card count, due count, language badge", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")
    expect(screen.getByText(/5 cards/i)).toBeInTheDocument()
    // Language badge (ES) will appear at least once (multiple = badge + select option)
    const esBadges = screen.getAllByText("ES")
    expect(esBadges.length).toBeGreaterThan(0)
  })

  it("renders due count badge with accessible aria-label", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")
    const dueBadge = screen.getByRole("generic", { name: /2 cards due for review/i })
    expect(dueBadge).toBeInTheDocument()
  })

  it("deck card has link to /decks/$deckId route", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")
    const link = screen.getByRole("link", { name: /Spanish Vocab/i })
    expect(link).toHaveAttribute("href", expect.stringContaining("1"))
  })

  // ── Client-side filter ────────────────────────────────────────────────────

  it("filters decks by name input (client-side)", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK, MOCK_DECK_2])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")
    await screen.findByText("Travel Phrases")

    const filterInput = screen.getByRole("textbox", { name: /filter decks by name/i })
    await userEvent.type(filterInput, "Spanish")

    await waitFor(() => {
      expect(screen.getByText("Spanish Vocab")).toBeInTheDocument()
      expect(screen.queryByText("Travel Phrases")).not.toBeInTheDocument()
    })
  })

  // ── Create deck ───────────────────────────────────────────────────────────

  it("create new deck form submits POST /decks and adds to list", async () => {
    const newDeck = { ...MOCK_DECK, id: 99, name: "New Test Deck", card_count: 0, due_card_count: 0 }
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([])
      return Promise.reject(new Error("unexpected"))
    })
    vi.mocked(post).mockResolvedValue(newDeck)

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText(/no decks/i)

    const newDeckBtn = screen.getByRole("button", { name: /new deck/i })
    await userEvent.click(newDeckBtn)

    const deckNameInput = screen.getByRole("textbox", { name: /new deck name/i })
    await userEvent.type(deckNameInput, "New Test Deck")

    const createBtn = screen.getByRole("button", { name: /^create$/i })
    await userEvent.click(createBtn)

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/decks", expect.objectContaining({ name: "New Test Deck" }))
    })
  })

  it("create deck with duplicate name shows error notification", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })
    vi.mocked(post).mockRejectedValue(
      new ApiError(409, "/errors/deck-name-conflict", "Deck name already exists", "...")
    )

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")
    const newDeckBtn = screen.getByRole("button", { name: /new deck/i })
    await userEvent.click(newDeckBtn)

    const deckNameInput = screen.getByRole("textbox", { name: /new deck name/i })
    await userEvent.type(deckNameInput, "Spanish Vocab")

    const createBtn = screen.getByRole("button", { name: /^create$/i })
    await userEvent.click(createBtn)

    await waitFor(() => {
      const notifications = useAppStore.getState().pendingNotifications
      expect(notifications.length).toBeGreaterThan(0)
      expect(notifications[0].type).toBe("error")
    })
  })

  it("cancel create deck form hides the form", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)
    await screen.findByText(/no decks/i)

    const newDeckBtn = screen.getByRole("button", { name: /new deck/i })
    await userEvent.click(newDeckBtn)

    expect(screen.getByRole("textbox", { name: /new deck name/i })).toBeInTheDocument()

    const cancelBtn = screen.getByRole("button", { name: /cancel/i })
    await userEvent.click(cancelBtn)

    await waitFor(() => {
      expect(screen.queryByRole("textbox", { name: /new deck name/i })).not.toBeInTheDocument()
    })
  })

  // ── Rename deck ───────────────────────────────────────────────────────────

  it("rename inline edit calls PATCH /decks/{id} exactly once (no double-call on Enter)", async () => {
    const renamedDeck = { ...MOCK_DECK, name: "Renamed Deck" }
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })
    vi.mocked(patch).mockResolvedValue(renamedDeck)

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")

    const renameBtn = screen.getByRole("button", { name: /rename Spanish Vocab/i })
    await userEvent.click(renameBtn)

    const renameInput = screen.getByDisplayValue("Spanish Vocab")
    await userEvent.clear(renameInput)
    await userEvent.type(renameInput, "Renamed Deck")
    fireEvent.keyDown(renameInput, { key: "Enter" })

    await waitFor(() => {
      expect(patch).toHaveBeenCalledWith(`/decks/${MOCK_DECK.id}`, { name: "Renamed Deck" })
      // Must be called exactly once — the unmount-triggered blur must not fire a second call
      expect(patch).toHaveBeenCalledTimes(1)
    })
  })

  it("pressing Escape on rename input cancels without saving (empty draft)", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")

    const renameBtn = screen.getByRole("button", { name: /rename Spanish Vocab/i })
    await userEvent.click(renameBtn)

    const renameInput = screen.getByDisplayValue("Spanish Vocab")
    fireEvent.keyDown(renameInput, { key: "Escape" })

    await waitFor(() => {
      expect(screen.getByText("Spanish Vocab")).toBeInTheDocument()
      expect(patch).not.toHaveBeenCalled()
    })
  })

  it("pressing Escape after typing a new name discards without saving", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")

    const renameBtn = screen.getByRole("button", { name: /rename Spanish Vocab/i })
    await userEvent.click(renameBtn)

    const renameInput = screen.getByDisplayValue("Spanish Vocab")
    await userEvent.clear(renameInput)
    await userEvent.type(renameInput, "Partially Typed Name")
    // Press Escape to cancel — blur fires on unmount but must NOT call PATCH
    fireEvent.keyDown(renameInput, { key: "Escape" })

    await waitFor(() => {
      expect(patch).not.toHaveBeenCalled()
    })
  })

  // ── Delete deck ───────────────────────────────────────────────────────────

  it("delete shows confirmation dialog then calls DELETE /decks/{id}", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })
    vi.mocked(del).mockResolvedValue(undefined)

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")

    const deleteBtn = screen.getByRole("button", { name: /delete Spanish Vocab/i })
    await userEvent.click(deleteBtn)

    // Dialog should appear
    await screen.findByRole("dialog")

    const confirmDeleteBtn = screen.getByRole("button", { name: /^delete$/i })
    await userEvent.click(confirmDeleteBtn)

    await waitFor(() => {
      expect(del).toHaveBeenCalledWith(`/decks/${MOCK_DECK.id}`)
    })
  })

  it("delete cancel does not call DELETE", async () => {
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")

    const deleteBtn = screen.getByRole("button", { name: /delete Spanish Vocab/i })
    await userEvent.click(deleteBtn)

    await screen.findByRole("dialog")

    const cancelBtn = screen.getByRole("button", { name: /cancel/i })
    await userEvent.click(cancelBtn)

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })
    expect(del).not.toHaveBeenCalled()
  })

  // ── Language switcher ─────────────────────────────────────────────────────

  it("language switcher calls PUT /settings with new active_target_language", async () => {
    const settingsFr = { ...MOCK_SETTINGS, active_target_language: "fr" }
    vi.mocked(get).mockImplementation((path: string) => {
      if (path === "/settings") return Promise.resolve(MOCK_SETTINGS)
      if (path.startsWith("/decks")) return Promise.resolve([MOCK_DECK])
      return Promise.reject(new Error("unexpected"))
    })
    vi.mocked(put).mockResolvedValue(settingsFr)

    renderWithQueryClient(<DeckGrid />, queryClient)

    await screen.findByText("Spanish Vocab")

    const langSelector = screen.getByRole("combobox", { name: /active target language/i })
    await userEvent.selectOptions(langSelector, "fr")

    await waitFor(() => {
      expect(put).toHaveBeenCalledWith("/settings", { active_target_language: "fr" })
    })
  })
})
