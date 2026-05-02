# Story 3.2: Self-Assess Practice Mode

Status: review

## Story

As a user,
I want to flip cards and rate my recall (Again / Hard / Good / Easy) with FSRS updating my schedule after each rating and the next card loading instantly,
so that I can build vocabulary retention through a fast, frictionless daily habit.

## Acceptance Criteria

1. **`POST /practice/session/start`** returns the due card queue for the session (up to `cards_per_session` from Settings, ordered by `due` ASC, filtered by `active_target_language`). Response is `list[QueueCard]` (same shape as `GET /practice/queue`). Returns `[]` when nothing is due.

2. **`GET /practice/next-due`** returns `{"next_due": "<ISO 8601 UTC datetime> | null"}` — the earliest `due` date across all cards for the active language, regardless of whether it is in the past. Used by `SessionSummary` and `QueueWidget` empty state.

3. **D4 layout activates** when `usePracticeStore.sessionState === "active"`: the icon sidebar and right column animate out (CSS `transition`); the main content area expands to centered single-column (max-w-xl, mx-auto). `prefers-reduced-motion` makes all transitions instant. D2 restores when `sessionState !== "active"`.

4. **`PracticeCard`** component in `front` state shows the target word at `text-4xl` and a muted hint "Space to reveal" below. Pressing **Space** or clicking the card transitions to `revealed` state.

5. **`PracticeCard`** in `revealed` state shows: translation, grammatical forms (if present), example sentence (if present), and the FSRS rating row sliding up from below: **Again · Hard · Good · Easy** (keyboard: **1–4**, Tab navigates). Pressing a rating key or clicking a button submits the rating.

6. **Rating submission is optimistic** — next card loads immediately (60fps, no blocking spinner). `POST /practice/cards/{card_id}/rate` fires in the background. On API failure, a toast notification is shown and the rating can be re-submitted.

7. **First 3 practice sessions**: each FSRS rating button shows a tooltip label (Again = "Forgot", Hard = "Struggled", Good = "Recalled", Easy = "Instant"). After 3 sessions, tooltips are hidden; labels reappear on `title` hover only.

8. **Session ends when the last card is rated.** `SessionSummary` renders: cards reviewed (count), recall rate (% of ratings ≥ 3 — Good or Easy), and next session due (formatted from `GET /practice/next-due`). After the summary, the user can click "Return to home" or it auto-returns after 5 seconds — D2 layout restores with animation.

9. **`QueueWidget` in-session count** is live: after each card is rated, `["practice", "queue"]` is invalidated so the "N remaining" count in the status bar is accurate. (This is the deferred fix from Story 3.1 code review.)

10. **`routes/practice.tsx`** is fully implemented replacing the current stub. It owns the D4 layout shell and renders `PracticeCard` or `SessionSummary` based on session phase.

11. **`api.d.ts`** regenerated after all new endpoints are added.

## Tasks / Subtasks

- [x] T1: Add `POST /practice/session/start` to `api/practice.py` (AC: 1)
  - [x] T1.1: Write `tests/api/test_practice.py::TestSessionStart` FIRST (TDD) — see §TestCoverage
  - [x] T1.2: Add `SessionStartResponse = list[QueueCard]` (no new model needed — same `QueueCard` shape)
  - [x] T1.3: Implement handler: fetch `cards_per_session` from Settings, query `cards WHERE due <= now AND target_language = active_lang ORDER BY due LIMIT cards_per_session`
  - [x] T1.4: Run tests to confirm they pass

- [x] T2: Add `GET /practice/next-due` to `api/practice.py` (AC: 2)
  - [x] T2.1: Write `tests/api/test_practice.py::TestNextDue` FIRST (TDD)
  - [x] T2.2: Add `NextDueResponse(next_due: datetime | None)` Pydantic model
  - [x] T2.3: Implement handler: `SELECT MIN(due) FROM cards WHERE target_language = active_lang`
  - [x] T2.4: Run tests

- [x] T3: Update `usePracticeStore.ts` — extend, do NOT replace (AC: 3, 8)
  - [x] T3.1: Add `sessionCount: number` field (persisted count of completed sessions, for first-3-tooltip logic)
  - [x] T3.2: Update `endSession()` to increment `sessionCount`
  - [x] T3.3: Use `zustand/middleware` `persist` to persist `sessionCount` to `localStorage` (key: `"practice-session-count"`)
  - [x] T3.4: Preserve all existing fields: `sessionState`, `mode`, `currentCardIndex`, `startSession`, `nextCard`

- [x] T4: Update `__root.tsx` D4 layout (AC: 3)
  - [x] T4.1: Import `usePracticeStore` in `__root.tsx`
  - [x] T4.2: Read `sessionState` from store; add conditional classes to sidebar and right column:
    - Sidebar: `transition-all duration-300 motion-reduce:transition-none` + `w-0 overflow-hidden opacity-0` when `active`
    - Right column: same pattern
    - Main area: `transition-all duration-300 motion-reduce:transition-none` + expands when `active`
  - [x] T4.3: Write Vitest test to verify sidebar is hidden when session is active

- [x] T5: Create `frontend/src/features/practice/usePracticeSession.ts` (AC: 6, 9)
  - [x] T5.1: Write `usePracticeSession.test.ts` FIRST (TDD)
  - [x] T5.2: Hook uses `useState<QueueCard[]>` for `sessionCards` (snapshot fetched via `POST /practice/session/start`)
  - [x] T5.3: `rateCard(cardId, rating)` mutation: optimistic advance to next card immediately; `POST /practice/cards/{card_id}/rate` in background; on error → toast + allow retry; on settled → `invalidateQueries(["practice", "queue"])`
  - [x] T5.4: Track `ratings: number[]` in `useState` (for recall rate in summary)
  - [x] T5.5: Expose: `{ currentCard, isLastCard, rateCard, sessionSummary, sessionPhase }`
  - [x] T5.6: `sessionPhase: "loading" | "practicing" | "complete"`

- [x] T6: Create `frontend/src/features/practice/PracticeCard.tsx` (AC: 4, 5, 6, 7)
  - [x] T6.1: Write `PracticeCard.test.tsx` FIRST (TDD) — all states + keyboard + accessibility
  - [x] T6.2: State machine: `type PracticeCardState = "front" | "revealed" | "write-active" | "write-result" | "speak-recording" | "speak-result"` — ALL 6 states defined even if only `front`/`revealed` are functional in this story
  - [x] T6.3: `front` state: target word at `text-4xl`, hint `text-sm text-zinc-500 mt-2 "Space to reveal"`, Space keydown or click → `revealed`
  - [x] T6.4: `revealed` state: translation `text-xl`, forms `text-sm text-zinc-400`, example `italic text-zinc-400`, FSRS rating row slides up (`transition-transform duration-200 motion-reduce:duration-0`)
  - [x] T6.5: FSRS rating row: 4 buttons with `aria-keyshortcuts="1"` etc; keyboard 1–4 handled at document level (not input capture) to avoid conflicts; Tab navigates row
  - [x] T6.6: Tooltip logic: `sessionCount < 3` from `usePracticeStore` → show tooltip labels; else hide (buttons remain, `title` attr for hover)
  - [x] T6.7: `write-active`, `write-result`, `speak-recording`, `speak-result` states: render a `<div data-testid="practice-card-{state}">Story {story} placeholder</div>` — implemented in Stories 3.3/3.4
  - [x] T6.8: Accept props: `card: QueueCard`, `onRate: (rating: number) => void`, `sessionCount: number`

- [x] T7: Create `frontend/src/features/practice/SessionSummary.tsx` (AC: 8)
  - [x] T7.1: Write `SessionSummary.test.tsx` FIRST (TDD)
  - [x] T7.2: Props: `cardsReviewed: number`, `recallRate: number` (0–1 fraction), `nextDue: string | null`
  - [x] T7.3: Display: "X cards reviewed", "X% recall rate", next due date formatted with `Intl.DateTimeFormat` (no date libraries); if `nextDue` is null → "All caught up!"
  - [x] T7.4: "Return to home" button → calls `usePracticeStore.endSession()` → navigates to `/`
  - [x] T7.5: Auto-return after 5 seconds using `useEffect` + `setTimeout`; cancelled on unmount
  - [x] T7.6: No stars, no streaks, no congratulations copy — tone is neutral and factual

- [x] T8: Implement `routes/practice.tsx` (AC: 3, 10)
  - [x] T8.1: Write `practice.test.tsx` FIRST (TDD) — loading, empty queue, card flip, rating, summary phases
  - [x] T8.2: Use `usePracticeSession` hook for all state
  - [x] T8.3: `loading` phase: skeleton or spinner
  - [x] T8.4: `practicing` phase: `<PracticeCard>` centered (max-w-xl mx-auto)
  - [x] T8.5: `complete` phase: `<SessionSummary>`
  - [x] T8.6: If session starts with 0 cards: show "No cards due — come back later" + "Return home" button

- [x] T9: Update `features/practice/index.ts` exports (AC: 10)
  - [x] T9.1: Export `PracticeCard`, `SessionSummary`, `usePracticeSession`

- [x] T10: Regenerate `api.d.ts` (AC: 11)
  - [x] T10.1: Start backend: `uv run uvicorn lingosips.api.app:app --port 7842`
  - [x] T10.2: `cd frontend && npx openapi-typescript http://localhost:7842/openapi.json -o src/lib/api.d.ts`
  - [x] T10.3: Verify `/practice/session/start` and `/practice/next-due` appear in types

- [x] T11: Validate all tests pass
  - [x] T11.1: `uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90` → 533 passed, 95.49% coverage
  - [x] T11.2: `cd frontend && npm run test -- --coverage` → 278 passed, 24 test files
  - [x] T11.3: Write Playwright E2E: `frontend/e2e/features/practice-self-assess.spec.ts`

---

## Dev Notes

### §WhatAlreadyExists — READ BEFORE TOUCHING ANYTHING

**Do NOT recreate or modify these — they are complete and tested:**

| File | Status | Notes |
|---|---|---|
| `src/lingosips/core/fsrs.py` | ✅ complete | `rate_card()` and `build_fsrs_card()` — do not touch |
| `src/lingosips/api/practice.py` | ✅ partial | `GET /practice/queue` + `POST /cards/{card_id}/rate` — ADD new endpoints below, do NOT modify existing |
| `tests/api/test_practice.py` | ✅ 14 tests passing | ADD new test classes — do not modify existing tests |
| `tests/core/test_fsrs.py` | ✅ 13 tests passing | do not touch |
| `frontend/.../QueueWidget.tsx` | ✅ complete | will receive one fix: query invalidation after rating (T5.3) |
| `frontend/.../usePracticeStore.ts` | ⚠️ extend only | EXTEND with `sessionCount` + `persist` — do NOT replace existing fields |
| `frontend/src/lib/stores/` | ✅ pattern set | `useAppStore`, `usePracticeStore`, `useSettingsStore` |

**Current `usePracticeStore` interface (PRESERVE all fields):**
```typescript
interface PracticeStore {
  sessionState: "idle" | "active" | "complete"
  mode: "self_assess" | "write" | "speak" | null
  currentCardIndex: number
  startSession: (mode: PracticeMode) => void
  endSession: () => void
  nextCard: () => void
}
```

**`routes/practice.tsx` is a stub** — replace the entire component body. The `createFileRoute("/practice")` export line stays.

**`frontend/src/features/practice/index.ts`** currently only exports `QueueWidget`. Add new exports.

---

### §SessionStartEndpoint — POST /practice/session/start

New endpoint to add to `api/practice.py` BELOW all existing handlers:

```python
@router.post("/session/start", response_model=list[QueueCard])
async def start_session(
    session: AsyncSession = Depends(get_session),
) -> list[QueueCard]:
    """Return the due card queue for a new session, limited by cards_per_session setting.

    Respects active_target_language and cards_per_session from Settings.
    Returns [] (never null) when nothing is due.
    """
    settings = await core_settings.get_or_create_settings(session)
    active_lang = settings.active_target_language
    limit = settings.cards_per_session  # default: 20
    now = datetime.now(UTC)

    result = await session.execute(
        select(Card)
        .where(Card.due <= now, Card.target_language == active_lang)
        .order_by(Card.due.asc())
        .limit(limit)
    )
    cards = result.scalars().all()
    return [QueueCard.model_validate(c) for c in cards]
```

No new imports needed beyond what's already in `api/practice.py`.

---

### §NextDueEndpoint — GET /practice/next-due

```python
class NextDueResponse(BaseModel):
    next_due: datetime | None = None


@router.get("/next-due", response_model=NextDueResponse)
async def get_next_due(
    session: AsyncSession = Depends(get_session),
) -> NextDueResponse:
    """Return the earliest due date across ALL cards for the active language.

    Includes cards due in the past (already overdue) and future.
    Returns {"next_due": null} if no cards exist.
    """
    settings = await core_settings.get_or_create_settings(session)
    active_lang = settings.active_target_language

    result = await session.execute(
        select(func.min(Card.due)).where(Card.target_language == active_lang)
    )
    min_due = result.scalar()
    return NextDueResponse(next_due=min_due)
```

Add `from sqlalchemy import func` to imports in `api/practice.py`.

---

### §D4LayoutTransition — Collapsing Sidebar and Right Column

The D4 layout is driven by `usePracticeStore.sessionState === "active"` in `__root.tsx`. The sidebar and right column get CSS transition classes. Do NOT restructure the layout — just add conditional width/opacity.

**Pattern (in `__root.tsx`):**
```tsx
const sessionState = usePracticeStore((s) => s.sessionState)
const isPracticing = sessionState === "active"

// Sidebar — currently ~64px wide
<aside className={`
  transition-all duration-300 motion-reduce:duration-0
  ${isPracticing ? "w-0 overflow-hidden opacity-0 pointer-events-none" : "w-16"}
`}>

// Right column — currently ~360px wide
<div className={`
  transition-all duration-300 motion-reduce:duration-0
  ${isPracticing ? "w-0 overflow-hidden opacity-0 pointer-events-none" : "w-90"}
`}>

// Main content area
<main className={`
  transition-all duration-300 motion-reduce:duration-0
  flex-1
`}>
```

**`prefers-reduced-motion`**: Tailwind's `motion-reduce:` prefix handles this — `motion-reduce:duration-0` makes transitions instant when the user has `prefers-reduced-motion: reduce` set.

---

### §usePracticeSessionHook — Session State Orchestration

**This hook is the heart of the practice session.** Key design decisions:

1. **Session cards are local state** (not Zustand, not TanStack Query cache) — they are a snapshot fetched once at session start. Use `useState<QueueCard[]>`.

2. **`POST /practice/session/start`** fetches the snapshot via `useMutation` triggered on mount. Use `useEffect` with `startSession` as the trigger.

3. **Rating is optimistic** — advance `currentCardIndex` immediately on submit; fire the API call in the background:

```typescript
const rateCardMutation = useMutation({
  mutationFn: ({ cardId, rating }: { cardId: number; rating: number }) =>
    post<RatedCardResponse>(`/practice/cards/${cardId}/rate`, { rating }),
  onMutate: ({ cardId }) => {
    // Advance immediately — 60fps, no spinner
    if (currentCardIndex >= sessionCards.length - 1) {
      advanceToSummary()
    } else {
      nextCard()  // usePracticeStore.nextCard()
    }
  },
  onError: (error) => {
    // Roll back currentCardIndex by one
    prevCard()
    useAppStore.getState().addNotification({
      type: "error",
      message: "Rating failed — please try again",
    })
  },
  onSettled: () => {
    // Invalidate queue so QueueWidget status bar count is accurate (fixes Story 3.1 deferred)
    void queryClient.invalidateQueries({ queryKey: ["practice", "queue"] })
  },
})
```

4. **Recall rate**: track ratings in `useState<number[]>`. `recallRate = ratings.filter(r => r >= 3).length / ratings.length`.

5. **`sessionPhase`** derived from store + local state:
   - `"loading"` — session cards not yet fetched
   - `"practicing"` — cards exist, `currentCardIndex < sessionCards.length`
   - `"complete"` — `currentCardIndex >= sessionCards.length` OR 0 cards returned

---

### §PracticeCardComponent — State Machine Details

**The full 6-state machine must be defined in this story** even though write/speak states are stubs. This avoids refactoring the type in Stories 3.3/3.4.

```typescript
type PracticeCardState =
  | "front"         // Shows target word — THIS STORY
  | "revealed"      // Shows all fields + FSRS row — THIS STORY
  | "write-active"  // Write input focused — Story 3.3
  | "write-result"  // AI feedback shown — Story 3.3
  | "speak-recording" // Mic active — Story 3.4 (Epic 4)
  | "speak-result"    // Syllable feedback — Story 3.4 (Epic 4)
```

**Keyboard handling**: Space and 1–4 must be added as `document.addEventListener("keydown", ...)` in a `useEffect` with cleanup, NOT as `onKeyDown` on a div (which requires focus). This ensures keyboard control works even when no button is focused.

```typescript
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (e.code === "Space" && cardState === "front") {
      e.preventDefault()  // prevent page scroll
      setCardState("revealed")
    }
    if (cardState === "revealed") {
      const ratingMap: Record<string, number> = { "1": 1, "2": 2, "3": 3, "4": 4 }
      const rating = ratingMap[e.key]
      if (rating) onRate(rating)
    }
  }
  document.addEventListener("keydown", handler)
  return () => document.removeEventListener("keydown", handler)
}, [cardState, onRate])
```

**Card transition between sessions**: When `currentCardIndex` advances (optimistic), the `PracticeCard` component unmounts and remounts with the next card — this automatically resets `cardState` to `"front"`. No explicit reset needed.

**FSRS rating buttons accessibility**:
```tsx
<div role="group" aria-label="Rate your recall">
  {RATINGS.map(({ value, label, shortcut, tooltip }) => (
    <button
      key={value}
      onClick={() => onRate(value)}
      aria-keyshortcuts={String(shortcut)}
      title={sessionCount >= 3 ? tooltip : undefined}
    >
      {label}
      {sessionCount < 3 && (
        <span className="sr-only">{tooltip}</span>
      )}
    </button>
  ))}
</div>
```

---

### §SessionCountPersistence — Tooltip Logic

`sessionCount` in `usePracticeStore` tracks how many sessions the user has completed. It must survive app restart → use `zustand/middleware`'s `persist`.

```typescript
import { persist } from "zustand/middleware"

export const usePracticeStore = create<PracticeStore>()(
  persist(
    (set, get) => ({
      // ... existing fields ...
      sessionCount: 0,
      endSession: () => set((s) => ({
        sessionState: "complete",
        sessionCount: s.sessionCount + 1,  // increment on session end
      })),
    }),
    {
      name: "practice-session-count",
      partialize: (state) => ({ sessionCount: state.sessionCount }),  // only persist count
    }
  )
)
```

**Do NOT wrap the entire store in `persist`** — only `sessionCount` needs persistence. `partialize` ensures other state (sessionState, currentCardIndex) is NOT persisted to localStorage (those reset on app restart intentionally).

---

### §SessionSummaryDisplay — Formatting

- **Cards reviewed**: plain integer — `12 cards reviewed`
- **Recall rate**: `Math.round(recallRate * 100)` → `"75% recall rate"`
- **Next due**: `Intl.DateTimeFormat` — no date libraries. Format as relative:
  - If `nextDue` is null: "All caught up!"
  - If `nextDue` is in the past or within 1 hour: "Cards due now"
  - Else: use `Intl.RelativeTimeFormat` with `"auto"` style: "in 3 hours", "in 2 days"
  
```typescript
function formatNextDue(nextDue: string | null): string {
  if (!nextDue) return "All caught up!"
  const diff = new Date(nextDue).getTime() - Date.now()
  if (diff <= 3_600_000) return "Cards due soon"
  const rtf = new Intl.RelativeTimeFormat("en", { style: "long" })
  const hours = diff / 3_600_000
  if (hours < 24) return rtf.format(Math.round(hours), "hour")
  return rtf.format(Math.round(hours / 24), "day")
}
```

---

### §TestCoverage — Required New Tests

**`tests/api/test_practice.py`** — ADD new test classes (do not modify existing):

```python
class TestSessionStart:
    async def test_session_start_returns_due_cards()            # 200, list[QueueCard]
    async def test_session_start_respects_cards_per_session()   # returns max N cards
    async def test_session_start_empty_when_no_cards_due()      # returns []
    async def test_session_start_filters_by_active_language()   # language isolation
    async def test_session_start_orders_by_due_asc()            # oldest due first

class TestNextDue:
    async def test_next_due_returns_earliest_due()              # min date returned
    async def test_next_due_null_when_no_cards()                # null when empty DB
    async def test_next_due_includes_overdue_cards()            # past due = valid next_due
    async def test_next_due_filters_by_active_language()        # language isolation
```

**`frontend/src/features/practice/PracticeCard.test.tsx`** — Vitest + RTL:

```typescript
describe("PracticeCard", () => {
  it("renders front state with target word and hint")
  it("flips to revealed on Space keypress")
  it("flips to revealed on card click")
  it("shows translation, forms, example in revealed state")
  it("shows FSRS rating row in revealed state")
  it("calls onRate with correct value on button click")
  it("calls onRate(1) on key 1 press when revealed")
  it("calls onRate(4) on key 4 press when revealed")
  it("shows tooltip labels when sessionCount < 3")
  it("hides tooltip labels when sessionCount >= 3")
  it("rating row has role=group with aria-label")
  it("Space key prevents page scroll (preventDefault)")
})
```

**`frontend/src/features/practice/SessionSummary.test.tsx`**:
```typescript
describe("SessionSummary", () => {
  it("shows cards reviewed count")
  it("shows recall rate as percentage")
  it("formats next due date with Intl.RelativeTimeFormat")
  it("shows 'All caught up!' when nextDue is null")
  it("auto-returns home after 5 seconds")
  it("cancels auto-return timer on unmount")
  it("'Return to home' button calls endSession and navigates")
})
```

**`frontend/e2e/features/practice-self-assess.spec.ts`** (Playwright, runs against real backend):
```typescript
test("full self-assess session: queue → flip × N → summary → home", async ({ page }) => {
  // Seed: create 3 due cards via API
  // Click Practice on home dashboard
  // Verify D4 layout (sidebar hidden)
  // Flip card (Space), verify revealed state
  // Rate with keyboard (3 = Good)
  // Repeat for all cards
  // Verify SessionSummary appears
  // Verify D2 layout restores after clicking Return to home
})
test("session with empty queue shows no-cards message")
test("keyboard navigation: 1–4 rating keys work")
test("failed rating shows notification and allows retry")
```

---

### §FsrsLibraryAPI — Critical Note from Story 3.1

The installed `fsrs` package uses `Scheduler` (NOT `FSRS`), has no `State.New` (use `State.Learning`), and `Card` has no `reps`/`lapses` fields. **`core/fsrs.py` is already correct** — do not reimport or re-implement FSRS. Story 3.2 never needs to import from the `fsrs` library.

---

### §AntiPatterns — Do NOT Do These

| Anti-Pattern | Correct Approach |
|---|---|
| Store `sessionCards` in Zustand | `useState<QueueCard[]>` in `usePracticeSession` — never server data in Zustand |
| Store `sessionCards` in TanStack Query cache | Local state only — this is a one-shot snapshot |
| Boolean flags in `PracticeCard` | `type PracticeCardState = "front" \| "revealed" \| ...` — always enum |
| `import { Scheduler } from "fsrs"` anywhere except `core/fsrs.py` | `core/fsrs.py` is the ONLY fsrs importer |
| Blocking spinner between cards | Optimistic: advance card immediately, fire API in background |
| 3D CSS flip animation | Vertical slide only (`translateY`) — spec explicitly says no 3D flip |
| `onKeyDown` prop on a div for Space/1–4 | `document.addEventListener` in `useEffect` with cleanup |
| Create a new `usePracticeStore` from scratch | EXTEND the existing store — add `sessionCount` and `persist` wrapper |
| Replace existing `tests/api/test_practice.py` | Add new test classes only — 14 existing tests must continue to pass |
| Manually edit `api.d.ts` | Always regenerated via `openapi-typescript` |
| Gratuitous copy in SessionSummary | Neutral and factual: numbers only, no stars, no confetti, no "Great job!" |

---

### §DeferredFromPreviousStory — Queue Count Fix

From Story 3.1 code review (deferred): "Queue count in 'in-session' status bar can go stale — no `refetchInterval`; Epic 3.2 owns this."

**Fix**: in `usePracticeSession.rateCardMutation.onSettled`, call:
```typescript
void queryClient.invalidateQueries({ queryKey: ["practice", "queue"] })
```
This forces `QueueWidget` to refetch after each card is rated, keeping the "N remaining" count accurate. No changes to `QueueWidget.tsx` itself are needed.

---

### §Settings — cards_per_session Field

`Settings` DB model already has `cards_per_session: int = Field(default=20)` from Story 2.3. `POST /practice/session/start` reads it via `core_settings.get_or_create_settings(session)`. No migration needed.

---

### References

- FSRS endpoint design: [Source: Story 3.1 dev notes §RateEndpointDesign] — existing `api/practice.py` patterns to follow
- `usePracticeStore` current state: [Source: `frontend/src/lib/stores/usePracticeStore.ts`] — extend, do not replace
- D4 layout spec: [Source: `_bmad-output/planning-artifacts/ux-design-specification.md` — "D4 · Focus Flow"] — sidebar hidden, centered single column
- PracticeCard UX spec: [Source: ux-design-specification.md §PracticeCard] — 6 states, vertical slide (not 3D flip), `prefers-reduced-motion`
- FSRS tooltip spec: [Source: ux-design-specification.md — "FSRS rating labels"] — shown first 3 sessions only
- SessionSummary spec: [Source: ux-design-specification.md] — "3 data points only: cards reviewed, recall rate, next session due; no stars, no streaks"
- Optimistic updates pattern: [Source: project-context.md §Loading states] — "no spinner during practice card transitions (60fps target)"
- Enum-driven state: [Source: project-context.md §Component state machines] — never boolean flags
- TanStack Query keys: [Source: project-context.md §TanStack Query key conventions] — `["practice", "queue"]`
- `zustand/middleware persist`: [Source: project-context.md §Zustand store files] — `useSettingsStore` already uses it as pattern reference
- `func.min` SQLAlchemy: standard `sqlalchemy.func` — no new imports beyond what's in `api/practice.py`
- `cards_per_session` field: [Source: `src/lingosips/db/models.py` Settings model] — default 20, already migrated
- Story 3.1 deferred queue staleness fix: [Source: `_bmad-output/implementation-artifacts/3-1-fsrs-scheduling-engine-practice-queue.md` §Review Findings]
- E2E test spec: [Source: project-context.md §E2E — Playwright] — `frontend/e2e/features/practice-self-assess.spec.ts` (FR17–18, FR24–25)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5 (2026-05-02)

### Debug Log References

- Fixed React Rules of Hooks violation: `usePracticeStore` was called after early returns in `__root.tsx` — moved to top of component before conditional branches.
- Added `localStorage` mock to `test-setup.ts` — Vitest's jsdom environment doesn't expose `window.localStorage.setItem` as a real function; zustand's `persist` middleware requires it when calling `setState` directly from tests.
- `PracticeCard` tooltip text was rendered twice (sr-only + visible), causing `getByText` to fail on "multiple elements found"; simplified to single visible span.
- `createFileRoute` mock in `practice.test.tsx` needed to be a curried function `(_path) => (config) => config` to match TanStack Router's actual API shape.

### Completion Notes List

- **T1**: `POST /practice/session/start` added to `api/practice.py`. Fetches `cards_per_session` from Settings, queries due cards ordered by `due ASC`, limited. 5 new tests in `TestSessionStart` — all pass.
- **T2**: `GET /practice/next-due` added with `NextDueResponse` Pydantic model and `func.min` SQLAlchemy query. 4 new tests in `TestNextDue` — all pass. Total backend: 533 tests, 95.49% coverage.
- **T3**: `usePracticeStore.ts` extended with `sessionCount: number` (default 0) and `prevCard()` action. Wrapped in `zustand/middleware persist` with `partialize` so only `sessionCount` persists to localStorage. All existing fields preserved.
- **T4**: `__root.tsx` updated — `usePracticeStore` called unconditionally at top of component; `data-testid="sidebar-wrapper"` and `data-testid="right-column-wrapper"` wrappers added with `w-0 overflow-hidden opacity-0 pointer-events-none` when `isPracticing`. 3 Vitest tests verify D4 behavior.
- **T5**: `usePracticeSession.ts` hook created. Session cards in `useState` (not Zustand). Optimistic rating via `useMutation` with `onMutate` advancing card immediately, `onError` rolling back + toast, `onSettled` invalidating `["practice", "queue"]` (deferred Story 3.1 fix). 9 tests pass.
- **T6**: `PracticeCard.tsx` component created. Full 6-state machine defined. Document-level keyboard handlers for Space (flip) and 1–4 (rate). Tooltip labels shown when `sessionCount < 3`. All 4 stub states render `data-testid` placeholders. 17 tests pass.
- **T7**: `SessionSummary.tsx` created. Uses `Intl.RelativeTimeFormat` for next-due formatting (no date libraries). Auto-returns after 5 seconds with timer cleanup on unmount. Neutral tone — no congratulations. 9 tests pass.
- **T8**: `routes/practice.tsx` fully implemented replacing stub. Renders loading spinner, PracticeCard (max-w-xl mx-auto), SessionSummary, or "No cards due" message based on `sessionPhase`. 5 tests pass.
- **T9**: `features/practice/index.ts` updated with exports for `PracticeCard`, `SessionSummary`, `usePracticeSession` and their types.
- **T10**: `api.d.ts` regenerated — verified `/practice/session/start` and `/practice/next-due` appear in types.
- **T11**: All validations pass: backend 533 tests (95.49% coverage), frontend 278 tests (24 files), E2E spec written.
- **test-setup.ts**: Added `localStorage` mock so zustand `persist` middleware works correctly in Vitest jsdom environment.

### File List

**CREATED (new files):**
- `frontend/src/features/practice/PracticeCard.tsx`
- `frontend/src/features/practice/PracticeCard.test.tsx`
- `frontend/src/features/practice/SessionSummary.tsx`
- `frontend/src/features/practice/SessionSummary.test.tsx`
- `frontend/src/features/practice/usePracticeSession.ts`
- `frontend/src/features/practice/usePracticeSession.test.ts`
- `frontend/src/routes/__root.test.tsx`
- `frontend/src/routes/practice.test.tsx`
- `frontend/e2e/features/practice-self-assess.spec.ts`

**UPDATED (existing files modified):**
- `src/lingosips/api/practice.py` — added `POST /session/start`, `GET /next-due` endpoints + `NextDueResponse` model + `func` import
- `tests/api/test_practice.py` — added `TestSessionStart` (5 tests) and `TestNextDue` (4 tests) classes
- `frontend/src/lib/stores/usePracticeStore.ts` — added `sessionCount` with `persist` middleware + `prevCard()` action
- `frontend/src/routes/practice.tsx` — replaced stub with full implementation
- `frontend/src/features/practice/index.ts` — added exports for new components and hook
- `frontend/src/routes/__root.tsx` — D4 layout: `usePracticeStore` import + conditional wrapper divs with testids
- `frontend/src/lib/api.d.ts` — regenerated via openapi-typescript
- `frontend/src/test-setup.ts` — added localStorage mock for Vitest jsdom compatibility
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — updated story status

**DO NOT TOUCH (unchanged as specified):**
- `src/lingosips/core/fsrs.py`
- `src/lingosips/db/models.py`
- `frontend/src/features/practice/QueueWidget.tsx`
- `tests/core/test_fsrs.py`

## Change Log

| Date | Description |
|---|---|
| 2026-05-02 | Story created — ready for dev |
| 2026-05-02 | Story implemented — all 11 tasks complete, 533 backend + 278 frontend tests pass, status → review |
