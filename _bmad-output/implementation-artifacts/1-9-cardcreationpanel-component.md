# Story 1.9: CardCreationPanel Component

Status: done

## Story

As a user,
I want a creation input that instantly shows skeleton placeholders on Enter and reveals each card field sequentially as AI fills them,
so that card creation feels alive and fast — not like waiting for a spinner.

## Acceptance Criteria

1. **Given** I am on the home dashboard on desktop
   **When** the page loads
   **Then** the creation input is focused automatically with `aria-label="New card — type a word or phrase"`

2. **Given** I type a word and press Enter
   **When** the request begins
   **Then** skeleton placeholders appear immediately (zero delay) for translation, forms, example, and audio
   **And** the input is disabled during generation
   **And** no blocking spinner is displayed

3. **Given** the AI streams field data back
   **When** each field is ready
   **Then** it replaces the skeleton with a fade-in from slightly below, staggered 150ms between fields (translation → forms → example → audio)
   **And** each field slot has `aria-live="polite"` so screen readers announce content as it populates

4. **Given** the card fully populates and I save it
   **When** the save completes
   **Then** the input clears and refocuses automatically — ready for the next word
   **And** TanStack Query cache is invalidated for `["cards"]`

5. **Given** the LLM request fails
   **When** the error occurs
   **Then** a specific inline error appears below the input (e.g., "Local Qwen timeout after 10s")
   **And** the error is never the generic "Something went wrong"
   **And** a retry action is available

6. **Given** a user has `prefers-reduced-motion` enabled
   **When** fields populate
   **Then** all stagger animations are disabled — fields appear instantly

7. Vitest + RTL tests must cover all 5 component states (`idle`, `loading`, `populated`, `saving`, `error`), keyboard flow (Enter submits), and `aria-live` announcements.

## Tasks / Subtasks

> **TDD MANDATORY**: Write failing tests BEFORE writing implementation. All tasks marked [TDD] require tests first.

---

- [x] **T1: Add `streamPost()` to `src/lib/client.ts`** [TDD] (AC: 2, 5)
  - [x] T1.1: Define `SseEvent` interface: `{ event: "field_update" | "complete" | "error" | "progress"; data: unknown }`
  - [x] T1.2: Implement `streamPost(path, body, signal?)` as an `async function*` (AsyncGenerator) — POST with `Accept: text/event-stream`, parse ReadableStream line-by-line splitting on `\n\n`
  - [x] T1.3: SSE line parsing: accumulate `event:` and `data:` lines per event block; yield parsed `SseEvent` on double newline; JSON.parse the `data:` line value
  - [x] T1.4: If HTTP response is not ok, throw `ApiError` reusing the existing `handleResponse` error logic (same RFC 7807 parsing); do NOT yield an event for HTTP errors
  - [x] T1.5: If `signal` is aborted, stop reading and return (no error thrown)
  - [x] T1.6: Write Vitest tests for `streamPost()` — mock global `fetch` using `vi.stubGlobal`; verify: (a) yields correct events from a multi-event SSE stream, (b) throws `ApiError` on non-ok HTTP response, (c) stops cleanly when `signal.abort()` is called

- [x] **T2: Create `src/features/cards/useCardStream.ts`** [TDD] (AC: 2, 3, 4, 5)
  - [x] T2.1: Define `CardCreationState` type alias: `"idle" | "loading" | "populated" | "saving" | "error"` — this is the component state machine (NEVER boolean flags)
  - [x] T2.2: Define `CardFieldData` interface (fields arrive from SSE, types match exactly what `core/cards.py` emits — see §SseFieldTypes):
    ```typescript
    interface CardFieldData {
      translation?: string
      forms?: { gender: string | null; article: string | null; plural: string | null; conjugations: Record<string, string> }
      example_sentences?: string[]
      audio?: string  // relative URL e.g. "/cards/42/audio"
      card_id?: number
    }
    ```
  - [x] T2.3: Implement `useCardStream()` hook returning `{ state, fields, errorMessage, startStream, saveCard, discard, reset }`
  - [x] T2.4: `startStream(targetWord)` — aborts any in-flight request via `AbortController` ref, sets `state = "loading"`, clears fields/error, iterates `streamPost("/cards/stream", { target_word })`, applies `field_update` events to `fields`, sets `state = "populated"` on `complete`, sets `state = "error"` on `error` event
  - [x] T2.5: On `complete` event: extract `card_id` from event data and store in `fields.card_id`
  - [x] T2.6: `saveCard()` — transitions `populated → saving`, calls `queryClient.invalidateQueries({ queryKey: ["cards"] })`, then resets to `idle` after 300ms using `setTimeout` (brief save highlight window)
  - [x] T2.7: `discard()` — resets to `idle` without any API call (card remains in DB; DELETE endpoint is Story 2.1)
  - [x] T2.8: `reset()` — alias for `discard()` used in error state retry setup
  - [x] T2.9: Cleanup on unmount: `useEffect(() => () => abortControllerRef.current?.abort(), [])` — prevents state updates after unmount
  - [x] T2.10: Write Vitest tests for hook — mock `streamPost` with `vi.mock("../../lib/client")`:
    - Test `loading → populated` on successful stream (verify fields accumulate correctly)
    - Test `loading → error` on SSE error event
    - Test `loading → error` when `streamPost` throws `ApiError`
    - Test `populated → idle` after `saveCard()` call
    - Test `discard()` resets all state from populated
    - Test that `reset()` in error state returns to idle

- [x] **T3: Create `src/features/cards/CardCreationPanel.tsx`** [TDD] (AC: 1, 2, 3, 4, 5, 6)
  - [x] T3.1: Input element — `autoFocus`, `aria-label="New card — type a word or phrase"`, `disabled` when `state !== "idle"`, `value` controlled, `onKeyDown` handles Enter (calls `startStream`, clears input value) and Escape (calls `reset`)
  - [x] T3.2: **Loading state** — render 4 `<Skeleton />` placeholders (from `src/components/ui/skeleton.tsx`) in the card preview area; `aria-busy="true"` on the preview container
  - [x] T3.3: **Field reveal slots** (visible in `populated`/`saving` states) — each slot has `aria-live="polite"` — slots in order: Translation, Forms, Example Sentences, Audio
  - [x] T3.4: Translation slot: plain text, `text-lg` font weight
  - [x] T3.5: Forms slot: display `forms.article + forms.plural` if available; handle null fields gracefully (render nothing for null)
  - [x] T3.6: Example sentences slot: render `<ul>` with each sentence as `<li>`
  - [x] T3.7: Audio slot: if `fields.audio` URL is set, render `<audio src={fields.audio} controls preload="auto" />` that auto-plays once (use `onCanPlay` event + ref to call `.play()` once); if no audio after `complete` event, render muted "Not available" text in `text-zinc-400`
  - [x] T3.8: **150ms stagger animation** — each field slot has CSS `transition-delay` increasing by 150ms (translation: 0ms, forms: 150ms, example: 300ms, audio: 450ms); use `opacity-0 translate-y-1` → `opacity-100 translate-y-0` transition; wrap in `motion-safe:` Tailwind prefix (disables when `prefers-reduced-motion: reduce`)
  - [x] T3.9: **Save / Discard action row** — visible in `populated` state only: "Save card" primary `Button` calls `saveCard()`; "Discard" secondary/ghost `Button` calls `discard()`
  - [x] T3.10: **Error state** — inline `<p className="text-red-400 text-sm">` below the input showing the specific `errorMessage` (never "Something went wrong"); "Try again" `Button` calls `reset()` (which resets state to idle so user can retry by pressing Enter again)
  - [x] T3.11: **Saving state** — card preview area gets `ring-1 ring-emerald-500` border briefly; input stays disabled during this transition
  - [x] T3.12: After `saveCard()` resolves: input `ref.current.focus()` — refocus input for next word entry
  - [x] T3.13: Use `useRef` for input element to manage programmatic focus

- [x] **T4: Write `src/features/cards/CardCreationPanel.test.tsx`** [TDD] (AC: 7)
  - [x] T4.1: Mock `useCardStream` via `vi.mock("./useCardStream")` — control returned state/fields for each test case
  - [x] T4.2: Test `idle` state: input is visible + has `autoFocus`, preview area hidden, no error, no action row
  - [x] T4.3: Test `loading` state: 4 Skeleton elements visible, input disabled, no action row
  - [x] T4.4: Test `populated` state: field values rendered, Save/Discard buttons visible, input still disabled
  - [x] T4.5: Test `saving` state: action row hidden, input disabled (brief — component self-transitions)
  - [x] T4.6: Test `error` state: error message text visible (the specific message from mock), "Try again" button visible, input NOT disabled (user can retype after error)
  - [x] T4.7: Test keyboard flow — `userEvent.type(input, "{enter}")` triggers `startStream` mock
  - [x] T4.8: Test `aria-live="polite"` attribute present on each field slot (verify with `getAllByRole` or attribute query)
  - [x] T4.9: Test that input has `aria-label="New card — type a word or phrase"`
  - [x] T4.10: Test audio "Not available" renders when `fields.audio` is undefined after `complete`
  - [x] T4.11: Achieve 100% state machine branch coverage (required for the 5 primary custom components per project-context.md)

- [x] **T5: Create `src/features/cards/index.ts`** (public surface)
  - [x] T5.1: Export `{ CardCreationPanel }` only — do not export `useCardStream` (internal hook)

- [x] **T6: Update `src/routes/index.tsx`** (AC: 1)
  - [x] T6.1: Replace `HomePage` placeholder div with `<CardCreationPanel />`
  - [x] T6.2: Import `CardCreationPanel` from `"../features/cards"`

- [x] **T7: E2E test — `frontend/e2e/journeys/first-launch-card-creation.spec.ts`** (AC: 1–5)
  - [x] T7.1: Happy path — type a word → Enter → wait for populated state → Save → verify input cleared and refocused
  - [x] T7.2: Error path — mock a slow network or use a deliberately invalid word; verify specific error text appears (not generic)
  - [x] T7.3: Keyboard navigation — tab to Save button, press Space to save

- [x] **T8: TypeScript + Tailwind compliance**
  - [x] T8.1: `npx tsc --noEmit` — zero TypeScript errors (strict mode; no `any` types)
  - [x] T8.2: `npm run test -- --coverage` — all tests pass; 100% branch coverage on `CardCreationPanel` state machine

---

## Dev Notes

### §WhatAlreadyExists — DO NOT Recreate

| Existing | Location | What it provides |
|---|---|---|
| `<Skeleton />` component | `src/components/ui/skeleton.tsx` | shadcn/ui Skeleton — use `<Skeleton className="h-4 w-full" />` |
| `<Input />` component | `src/components/ui/input.tsx` | shadcn/ui Input — wraps `<input>` with Tailwind styles |
| `<Button />` component | `src/components/ui/button.tsx` | shadcn/ui Button — variants: `default`, `ghost`, `outline` |
| `<Card />` wrapper | `src/components/ui/card.tsx` | shadcn/ui Card — card container |
| `useAppStore.addNotification()` | `src/lib/stores/useAppStore.ts` | Error notifications go through this store → Toast |
| `ApiError` class | `src/lib/client.ts:12` | Already defined — reuse in `streamPost` error handling |
| `handleResponse` function | `src/lib/client.ts:28` | Already parses RFC 7807 errors — do NOT duplicate this logic |
| `client.ts` `get`/`post`/`put`/`del` | `src/lib/client.ts` | Existing API methods — `streamPost` is a NEW addition |
| `src/features/onboarding/` | `src/features/onboarding/` | Reference for feature folder structure (index.ts + co-located test) |
| `RightColumn` | `src/components/layout/RightColumn.tsx` | Already rendered in `__root.tsx`; has `{/* QueueWidget — Story 1.9 */}` placeholder — **do NOT pass QueueWidget children** (QueueWidget is out of scope for this story) |

### §SseFieldTypes — CRITICAL: Exact SSE Event Data Shapes

The backend (`core/cards.py`) emits these **exact** data shapes. The frontend must match these types precisely — mismatched types cause silent rendering bugs.

```typescript
// field_update event — data shape varies by field:
{ field: "translation", value: string }
{ field: "forms", value: {
    gender: string | null,   // "masculine" | "feminine" | "neuter" | null
    article: string | null,  // "el" | "la" | null
    plural: string | null,   // plural form or null
    conjugations: Record<string, string>  // e.g. {present_1s: "..."}, can be {}
  }
}
{ field: "example_sentences", value: string[] }  // exactly 2 items normally
{ field: "audio", value: string }  // relative URL: "/cards/42/audio" — ONLY emitted if TTS succeeded

// complete event:
{ card_id: number }

// error event:
{ message: string }  // specific message from backend, e.g. "Local Qwen timeout after 10s"
```

**CRITICAL — `forms` and `example_sentences` are NOT JSON strings in SSE events.** They are emitted as native JavaScript objects/arrays after JSON parsing by the SSE client. Contrast with the database where they are stored as `json.dumps(...)` strings — this distinction only matters when reading from `GET /cards/{card_id}` (Story 2.1), not in this story.

**Audio event is conditional** — if TTS fails, the `audio` field_update is silently skipped. The `complete` event still fires. The component must handle `fields.audio` being undefined after `complete`.

### §StreamPost — New Client.ts Function

Add this to `src/lib/client.ts` (after the existing `del` function):

```typescript
export interface SseEvent {
  event: "field_update" | "complete" | "error" | "progress"
  data: unknown
}

/**
 * POST to an SSE endpoint and yield parsed events.
 * This is the ONLY place fetch() is called for SSE — never call fetch() in feature hooks.
 * Requires POST (not EventSource which only supports GET).
 */
export async function* streamPost(
  path: string,
  body: unknown,
  signal?: AbortSignal
): AsyncGenerator<SseEvent> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    // Reuse same RFC 7807 parsing as handleResponse
    const contentType = response.headers.get("content-type") ?? ""
    if (contentType.includes("problem+json") || contentType.includes("application/json")) {
      const errBody = await response.json()
      throw new ApiError(
        response.status,
        errBody.type ?? `/errors/${response.status}`,
        errBody.title ?? response.statusText,
        errBody.detail
      )
    }
    throw new ApiError(response.status, `/errors/${response.status}`, response.statusText)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    let chunk: ReadableStreamReadResult<Uint8Array>
    try {
      chunk = await reader.read()
    } catch {
      break  // AbortError or network failure — stop iteration
    }

    if (chunk.done) break
    buffer += decoder.decode(chunk.value, { stream: true })

    // Split on double newline — SSE event separator
    const eventBlocks = buffer.split("\n\n")
    buffer = eventBlocks.pop() ?? ""  // last partial block stays in buffer

    for (const block of eventBlocks) {
      if (!block.trim()) continue
      let eventType = ""
      let dataStr = ""
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim()
        else if (line.startsWith("data: ")) dataStr = line.slice(6).trim()
      }
      if (eventType && dataStr) {
        yield { event: eventType as SseEvent["event"], data: JSON.parse(dataStr) }
      }
    }
  }
}
```

### §UseCardStream — Hook Implementation Pattern

```typescript
// src/features/cards/useCardStream.ts
import { useCallback, useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { streamPost, ApiError, type SseEvent } from "../../lib/client"

export type CardCreationState = "idle" | "loading" | "populated" | "saving" | "error"

export interface CardFieldData {
  translation?: string
  forms?: { gender: string | null; article: string | null; plural: string | null; conjugations: Record<string, string> }
  example_sentences?: string[]
  audio?: string
  card_id?: number
}

export function useCardStream() {
  const [state, setState] = useState<CardCreationState>("idle")
  const [fields, setFields] = useState<CardFieldData>({})
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const queryClient = useQueryClient()

  // Cleanup on unmount
  useEffect(() => () => { abortRef.current?.abort() }, [])

  const startStream = useCallback(async (targetWord: string) => {
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    const { signal } = abortRef.current

    setState("loading")
    setFields({})
    setErrorMessage(null)

    try {
      for await (const event of streamPost("/cards/stream", { target_word: targetWord }, signal)) {
        if (signal.aborted) return
        if (event.event === "field_update") {
          const { field, value } = event.data as { field: string; value: unknown }
          setFields((prev) => ({ ...prev, [field]: value }))
        } else if (event.event === "complete") {
          const { card_id } = event.data as { card_id: number }
          setFields((prev) => ({ ...prev, card_id }))
          setState("populated")
        } else if (event.event === "error") {
          const { message } = event.data as { message: string }
          setErrorMessage(message)
          setState("error")
        }
      }
    } catch (err) {
      if (signal.aborted) return
      setErrorMessage(err instanceof ApiError ? err.title : "Connection failed")
      setState("error")
    }
  }, [])

  const saveCard = useCallback(() => {
    setState("saving")
    queryClient.invalidateQueries({ queryKey: ["cards"] })
    setTimeout(() => {
      setState("idle")
      setFields({})
      setErrorMessage(null)
    }, 300)
  }, [queryClient])

  const discard = useCallback(() => {
    // Card is already in DB — no DELETE call here (DELETE is Story 2.1)
    // Discard just resets the UI
    abortRef.current?.abort()
    setState("idle")
    setFields({})
    setErrorMessage(null)
  }, [])

  const reset = discard  // alias — used from error state

  return { state, fields, errorMessage, startStream, saveCard, discard, reset }
}
```

### §CardCreationPanel — Component Structure

The component owns input state (`value`/`setValue`) but delegates streaming state to `useCardStream`.

```typescript
// src/features/cards/CardCreationPanel.tsx
export function CardCreationPanel() {
  const [inputValue, setInputValue] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const hasPlayedRef = useRef(false)  // prevent audio from replaying on re-render
  const { state, fields, errorMessage, startStream, saveCard, discard, reset } = useCardStream()

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && inputValue.trim() && state === "idle") {
      startStream(inputValue.trim())
      setInputValue("")
    }
    if (e.key === "Escape") {
      reset()
      setInputValue("")
    }
  }

  // Refocus input after save completes (state returns to idle)
  useEffect(() => {
    if (state === "idle") {
      hasPlayedRef.current = false  // reset audio play flag for next card
      inputRef.current?.focus()
    }
  }, [state])

  // ... render
}
```

**Input disabled states:** `state !== "idle"` — disabled during loading, populated, saving, error.

Wait — the error state should have the input re-enabled or at minimum the "Try again" button should let the user re-enter. Actually re-reading AC5: "a retry action is available". The retry resets to `idle`, enabling the input. The input itself should be re-enabled in `error` state so the user can edit the word before retrying. So: `disabled={state === "loading" || state === "saving"}` only.

**Audio autoplay:** Use `onCanPlay` on the `<audio>` element + a ref guard to play only once per card:

```typescript
<audio
  ref={audioRef}
  src={fields.audio}
  controls
  preload="auto"
  onCanPlay={() => {
    if (!hasPlayedRef.current && audioRef.current) {
      hasPlayedRef.current = true
      audioRef.current.play().catch(() => {
        // Autoplay blocked by browser policy — user can click controls manually
      })
    }
  }}
/>
```

### §FieldRevealAnimation — 150ms Stagger

Use Tailwind `transition-all duration-300` + conditional `opacity-0 translate-y-1` → `opacity-100 translate-y-0`. Apply `motion-safe:` prefix to prevent animation in reduced-motion contexts:

```tsx
// Each field slot — show when the field has data
<div
  className={cn(
    "transition-all duration-300 motion-safe:translate-y-0",
    fields.translation
      ? "opacity-100 translate-y-0"
      : "opacity-0 translate-y-1 pointer-events-none"
  )}
  style={{ transitionDelay: "0ms" }}  // translation: 0ms
  aria-live="polite"
>
  {fields.translation ?? <Skeleton className="h-5 w-3/4" />}
</div>
```

Field delays:
- Translation: `0ms`
- Forms: `150ms`
- Example sentences: `300ms`
- Audio: `450ms`

**`motion-safe:` prefix in Tailwind** — Tailwind v4 supports `@media (prefers-reduced-motion: no-preference)` via `motion-safe:`. Use `motion-safe:transition-all motion-safe:duration-300` to disable animation when reduced motion is preferred. The Tailwind v4 config already includes motion-safe utilities.

**Skeleton vs field slot:** In `loading` state, show `<Skeleton />` in ALL 4 slots (even if no field data yet). In `populated`/`saving` state, show field data with fade-in transitions.

### §SaveVsDiscard — Scope Clarification

- **Save**: The card is ALREADY persisted in the DB (backend committed it before emitting `complete`). Clicking Save just: (1) transitions UI through `saving → idle`, (2) invalidates `["cards"]` TanStack Query cache, (3) refocuses input.
- **Discard**: No API call. The card remains in the DB as an unlisted card. `DELETE /cards/{card_id}` is not implemented until Story 2.1. Add a TODO comment in the `discard()` function: `// TODO Story 2.1: call DELETE /cards/${fields.card_id} to actually remove the card`.
- **QueueWidget in RightColumn**: `RightColumn.tsx` has `{/* QueueWidget — Story 1.9 */}` comments. **QueueWidget is OUT OF SCOPE for Story 1.9.** Do NOT add children to `RightColumn`. The comments are forward references for future stories. Leave `RightColumn` as-is.

### §TestStrategy — Three-Layer Testing Approach

1. **`client.test.ts`** (or new `streamPost.test.ts`) — Unit-test the `streamPost` async generator:
   - Mock `globalThis.fetch` with `vi.stubGlobal("fetch", vi.fn())`
   - Use a `ReadableStream` that sends pre-built SSE chunks
   - Verify correct event parsing for multi-event streams
   - Verify `ApiError` thrown on 4xx/5xx responses

2. **`useCardStream.test.ts`** — Integration-test the hook:
   - Mock `streamPost` with `vi.mock("../../lib/client", () => ({ streamPost: vi.fn() }))`
   - Use `renderHook()` from `@testing-library/react` with a `QueryClientProvider` wrapper
   - Drive state machine with controlled generator sequences

3. **`CardCreationPanel.test.tsx`** — Component-test:
   - Mock the entire `useCardStream` hook: `vi.mock("./useCardStream")`
   - Render with `render(<CardCreationPanel />)` inside a `QueryClientProvider`
   - Verify each state machine branch with RTL queries
   - `screen.getByRole("textbox", { name: /new card/i })` for the input
   - Verify `aria-live="polite"` on all field slots

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `const [isLoading, setIsLoading] = useState(false)` | `type CardCreationState = "idle" \| "loading" \| ...` |
| `EventSource` API for `POST /cards/stream` | `EventSource` only supports GET — use `fetch()` with ReadableStream |
| Calling `fetch()` inside `useCardStream.ts` | `fetch()` ONLY in `client.ts` — hook calls `streamPost` from `lib/client` |
| `JSON.parse(fields.forms)` in component | `forms` in SSE events is already an object — no parsing needed |
| `JSON.parse(fields.example_sentences)` | Same — already an array from SSE, no parsing needed |
| Server data (card list) in Zustand | TanStack Query `["cards"]` owns all card server data |
| `useAppStore` to store card data | `useAppStore` is UI-only — use `useCardStream` local state |
| Cross-feature import (e.g., `import { X } from "../practice"`) | Only import from `src/lib/` for cross-feature needs |
| Audio autoplay without catch | `audio.play()` returns a Promise that may reject — always `.catch(() => {})` |
| `motion-reduce:` Tailwind prefix | Use `motion-safe:` — applies styles when motion is OK, naturally disables on reduce |
| `disabled={state !== "idle"}` for error state | Input should be enabled in error state so user can edit the word before retrying |
| Manually editing `api.d.ts` | NEVER — auto-generated; define inline types in `useCardStream.ts` for SSE shapes |
| `import type { ... }` from `api.d.ts` for `/cards/stream` | Not in `api.d.ts` yet (only `/health` and `/settings` are there) — define SSE types locally |

### §ProjectStructureNotes

New files to create (none exist yet — `features/` only has `onboarding/`):

```
frontend/src/
├── features/
│   ├── cards/                          ← NEW directory
│   │   ├── CardCreationPanel.tsx       ← NEW
│   │   ├── CardCreationPanel.test.tsx  ← NEW (co-located, matches onboarding pattern)
│   │   ├── useCardStream.ts            ← NEW
│   │   └── index.ts                   ← NEW (exports CardCreationPanel only)
├── lib/
│   └── client.ts                       ← MODIFIED: add SseEvent + streamPost
├── routes/
│   └── index.tsx                       ← MODIFIED: render <CardCreationPanel />
frontend/e2e/journeys/
│   └── first-launch-card-creation.spec.ts  ← NEW (was a stub; now implement)
```

No backend files modified. No new npm packages required — Tailwind `motion-safe:`, `@tanstack/react-query` `invalidateQueries`, `ReadableStream`, and `fetch` are already available.

### §PreviousStoryIntelligence

From Stories 1.7 + 1.8 (TDD learnings that apply to frontend):

- **TDD is non-negotiable**: Write failing tests BEFORE implementation. The project-context rule is a hard gate.
- **State machines over boolean flags**: `RightColumn.tsx` already implements `"expanded" | "collapsed"` — follow the exact same pattern.
- **`motion-safe:` vs `motion-reduce:`**: Tailwind's `motion-safe:` variant applies styles only when the user has NOT requested reduced motion. This is the right approach (additive, not subtractive).
- **`useEffect` cleanup pattern**: The `OnboardingWizard.tsx` uses `useEffect(() => () => cleanup(), [])` — same cleanup pattern required for `AbortController`.
- **QueryClient access in hooks**: `useQueryClient()` from `@tanstack/react-query` (v5 API) — do NOT import the QueryClient directly.
- **`vi.mock()` hoisting**: Vitest automatically hoists `vi.mock()` calls to the top of the file. Place them at module level, not inside test functions.
- **`@testing-library/user-event`**: Use `userEvent.setup()` + `await userEvent.type()` for keyboard interactions (not `fireEvent`).

From Story 1.8 review (patterns that transfer to frontend):
- **Clean teardown**: In hook tests, ensure `queryClient.clear()` in `afterEach` to prevent test bleed.
- **Async generators and `for await`**: The `for await` loop must handle `AbortError` — catch and check `signal.aborted` before setting state.

### References

- Story 1.9 acceptance criteria: [Source: _bmad-output/planning-artifacts/epics.md#Story 1.9]
- UX-DR1 CardCreationPanel design: [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Custom Components]
- `CardCreationState` type: `"idle" | "loading" | "populated" | "saving" | "error"` [Source: _bmad-output/project-context.md#Frontend Architecture Rules]
- SSE event envelope format: `event: {type}\ndata: {json}\n\n` [Source: src/lingosips/core/cards.py:47-56]
- Exact SSE event sequence: 1→translation, 2→forms, 3→example_sentences, 4→audio (optional), 5→complete [Source: src/lingosips/core/cards.py:196-256]
- `forms` value is an object (not JSON string) in SSE events: [Source: src/lingosips/core/cards.py:212]
- `example_sentences` value is a string[] (not JSON string) in SSE events: [Source: src/lingosips/core/cards.py:212]
- Audio conditional: emitted only if TTS succeeds; `complete` fires regardless: [Source: src/lingosips/core/cards.py:246]
- `client.ts` is the ONLY module calling `fetch()`: [Source: _bmad-output/project-context.md#Layer Architecture & Boundaries]
- TanStack Query key convention `["cards"]`: [Source: _bmad-output/project-context.md#TanStack Query key conventions]
- Never store server data in Zustand: [Source: _bmad-output/project-context.md#Frontend state boundary]
- 100% state machine branch coverage for 5 primary custom components: [Source: _bmad-output/project-context.md#Frontend components — Vitest + React Testing Library]
- `prefers-reduced-motion` handling: all stagger animations disabled: [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Animation Rules]
- Feature folder isolation — `src/features/{domain}/` never imports cross-feature: [Source: _bmad-output/project-context.md#Feature isolation]
- `routes/index.tsx` is currently a placeholder: [Source: frontend/src/routes/index.tsx]
- `RightColumn.tsx` QueueWidget placeholder: OUT OF SCOPE for this story: [Source: frontend/src/components/layout/RightColumn.tsx:27]
- Existing shadcn/ui components available: Skeleton, Input, Button, Card: [Source: frontend/src/components/ui/]
- `api.d.ts` does NOT yet include `/cards/stream` types — define inline: [Source: frontend/src/lib/api.d.ts]
- Tailwind v4 + shadcn/ui Zinc palette + `zinc-950` bg: [Source: _bmad-output/project-context.md#Technology Stack]
- E2E runs against real backend on port 7842 — NEVER mocked: [Source: _bmad-output/project-context.md#E2E — Playwright]

---

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5)

### Debug Log References

- T1 abort test: initial `ReadableStream.pull()` blocking approach timed out in jsdom — fixed with a direct mock reader that exposes `rejectSecondRead` via Promise executor, combined with `await Promise.resolve()` microtask yield to synchronize timing.
- T2 saveCard test: `vi.useFakeTimers()` breaks `waitFor` (RTL polls with `setInterval` which is faked) — removed fake timers entirely, used real `setTimeout` + `waitFor({ timeout: 2000 })` instead. Added `afterEach(() => vi.useRealTimers())` guard to prevent fake timer leaks across tests.
- T3 branch coverage: dead branches in `cn()` calls with redundant ternaries (`hasForms ? "opacity-100" : "opacity-0"` inside the `hasForms ?` guard) — removed all redundant ternaries, flattened to static class strings.
- T2 signal.aborted catch guard: test timing required the mock generator to explicitly listen for the `abort` event and throw, rather than checking `signal.aborted` synchronously, to ensure `signal.aborted === true` in the catch block.

### Completion Notes List

- T1: `streamPost()` async generator added to `src/lib/client.ts`. Exports `SseEvent` interface. Uses `ReadableStream` reader with double-newline SSE event block splitting. RFC 7807 error parsing reused from existing `handleResponse`. AbortSignal cancellation handled by catching reader.read() errors. 7 Vitest tests covering happy path, partial chunks, HTTP errors, and abort.
- T2: `useCardStream()` hook created at `src/features/cards/useCardStream.ts`. Implements `CardCreationState` enum machine (`idle|loading|populated|saving|error`). All 5 transitions tested: `loading→populated`, `loading→error` (SSE event), `loading→error` (thrown ApiError), `populated→saving→idle` (saveCard), `populated→idle` (discard), `error→idle` (reset). Added extra tests for signal.aborted mid-loop guard and catch guard. 12 tests total.
- T3+T4: `CardCreationPanel.tsx` implements all 5 state branches with proper Tailwind `motion-safe:` animation prefix, 150ms stagger via inline `style={{ transitionDelay }}`, `aria-live="polite"` on all 4 field slots, `aria-busy` on loading container, `ring-1 ring-emerald-500` saving highlight. Input disabled only during `loading|saving|populated`. 32 Vitest/RTL tests covering all state branches, keyboard flow (Enter/Escape), aria attributes, audio autoplay guard, and null form handling. CardCreationPanel.tsx achieves 100% branch coverage.
- T5: `src/features/cards/index.ts` exports only `CardCreationPanel` (not `useCardStream`).
- T6: `src/routes/index.tsx` updated — replaced placeholder div with `<CardCreationPanel />`.
- T7: E2E spec `first-launch-card-creation.spec.ts` fully implemented: happy path (type→Enter→save→refocus), error path (network intercept→specific error text), keyboard navigation (Tab to Save, Space). Uses `page.route()` for network interception in error test.
- T8: `npx tsc --noEmit` — 0 errors. All 90 tests pass. features/cards directory shows no uncovered lines in coverage report (100% statements, branches, functions, lines).

### File List

- `frontend/src/lib/client.ts` — MODIFIED: added `SseEvent` interface + `streamPost()` async generator
- `frontend/src/lib/streamPost.test.ts` — NEW: 7 Vitest tests for `streamPost()`
- `frontend/src/features/cards/useCardStream.ts` — NEW: `useCardStream()` hook with state machine
- `frontend/src/features/cards/useCardStream.test.ts` — NEW: 12 Vitest tests for `useCardStream()`
- `frontend/src/features/cards/CardCreationPanel.tsx` — NEW: main UI component
- `frontend/src/features/cards/CardCreationPanel.test.tsx` — NEW: 32 Vitest/RTL tests for `CardCreationPanel`
- `frontend/src/features/cards/index.ts` — NEW: public surface (exports `CardCreationPanel` only)
- `frontend/src/routes/index.tsx` — MODIFIED: replaced placeholder with `<CardCreationPanel />`
- `frontend/e2e/journeys/first-launch-card-creation.spec.ts` — MODIFIED: full E2E spec (happy path, error path, keyboard nav)

## Change Log

- 2026-05-01: Story 1.9 implemented — CardCreationPanel component with full TDD. Added `streamPost()` SSE async generator to client.ts; created `useCardStream` hook (state machine: idle/loading/populated/saving/error); created `CardCreationPanel` component with skeleton loading, staggered field reveal (motion-safe:), aria-live announcements, audio autoplay guard, save/discard/retry actions. Updated routes/index.tsx to render CardCreationPanel. Implemented full E2E journey spec. All 90 tests pass; zero TypeScript errors; features/cards achieves 100% coverage.
- 2026-05-01: Code review completed — 13 patches applied. All issues resolved. Story status: done.

---

### Review Findings

**Review date:** 2026-05-01
**Reviewer:** bmad-code-review (Blind Hunter + Edge Case Hunter + Acceptance Auditor)
**Final test run:** 96 tests passing, 0 failing (8 test files) | ESLint: 0 errors | tsc: 0 errors

#### Patched ✓ (13 items — all applied automatically)

| # | File | Issue | Fix |
|---|---|---|---|
| 1 | `client.ts` | `response.body` could be null — spec `!` assertion would throw untyped TypeError | Added explicit null guard: throw `ApiError` with `/errors/no-body` type |
| 2 | `client.ts` | Non-abort mid-stream read errors silently swallowed (`catch { break }`) — network resets appeared as clean end, no error state set | Changed to `catch (e) { if (signal?.aborted) break; throw e }` — propagates to `useCardStream` catch block |
| 3 | `client.ts` | `JSON.parse(dataStr)` throws on malformed SSE data, crashing entire stream | Wrapped in try/catch — malformed event skipped, stream continues |
| 4 | `client.ts` | `TextDecoder` not flushed after stream end — multi-byte characters split across final chunk silently dropped | Added `decoder.decode()` flush + remaining buffer processing after `chunk.done` |
| 5 | `client.ts` | Events in final SSE block (missing trailing `\n\n`) silently dropped | Process remaining `buffer` after loop for events without trailing double-newline |
| 6 | `useCardStream.ts` | `saveCard()` creates a `setTimeout` but never stores the ID — `discard()` and `startStream()` can't cancel it, causing stale state updates | Added `saveTimeoutRef`, cleared in `startStream`, `discard`, and unmount cleanup |
| 7 | `useCardStream.ts` | Error message fallback was generic `"Connection failed"` for non-ApiError throws (e.g. network resets) | Changed fallback to `err instanceof Error ? err.message : "Connection failed"` for specific messages (AC5) |
| 8 | `CardCreationPanel.tsx` | Animation was a no-op — `transitionDelay` on wrapper `div` doesn't propagate to children; content started at `opacity-100` so no transition could fire | Replaced with `tailwindcss-animate` keyframe classes (`animate-in fade-in-0 slide-in-from-bottom-1`) with `animationDelay` directly on content elements |
| 9 | `CardCreationPanel.tsx` | Card container conditionally removed from DOM in idle/error — `aria-live` regions unregistered before streaming starts, so screen readers miss first announcement (AC3) | Used `sr-only` Tailwind class instead of conditional rendering — container always in DOM, visually hidden in idle/error |
| 10 | `CardCreationPanel.tsx` | Input disabled during `error` state — user can't edit the word before retrying, contradicting AC5 and §AntiPatterns | `inputDisabled` changed to `state === "loading" \|\| state === "saving" \|\| state === "populated"` |
| 11 | `useCardStream.test.ts` | ESLint `require-yield` errors on 4 `async function*` mocks that only throw/await without yielding | Added `// eslint-disable-next-line require-yield` before each offending mock |
| 12 | `useCardStream.test.ts` | Test expected `"Connection failed"` but implementation now correctly returns `err.message` | Updated test name and expectation to `"Network error"` |
| 13 | `streamPost.test.ts` + `CardCreationPanel.test.tsx` | Missing coverage for 4 new `streamPost` behaviors + 2 component behaviors | Added 4 tests to `streamPost.test.ts` (null body, non-abort error, malformed JSON, missing `\n\n`); added 2 tests to `CardCreationPanel.test.tsx` (aria-live always-in-DOM, specific error message) |

#### Dismissed (0 items)

No findings were dismissed — all identified issues were valid and patched.

#### Deferred (0 items)

No findings deferred — all items were within story scope and fixable without changing the public API.
