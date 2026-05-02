/**
 * Tests for SyllableFeedback component.
 * TDD: written before implementation.
 * AC: 1–7
 *
 * Covers:
 *   - All 5 SyllableFeedbackState values
 *   - All 4 chip states (neutral, correct, wrong, pending)
 *   - aria-live="assertive" on correction text container
 *   - Per-chip aria-label includes syllable text AND status
 *   - Keyboard navigation: Tab reaches "Try again" → Tab reaches "Move on" → Enter triggers onMoveOn
 *   - "Try again" click triggers onRetry callback
 *   - Wrong chips have both color class AND text label (not color-only)
 */
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SyllableFeedback } from "./SyllableFeedback"

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_SYLLABLES_ALL_CORRECT = [
  { syllable: "a", correct: true, score: 0.95 },
  { syllable: "gua", correct: true, score: 0.88 },
  { syllable: "ca", correct: true, score: 0.91 },
  { syllable: "te", correct: true, score: 0.93 },
]

const MOCK_SYLLABLES_PARTIAL = [
  { syllable: "a", correct: true, score: 0.95 },
  { syllable: "gua", correct: true, score: 0.88 },
  { syllable: "CA", correct: false, score: 0.35 },
  { syllable: "te", correct: true, score: 0.90 },
]

const MOCK_CORRECTION = "a-gua-CA-te — stress on third syllable"

// ── Test suite ────────────────────────────────────────────────────────────────

describe("SyllableFeedback", () => {
  const onRetry = vi.fn()
  const onMoveOn = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── awaiting state (AC1) ───────────────────────────────────────────────────

  describe("awaiting state", () => {
    it("renders target word in header", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="awaiting"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
        />
      )
      expect(screen.getByText("aguacate")).toBeInTheDocument()
    })

    it("renders all chips as neutral (no emerald or amber classes)", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="awaiting"
          syllables={MOCK_SYLLABLES_PARTIAL}
        />
      )
      const chips = screen.getAllByRole("img")
      for (const chip of chips) {
        expect(chip.className).toMatch(/zinc/)
        expect(chip.className).not.toMatch(/emerald/)
        expect(chip.className).not.toMatch(/amber/)
      }
    })

    it("does not show correction text", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="awaiting"
          correctionMessage={MOCK_CORRECTION}
        />
      )
      expect(screen.queryByText(MOCK_CORRECTION)).not.toBeInTheDocument()
    })

    it("does not show fallback badge", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="awaiting"
          providerUsed="local_whisper"
        />
      )
      expect(screen.queryByText(/Using local Whisper/)).not.toBeInTheDocument()
    })

    it("does not show Try again or Move on buttons", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="awaiting"
        />
      )
      expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument()
      expect(screen.queryByRole("button", { name: /move on/i })).not.toBeInTheDocument()
    })
  })

  // ── evaluating state (AC2) ────────────────────────────────────────────────

  describe("evaluating state", () => {
    it("shows Evaluating... label", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="evaluating"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
        />
      )
      expect(screen.getByText(/evaluating\.\.\./i)).toBeInTheDocument()
    })

    it("chips have animate-pulse class (pending state)", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="evaluating"
          syllables={MOCK_SYLLABLES_PARTIAL}
        />
      )
      const chips = screen.getAllByRole("img")
      for (const chip of chips) {
        expect(chip.className).toMatch(/animate-pulse/)
      }
    })

    it("does not show correction text", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="evaluating"
          correctionMessage={MOCK_CORRECTION}
        />
      )
      expect(screen.queryByText(MOCK_CORRECTION)).not.toBeInTheDocument()
    })
  })

  // ── result-correct state (AC3) ────────────────────────────────────────────

  describe("result-correct state", () => {
    it("all chips have emerald classes", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-correct"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
        />
      )
      const chips = screen.getAllByRole("img")
      for (const chip of chips) {
        expect(chip.className).toMatch(/emerald/)
      }
    })

    it("component header has emerald tint", () => {
      const { container } = render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-correct"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
        />
      )
      // Header element should have emerald-950 background tint
      const header = container.querySelector("[data-testid='syllable-feedback-header']")
      expect(header).not.toBeNull()
      expect(header!.className).toMatch(/emerald/)
    })

    it("no Try again button shown", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-correct"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
        />
      )
      expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument()
    })
  })

  // ── result-partial state (AC4) ────────────────────────────────────────────

  describe("result-partial state", () => {
    it("wrong chips have amber classes", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      const wrongChip = screen.getByRole("img", { name: /CA — incorrect/i })
      expect(wrongChip.className).toMatch(/amber/)
    })

    it("correct chips have emerald classes", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      const correctChip = screen.getByRole("img", { name: /^a — correct/i })
      expect(correctChip.className).toMatch(/emerald/)
    })

    it("shows correction text", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      expect(screen.getByText(MOCK_CORRECTION)).toBeInTheDocument()
    })

    it("renders Try again as primary button", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      const btn = screen.getByRole("button", { name: /try again/i })
      expect(btn).toBeInTheDocument()
      expect(btn.className).toMatch(/indigo/)
    })

    it("renders Move on as secondary button", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      const btn = screen.getByRole("button", { name: /move on/i })
      expect(btn).toBeInTheDocument()
      expect(btn.className).toMatch(/zinc/)
    })

    it("Try again click triggers onRetry", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      fireEvent.click(screen.getByRole("button", { name: /try again/i }))
      expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it("Move on click triggers onMoveOn", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      fireEvent.click(screen.getByRole("button", { name: /move on/i }))
      expect(onMoveOn).toHaveBeenCalledTimes(1)
    })

    it("does not crash when onRetry is not provided (optional callback guard)", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          // onRetry intentionally omitted
          onMoveOn={onMoveOn}
        />
      )
      expect(() =>
        fireEvent.click(screen.getByRole("button", { name: /try again/i }))
      ).not.toThrow()
    })

    it("does not crash when onMoveOn is not provided (optional callback guard)", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          // onMoveOn intentionally omitted
        />
      )
      expect(() =>
        fireEvent.click(screen.getByRole("button", { name: /move on/i }))
      ).not.toThrow()
    })

    it("renders buttons even without syllables prop", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument()
      expect(screen.getByRole("button", { name: /move on/i })).toBeInTheDocument()
      expect(screen.queryAllByRole("img")).toHaveLength(0)
    })

    it("does not show correction text when correctionMessage is null", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={null}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      // Buttons still shown; correction paragraph suppressed; aria-live region stays empty
      expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument()
      expect(screen.queryByText(MOCK_CORRECTION)).not.toBeInTheDocument()
      const liveRegion = document.querySelector("[aria-live='assertive']")
      expect(liveRegion?.textContent).toBe("")
    })
  })

  // ── fallback-notice state (AC5) ───────────────────────────────────────────

  describe("fallback-notice state", () => {
    it("shows amber badge with 'Using local Whisper · ~3s' text", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="fallback-notice"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
          providerUsed="local_whisper"
        />
      )
      expect(screen.getByText(/Using local Whisper · ~3s/)).toBeInTheDocument()
    })

    it("fallback badge has amber styling", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="fallback-notice"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
          providerUsed="local_whisper"
        />
      )
      const badge = screen.getByText(/Using local Whisper · ~3s/)
      expect(badge.className).toMatch(/amber/)
    })

    it("chips are in pending state (animate-pulse)", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="fallback-notice"
          syllables={MOCK_SYLLABLES_PARTIAL}
        />
      )
      const chips = screen.getAllByRole("img")
      for (const chip of chips) {
        expect(chip.className).toMatch(/animate-pulse/)
      }
    })

    it("does not show Evaluating... label (badge+chips only per AC2/AC5 scoping)", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="fallback-notice"
          syllables={MOCK_SYLLABLES_PARTIAL}
          providerUsed="local_whisper"
        />
      )
      expect(screen.queryByText(/evaluating\.\.\./i)).not.toBeInTheDocument()
    })

    it("renders badge and no chip row when syllables prop is omitted", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="fallback-notice"
          providerUsed="local_whisper"
        />
      )
      expect(screen.getByText(/Using local Whisper · ~3s/)).toBeInTheDocument()
      expect(screen.queryAllByRole("img")).toHaveLength(0)
    })
  })

  // ── accessibility (AC6, AC7) ──────────────────────────────────────────────

  describe("accessibility", () => {
    it("per-chip aria-label includes syllable text and correct status", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-correct"
          syllables={MOCK_SYLLABLES_ALL_CORRECT}
        />
      )
      expect(screen.getByRole("img", { name: /^a — correct/i })).toBeInTheDocument()
      expect(screen.getByRole("img", { name: /^gua — correct/i })).toBeInTheDocument()
      expect(screen.getByRole("img", { name: /^ca — correct/i })).toBeInTheDocument()
      expect(screen.getByRole("img", { name: /^te — correct/i })).toBeInTheDocument()
    })

    it("per-chip aria-label includes 'incorrect' for wrong syllables", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
        />
      )
      expect(screen.getByRole("img", { name: /CA — incorrect/i })).toBeInTheDocument()
    })

    it("correction sentence is in aria-live assertive region", () => {
      const { container } = render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
        />
      )
      const liveRegion = container.querySelector("[aria-live='assertive']")
      expect(liveRegion).not.toBeNull()
      expect(liveRegion!.textContent).toContain(MOCK_CORRECTION)
    })

    it("wrong chips encode error in both color class AND text label (not color-only, AC7)", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
        />
      )
      // The chip must have amber styling AND the aria-label must say "incorrect"
      const wrongChip = screen.getByRole("img", { name: /CA — incorrect/i })
      expect(wrongChip.className).toMatch(/amber/)          // color encoding
      expect(wrongChip).toHaveAccessibleName(/incorrect/i)  // text encoding
    })

    it("neutral chips in awaiting state have aria-label with syllable text", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="awaiting"
          syllables={MOCK_SYLLABLES_PARTIAL}
        />
      )
      // Each chip should still have an aria-label in awaiting state
      const chips = screen.getAllByRole("img")
      for (const chip of chips) {
        expect(chip).toHaveAttribute("aria-label")
      }
    })
  })

  // ── keyboard navigation (AC4, AC6) ────────────────────────────────────────

  describe("keyboard navigation", () => {
    it("Tab navigates from Try again to Move on", async () => {
      const user = userEvent.setup()
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      const tryAgainBtn = screen.getByRole("button", { name: /try again/i })
      const moveOnBtn = screen.getByRole("button", { name: /move on/i })

      tryAgainBtn.focus()
      expect(document.activeElement).toBe(tryAgainBtn)

      await user.tab()
      expect(document.activeElement).toBe(moveOnBtn)
    })

    it("Enter on Move on triggers onMoveOn", async () => {
      const user = userEvent.setup()
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      const moveOnBtn = screen.getByRole("button", { name: /move on/i })
      moveOnBtn.focus()
      await user.keyboard("{Enter}")
      expect(onMoveOn).toHaveBeenCalledTimes(1)
    })

    it("Try again button is focusable", () => {
      render(
        <SyllableFeedback
          targetWord="aguacate"
          state="result-partial"
          syllables={MOCK_SYLLABLES_PARTIAL}
          correctionMessage={MOCK_CORRECTION}
          onRetry={onRetry}
          onMoveOn={onMoveOn}
        />
      )
      const tryAgainBtn = screen.getByRole("button", { name: /try again/i })
      tryAgainBtn.focus()
      expect(document.activeElement).toBe(tryAgainBtn)
    })
  })
})
