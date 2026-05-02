# Story 3.3: Write Mode with AI Feedback

Status: done

## Story

As a user,
I want to type the answer in write mode and receive inline AI feedback — showing exactly which characters were wrong, the correct form, and why — so that each mistake becomes a specific learning moment.

## Acceptance Criteria

1. **`POST /practice/cards/{card_id}/evaluate`** accepts `{"answer": "..."}` and returns `EvaluationResponse`: `is_correct`, `highlighted_chars` (character-level diff), `correct_value`, `explanation` (or `null`), `suggested_rating`. Implemented in `api/practice.py` and delegated to `core/practice.py`.

2. **Exact match (case-insensitive, trimmed)** → `is_correct: true`, `suggested_rating: 3`, `explanation: null`, no LLM call made.

3. **Near-miss or wrong answer** → `is_correct: false`, `suggested_rating: 1`, character diff populates `highlighted_chars`, LLM called for single-sentence explanation (max 64 tokens). LLM timeout (10s) or error → `explanation: null` silently; session continues.

4. **`routes/practice.tsx`** supports `?mode=write` (TanStack Router `validateSearch`). `startSession(mode)` is called with the search param value (default `"self_assess"`). Existing self-assess behaviour unchanged.

5. **`PracticeCard`** in `write-active` state shows: target word at `text-4xl` above; an autofocused `<textarea>` (single-line behaviour via `rows=1`/Enter intercept) below; a "Submit" button; hint text "Enter to submit". Pressing Enter or clicking Submit calls `onEvaluate(answer)`.

6. **`PracticeCard`** in `write-result` state shows: target word above; the user's answer rendered char-by-char — correct chars in normal colour, wrong chars with `text-red-400 underline`; the correct value below in `text-emerald-500` (hidden when `is_correct: true`); explanation in `text-zinc-400` below that (or "Evaluation unavailable — rate manually" when `explanation` is null and `is_correct: false`); FSRS rating row at bottom with `suggested_rating` pre-selected.

7. **FSRS rating row in write-result** is pre-selected to `suggested_rating` from the evaluation. User can Tab/click to change selection. Enter confirms the currently selected rating. Calling `onRate(rating)` advances to the next card (same optimistic pattern as self-assess).

8. **`usePracticeSession` extended** with: `evaluateAnswer(cardId, answer)` — fires the evaluate endpoint; `evaluationResult: EvaluationResult | "pending" | null` — reset to `null` on card advance. Session hook accepts `mode?: PracticeMode` param to enable mode-aware behaviour.

9. **No Alembic migration required** — evaluation is stateless. No new DB columns.

10. **`api.d.ts`** regenerated after the evaluate endpoint is added.

11. **E2E Playwright**: `frontend/e2e/features/practice-write-mode.spec.ts` — correct answer → success state → Good rating; wrong answer → char highlighting → explanation shown → rating row; LLM unavailable → "Evaluation unavailable" message.

## Tasks / Subtasks

- [x] T1: Create `src/lingosips/core/practice.py` (AC: 1, 2, 3)
  - [x] T1.1: Write `tests/core/test_practice.py` FIRST (TDD) — see §TestCoverage
  - [x] T1.2: Define `CharHighlight` dataclass (`char: str`, `correct: bool`) and `EvaluationResult` dataclass
  - [x] T1.3: Implement `_char_diff(user_answer, correct_value) -> list[CharHighlight]` using `difflib.SequenceMatcher`
  - [x] T1.4: Implement `evaluate_answer(card, user_answer, llm) -> EvaluationResult`: exact-match check → LLM call for wrong answers → timeout/error fallback
  - [x] T1.5: Run tests; confirm all pass

- [x] T2: Add `POST /practice/cards/{card_id}/evaluate` to `api/practice.py` (AC: 1)
  - [x] T2.1: Write `tests/api/test_practice.py::TestEvaluateAnswer` FIRST (TDD) — see §TestCoverage
  - [x] T2.2: Add imports: `from lingosips.core import practice as core_practice`, `from lingosips.services.registry import get_llm_provider`, `from lingosips.services.llm.base import AbstractLLMProvider`
  - [x] T2.3: Add Pydantic models: `EvaluateAnswerRequest(answer: str)` with `not_whitespace_only` validator, `CharHighlightSchema(char, correct)`, `EvaluationResponse(is_correct, highlighted_chars, correct_value, explanation, suggested_rating)`
  - [x] T2.4: Implement handler — fetch card (404 if missing), delegate to `core_practice.evaluate_answer`, return `EvaluationResponse`
  - [x] T2.5: Run tests; confirm all pass

- [x] T3: Update `routes/practice.tsx` to support write mode (AC: 4, 5, 6, 7, 8)
  - [x] T3.1: Write `practice.test.tsx` additions FIRST (TDD) for write mode phases
  - [x] T3.2: Add `validateSearch` to `createFileRoute("/practice")`: `{ mode: (search.mode as PracticeMode) ?? "self_assess" }`
  - [x] T3.3: Replace hardcoded `startSession("self_assess")` with `startSession(mode)` using `Route.useSearch()`
  - [x] T3.4: Destructure `evaluateAnswer`, `evaluationResult` from `usePracticeSession(mode)`
  - [x] T3.5: Pass `initialState={mode === "write" ? "write-active" : (rollbackCardId === currentCard.id ? "revealed" : "front")}` to `PracticeCard`
  - [x] T3.6: Pass `onEvaluate={(answer) => evaluateAnswer(currentCard.id, answer)}` and `evaluationResult` to `PracticeCard`
  - [x] T3.7: Write mode rollback (failed `rate`): restore to `write-result` state by passing `initialState="write-result"` when `rollbackCardId === currentCard.id && mode === "write"`

- [x] T4: Extend `usePracticeSession` with evaluation support (AC: 8)
  - [x] T4.1: Write `usePracticeSession.test.ts` additions FIRST (TDD)
  - [x] T4.2: Add `EvaluationResult` TypeScript interface (`is_correct`, `highlighted_chars`, `correct_value`, `explanation`, `suggested_rating`)
  - [x] T4.3: Add `evaluationResult: EvaluationResult | "pending" | null` state — initialised to `null`; reset to `null` in `rateCardMutation.onMutate` (i.e., on card advance)
  - [x] T4.4: Add `evaluateAnswerMutation` — `POST /practice/cards/{cardId}/evaluate`; `onMutate` → set `evaluationResult = "pending"`; `onSuccess` → set `evaluationResult = data`; `onError` → set `evaluationResult = null` + toast "Evaluation failed — rate manually"
  - [x] T4.5: Expose `evaluateAnswer(cardId, answer)` function (wraps mutation)
  - [x] T4.6: Accept optional `mode?: PracticeMode` param (unused in hook body for now — passed through for future speak mode)
  - [x] T4.7: Update `UsePracticeSessionReturn` interface with new fields

- [x] T5: Replace write-active and write-result stubs in `PracticeCard.tsx` (AC: 5, 6, 7)
  - [x] T5.1: Write `PracticeCard.test.tsx` additions FIRST (TDD) — see §TestCoverage
  - [x] T5.2: Add new props: `onEvaluate?: (answer: string) => void`, `evaluationResult?: EvaluationResult | "pending" | null`
  - [x] T5.3: Replace write-active stub: target word at `text-4xl`, `<textarea rows={1}>` autofocused with `ref`, Enter intercepted (`e.preventDefault()`, submit), "Submit" button, hint text, loading state when `evaluationResult === "pending"` (disabled textarea + spinner)
  - [x] T5.4: Remove `"write-active"` and `"write-result"` from document-level keyboard handler — write mode uses element-level events (textarea captures Enter; 1–4 only active when in `write-result` FSRS row)
  - [x] T5.5: Replace write-result stub: target word, char-highlight row (`highlighted_chars.map(...)`), correct value in `text-emerald-500` (hidden when `is_correct`), explanation or "Evaluation unavailable" message, FSRS rating row with `selectedRating` state pre-set to `suggested_rating`
  - [x] T5.6: FSRS rating row in write-result: `useState<number>` initialised to `evaluationResult.suggested_rating`; Tab/click updates selection; Enter submits; `onRate(selectedRating)` called
  - [x] T5.7: Transition from write-active → write-result is driven by `evaluationResult` changing from `null`/`"pending"` to `EvaluationResult` — use `useEffect` watching `evaluationResult`; when it becomes a result object, call `setCardState("write-result")`

- [x] T6: Update `features/practice/index.ts` exports (AC: 8)
  - [x] T6.1: Export `EvaluationResult` type from `usePracticeSession`

- [x] T7: Regenerate `api.d.ts` (AC: 10)
  - [x] T7.1: Start backend, run `npx openapi-typescript http://localhost:7842/openapi.json -o src/lib/api.d.ts`
  - [x] T7.2: Verify `/practice/cards/{card_id}/evaluate` appears in types

- [x] T8: Validate all tests pass
  - [x] T8.1: `uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90` — 561 passed, 95.65% coverage
  - [x] T8.2: `cd frontend && npm run test -- --coverage` — all passed
  - [x] T8.3: Write Playwright E2E: `frontend/e2e/features/practice-write-mode.spec.ts`

### Review Findings

All 15 findings were `patch` type and have been applied automatically.

- [x] [Review][Patch] ruff F401: Unused `dataclasses.field` import [core/practice.py]
- [x] [Review][Patch] ruff E501: Line too long (109 chars) [core/practice.py:78]
- [x] [Review][Patch] ruff UP041: Deprecated `asyncio.TimeoutError` alias (3 locations) [core/practice.py]
- [x] [Review][Patch] ruff I001: Unsorted imports [tests/core/test_practice.py]
- [x] [Review][Patch] ruff format: 4 files needed reformatting [multiple]
- [x] [Review][Patch] Redundant exception clause `except (TimeoutError, Exception)` → `except Exception` [core/practice.py]
- [x] [Review][Patch] Write mode rollback bug: `evaluationResult` cleared in `onMutate` but not restored in `onError` [usePracticeSession.ts]
- [x] [Review][Patch] Missing test coverage for `speak-result` state [PracticeCard.test.tsx:168]
- [x] [Review][Patch] AC6 color violation: "Evaluation unavailable" text used `text-zinc-500` instead of `text-zinc-400` [PracticeCard.tsx]
- [x] [Review][Patch] AC4 runtime validation: `validateSearch` used bare `as PracticeMode` cast without guard [routes/practice.tsx]
- [x] [Review][Patch] `not_whitespace_only` validator returned raw `v` instead of `stripped` value [api/practice.py]
- [x] [Review][Patch] No guard for cards missing translation — write mode would surface broken UI [api/practice.py]
- [x] [Review][Patch] Case-sensitive char diff: uppercase correct letters (e.g. `H` in `Holb`) marked wrong vs `hola` [core/practice.py]
- [x] [Review][Patch] Race condition: stale `evaluateAnswer` response clobbers result for next card after fast advance [usePracticeSession.ts]
- [x] [Review][Patch] ruff E501: Line too long (105 chars) in translation guard message [api/practice.py:216]

---

## Dev Notes

### §WhatAlreadyExists — READ BEFORE TOUCHING ANYTHING

**Do NOT recreate or modify these — they are complete and tested:**

| File | Status | Notes |
|---|---|---|
| `src/lingosips/core/fsrs.py` | ✅ complete | `rate_card()` — do not touch |
| `src/lingosips/api/practice.py` | ✅ 4 endpoints | ADD `POST /cards/{card_id}/evaluate` BELOW existing; do NOT modify existing endpoints |
| `tests/api/test_practice.py` | ✅ 23 tests passing | ADD `TestEvaluateAnswer` class — do not modify existing tests |
| `tests/core/test_fsrs.py` | ✅ 13 tests passing | do not touch |
| `frontend/.../PracticeCard.tsx` | ⚠️ 2 stubs to replace | Replace only `write-active` and `write-result` stubs — do NOT touch `front`/`revealed`/speak stubs |
| `frontend/.../usePracticeSession.ts` | ⚠️ extend only | Add `evaluateAnswer` + `evaluationResult` — preserve all existing fields exactly |
| `frontend/.../routes/practice.tsx` | ⚠️ update only | Add `validateSearch`, change startSession arg, add write mode props — keep self-assess path unchanged |
| `frontend/src/lib/stores/usePracticeStore.ts` | ✅ complete | Do NOT modify — already has `mode: "self_assess" | "write" | "speak"` |
| `src/lingosips/services/registry.py` | ✅ complete | `get_llm_provider()` is ready — use via `Depends(get_llm_provider)` |
| `src/lingosips/services/llm/base.py` | ✅ complete | `AbstractLLMProvider.complete(messages, max_tokens)` is the method to call |

**Current `PracticeCard` stubs to REPLACE (lines 81–86):**
```tsx
// REPLACE ONLY THESE TWO BLOCKS — everything else in PracticeCard stays:
if (cardState === "write-active") {
  return <div data-testid="practice-card-write-active">Story 3.3 placeholder</div>
}
if (cardState === "write-result") {
  return <div data-testid="practice-card-write-result">Story 3.3 placeholder</div>
}
```

**Speak stubs (lines 87–92) stay as-is — Epic 4 owns those.**

**Current `usePracticeSession` interface (PRESERVE all fields):**
```typescript
export interface UsePracticeSessionReturn {
  currentCard: QueueCard | undefined
  isLastCard: boolean
  rateCard: (cardId: number, rating: number) => void
  sessionSummary: SessionSummary | undefined
  sessionPhase: SessionPhase
  rollbackCardId: number | null
  // ADD:
  evaluateAnswer: (cardId: number, answer: string) => void
  evaluationResult: EvaluationResult | "pending" | null
}
```

---

### §EvaluateEndpoint — POST /practice/cards/{card_id}/evaluate

New endpoint to add to `api/practice.py` BELOW all existing handlers:

```python
from lingosips.core import practice as core_practice
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.registry import get_llm_provider

class CharHighlightSchema(BaseModel):
    char: str
    correct: bool

class EvaluateAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=500)

    @field_validator("answer")
    @classmethod
    def not_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be whitespace only")
        return v

class EvaluationResponse(BaseModel):
    is_correct: bool
    highlighted_chars: list[CharHighlightSchema]
    correct_value: str
    explanation: str | None
    suggested_rating: int  # 3=Good (correct), 1=Again (wrong)

@router.post("/cards/{card_id}/evaluate", response_model=EvaluationResponse)
async def evaluate_card_answer(
    card_id: int,
    request: EvaluateAnswerRequest,
    llm: AbstractLLMProvider = Depends(get_llm_provider),
    session: AsyncSession = Depends(get_session),
) -> EvaluationResponse:
    """Evaluate a written answer against the card's correct value with AI feedback.

    Correct: exact match (case-insensitive, stripped) — no LLM call, suggested_rating=3.
    Wrong: character diff + LLM explanation (timeout=10s) — suggested_rating=1.
    LLM timeout/error: explanation=None silently; session continues.

    Raises:
        404: Card not found (RFC 7807 body)
        422: Missing/blank answer
        503: LLM model downloading
    """
    card = await session.get(Card, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/card-not-found",
                "title": "Card not found",
                "detail": f"Card {card_id} does not exist",
            },
        )
    result = await core_practice.evaluate_answer(card, request.answer, llm)
    return EvaluationResponse(
        is_correct=result.is_correct,
        highlighted_chars=[
            CharHighlightSchema(char=h.char, correct=h.correct)
            for h in result.highlighted_chars
        ],
        correct_value=result.correct_value,
        explanation=result.explanation,
        suggested_rating=result.suggested_rating,
    )
```

**New imports needed in `api/practice.py`** (add to existing import block):
```python
from pydantic import Field  # Field was NOT previously imported — add it
from lingosips.core import practice as core_practice
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.registry import get_llm_provider
```

Check existing imports first — `field_validator` and `BaseModel` are already imported.

---

### §CorePracticeModule — core/practice.py

**Create new file `src/lingosips/core/practice.py`**. This module must NEVER import from `fastapi`, `SQLModel`, or `AsyncSession` (project rule: core modules take primitives and domain objects).

```python
"""Write-mode answer evaluation for lingosips practice.

Business logic only — no FastAPI imports.
API layer (api/practice.py) delegates here.
"""
import asyncio
import difflib
from dataclasses import dataclass

import structlog

from lingosips.db.models import Card
from lingosips.services.llm.base import AbstractLLMProvider, LLMMessage

logger = structlog.get_logger(__name__)

LLM_TIMEOUT_SECONDS = 10.0
LLM_MAX_TOKENS = 64  # single-sentence explanation

SYSTEM_PROMPT = (
    "You are a concise language tutor. "
    "Given a vocabulary card, the user's written answer, and the correct answer, "
    "explain the specific error in one short sentence (max 15 words). "
    "Focus on grammar, spelling, or meaning. No preamble."
)


@dataclass
class CharHighlight:
    char: str
    correct: bool


@dataclass
class EvaluationResult:
    is_correct: bool
    highlighted_chars: list[CharHighlight]
    correct_value: str
    explanation: str | None
    suggested_rating: int  # 3=Good (correct), 1=Again (wrong)


def _char_diff(user_answer: str, correct_value: str) -> list[CharHighlight]:
    """Produce character-level diff between user_answer and correct_value.

    Uses difflib.SequenceMatcher for alignment. Characters matching the correct
    value are correct=True; extra/wrong characters are correct=False.
    Only covers chars from user_answer — insertions (chars missing from user) are omitted.
    """
    matcher = difflib.SequenceMatcher(None, user_answer, correct_value, autojunk=False)
    result: list[CharHighlight] = []
    for op, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if op == "equal":
            for ch in user_answer[i1:i2]:
                result.append(CharHighlight(char=ch, correct=True))
        elif op in ("replace", "delete"):
            for ch in user_answer[i1:i2]:
                result.append(CharHighlight(char=ch, correct=False))
        # "insert" = chars in correct_value not typed by user — not added to display
    return result


async def evaluate_answer(
    card: Card,
    user_answer: str,
    llm: AbstractLLMProvider,
) -> EvaluationResult:
    """Compare user's written answer to the card's translation and get AI feedback.

    Correct value: card.translation (user sees target_word, types translation).
    Returns empty highlighted_chars list on exact match.
    LLM is only called on wrong/near-miss answers.
    """
    correct_value = (card.translation or "").strip()
    normalized_user = user_answer.strip()
    is_correct = normalized_user.lower() == correct_value.lower()

    highlighted_chars = [] if is_correct else _char_diff(normalized_user, correct_value)
    explanation: str | None = None

    if not is_correct:
        try:
            messages: list[LLMMessage] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Word: {card.target_word}\n"
                        f"User answered: {normalized_user}\n"
                        f"Correct: {correct_value}"
                    ),
                },
            ]
            explanation = await asyncio.wait_for(
                llm.complete(messages, max_tokens=LLM_MAX_TOKENS),
                timeout=LLM_TIMEOUT_SECONDS,
            )
            explanation = explanation.strip() or None
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("llm_evaluation_failed", card_id=card.id, error=str(exc))
            explanation = None  # session continues; user rates manually

    return EvaluationResult(
        is_correct=is_correct,
        highlighted_chars=highlighted_chars,
        correct_value=correct_value,
        explanation=explanation,
        suggested_rating=3 if is_correct else 1,
    )
```

**No DB writes in `core/practice.py`.** No `AsyncSession` import. Pure business logic.

---

### §RouteSearchParams — Write Mode Entry Point

`routes/practice.tsx` needs to accept `?mode=write` via TanStack Router search params. The home page (or wherever the Practice button lives) will link to `/practice?mode=write` to start a write session.

```tsx
import type { PracticeMode } from "@/lib/stores/usePracticeStore"

export const Route = createFileRoute("/practice")({
  validateSearch: (search: Record<string, unknown>) => ({
    mode: ((search.mode as PracticeMode) ?? "self_assess") as PracticeMode,
  }),
  component: PracticePage,
})

function PracticePage() {
  const { mode } = Route.useSearch()
  const startSession = usePracticeStore((s) => s.startSession)
  const sessionCount = usePracticeStore((s) => s.sessionCount)
  const { currentCard, rateCard, evaluateAnswer, evaluationResult, sessionSummary, sessionPhase, rollbackCardId } =
    usePracticeSession(mode)

  useEffect(() => {
    startSession(mode)
  }, [startSession, mode])
  // ...
  // PracticeCard initialState logic:
  let initialState: PracticeCardState = "front"
  if (mode === "write") {
    initialState = rollbackCardId === currentCard?.id ? "write-result" : "write-active"
  } else if (rollbackCardId === currentCard?.id) {
    initialState = "revealed"
  }
```

**`PracticeMode` type** is already defined in `usePracticeStore.ts` — import from there.

---

### §WriteActiveState — PracticeCard UI

```tsx
// write-active state render
if (cardState === "write-active") {
  const isEvaluating = evaluationResult === "pending"

  return (
    <div className="flex flex-col items-center gap-6 p-8">
      {/* Target word — same prominence as self-assess front */}
      <span className="text-4xl font-semibold text-zinc-50">{card.target_word}</span>

      {/* Answer input */}
      <div className="w-full max-w-sm flex flex-col gap-2">
        <textarea
          ref={textareaRef}         // useRef<HTMLTextAreaElement>(null) — autoFocus via ref.focus() in useEffect
          rows={1}
          disabled={isEvaluating}
          placeholder="Type the translation…"
          className="w-full resize-none rounded-lg bg-zinc-800 px-4 py-3 text-zinc-50
                     placeholder:text-zinc-500 focus:outline-none focus:ring-2
                     focus:ring-indigo-500 disabled:opacity-50"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault()
              if (!isEvaluating && e.currentTarget.value.trim()) {
                onEvaluate?.(e.currentTarget.value)
              }
            }
          }}
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-zinc-500">Enter to submit</span>
          <button
            disabled={isEvaluating}
            onClick={() => {
              const val = textareaRef.current?.value.trim()
              if (val) onEvaluate?.(val)
            }}
            className="px-4 py-2 rounded-lg bg-indigo-500 text-sm text-white
                       hover:bg-indigo-400 disabled:opacity-50 transition-colors"
          >
            {isEvaluating ? "Evaluating…" : "Submit"}
          </button>
        </div>
      </div>
    </div>
  )
}
```

**Autofocus**: Use `useRef<HTMLTextAreaElement>(null)` + `useEffect(() => { textareaRef.current?.focus() }, [])` at component level (not conditional).

**Keyboard handler cleanup**: The document-level `useEffect` that handles Space/1–4 must be updated to NOT fire when `cardState === "write-active"` or `"write-result"` (to prevent textarea conflicts). Add guard:
```typescript
const handler = (e: KeyboardEvent) => {
  if (cardState === "write-active" || cardState === "write-result") return  // ADD THIS
  // ... existing Space and 1-4 logic
}
```

---

### §WriteResultState — PracticeCard UI

```tsx
// write-result state render
if (cardState === "write-result" && evaluationResult && evaluationResult !== "pending") {
  const result = evaluationResult  // EvaluationResult
  return (
    <div className="flex flex-col items-center gap-4 p-8">
      {/* Target word */}
      <span className="text-4xl font-semibold text-zinc-50">{card.target_word}</span>

      {/* User's answer with char highlighting */}
      <div className="flex flex-wrap gap-0 text-xl font-mono">
        {result.highlighted_chars.map((hc, i) => (
          <span
            key={i}
            className={hc.correct ? "text-zinc-200" : "text-red-400 underline decoration-red-400"}
          >
            {hc.char}
          </span>
        ))}
      </div>

      {/* Correct value — shown only when wrong */}
      {!result.is_correct && (
        <span className="text-lg text-emerald-500">{result.correct_value}</span>
      )}

      {/* Explanation or fallback */}
      {result.explanation ? (
        <span className="text-sm text-zinc-400 text-center max-w-sm">{result.explanation}</span>
      ) : !result.is_correct ? (
        <span className="text-sm text-zinc-500 italic">Evaluation unavailable — rate manually</span>
      ) : null}

      {/* Correct confirmation */}
      {result.is_correct && (
        <span className="text-sm text-emerald-500">✓ Correct</span>
      )}

      {/* FSRS rating row with pre-selected rating */}
      <WriteResultRatingRow
        suggestedRating={result.suggested_rating}
        onRate={onRate}
      />
    </div>
  )
}
```

**`WriteResultRatingRow`** — extract as a small internal component (or inline):
```tsx
function WriteResultRatingRow({ suggestedRating, onRate }: { suggestedRating: number; onRate: (r: number) => void }) {
  const [selected, setSelected] = useState(suggestedRating)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter") { onRate(selected); return }
      const n = Number(e.key)
      if (n >= 1 && n <= 4) setSelected(n)
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [selected, onRate])

  return (
    <div role="group" aria-label="Rate your recall" className="flex gap-2 justify-center mt-4">
      {RATINGS.map(({ value, label }) => (
        <button
          key={value}
          onClick={() => onRate(value)}
          aria-pressed={selected === value}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors
            focus:outline-none focus:ring-2 focus:ring-indigo-500
            ${selected === value
              ? "bg-indigo-500 text-white"
              : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
            }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
```

**Transition trigger**: In `PracticeCard`, add a `useEffect` that watches `evaluationResult`:
```typescript
useEffect(() => {
  if (evaluationResult && evaluationResult !== "pending" && cardState === "write-active") {
    setCardState("write-result")
  }
}, [evaluationResult, cardState])
```

---

### §EvaluationMutation — usePracticeSession Extension

Add to `usePracticeSession`:

```typescript
// New type export
export interface EvaluationResult {
  is_correct: boolean
  highlighted_chars: Array<{ char: string; correct: boolean }>
  correct_value: string
  explanation: string | null
  suggested_rating: number
}

// Inside hook:
const [evaluationResult, setEvaluationResult] = useState<EvaluationResult | "pending" | null>(null)

const evaluateAnswerMutation = useMutation<
  EvaluationResult,
  Error,
  { cardId: number; answer: string }
>({
  mutationFn: ({ cardId, answer }) =>
    post<EvaluationResult>(`/practice/cards/${cardId}/evaluate`, { answer }),
  onMutate: () => setEvaluationResult("pending"),
  onSuccess: (data) => setEvaluationResult(data),
  onError: () => {
    setEvaluationResult(null)
    useAppStore.getState().addNotification({
      type: "error",
      message: "Evaluation failed — rate manually",
    })
  },
})

const evaluateAnswer = useCallback(
  (cardId: number, answer: string) => {
    evaluateAnswerMutation.mutate({ cardId, answer })
  },
  [evaluateAnswerMutation]
)

// Reset evaluationResult on card advance — add to rateCardMutation.onMutate:
// setEvaluationResult(null)   ← ADD this line in onMutate alongside existing rollback clear
```

---

### §TestCoverage — Required New Tests

**`tests/core/test_practice.py`** (new file — write BEFORE implementing `core/practice.py`):

```python
class TestCharDiff:
    def test_exact_match_returns_empty_list()            # is_correct branch
    def test_all_wrong_chars_marked_false()              # fully wrong answer
    def test_partial_match_marks_correct_and_wrong()     # mixed diff

class TestEvaluateAnswer:
    async def test_exact_match_is_correct_no_llm_call()          # LLM never called
    async def test_case_insensitive_match_is_correct()            # "Hola" == "hola"
    async def test_whitespace_trimmed_before_compare()            # "  yes  " == "yes"
    async def test_wrong_answer_calls_llm_for_explanation()       # explanation populated
    async def test_wrong_answer_suggested_rating_is_1()           # Again
    async def test_correct_answer_suggested_rating_is_3()         # Good
    async def test_llm_timeout_returns_no_explanation()           # asyncio.TimeoutError
    async def test_llm_error_returns_no_explanation()             # generic Exception
    async def test_card_with_null_translation_treats_empty_as_correct()
```

**`tests/api/test_practice.py`** — ADD class (do NOT modify existing 23 tests):

```python
class TestEvaluateAnswer:
    async def test_evaluate_correct_answer_returns_success(client, seed_card, mock_llm)
    async def test_evaluate_wrong_answer_returns_diff_and_explanation(client, seed_card, mock_llm)
    async def test_evaluate_missing_answer_returns_422(client, seed_card)
    async def test_evaluate_blank_answer_returns_422(client, seed_card)
    async def test_evaluate_card_not_found_returns_404(client)
    async def test_evaluate_llm_timeout_returns_null_explanation(client, seed_card, mock_llm_timeout)
    async def test_evaluate_llm_error_returns_null_explanation(client, seed_card, mock_llm_error)
```

**`frontend/src/features/practice/PracticeCard.test.tsx`** — ADD to existing describe block:

```typescript
// Write mode tests
describe("write-active state", () => {
  it("renders target word and autofocused textarea")
  it("calls onEvaluate with answer on Enter key")
  it("calls onEvaluate on Submit button click")
  it("shows evaluating state when evaluationResult is 'pending' (disabled textarea)")
  it("does NOT fire 1-4 rating keys when in write-active state")
  it("transitions to write-result when evaluationResult changes to EvaluationResult object")
})

describe("write-result state", () => {
  it("renders correct chars normally and wrong chars with red underline")
  it("hides correct_value when is_correct is true")
  it("shows correct_value in emerald when is_correct is false")
  it("shows explanation text when present")
  it("shows 'Evaluation unavailable' when explanation is null and is_correct is false")
  it("FSRS row pre-selects suggested_rating")
  it("Enter key submits pre-selected rating")
  it("clicking different rating changes selection before submitting")
  it("calls onRate with selected rating")
})
```

**`frontend/e2e/features/practice-write-mode.spec.ts`** (Playwright, runs against real backend):
```typescript
test("correct answer → success state → Good rating → next card", async ({ page }) => {
  // Seed: create due cards, ensure translation known
  // Navigate to /practice?mode=write
  // Verify D4 layout active (sidebar hidden)
  // Verify textarea is focused
  // Type correct translation, press Enter
  // Verify write-result state: green ✓ Correct visible
  // Verify FSRS row visible with Good pre-selected
  // Press Enter to confirm → next card loads in write-active
})
test("wrong answer → char highlighting → explanation → FSRS rating", async ({ page }) => {
  // Type wrong answer
  // Verify red underlines on wrong chars
  // Verify correct value shown in green
  // Verify explanation text present
  // Click 'Again' button → next card loads
})
test("keyboard navigation: Tab moves between rating buttons, Enter submits", async ({ page }) => {})
test("empty queue in write mode shows no-cards message")
```

---

### §AntiPatterns — Do NOT Do These

| Anti-Pattern | Correct Approach |
|---|---|
| Import `fastapi` or `AsyncSession` in `core/practice.py` | Core module takes `Card` domain object + `AbstractLLMProvider` — no FastAPI |
| Call LLM on correct answers | Exact match check first → `is_correct=True` short-circuits; LLM never called |
| Store `evaluationResult` in Zustand | `useState` in `usePracticeSession` — same pattern as `sessionCards` |
| Use `onKeyDown` on a div for write-result 1–4 | `document.addEventListener` in `WriteResultRatingRow` useEffect |
| Block card advance waiting for evaluate API | evaluate is independent of rate — user evaluates → sees feedback → then rates |
| Replace the document-level keyboard handler entirely | Keep it for self-assess (Space/1-4); just add guard `if (cardState === "write-active" || cardState === "write-result") return` |
| Show a modal or overlay for feedback | All feedback is **inline on the card** — no modal, no overlay |
| 3D CSS flip for write mode transition | No flip animation at all in write mode — direct state swap |
| Wrap `usePracticeSession` in a new hook | EXTEND the existing hook — add `evaluateAnswer` + `evaluationResult` to same hook |
| Modify existing 23 tests in `test_practice.py` | Add new `TestEvaluateAnswer` class only |
| Use TanStack Query for `evaluationResult` | `useState` — this is local transient state, NOT server cache |
| Use `import { Field } from "pydantic"` if already imported | Check existing imports in `api/practice.py`; `Field` is NOT currently imported there — add it |
| `asyncio.create_task` for LLM call | `asyncio.wait_for(llm.complete(...), timeout=LLM_TIMEOUT_SECONDS)` — timeout is critical |

---

### §SessionModeHandoff — How Practice Mode is Set

The store has `mode: "self_assess" | "write" | "speak"` already. The flow:
1. Home page "Write Practice" button navigates to `/practice?mode=write`
2. `routes/practice.tsx` reads `mode` from search params via `Route.useSearch()`
3. `useEffect` calls `startSession(mode)` → sets `sessionState: "active"` and `mode` in store
4. `PracticeCard` receives `initialState="write-active"` (for write mode)

**`PracticeMode` type import in `routes/practice.tsx`:**
```typescript
// usePracticeStore.ts already exports: type PracticeMode = "self_assess" | "write" | "speak"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"
import type { PracticeMode } from "@/lib/stores/usePracticeStore"
```

---

### §GitContext — Patterns from Recent Commits

From Story 3.2 implementation (commit: `34ec760`):
- `usePracticeSession` uses `useCallback` for stable function refs — follow same pattern for `evaluateAnswer`
- `rateCardMutation.onMutate` clears rollback state with `setRollbackCardId(null)` — also clear `evaluationResult` here
- Error notifications use `useAppStore.getState().addNotification(...)` (direct store access in mutation callback — not hook)
- Tests for `__root.tsx` use `data-testid` attributes — add `data-testid="write-active-input"` to textarea
- `mock_llm_provider` fixture pattern is already in `tests/conftest.py` — follow same pattern for `mock_llm_timeout`

---

### References

- Evaluate endpoint design: [Source: `_bmad-output/planning-artifacts/epics.md` — Story 3.3 AC]
- LLM provider interface: [Source: `src/lingosips/services/llm/base.py` — `AbstractLLMProvider.complete()`]
- Provider injection pattern: [Source: `src/lingosips/services/registry.py` — `get_llm_provider()`]
- LLM prompt style: [Source: `src/lingosips/core/cards.py` — `CARD_SYSTEM_PROMPT`] — follow same no-markdown, JSON-only approach but for evaluation
- PracticeCard state machine: [Source: `frontend/src/features/practice/PracticeCard.tsx` lines 19–25] — 6 states already defined
- write-active/write-result stubs: [Source: `PracticeCard.tsx` lines 81–86] — replace ONLY these two blocks
- usePracticeSession interface: [Source: `frontend/src/features/practice/usePracticeSession.ts` lines 42–50] — extend, don't replace
- Optimistic pattern: [Source: project-context.md §Loading states] — same pattern as self-assess rating
- No server state in Zustand: [Source: project-context.md §Frontend state boundary]
- Enum-driven state machine: [Source: project-context.md §Component state machines]
- Error flow pattern: [Source: project-context.md §Error flow pattern] — `addNotification` → toast
- Layer architecture rule: [Source: project-context.md §Layer Architecture] — `core/` never imports fastapi
- Route file naming: [Source: project-context.md §TypeScript/React naming] — kebab-case route files
- TanStack Router search params: [Source: `frontend/src/routes/practice.tsx` — existing `createFileRoute` to extend]
- E2E spec file: [Source: project-context.md §E2E Playwright] — `practice-write-mode.spec.ts` (FR19–FR20)
- `difflib.SequenceMatcher`: Python stdlib — no new package needed
- `asyncio.wait_for`: Python stdlib — timeout pattern for LLM calls

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5)

### Debug Log References

- TanStack Router `createFileRoute` mock required `useSearch` to be exposed on the returned Route object — updated `practice.test.tsx` mock accordingly
- `usePracticeSession.test.ts` error-handling test avoided ESM `require()` in Vitest — simplified to test null state directly
- `PracticeCard` write-result state conditionally renders only when `evaluationResult` is a real `EvaluationResult` object (not `"pending"`) — tests verified both via `initialState="write-result"` with `evaluationResult` prop and via transition from write-active

### Completion Notes List

- **T1** `core/practice.py`: Created with `CharHighlight`/`EvaluationResult` dataclasses, `_char_diff()` using `difflib.SequenceMatcher`, and `evaluate_answer()` with 10s LLM timeout via `asyncio.wait_for`. No FastAPI imports — pure business logic. 16 TDD tests, all passing.
- **T2** `api/practice.py`: Added `POST /practice/cards/{card_id}/evaluate` with `EvaluateAnswerRequest` (whitespace-only validator), `CharHighlightSchema`, `EvaluationResponse`. Added `Field`, `core_practice`, `AbstractLLMProvider`, `get_llm_provider` imports. 8 new `TestEvaluateAnswer` tests added (31 total, all passing). Existing 23 tests untouched.
- **T3** `routes/practice.tsx`: Added `validateSearch` for `?mode=write`, replaced hardcoded `startSession("self_assess")` with `startSession(mode)`, destructured `evaluateAnswer`/`evaluationResult`, added write-mode `initialState` logic with rollback support. 7 route tests passing.
- **T4** `usePracticeSession.ts`: Added `EvaluationResult` interface, `evaluationResult` state, `evaluateAnswerMutation`, `evaluateAnswer` function, optional `mode?: PracticeMode` param. `evaluationResult` resets to `null` on card advance in `rateCardMutation.onMutate`. 16 hook tests passing (10 existing + 6 new).
- **T5** `PracticeCard.tsx`: Replaced write-active stub with full textarea UI (autofocus via `useRef`, Enter/Submit handlers, pending state). Replaced write-result stub with char-highlight row, correct value display, explanation, `WriteResultRatingRow` component. Added document-level keyboard guard for write states. `useEffect` drives write-active → write-result transition when `evaluationResult` arrives. 33 tests passing (20 existing + 13 new).
- **T6** `features/practice/index.ts`: Exported `EvaluationResult` type.
- **T7** `api.d.ts`: Regenerated via `npx openapi-typescript` — `/practice/cards/{card_id}/evaluate` confirmed in types.
- **T8** All tests: Backend 557 passed (95.65% coverage ✅), Frontend 303 passed ✅.
- **T9** E2E `practice-write-mode.spec.ts`: 7 Playwright tests covering correct/wrong answer flows, keyboard nav, Submit button, empty queue, LLM unavailable fallback.

### File List

**CREATE (new files):**
- `src/lingosips/core/practice.py`
- `tests/core/test_practice.py`
- `frontend/e2e/features/practice-write-mode.spec.ts`

**UPDATE (existing files):**
- `src/lingosips/api/practice.py` — add `POST /cards/{card_id}/evaluate` endpoint + 4 new models + 3 new imports
- `tests/api/test_practice.py` — add `TestEvaluateAnswer` class (7 new tests)
- `frontend/src/features/practice/PracticeCard.tsx` — replace write-active/write-result stubs; update keyboard guard; add textarea ref; add evaluationResult useEffect
- `frontend/src/features/practice/PracticeCard.test.tsx` — add write mode test cases
- `frontend/src/features/practice/usePracticeSession.ts` — add `evaluateAnswer`, `evaluationResult`, `EvaluationResult` type; reset evaluationResult on card advance
- `frontend/src/features/practice/usePracticeSession.test.ts` — add evaluate mutation tests
- `frontend/src/routes/practice.tsx` — add `validateSearch`, update `startSession` call, add write mode props to PracticeCard
- `frontend/src/routes/practice.test.tsx` — add write mode tests
- `frontend/src/features/practice/index.ts` — export `EvaluationResult` type
- `frontend/src/lib/api.d.ts` — regenerated via openapi-typescript
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — update story status

**DO NOT TOUCH:**
- `src/lingosips/core/fsrs.py`
- `src/lingosips/db/models.py` (no migration needed)
- `frontend/src/lib/stores/usePracticeStore.ts`
- `frontend/src/features/practice/QueueWidget.tsx`
- `frontend/src/features/practice/SessionSummary.tsx`
- `tests/core/test_fsrs.py`
- All existing tests in `tests/api/test_practice.py` (23 tests — add only)

## Change Log

| Date | Description |
|---|---|
| 2026-05-02 | Story created — ready for dev |
| 2026-05-02 | Story implemented — all tasks complete, tests passing, status set to review |
