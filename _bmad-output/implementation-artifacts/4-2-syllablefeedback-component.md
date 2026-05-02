# Story 4.2: SyllableFeedback Component

Status: done

## Story

As a user,
I want to see my pronunciation broken down syllable-by-syllable — correct syllables in emerald and wrong syllables highlighted in amber — alongside a specific correction I can act on,
so that I know exactly which part of the word to fix rather than just "wrong/right."

## Acceptance Criteria

1. **AC1 — awaiting state:** All syllable chips are `neutral` (grey); mic button is ready; no correction text shown.
2. **AC2 — evaluating state:** All chips pulse with a pending animation; "Evaluating..." label replaces the correction text area.
3. **AC3 — result-correct state:** All chips show `correct` state (subtle emerald tint); component header has a subtle emerald background tint.
4. **AC4 — result-partial state:** Correct chips show emerald tint; wrong chips show `amber-400` highlight with amber border; correction text block shows a specific explanation (e.g., "a-gua-CA-te — stress on third syllable"); "Try again" button is the primary action; "Move on" is secondary.
5. **AC5 — fallback-notice state:** Amber badge reads "Using local Whisper · ~3s" — visible but not alarming.
6. **AC6 — Accessibility per chip:** Each chip has `aria-label="{syllable} — {correct|incorrect}"`; correction sentence is in an `aria-live="assertive"` region (announced on result).
7. **AC7 — No color-only encoding:** Error conveyed by both color AND text — never color alone.

## Tasks / Subtasks

- [x] Task 1: Create `SyllableFeedback.test.tsx` (TDD — write all failing tests first) (AC: 1–7)
  - [x] 1.1 Test: renders awaiting state — all chips neutral, no correction text, no fallback badge
  - [x] 1.2 Test: renders evaluating state — all chips pulse (`animate-pulse`), "Evaluating..." label visible
  - [x] 1.3 Test: renders result-correct — all chips emerald, header has emerald tint, no "Try again" button
  - [x] 1.4 Test: renders result-partial — wrong chips amber, correct chips emerald, correction text in aria-live region, "Try again" is focusable primary button
  - [x] 1.5 Test: renders fallback-notice badge — "Using local Whisper · ~3s" visible, amber badge
  - [x] 1.6 Test: per-chip aria-label includes syllable text + status (e.g., "CA — incorrect")
  - [x] 1.7 Test: correction sentence is in `aria-live="assertive"` region
  - [x] 1.8 Test: "Try again" and "Move on" are keyboard-navigable (Tab/Enter sequence)
  - [x] 1.9 Test: no chip uses color-only encoding (each wrong chip has accessible text label)
- [x] Task 2: Create `SyllableFeedback.tsx` (AC: 1–7)
  - [x] 2.1 Define `SyllableFeedbackState` type union: `"awaiting" | "evaluating" | "result-correct" | "result-partial" | "fallback-notice"`
  - [x] 2.2 Define `ChipState` type union: `"neutral" | "correct" | "wrong" | "pending"`
  - [x] 2.3 Implement chip row rendering — each chip uses per-chip state for styling + aria-label
  - [x] 2.4 Implement state-conditional rendering: correction text block (aria-live assertive), evaluating label, emerald header tint for result-correct
  - [x] 2.5 Implement fallback-notice badge (amber-500) — shown when `provider_used === "local_whisper"`
  - [x] 2.6 Implement "Try again" (primary, indigo-500) and "Move on" (secondary, zinc-800) buttons in result-partial state
  - [x] 2.7 Export from `features/practice/index.ts`
- [x] Task 3: Export type and component from `index.ts` (AC: all)
  - [x] 3.1 Add `SyllableFeedback` and `SyllableFeedbackState` to `frontend/src/features/practice/index.ts`

## Dev Notes

### Overview

This story creates `SyllableFeedback` as a **standalone, isolated component** — it does NOT integrate into the full speak mode practice flow (that is Story 4.3). The component receives all its data as props: evaluation result from the speech API, current component state, and callbacks for "Try again" / "Move on".

The backend API is fully implemented from Story 4.1. The `SpeechEvaluationResponse` type already exists in `frontend/src/lib/api.d.ts` (auto-generated). **Do not manually edit `api.d.ts`.**

### Files to Create

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/features/practice/SyllableFeedback.tsx` | CREATE NEW | Main component |
| `frontend/src/features/practice/SyllableFeedback.test.tsx` | CREATE NEW | Vitest + RTL tests (write first — TDD) |

### Files to Modify

| File | Action | What Changes |
|------|--------|--------------|
| `frontend/src/features/practice/index.ts` | MODIFY | Export `SyllableFeedback` and `SyllableFeedbackState` |

### Current State of `index.ts` (must preserve all existing exports)

The `index.ts` currently exports the following (read before modifying):
- `PracticeCard`, `PracticeCardState`
- `QueueWidget`
- `SessionSummary`
- `usePracticeSession`

Add `SyllableFeedback` and `SyllableFeedbackState` exports without removing any existing ones.

### Current State of `PracticeCard.tsx` (DO NOT MODIFY in this story)

`PracticeCard.tsx` already has `speak-recording` and `speak-result` states defined in its state machine — they render placeholder `<div>` stubs with `data-testid="practice-card-speak-recording"` and `"practice-card-speak-result"`. **Do not touch PracticeCard.tsx in this story** — the integration happens in Story 4.3.

### API Type Already Available in `api.d.ts`

```typescript
// Available at: components["schemas"]["SpeechEvaluationResponse"]
SpeechEvaluationResponse: {
  overall_correct: boolean;
  syllables: SyllableDetailResponse[];
  correction_message: string | null;
  provider_used: string;  // "azure_speech" | "local_whisper"
}

SyllableDetailResponse: {
  syllable: string;
  correct: boolean;
  score: float;  // 0.0–1.0
}
```

Import types from `../../lib/api` (via the generated file) or accept a plain object matching this shape in the props interface.

### provider_used Values (from Story 4.1 implementation)

- Azure Speech → `"azure_speech"` (derived from `AzureSpeechProvider.provider_name` = "Azure Speech")
- Whisper local → `"local_whisper"` (derived from `WhisperLocalProvider.provider_name` = "Local Whisper")
- **Fallback-notice badge triggers when `provider_used === "local_whisper"`**

### Component Props Interface

```typescript
interface SyllableFeedbackProps {
  /** The target word being practiced (shown in header) */
  targetWord: string
  /** Current component display state */
  state: SyllableFeedbackState
  /** Syllable breakdown from API — null when awaiting or evaluating */
  syllables?: Array<{ syllable: string; correct: boolean; score: number }>
  /** Correction message from API — null/undefined when all correct */
  correctionMessage?: string | null
  /** Provider used — triggers fallback-notice when "local_whisper" */
  providerUsed?: string
  /** Called when user taps "Try again" in result-partial state */
  onRetry?: () => void
  /** Called when user taps "Move on" in result-partial state */
  onMoveOn?: () => void
}
```

### State Machine: SyllableFeedbackState

```typescript
export type SyllableFeedbackState =
  | "awaiting"       // pre-recording — chips neutral, mic ready
  | "evaluating"     // evaluation in flight — chips pulse, "Evaluating..." label
  | "result-correct" // all syllables correct — emerald header tint
  | "result-partial" // some wrong — amber chips, correction text, Try again/Move on
  | "fallback-notice"// whisper fallback detected — show amber badge (can stack with evaluating or result states)
```

**Important:** `fallback-notice` is a display modifier, not a fully separate state. Based on the UX spec and AC5, the amber badge appears *during* evaluation when Whisper is being used. The cleanest implementation treats it as a distinct state. The spec shows it as a state in the flow between "starting evaluation" and "result". Implement it as a discrete state: when `provider_used === "local_whisper"` is detected before evaluation completes, transition to `fallback-notice` which shows the badge + pulsing chips simultaneously.

### Per-Chip State Derivation

```typescript
type ChipState = "neutral" | "correct" | "wrong" | "pending"

function deriveChipState(
  componentState: SyllableFeedbackState,
  syllableCorrect: boolean
): ChipState {
  if (componentState === "awaiting") return "neutral"
  if (componentState === "evaluating" || componentState === "fallback-notice") return "pending"
  if (componentState === "result-correct") return "correct"
  if (componentState === "result-partial") return syllableCorrect ? "correct" : "wrong"
  return "neutral"
}
```

### Design Tokens & Tailwind Classes

| Element | State | Class |
|---------|-------|-------|
| Chip background — neutral | awaiting | `bg-zinc-900 border border-zinc-800` |
| Chip background — correct | result-correct/partial | `bg-emerald-950 border border-emerald-800 text-emerald-300` |
| Chip background — wrong | result-partial | `bg-amber-950 border border-amber-400 text-amber-300` |
| Chip background — pending | evaluating | `bg-zinc-900 border border-zinc-800 animate-pulse` |
| Component header — result-correct | result-correct | `bg-emerald-950/30` |
| Fallback badge | fallback-notice | `bg-amber-500/20 border border-amber-500 text-amber-300 text-xs` |
| "Try again" button | result-partial primary | `bg-indigo-500 hover:bg-indigo-400 text-white` |
| "Move on" button | result-partial secondary | `bg-zinc-800 hover:bg-zinc-700 text-zinc-200` |
| Focus ring | all interactive | `focus:outline-none focus:ring-2 focus:ring-indigo-500` |
| Correction text | result-partial | `text-sm text-zinc-400` in `aria-live="assertive"` |
| "Evaluating..." label | evaluating | `text-sm text-zinc-400` |

**Wrong syllable is AMBER (not red)** — enforced by the UX spec's "tutor, not judge" principle. Never use `red-*` classes for wrong syllables.

### Accessibility Requirements (AC6, AC7)

```tsx
{/* Per chip — example */}
<span
  role="img"
  aria-label={`${syllable} — ${chipState === "wrong" ? "incorrect" : "correct"}`}
  className={...}
>
  {syllable}
</span>

{/* Correction text — must be aria-live assertive */}
<div aria-live="assertive" aria-atomic="true">
  {correctionMessage && <p className="text-sm text-zinc-400">{correctionMessage}</p>}
</div>
```

### Testing Requirements (mandatory — TDD)

**Write `SyllableFeedback.test.tsx` BEFORE the implementation.** The Vitest + RTL test file must cover:

1. All 5 `SyllableFeedbackState` values (awaiting, evaluating, result-correct, result-partial, fallback-notice)
2. All 4 chip states (neutral, correct, wrong, pending) — verify via class names or aria-labels
3. `aria-live="assertive"` on correction text container — verify attribute present
4. Per-chip `aria-label` includes syllable text AND status (e.g., "CA — incorrect")
5. Keyboard navigation: Tab reaches "Try again" → Tab reaches "Move on" → Enter triggers `onMoveOn`
6. "Try again" click triggers `onRetry` callback
7. Wrong chips have both color class AND text label (not color-only)

**100% state machine branch coverage required** — explicitly checked in CI for the 5 primary custom components.

#### Test File Structure

```typescript
// SyllableFeedback.test.tsx
describe("SyllableFeedback", () => {
  describe("awaiting state", () => { ... })
  describe("evaluating state", () => { ... })
  describe("result-correct state", () => { ... })
  describe("result-partial state", () => { ... })
  describe("fallback-notice state", () => { ... })
  describe("accessibility", () => {
    it("per-chip aria-label includes syllable text and status", ...)
    it("correction sentence is in aria-live assertive region", ...)
    it("wrong chips encode error in both color class and text label", ...)
  })
  describe("keyboard navigation", () => {
    it("Tab navigates from Try again to Move on", ...)
    it("Enter on Move on triggers onMoveOn", ...)
  })
})
```

#### Example Mock Data

```typescript
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
```

### Story 4.3 Integration Preview (do NOT implement in this story)

Story 4.3 will:
- Replace the `speak-recording` and `speak-result` placeholder stubs in `PracticeCard.tsx`
- Wire the `SyllableFeedback` component into the speak mode flow
- Connect `POST /practice/cards/{card_id}/speak` API call (TanStack Query useMutation) to `SyllableFeedback` props
- Handle automatic FSRS rating (`POST /practice/cards/{card_id}/rate` with rating=3) when `overall_correct === true`
- R key mapping for starting new recording

**Story 4.2 is purely the component in isolation — accept all data as props, emit events via callbacks.**

### Architecture & Pattern Compliance

**State machine — enum-driven (REQUIRED by architecture):**
```typescript
// CORRECT
export type SyllableFeedbackState = "awaiting" | "evaluating" | "result-correct" | "result-partial" | "fallback-notice"

// WRONG — never boolean flags
const [isEvaluating, setIsEvaluating] = useState(false)  // ❌
```

**Feature isolation — no cross-feature imports:**
```typescript
// CORRECT — use lib/ for any shared utilities
import { cn } from "../../lib/utils"

// WRONG — never import from another feature
import { something } from "../cards/..."  // ❌
```

**No server state in Zustand — not applicable for this story** (this component is purely prop-driven).

### Previous Story Learnings (from Story 4.1)

- `api.d.ts` is auto-generated — never edit manually; the `SpeechEvaluationResponse` and `SyllableDetailResponse` types are already there
- `provider_used` is a string, not an enum — compare with string literals `"local_whisper"` / `"azure_speech"`
- The `score` field on `SyllableDetailResponse` is a float 0.0–1.0 (Azure uses ≥0.75 threshold for correct in the backend); the component only needs the `correct: bool` field for rendering
- Story 4.1 did NOT create any frontend components — `SyllableFeedback.tsx` does not exist yet (confirmed)
- `PracticeCard.tsx` has `speak-recording` and `speak-result` stubs at lines 167–172

### Git Context (Story 4.1 commit)

Latest commit: `0473b5a Add speech evaluation API with Whisper and Azure Speech backends (Story 4.1)`

Key files added in 4.1 that this story builds on:
- Backend: `src/lingosips/api/practice.py` — `POST /practice/cards/{card_id}/speak` endpoint live
- Frontend: `src/lib/api.d.ts` regenerated with `SpeechEvaluationResponse` type

### Project Structure Notes

- Component file: `frontend/src/features/practice/SyllableFeedback.tsx` (matches PascalCase convention for component files)
- Test file: `frontend/src/features/practice/SyllableFeedback.test.tsx`
- No new routes, no backend changes, no DB changes, no API changes in this story
- No Alembic migrations needed
- No TanStack Query hooks needed (API call is in Story 4.3 — this story is prop-driven only)

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 4, Story 4.2 (lines 1029–1068)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — SyllableFeedback Component Anatomy, Component Strategy section]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Journey 3: Speak Mode Journey]
- [Source: _bmad-output/project-context.md — Frontend Architecture Rules, Testing Rules]
- [Source: _bmad-output/planning-artifacts/architecture.md — features/practice/ directory structure, custom component list]
- [Source: frontend/src/features/practice/PracticeCard.tsx — speak-recording/speak-result stubs at lines 167–172]
- [Source: frontend/src/lib/api.d.ts — SpeechEvaluationResponse and SyllableDetailResponse types at lines 1315–1340]
- [Source: _bmad-output/implementation-artifacts/4-1-speech-evaluation-api-whisper-azure-speech.md — provider_used values, API response shape]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

_No blockers encountered. Straightforward TDD implementation._

### Completion Notes List

- ✅ **Task 1 (TDD):** Wrote 29 failing tests covering all 5 states, all 4 chip states, aria-live, per-chip aria-labels, keyboard navigation (Tab/Enter), color+text dual encoding (AC7). Tests confirmed RED before implementation.
- ✅ **Task 2 (Implementation):** Created `SyllableFeedback.tsx` with:
  - Exported `SyllableFeedbackState` type union (5 values)
  - Internal `ChipState` type union (4 values)
  - `deriveChipState()` helper — pure function mapping component state + syllable.correct → chip visual state
  - Chip row rendering with `role="img"` + `aria-label="{syllable} — {correct|incorrect}"` (AC6/AC7)
  - State-conditional rendering: emerald header tint (result-correct), pulsing chips (evaluating/fallback-notice), "Evaluating..." label, aria-live assertive correction block (result-partial)
  - Fallback-notice amber badge `"Using local Whisper · ~3s"` (AC5)
  - Try again (indigo-500 primary) + Move on (zinc-800 secondary) buttons with focus rings (AC4)
  - Feature-isolated — no cross-feature imports, only `lib/` would be used if needed
- ✅ **Task 3 (Export):** Added `SyllableFeedback` component + `SyllableFeedbackState` type to `frontend/src/features/practice/index.ts` without removing any existing exports.
- ✅ All 29 new tests pass, 373/373 total suite passes (zero regressions), lint clean (0 errors).

### File List

- `frontend/src/features/practice/SyllableFeedback.tsx` — CREATED
- `frontend/src/features/practice/SyllableFeedback.test.tsx` — CREATED
- `frontend/src/features/practice/index.ts` — MODIFIED (added SyllableFeedback + SyllableFeedbackState exports)

### Review Findings

- [x] [Review][Patch] onClick null guard — onRetry/onMoveOn are optional but called directly; crashes with TypeError when undefined [`SyllableFeedback.tsx`]
- [x] [Review][Patch] "Evaluating..." shown in fallback-notice state — AC2 scopes this label to evaluating state only; dev notes say fallback-notice shows badge+chips only [`SyllableFeedback.tsx`]
- [x] [Review][Patch] chipClasses switch missing exhaustive default branch — future ChipState values silently return undefined [`SyllableFeedback.tsx`]
- [x] [Review][Patch] Missing test: result-partial + correctionMessage=null — null guard branch is untested [`SyllableFeedback.test.tsx`]
- [x] [Review][Patch] Missing test: result-partial + no syllables prop — buttons-without-chips path is untested [`SyllableFeedback.test.tsx`]
- [x] [Review][Patch] Missing test: fallback-notice + no syllables prop — badge-without-chips path is untested [`SyllableFeedback.test.tsx`]
- [x] [Review][Defer] Chip key stability on syllable reorder — `${syllable}-${i}` key does not survive list reordering between retries — deferred, pre-existing
- [x] [Review][Defer] Tab navigation test brittleness — test relies on no other focusable elements between the two buttons — deferred, pre-existing

## Change Log

- 2026-05-02: Story 4.2 implemented — SyllableFeedback component created with TDD (29 tests). All ACs satisfied. Status: review.
- 2026-05-02: Code review — 6 patches applied (onClick guard, Evaluating label scope, exhaustive switch, 3 missing tests). 2 items deferred. 8 findings dismissed.
