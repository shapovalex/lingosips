/**
 * Tests for PracticeCard component.
 * TDD: written before implementation.
 * AC: 4, 5, 6, 7
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { PracticeCard } from "./PracticeCard"
import type { QueueCard, EvaluationResult } from "./usePracticeSession"

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
  card_type: "word",
  forms: null,
  example_sentences: null,
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

  // ── Speak stubs (Epic 4 — replaced by real implementation in Story 4.3) ──────

  it("renders speak-recording state with correct data-testid", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} initialState="speak-recording" />)
    expect(screen.getByTestId("practice-card-speak-recording")).toBeInTheDocument()
  })

  it("renders speak-result state with correct data-testid", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} initialState="speak-result" />)
    expect(screen.getByTestId("practice-card-speak-result")).toBeInTheDocument()
  })
})

// ── Write-active state ──────────────────────────────────────────────────────

const MOCK_EVAL_RESULT: EvaluationResult = {
  is_correct: false,
  highlighted_chars: [
    { char: "h", correct: true },
    { char: "e", correct: true },
    { char: "l", correct: true },
    { char: "o", correct: false },
  ],
  correct_value: "hell",
  explanation: "Wrong last letter.",
  suggested_rating: 1,
}

describe("PracticeCard — write-active state", () => {
  const onRate = vi.fn()
  const onEvaluate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders target word at text-4xl and textarea", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={null}
        sessionCount={0}
        initialState="write-active"
      />
    )
    expect(screen.getByText("melancólico")).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /submit/i })).toBeInTheDocument()
    expect(screen.getByText(/enter to submit/i)).toBeInTheDocument()
  })

  it("calls onEvaluate with answer on Enter key in textarea", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={null}
        sessionCount={0}
        initialState="write-active"
      />
    )
    const textarea = screen.getByRole("textbox")
    fireEvent.change(textarea, { target: { value: "melancholic" } })
    fireEvent.keyDown(textarea, { key: "Enter" })
    expect(onEvaluate).toHaveBeenCalledWith("melancholic")
  })

  it("calls onEvaluate on Submit button click", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={null}
        sessionCount={0}
        initialState="write-active"
      />
    )
    const textarea = screen.getByRole("textbox")
    fireEvent.change(textarea, { target: { value: "melancholic" } })
    fireEvent.click(screen.getByRole("button", { name: /submit/i }))
    expect(onEvaluate).toHaveBeenCalledWith("melancholic")
  })

  it("shows evaluating state (disabled textarea + spinner text) when evaluationResult is 'pending'", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult="pending"
        sessionCount={0}
        initialState="write-active"
      />
    )
    const textarea = screen.getByRole("textbox")
    expect(textarea).toBeDisabled()
    expect(screen.getByRole("button", { name: /evaluating/i })).toBeDisabled()
  })

  it("does NOT fire 1-4 rating keys when in write-active state", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={null}
        sessionCount={0}
        initialState="write-active"
      />
    )
    fireEvent.keyDown(document, { key: "1" })
    fireEvent.keyDown(document, { key: "3" })
    expect(onRate).not.toHaveBeenCalled()
  })

  it("transitions to write-result when evaluationResult changes from null to EvaluationResult", async () => {
    const { rerender } = render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={null}
        sessionCount={0}
        initialState="write-active"
      />
    )
    // Still in write-active
    expect(screen.getByRole("textbox")).toBeInTheDocument()

    // evaluationResult changes to actual result
    rerender(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-active"
      />
    )

    // Should have transitioned to write-result
    await waitFor(() => {
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    })
  })
})

// ── Write-result state ──────────────────────────────────────────────────────

describe("PracticeCard — write-result state", () => {
  const onRate = vi.fn()
  const onEvaluate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders correct chars normally and wrong chars with red underline", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    // Wrong char 'o' should have red text (check via its existence)
    const wrongChars = document.querySelectorAll(".text-red-400")
    expect(wrongChars.length).toBeGreaterThan(0)
    // The 'o' char is the wrong one
    const wrongTexts = Array.from(wrongChars).map((el) => el.textContent)
    expect(wrongTexts).toContain("o")
  })

  it("hides correct_value when is_correct is true", () => {
    const correctResult: EvaluationResult = {
      is_correct: true,
      highlighted_chars: [{ char: "h", correct: true }, { char: "i", correct: true }],
      correct_value: "hi",
      explanation: null,
      suggested_rating: 3,
    }
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={correctResult}
        sessionCount={0}
        initialState="write-result"
      />
    )
    // correct_value "hi" should NOT be shown separately (it matches)
    // The correct value element (emerald) should not be rendered
    const emeraldElements = document.querySelectorAll(".text-emerald-500")
    const correctValueShown = Array.from(emeraldElements).some(
      (el) => el.textContent === "hi"
    )
    expect(correctValueShown).toBe(false)
  })

  it("shows correct_value in emerald when is_correct is false", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    // correct_value "hell" should be visible in emerald
    expect(screen.getByText("hell")).toBeInTheDocument()
  })

  it("shows explanation text when present", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    expect(screen.getByText("Wrong last letter.")).toBeInTheDocument()
  })

  it("shows 'Evaluation unavailable' when explanation is null and is_correct is false", () => {
    const noExplanation: EvaluationResult = {
      ...MOCK_EVAL_RESULT,
      explanation: null,
    }
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={noExplanation}
        sessionCount={0}
        initialState="write-result"
      />
    )
    expect(screen.getByText(/evaluation unavailable/i)).toBeInTheDocument()
  })

  it("FSRS row pre-selects suggested_rating", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    // suggested_rating is 1 = "Again" — it should be pre-selected (aria-pressed=true)
    const againBtn = screen.getByRole("button", { name: /again/i })
    expect(againBtn).toHaveAttribute("aria-pressed", "true")
  })

  it("Enter key submits the pre-selected rating", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    fireEvent.keyDown(document, { key: "Enter" })
    expect(onRate).toHaveBeenCalledWith(1)  // suggested_rating = 1
  })

  it("clicking a different rating button changes selection", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    // Click "Good" (value 3) to change selection
    fireEvent.click(screen.getByRole("button", { name: /good/i }))
    expect(onRate).toHaveBeenCalledWith(3)
  })

  it("calls onRate with selected rating", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    const easyBtn = screen.getByRole("button", { name: /easy/i })
    fireEvent.click(easyBtn)
    expect(onRate).toHaveBeenCalledWith(4)
  })

  it("does NOT fire Space rating in write-result state", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={MOCK_EVAL_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    // The document-level keydown handler should be guarded for write-result
    // Space should NOT call onRate (it's handled by WriteResultRatingRow's Enter)
    const callsBefore = onRate.mock.calls.length
    fireEvent.keyDown(document, { code: "Space", key: " " })
    // onRate not called by Space in write-result
    expect(onRate.mock.calls.length).toBe(callsBefore)
  })
})

// ── Story 3.4: Sentence/collocation card display tests ─────────────────────────

const SENTENCE_CARD: QueueCard & { grammatical_forms?: string; example_sentence?: string } = {
  ...MOCK_CARD,
  id: 10,
  target_word: "no te hagas el tonto",
  translation: "don't play dumb",
  card_type: "sentence",
  forms: JSON.stringify({ register_context: "informal, River Plate Spanish" }),
  grammatical_forms: "Register: informal, River Plate Spanish",
  example_sentence: "No te hagas el tonto, te vi.",
}

const COLLOCATION_CARD: QueueCard = {
  ...MOCK_CARD,
  id: 11,
  target_word: "morder el polvo",
  translation: "to bite the dust",
  card_type: "collocation",
  forms: JSON.stringify({ register_context: "informal" }),
}

describe("card_type-aware font sizing", () => {
  const onRate = vi.fn()
  beforeEach(() => vi.clearAllMocks())

  it("renders target_word at text-4xl for word cards (default)", () => {
    render(<PracticeCard card={MOCK_CARD} onRate={onRate} sessionCount={0} />)
    const span = screen.getByText("melancólico")
    expect(span.className).toContain("text-4xl")
  })

  it("renders target_word at text-2xl for sentence cards", () => {
    render(<PracticeCard card={SENTENCE_CARD} onRate={onRate} sessionCount={0} />)
    const span = screen.getByText("no te hagas el tonto")
    expect(span.className).toContain("text-2xl")
    expect(span.className).not.toContain("text-4xl")
  })

  it("renders target_word at text-2xl for collocation cards", () => {
    render(<PracticeCard card={COLLOCATION_CARD} onRate={onRate} sessionCount={0} />)
    const span = screen.getByText("morder el polvo")
    expect(span.className).toContain("text-2xl")
  })

  it("defaults to text-4xl when card_type is word", () => {
    const wordCard = { ...MOCK_CARD, card_type: "word" as const }
    render(<PracticeCard card={wordCard} onRate={onRate} sessionCount={0} />)
    const span = screen.getByText("melancólico")
    expect(span.className).toContain("text-4xl")
  })
})

describe("write-result — sentence card (empty highlighted_chars)", () => {
  const onRate = vi.fn()
  const onEvaluate = vi.fn()
  beforeEach(() => vi.clearAllMocks())

  const SENTENCE_WRONG_RESULT: EvaluationResult = {
    is_correct: false,
    highlighted_chars: [],
    correct_value: "don't play dumb",
    explanation: "That's not the right meaning.",
    suggested_rating: 1,
  }

  it("does NOT show char-highlight div when highlighted_chars is empty", () => {
    render(
      <PracticeCard
        card={SENTENCE_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={SENTENCE_WRONG_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    // No char-highlight wrapper div present
    const charHighlightDiv = document.querySelector(".flex.flex-wrap.gap-0.text-xl.font-mono")
    expect(charHighlightDiv).not.toBeInTheDocument()
  })

  it("still shows correct_value in emerald when is_correct=false", () => {
    render(
      <PracticeCard
        card={SENTENCE_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={SENTENCE_WRONG_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    const correctSpan = screen.getByText("don't play dumb")
    expect(correctSpan.className).toContain("emerald")
  })

  it("still shows explanation when present", () => {
    render(
      <PracticeCard
        card={SENTENCE_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={SENTENCE_WRONG_RESULT}
        sessionCount={0}
        initialState="write-result"
      />
    )
    expect(screen.getByText("That's not the right meaning.")).toBeInTheDocument()
  })
})

describe("write-active — userAnswer capture", () => {
  const onRate = vi.fn()
  const onEvaluate = vi.fn()
  beforeEach(() => vi.clearAllMocks())

  it("calls onEvaluate on Enter key submit", () => {
    render(
      <PracticeCard
        card={SENTENCE_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={null}
        sessionCount={0}
        initialState="write-active"
      />
    )
    const textarea = screen.getByTestId("write-active-input")
    fireEvent.change(textarea, { target: { value: "my answer" } })
    fireEvent.keyDown(textarea, { key: "Enter" })
    expect(onEvaluate).toHaveBeenCalledWith("my answer")
  })

  it("calls onEvaluate on Submit button click", () => {
    render(
      <PracticeCard
        card={SENTENCE_CARD}
        onRate={onRate}
        onEvaluate={onEvaluate}
        evaluationResult={null}
        sessionCount={0}
        initialState="write-active"
      />
    )
    const textarea = screen.getByTestId("write-active-input")
    fireEvent.change(textarea, { target: { value: "my button answer" } })
    const submitBtn = screen.getByRole("button", { name: /submit/i })
    fireEvent.click(submitBtn)
    expect(onEvaluate).toHaveBeenCalledWith("my button answer")
  })
})

// ── Speak mode — speak-recording state ────────────────────────────────────────

describe("PracticeCard — speak-recording state", () => {
  const onRate = vi.fn()
  const onSpeak = vi.fn()
  const onSkip = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it("renders mic button with aria-label and card target word", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    expect(screen.getByText("melancólico")).toBeInTheDocument()
    const micBtn = screen.getByRole("button", { name: /record pronunciation/i })
    expect(micBtn).toBeInTheDocument()
  })

  it("shows first-use tooltip when localStorage key is unset", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    expect(screen.getByText(/tap mic to record/i)).toBeInTheDocument()
  })

  it("does NOT show tooltip when localStorage key is '1'", () => {
    localStorage.setItem("lingosips-speak-tooltip-shown", "1")
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    expect(screen.queryByText(/tap mic to record/i)).not.toBeInTheDocument()
  })

  it("R key fires onSpeak callback", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    fireEvent.keyDown(document, { key: "r" })
    expect(onSpeak).toHaveBeenCalledTimes(1)
  })

  it("S key fires onSkip callback", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    fireEvent.keyDown(document, { key: "s" })
    expect(onSkip).toHaveBeenCalledTimes(1)
  })

  it("space key does NOT flip card or rate in speak-recording state", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    fireEvent.keyDown(document, { code: "Space", key: " " })
    expect(onRate).not.toHaveBeenCalled()
    // card should still be in speak-recording state (target word visible, no translation flipTo-reveal)
    expect(screen.getByTestId("practice-card-speak-recording")).toBeInTheDocument()
  })

  it("Skip button fires onSkip", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    const skipBtn = screen.getByRole("button", { name: /skip/i })
    fireEvent.click(skipBtn)
    expect(onSkip).toHaveBeenCalledTimes(1)
  })

  // ── AC3: isRecording prop — animate-pulse and dynamic aria-label ───────────

  it("mic button has animate-pulse class when isRecording=true", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
        isRecording={true}
      />
    )
    const micBtn = screen.getByRole("button", { name: /recording — release to evaluate/i })
    expect(micBtn).toHaveClass("animate-pulse")
  })

  it("mic button does NOT have animate-pulse when isRecording=false (default)", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
      />
    )
    const micBtn = screen.getByRole("button", { name: /record pronunciation/i })
    expect(micBtn).not.toHaveClass("animate-pulse")
  })

  it("mic button aria-label changes to 'Recording — release to evaluate' when isRecording=true", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-recording"
        isRecording={true}
      />
    )
    expect(
      screen.getByRole("button", { name: "Recording — release to evaluate" })
    ).toBeInTheDocument()
  })
})

// ── Speak mode — speak-result state ──────────────────────────────────────────

const MOCK_SYLLABLES = [
  { syllable: "me", correct: true, score: 0.9 },
  { syllable: "lan", correct: false, score: 0.3 },
  { syllable: "có", correct: true, score: 0.85 },
  { syllable: "li", correct: false, score: 0.2 },
  { syllable: "co", correct: true, score: 0.8 },
]

describe("PracticeCard — speak-result state", () => {
  const onRate = vi.fn()
  const onSpeak = vi.fn()
  const onSkip = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders SyllableFeedback with passed syllable props", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="result-partial"
        speechSyllables={MOCK_SYLLABLES}
        speechCorrectionMessage="Focus on 'lan' and 'li'"
      />
    )
    // SyllableFeedback renders target word in header
    expect(screen.getByText("melancólico")).toBeInTheDocument()
    // SyllableFeedback should be present (renders correction message area)
    expect(screen.getByTestId("practice-card-speak-result")).toBeInTheDocument()
  })

  it("R key fires onSpeak in speak-result state", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="result-partial"
        speechSyllables={MOCK_SYLLABLES}
      />
    )
    fireEvent.keyDown(document, { key: "R" })
    expect(onSpeak).toHaveBeenCalledTimes(1)
  })

  it("Skip button fires onSkip in speak-result state", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="result-partial"
        speechSyllables={MOCK_SYLLABLES}
      />
    )
    const skipBtn = screen.getByRole("button", { name: /skip/i })
    fireEvent.click(skipBtn)
    expect(onSkip).toHaveBeenCalledTimes(1)
  })

  it("syllableFeedbackState='evaluating' renders SyllableFeedback in evaluating state", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="evaluating"
      />
    )
    // In evaluating state, SyllableFeedback shows "Evaluating..."
    expect(screen.getByText(/evaluating/i)).toBeInTheDocument()
  })

  it("result-partial: SyllableFeedback onRetry calls onSpeak", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="result-partial"
        speechSyllables={MOCK_SYLLABLES}
      />
    )
    // "Try again" button inside SyllableFeedback calls onRetry → onSpeak
    const tryAgainBtn = screen.getByRole("button", { name: /try again/i })
    fireEvent.click(tryAgainBtn)
    expect(onSpeak).toHaveBeenCalledTimes(1)
  })

  it("result-partial: SyllableFeedback onMoveOn calls onRate(1)", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="result-partial"
        speechSyllables={MOCK_SYLLABLES}
      />
    )
    // "Move on" button inside SyllableFeedback calls onMoveOn → onRate(1)
    const moveOnBtn = screen.getByRole("button", { name: /move on/i })
    fireEvent.click(moveOnBtn)
    expect(onRate).toHaveBeenCalledWith(1)
  })

  it("space key does NOT trigger self-assess shortcuts in speak-result state", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="result-partial"
        speechSyllables={MOCK_SYLLABLES}
      />
    )
    fireEvent.keyDown(document, { code: "Space", key: " " })
    expect(onRate).not.toHaveBeenCalled()
  })

  // ── AC6: "Try again" receives focus on result-partial mount ───────────────

  it("'Try again' button receives focus in result-partial state (AC6)", () => {
    render(
      <PracticeCard
        card={MOCK_CARD}
        onRate={onRate}
        onSpeak={onSpeak}
        onSkip={onSkip}
        sessionCount={0}
        initialState="speak-result"
        syllableFeedbackState="result-partial"
        speechSyllables={MOCK_SYLLABLES}
      />
    )
    const tryAgainBtn = screen.getByRole("button", { name: /try again/i })
    expect(tryAgainBtn).toHaveFocus()
  })
})
