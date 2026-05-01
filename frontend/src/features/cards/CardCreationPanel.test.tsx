/**
 * CardCreationPanel component tests — TDD (written before implementation).
 *
 * Tests cover all 5 state machine branches:
 *   idle | loading | populated | saving | error
 *
 * Strategy: mock useCardStream entirely — component tests focus on render/interaction,
 * not streaming logic (that's covered in useCardStream.test.ts).
 *
 * AC covered: AC1 (autofocus, aria-label), AC2 (skeletons, disabled input),
 *             AC3 (field slots, aria-live), AC4 (save/discard), AC5 (error),
 *             AC6 (motion-safe), AC7 (all state branches + keyboard + aria)
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect, beforeEach } from "vitest"
import React from "react"
import { CardCreationPanel } from "./CardCreationPanel"

// ── Mock TanStack Router ─────────────────────────────────────────────────────
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useNavigate: () => vi.fn(),
}))

// ── Mock useCardStream ───────────────────────────────────────────────────────
vi.mock("./useCardStream")
import { useCardStream } from "./useCardStream"
const mockUseCardStream = vi.mocked(useCardStream)

// ── Default mock return — idle state ────────────────────────────────────────
const mockStartStream = vi.fn()
const mockSaveCard = vi.fn()
const mockDiscard = vi.fn()
const mockReset = vi.fn()

function mockHookIdle() {
  mockUseCardStream.mockReturnValue({
    state: "idle",
    fields: {},
    errorMessage: null,
    startStream: mockStartStream,
    saveCard: mockSaveCard,
    discard: mockDiscard,
    reset: mockReset,
  })
}

// ── Wrapper ──────────────────────────────────────────────────────────────────
function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(CardCreationPanel)
    )
  )
}

// ── Tests ────────────────────────────────────────────────────────────────────
describe("CardCreationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHookIdle()
  })

  // ── Idle state (AC1) ───────────────────────────────────────────────────────

  it("input is visible in idle state with correct aria-label (AC1)", () => {
    renderPanel()
    const input = screen.getByRole("textbox", { name: /new card — type a word or phrase/i })
    expect(input).toBeInTheDocument()
  })

  it("input has aria-label exactly 'New card — type a word or phrase' (AC1)", () => {
    renderPanel()
    const input = screen.getByLabelText("New card — type a word or phrase")
    expect(input).toBeInTheDocument()
  })

  it("no skeletons visible in idle state", () => {
    renderPanel()
    // Skeletons only appear in loading state — shadcn/ui Skeleton uses animate-pulse
    const skeletons = document.querySelectorAll(".animate-pulse")
    expect(skeletons).toHaveLength(0)
  })

  it("aria-live regions are always in the DOM for screen reader registration (AC3)", () => {
    // Even in idle state the 4 field slot aria-live regions must be in the DOM
    // so screen readers register them before streaming begins (sr-only container)
    renderPanel()
    const liveRegions = document.querySelectorAll('[aria-live="polite"]')
    expect(liveRegions.length).toBeGreaterThanOrEqual(4)
  })

  it("no Save/Discard action row in idle state", () => {
    renderPanel()
    expect(screen.queryByRole("button", { name: /save card/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /discard/i })).not.toBeInTheDocument()
  })

  it("no error message in idle state", () => {
    renderPanel()
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument()
  })

  it("input is enabled in idle state", () => {
    renderPanel()
    const input = screen.getByRole("textbox", { name: /new card/i })
    expect(input).not.toBeDisabled()
  })

  // ── Loading state (AC2) ────────────────────────────────────────────────────

  it("shows 4 skeleton placeholders in loading state (AC2)", () => {
    mockUseCardStream.mockReturnValue({
      state: "loading",
      fields: {},
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    // 4 skeletons — one per field slot (translation, forms, example, audio)
    const skeletons = document.querySelectorAll(".animate-pulse")
    expect(skeletons.length).toBeGreaterThanOrEqual(4)
  })

  it("input is disabled in loading state (AC2)", () => {
    mockUseCardStream.mockReturnValue({
      state: "loading",
      fields: {},
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()
    const input = screen.getByRole("textbox", { name: /new card/i })
    expect(input).toBeDisabled()
  })

  it("no Save/Discard buttons in loading state", () => {
    mockUseCardStream.mockReturnValue({
      state: "loading",
      fields: {},
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    expect(screen.queryByRole("button", { name: /save card/i })).not.toBeInTheDocument()
  })

  // ── Populated state (AC3, AC4) ─────────────────────────────────────────────

  it("renders field values in populated state (AC3)", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: {
        translation: "melancholic",
        forms: { gender: "masculine", article: "el", plural: "melancólicos", conjugations: {} },
        example_sentences: ["She felt melancholic.", "A melancholic mood."],
        audio: "/cards/42/audio",
        card_id: 42,
      },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    expect(screen.getByText("melancholic")).toBeInTheDocument()
    expect(screen.getByText("She felt melancholic.")).toBeInTheDocument()
    expect(screen.getByText("A melancholic mood.")).toBeInTheDocument()
  })

  it("renders forms article + plural when available (T3.5)", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: {
        translation: "test",
        forms: { gender: "masculine", article: "el", plural: "tests", conjugations: {} },
        card_id: 1,
      },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    // Article and plural should be rendered
    expect(screen.getByText(/el.*tests|el|tests/i)).toBeInTheDocument()
  })

  it("handles null forms gracefully (T3.5)", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: {
        translation: "run",
        forms: { gender: null, article: null, plural: null, conjugations: {} },
        card_id: 2,
      },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    // Should not throw or render null as text
    expect(() => renderPanel()).not.toThrow()
  })

  it("shows Save card and Discard buttons in populated state (AC4)", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    expect(screen.getByRole("button", { name: /save card/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /discard/i })).toBeInTheDocument()
  })

  it("renders 'View card →' link in populated state when card_id is set (T12)", async () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", card_id: 42 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    // useEffect fires after render — the link appears once completedCardId is set
    const link = await screen.findByText("View card →")
    expect(link).toBeInTheDocument()
  })

  it("calls saveCard when Save card button is clicked (AC4)", async () => {
    const user = userEvent.setup()
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()
    await user.click(screen.getByRole("button", { name: /save card/i }))
    expect(mockSaveCard).toHaveBeenCalledOnce()
  })

  it("calls discard when Discard button is clicked", async () => {
    const user = userEvent.setup()
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()
    await user.click(screen.getByRole("button", { name: /discard/i }))
    expect(mockDiscard).toHaveBeenCalledOnce()
  })

  it("input is disabled in populated state", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    const input = screen.getByRole("textbox", { name: /new card/i })
    expect(input).toBeDisabled()
  })

  it("renders audio element when fields.audio is set (T3.7)", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", audio: "/cards/1/audio", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    const audio = document.querySelector("audio")
    expect(audio).toBeInTheDocument()
    expect(audio?.getAttribute("src")).toBe("/cards/1/audio")
  })

  it("renders 'Not available' text when fields.audio is undefined after complete (T3.7, AC-implied)", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", card_id: 1 },
      // No audio field
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    expect(screen.getByText(/not available/i)).toBeInTheDocument()
  })

  // ── Saving state (T3.11, T4.5) ────────────────────────────────────────────

  it("action row is hidden and input is disabled in saving state", () => {
    mockUseCardStream.mockReturnValue({
      state: "saving",
      fields: { translation: "test", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    expect(screen.queryByRole("button", { name: /save card/i })).not.toBeInTheDocument()
    const input = screen.getByRole("textbox", { name: /new card/i })
    expect(input).toBeDisabled()
  })

  // ── Error state (AC5) ─────────────────────────────────────────────────────

  it("shows specific error message in error state (AC5)", () => {
    mockUseCardStream.mockReturnValue({
      state: "error",
      fields: {},
      errorMessage: "Local Qwen timeout after 10s",
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    expect(screen.getByText("Local Qwen timeout after 10s")).toBeInTheDocument()
  })

  it("shows 'Try again' button in error state (AC5)", () => {
    mockUseCardStream.mockReturnValue({
      state: "error",
      fields: {},
      errorMessage: "Service unavailable",
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument()
  })

  it("calls reset when 'Try again' button is clicked (AC5)", async () => {
    const user = userEvent.setup()
    mockUseCardStream.mockReturnValue({
      state: "error",
      fields: {},
      errorMessage: "Service unavailable",
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()
    await user.click(screen.getByRole("button", { name: /try again/i }))
    expect(mockReset).toHaveBeenCalledOnce()
  })

  it("input is NOT disabled in error state (per §CardCreationPanel note)", () => {
    mockUseCardStream.mockReturnValue({
      state: "error",
      fields: {},
      errorMessage: "Timeout",
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    const input = screen.getByRole("textbox", { name: /new card/i })
    expect(input).not.toBeDisabled()
  })

  it("no Save/Discard buttons in error state", () => {
    mockUseCardStream.mockReturnValue({
      state: "error",
      fields: {},
      errorMessage: "Timeout",
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    expect(screen.queryByRole("button", { name: /save card/i })).not.toBeInTheDocument()
  })

  it("displays network-level error message (e.g. 'Failed to fetch') — not generic 'Something went wrong' (AC5)", () => {
    // When streamPost re-throws a non-ApiError (e.g. TypeError from network reset),
    // useCardStream sets errorMessage = err.message (e.g. "Failed to fetch").
    // The component must display whatever errorMessage is provided — never replace it.
    mockUseCardStream.mockReturnValue({
      state: "error",
      fields: {},
      errorMessage: "Failed to fetch",
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    expect(screen.getByText("Failed to fetch")).toBeInTheDocument()
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument()
  })

  // ── Keyboard flow (AC7) ────────────────────────────────────────────────────

  it("pressing Enter calls startStream with input value (AC7)", async () => {
    const user = userEvent.setup()
    renderPanel()

    const input = screen.getByRole("textbox", { name: /new card/i })
    await user.type(input, "melancólico")
    await user.keyboard("{Enter}")

    expect(mockStartStream).toHaveBeenCalledWith("melancólico")
  })

  it("pressing Enter with empty input does not call startStream", async () => {
    const user = userEvent.setup()
    renderPanel()

    const input = screen.getByRole("textbox", { name: /new card/i })
    await user.click(input)
    await user.keyboard("{Enter}")

    expect(mockStartStream).not.toHaveBeenCalled()
  })

  it("pressing Escape calls reset (T3.1)", async () => {
    const user = userEvent.setup()
    renderPanel()

    const input = screen.getByRole("textbox", { name: /new card/i })
    await user.click(input)
    await user.keyboard("{Escape}")

    expect(mockReset).toHaveBeenCalled()
  })

  // ── Accessibility: aria-live on field slots (AC3, AC7) ────────────────────

  it("field slots have aria-live='polite' for screen reader announcements (AC3)", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    const liveRegions = document.querySelectorAll('[aria-live="polite"]')
    // At minimum 4 field slots (translation, forms, example, audio)
    expect(liveRegions.length).toBeGreaterThanOrEqual(4)
  })

  it("all 4 field slot aria-live regions exist in loading state too", () => {
    mockUseCardStream.mockReturnValue({
      state: "loading",
      fields: {},
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()
    // aria-live regions are always present (they hold skeletons in loading, data in populated)
    const liveRegions = document.querySelectorAll('[aria-live="polite"]')
    expect(liveRegions.length).toBeGreaterThanOrEqual(4)
  })

  // ── Example sentences rendered as list (T3.6) ────────────────────────────

  it("renders example sentences as a list", () => {
    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: {
        translation: "sad",
        example_sentences: ["She was sad.", "A sad day."],
        card_id: 1,
      },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })
    renderPanel()

    const listItems = screen.getAllByRole("listitem")
    expect(listItems).toHaveLength(2)
    expect(listItems[0]).toHaveTextContent("She was sad.")
    expect(listItems[1]).toHaveTextContent("A sad day.")
  })

  // ── Audio onCanPlay callback (T3.7 branch coverage) ───────────────────────

  it("audio onCanPlay triggers play() on first render, not on second (hasPlayedRef guard)", async () => {
    const mockPlay = vi.fn().mockResolvedValue(undefined)

    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", audio: "/cards/1/audio", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    const audio = document.querySelector("audio") as HTMLAudioElement
    expect(audio).toBeTruthy()

    // Patch play on the audio element
    Object.defineProperty(audio, "play", { value: mockPlay, writable: true })

    // Simulate canplay event (first time — should call play)
    audio.dispatchEvent(new Event("canplay"))
    expect(mockPlay).toHaveBeenCalledTimes(1)

    // Simulate canplay event again (second time — hasPlayedRef guard should prevent replay)
    audio.dispatchEvent(new Event("canplay"))
    expect(mockPlay).toHaveBeenCalledTimes(1) // still 1 — not called again
  })

  it("audio onCanPlay handles autoplay rejection gracefully (catch branch)", async () => {
    const mockPlay = vi.fn().mockRejectedValue(new DOMException("Autoplay blocked"))

    mockUseCardStream.mockReturnValue({
      state: "populated",
      fields: { translation: "test", audio: "/cards/1/audio", card_id: 1 },
      errorMessage: null,
      startStream: mockStartStream,
      saveCard: mockSaveCard,
      discard: mockDiscard,
      reset: mockReset,
    })

    renderPanel()

    const audio = document.querySelector("audio") as HTMLAudioElement
    Object.defineProperty(audio, "play", { value: mockPlay, writable: true })

    // Should not throw even when play() rejects
    await expect(async () => {
      audio.dispatchEvent(new Event("canplay"))
      // Wait for the rejection to be handled
      await Promise.resolve()
    }).not.toThrow()
  })
})
