/**
 * Tests for PracticeCard component.
 * TDD: written before implementation.
 * AC: 4, 5, 6, 7
 */
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { PracticeCard } from "./PracticeCard"
import type { QueueCard } from "./usePracticeSession"

const MOCK_CARD: QueueCard = {
  id: 1,
  target_word: "melancólico",
  translation: "melancholic",
  target_language: "es",
  due: new Date().toISOString(),
  fsrs_state: "review",
  stability: 3.5,
  difficulty: 4.0,
  reps: 5,
  lapses: 0,
}

const MOCK_CARD_WITH_FORMS: QueueCard & { grammatical_forms?: string; example_sentence?: string } = {
  ...MOCK_CARD,
  grammatical_forms: "adj. (masculine)",
  example_sentence: "El cielo está melancólico hoy.",
}

describe("PracticeCard", () => {
  const onRate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Front state ────────────────────────────────────────────────────────────

  it("renders front state with target word and hint", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    expect(screen.getByText("melancólico")).toBeInTheDocument()
    expect(screen.getByText(/space to reveal/i)).toBeInTheDocument()
  })

  it("does NOT show FSRS rating row in front state", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    expect(screen.queryByRole("group", { name: /rate your recall/i })).not.toBeInTheDocument()
  })

  // ── Flip to revealed ───────────────────────────────────────────────────────

  it("flips to revealed on Space keypress", async () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    expect(screen.getByText("melancholic")).toBeInTheDocument()
    expect(screen.getByRole("group", { name: /rate your recall/i })).toBeInTheDocument()
  })

  it("flips to revealed on card click", async () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    const card = screen.getByRole("button", { name: /flip card/i })
    fireEvent.click(card)
    expect(screen.getByText("melancholic")).toBeInTheDocument()
  })

  // ── Revealed state ─────────────────────────────────────────────────────────

  it("shows translation in revealed state", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    expect(screen.getByText("melancholic")).toBeInTheDocument()
  })

  it("shows grammatical forms and example sentence in revealed state when present", () => {
    render(<PracticeCard card={MOCK_CARD_WITH_FORMS} onRate={onRate} sessionCount={0} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    expect(screen.getByText("adj. (masculine)")).toBeInTheDocument()
    expect(screen.getByText("El cielo está melancólico hoy.")).toBeInTheDocument()
  })

  it("shows FSRS rating row in revealed state", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    expect(screen.getByRole("group", { name: /rate your recall/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /again/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /hard/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /good/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /easy/i })).toBeInTheDocument()
  })

  it("calls onRate with correct value 1 on Again button click", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={3} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    fireEvent.click(screen.getByRole("button", { name: /again/i }))
    expect(onRate).toHaveBeenCalledWith(1)
  })

  it("calls onRate with correct value 4 on Easy button click", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={3} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    fireEvent.click(screen.getByRole("button", { name: /easy/i }))
    expect(onRate).toHaveBeenCalledWith(4)
  })

  it("calls onRate(1) on key '1' press when revealed", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={3} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    fireEvent.keyDown(document, { key: "1" })
    expect(onRate).toHaveBeenCalledWith(1)
  })

  it("calls onRate(4) on key '4' press when revealed", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={3} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    fireEvent.keyDown(document, { key: "4" })
    expect(onRate).toHaveBeenCalledWith(4)
  })

  // ── Tooltip logic ──────────────────────────────────────────────────────────

  it("shows tooltip labels when sessionCount < 3", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    // Screen reader text (sr-only) should be present for tooltips
    expect(screen.getByText("Forgot")).toBeInTheDocument()
    expect(screen.getByText("Recalled")).toBeInTheDocument()
  })

  it("hides tooltip labels (sr-only visible text) when sessionCount >= 3", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={3} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    // sr-only tooltip text should NOT be rendered when sessionCount >= 3
    expect(screen.queryByText("Forgot")).not.toBeInTheDocument()
    expect(screen.queryByText("Recalled")).not.toBeInTheDocument()
  })

  // ── Accessibility ──────────────────────────────────────────────────────────

  it("rating row has role=group with aria-label", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={3} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    const ratingGroup = screen.getByRole("group", { name: /rate your recall/i })
    expect(ratingGroup).toBeInTheDocument()
  })

  it("Space key prevents default page scroll (event has preventDefault called)", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    const event = new KeyboardEvent("keydown", { code: "Space", key: " ", bubbles: true, cancelable: true })
    const preventDefaultSpy = vi.spyOn(event, "preventDefault")
    document.dispatchEvent(event)
    expect(preventDefaultSpy).toHaveBeenCalled()
  })

  it("rating buttons have aria-keyshortcuts attribute", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={3} />)
    fireEvent.keyDown(document, { code: "Space", key: " " })
    const againBtn = screen.getByRole("button", { name: /again/i })
    expect(againBtn).toHaveAttribute("aria-keyshortcuts", "1")
  })

  // ── Stub states ────────────────────────────────────────────────────────────

  it("renders write-active placeholder with correct data-testid", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} initialState="write-active" />)
    expect(screen.getByTestId("practice-card-write-active")).toBeInTheDocument()
  })

  it("renders speak-recording placeholder with correct data-testid", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} initialState="speak-recording" />)
    expect(screen.getByTestId("practice-card-speak-recording")).toBeInTheDocument()
  })
})
