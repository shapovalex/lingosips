# Story 1.10: Service Status Indicator

Status: done

## Story

As a user,
I want to always see which AI service is active (cloud or local fallback) in the sidebar,
so that I understand the quality and speed of AI generation at a glance without navigating to Settings.

## Acceptance Criteria

1. **Given** no API keys are configured
   **When** the home dashboard renders
   **Then** `ServiceStatusIndicator` shows "Local Qwen" with an amber dot in the sidebar footer
   **And** the status is communicated as text — not color alone

2. **Given** OpenRouter is configured and responding normally
   **When** the indicator renders
   **Then** it shows "OpenRouter · [model name]" with a green dot

3. **Given** a service switch occurs (e.g., OpenRouter → Local Qwen)
   **When** the switch happens
   **Then** `aria-live="polite"` announces the change to screen readers within 1 second
   **And** the indicator updates to reflect the new active service

4. **Given** I click the ServiceStatusIndicator
   **When** it expands
   **Then** it shows: active service name, last call latency (or "—" if not yet tracked), last successful call timestamp (or "—"), and a "Configure →" link to Settings
   **And** it collapses on outside click

5. **Given** the app is on mobile (<768px)
   **When** I navigate to Settings
   **Then** the ServiceStatusIndicator appears in the Settings screen header

6. Vitest + RTL tests must cover all 5 states (`cloud-active`, `local-active`, `cloud-degraded`, `switching`, `error`) plus aria-live announcement and keyboard expansion (100% branch coverage required — one of the 5 primary custom components).

## Tasks / Subtasks

> **TDD MANDATORY**: Write failing tests BEFORE writing implementation. All tasks marked [TDD] require tests first.

---

- [x] **T1: Add `get_service_status_info()` to `src/lingosips/services/registry.py`** [TDD] (AC: 1, 2)
  - [x] T1.1: Define `ServiceStatusInfo` as a `dataclass` at module-top in `registry.py`:
    ```python
    from dataclasses import dataclass

    @dataclass
    class ServiceStatusInfo:
        llm_provider: str          # "openrouter" | "qwen_local"
        llm_model: str | None      # model name for openrouter; None for qwen_local
        speech_provider: str       # "azure" | "pyttsx3"
        last_llm_latency_ms: float | None = None     # reserved — not tracked yet
        last_llm_success_at: str | None = None       # reserved — not tracked yet
        last_speech_latency_ms: float | None = None  # reserved — not tracked yet
        last_speech_success_at: str | None = None    # reserved — not tracked yet
    ```
  - [x] T1.2: Implement `get_service_status_info() -> ServiceStatusInfo`:
    ```python
    def get_service_status_info() -> ServiceStatusInfo:
        """Return current provider status without instantiating providers.
        Reads credentials from keyring (via services/credentials.py) to determine active providers.
        Does NOT raise — always returns a status even if providers are misconfigured.
        """
        api_key = get_credential(OPENROUTER_API_KEY)
        if api_key:
            llm_provider = "openrouter"
            llm_model = get_credential(OPENROUTER_MODEL) or DEFAULT_OPENROUTER_MODEL
        else:
            llm_provider = "qwen_local"
            llm_model = None

        azure_key = get_credential(AZURE_SPEECH_KEY)
        azure_region = get_credential(AZURE_SPEECH_REGION)
        speech_provider = "azure" if (azure_key and azure_region) else "pyttsx3"

        return ServiceStatusInfo(
            llm_provider=llm_provider,
            llm_model=llm_model,
            speech_provider=speech_provider,
        )
    ```
  - [x] T1.3: Write `tests/test_registry_service_status.py`:
    - `test_returns_qwen_when_no_openrouter_key` — patch `get_credential` returning empty, verify `llm_provider == "qwen_local"` and `llm_model is None`
    - `test_returns_openrouter_when_key_configured` — patch `get_credential` returning key + model, verify `llm_provider == "openrouter"` and `llm_model == expected_model`
    - `test_returns_default_model_when_model_not_configured` — patch key exists but model empty, verify `llm_model == DEFAULT_OPENROUTER_MODEL`
    - `test_returns_pyttsx3_when_no_azure_credentials` — patch no azure, verify `speech_provider == "pyttsx3"`
    - `test_returns_azure_when_both_azure_credentials_configured` — patch both key+region, verify `speech_provider == "azure"`
    - `test_returns_pyttsx3_when_only_azure_key_but_no_region` — only key, no region → pyttsx3

- [x] **T2: Create `src/lingosips/api/services.py`** [TDD] (AC: 1, 2, 4)
  - [x] T2.1: Define Pydantic response models:
    ```python
    class LLMServiceStatus(BaseModel):
        provider: str       # "openrouter" | "qwen_local"
        model: str | None   # model name for openrouter; null for local
        last_latency_ms: float | None = None
        last_success_at: str | None = None

    class SpeechServiceStatus(BaseModel):
        provider: str       # "azure" | "pyttsx3"
        last_latency_ms: float | None = None
        last_success_at: str | None = None

    class ServiceStatusResponse(BaseModel):
        llm: LLMServiceStatus
        speech: SpeechServiceStatus
    ```
  - [x] T2.2: Implement `GET /services/status` endpoint:
    ```python
    @router.get("/status", response_model=ServiceStatusResponse)
    async def get_service_status() -> ServiceStatusResponse:
        """Return active LLM and speech provider status.
        Does NOT require DB session — reads from keyring only.
        Always returns 200 — never raises on provider misconfiguration.
        """
        info = get_service_status_info()
        return ServiceStatusResponse(
            llm=LLMServiceStatus(
                provider=info.llm_provider,
                model=info.llm_model,
                last_latency_ms=info.last_llm_latency_ms,
                last_success_at=info.last_llm_success_at,
            ),
            speech=SpeechServiceStatus(
                provider=info.speech_provider,
                last_latency_ms=info.last_speech_latency_ms,
                last_success_at=info.last_speech_success_at,
            ),
        )
    ```
  - [x] T2.3: Write `tests/test_services_api.py` (class `TestGetServiceStatus`):
    - `test_returns_qwen_local_when_no_openrouter_key` — mock `get_service_status_info` returning qwen status, verify `200` + `{ "llm": { "provider": "qwen_local", "model": null } }`
    - `test_returns_openrouter_when_key_configured` — mock returning openrouter status, verify `200` + `{ "llm": { "provider": "openrouter", "model": "openai/gpt-4o-mini" } }`
    - `test_returns_pyttsx3_for_speech_when_no_azure` — verify `{ "speech": { "provider": "pyttsx3" } }`
    - `test_returns_azure_for_speech_when_configured` — verify `{ "speech": { "provider": "azure" } }`
    - `test_latency_and_timestamp_are_null_when_not_tracked` — verify `last_latency_ms: null`, `last_success_at: null`
    - `test_always_returns_200_even_without_db` — endpoint must NOT have `Depends(get_session)`

- [x] **T3: Register services router in `src/lingosips/api/app.py`** (AC: 1)
  - [x] T3.1: In `create_app()`, import and include the services router:
    ```python
    from lingosips.api.services import router as services_router
    # ...
    application.include_router(services_router, prefix="/services", tags=["services"])
    ```
  - [x] T3.2: Add registration BEFORE the static files mount (same order as other routers)

- [x] **T4: Regenerate `frontend/src/lib/api.d.ts`** (AC: 1, 2)
  - [x] T4.1: Start the dev server (`make dev` or `uv run uvicorn ...`)
  - [x] T4.2: Run: `npx openapi-typescript http://localhost:7842/openapi.json -o frontend/src/lib/api.d.ts`
  - [x] T4.3: Verify the generated file includes `ServiceStatusResponse`, `LLMServiceStatus`, `SpeechServiceStatus` schemas
  - [x] T4.4: **NEVER manually edit `api.d.ts`** — it is always generated

- [x] **T5: Write `frontend/src/components/ServiceStatusIndicator.test.tsx`** [TDD — write FIRST] (AC: 6)
  - [x] T5.1: Mock `@/lib/client` using `vi.mock("@/lib/client", () => ({ get: vi.fn() }))`
  - [x] T5.2: Create helper `renderSSI()` that wraps `<ServiceStatusIndicator />` in `QueryClientProvider` with a fresh `QueryClient`
  - [x] T5.3: Test `cloud-active` state: mock `get` resolving `{ llm: { provider: "openrouter", model: "openai/gpt-4o-mini" } }` → verify "OpenRouter · openai/gpt-4o-mini" text, green dot (`bg-emerald-500`)
  - [x] T5.4: Test `local-active` state: mock `get` resolving `{ llm: { provider: "qwen_local" } }` → verify "Local Qwen" text, amber dot (`bg-amber-500`)
  - [x] T5.5: Test `switching` state: mock `get` never resolving (pending) → verify loading/switching indicator visible
  - [x] T5.6: Test `error` state: mock `get` rejecting → verify "AI unavailable" text, red dot (`bg-red-400`)
  - [x] T5.7: Test `cloud-degraded` state: mock query returning openrouter but `isStale` or custom degraded flag → verify amber dot with "OpenRouter · slow" (see §StateMapping for exact degraded trigger)
  - [x] T5.8: Test aria-live announcement: render `local-active` first, then re-render `cloud-active` → verify `aria-live="polite"` region updates with announcement text within 1s
  - [x] T5.9: Test expansion: click badge → panel visible with "Configure →" link pointing to `/settings`
  - [x] T5.10: Test outside click collapse: click badge to expand → click outside → panel collapses
  - [x] T5.11: Test keyboard: focus badge, press Enter → panel opens; press Escape → panel closes
  - [x] T5.12: Test `aria-expanded` attribute: `aria-expanded="false"` when collapsed, `aria-expanded="true"` when expanded
  - [x] T5.13: Test `role="status"` present on the always-visible status badge area
  - [x] T5.14: Achieve 100% branch coverage on all 5 state machine branches (required per project-context.md)

- [x] **T6: Create `frontend/src/components/ServiceStatusIndicator.tsx`** [TDD] (AC: 1, 2, 3, 4)
  - [x] T6.1: Define state machine type:
    ```typescript
    type ServiceIndicatorState = "cloud-active" | "local-active" | "cloud-degraded" | "switching" | "error"
    ```
  - [x] T6.2: Define inline response types (matching `api.d.ts` shapes):
    ```typescript
    interface LLMServiceStatus {
      provider: "openrouter" | "qwen_local"
      model: string | null
      last_latency_ms: number | null
      last_success_at: string | null
    }
    interface SpeechServiceStatus {
      provider: "azure" | "pyttsx3"
      last_latency_ms: number | null
      last_success_at: string | null
    }
    interface ServiceStatusData {
      llm: LLMServiceStatus
      speech: SpeechServiceStatus
    }
    ```
    **OR** after T4 regenerates `api.d.ts`, import from there: `import type { components } from "@/lib/api"` → `type ServiceStatusData = components["schemas"]["ServiceStatusResponse"]`
  - [x] T6.3: TanStack Query fetch:
    ```typescript
    const { data, isLoading, isError } = useQuery<ServiceStatusData>({
      queryKey: ["services", "status"],
      queryFn: () => get<ServiceStatusData>("/services/status"),
      refetchInterval: 30_000,   // poll every 30 seconds
      retry: 2,
    })
    ```
  - [x] T6.4: Derive `indicatorState` from query state (see §StateMapping)
  - [x] T6.5: Derive display text and dot color from state (see §DisplayMapping)
  - [x] T6.6: `aria-live` always-in-DOM region (CRITICAL — lesson from Story 1.9 review):
    ```tsx
    {/* Always in DOM — sr-only hides visually but keeps live region registered */}
    <div aria-live="polite" aria-atomic="true" className="sr-only">
      {statusAnnouncement}
    </div>
    ```
  - [x] T6.7: Track previous state ref for change detection and announcement (see §AnnouncementPattern)
  - [x] T6.8: Update `useAppStore.setServiceStatus()` when provider changes (see §ZustandIntegration)
  - [x] T6.9: Outside-click collapse via `useRef` + `useEffect` on `mousedown`:
    ```typescript
    const containerRef = useRef<HTMLDivElement>(null)
    useEffect(() => {
      function handleOutsideClick(e: MouseEvent) {
        if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
          setExpanded(false)
        }
      }
      if (expanded) document.addEventListener("mousedown", handleOutsideClick)
      return () => document.removeEventListener("mousedown", handleOutsideClick)
    }, [expanded])
    ```
  - [x] T6.10: Keyboard: `onKeyDown` handles Enter/Space (toggle expand), Escape (close)
  - [x] T6.11: Expanded panel content:
    - Provider + model display
    - Last latency: `{data?.llm.last_latency_ms != null ? `${data.llm.last_latency_ms}ms` : "—"}`
    - Last success: `{data?.llm.last_success_at ?? "—"}`
    - `<Link to="/settings" className="...">Configure →</Link>` (TanStack Router `Link`)

- [x] **T7: Update `frontend/src/components/layout/IconSidebar.tsx`** (AC: 1, 2, 3)
  - [x] T7.1: Import `ServiceStatusIndicator` from `"../ServiceStatusIndicator"` (sibling to `layout/` in `components/`)
  - [x] T7.2: Replace the footer placeholder comment with the component:
    ```tsx
    {/* Before — placeholder comment */}
    <div className="flex flex-col items-center py-4">
      {/* ServiceStatusIndicator — Story 1.10 */}
    </div>

    {/* After — component rendered */}
    <div className="flex flex-col items-center py-4 border-t border-zinc-800">
      <ServiceStatusIndicator />
    </div>
    ```
  - [x] T7.3: The footer `div` already exists at line 45 in `IconSidebar.tsx` — replace only the inner comment, keep the outer wrapper

- [x] **T8: Update `frontend/src/routes/settings.tsx`** (AC: 5)
  - [x] T8.1: Import `ServiceStatusIndicator`
  - [x] T8.2: Add mobile-only header before the `<h1>`:
    ```tsx
    function SettingsPage() {
      return (
        <div className="p-8">
          {/* ServiceStatusIndicator in header — mobile only (md+ uses sidebar footer) */}
          <div className="md:hidden mb-6 pb-4 border-b border-zinc-800">
            <ServiceStatusIndicator />
          </div>
          <h1 className="text-2xl font-semibold text-zinc-50">Settings</h1>
          <p className="mt-2 text-zinc-400">Settings — implemented in Story 2.3.</p>
        </div>
      )
    }
    ```

- [x] **T9: TypeScript + coverage validation** (AC: 6)
  - [x] T9.1: `npx tsc --noEmit` — zero TypeScript errors (strict mode; no `any` types)
  - [x] T9.2: `npm run test -- --coverage` — all tests pass; 100% branch coverage on `ServiceStatusIndicator`

---

## Dev Notes

### §WhatAlreadyExists — DO NOT Recreate

| Existing | Location | What it provides |
|---|---|---|
| `useAppStore` with `activeServiceStatus` | `frontend/src/lib/stores/useAppStore.ts` | Already has `{ llm: "local" \| "cloud" \| "unavailable", speech: ... }` + `setServiceStatus()` action — reuse |
| `get<T>()` client function | `frontend/src/lib/client.ts:45` | Typed fetch wrapper — use for `GET /services/status` |
| `ApiError` class | `frontend/src/lib/client.ts:12` | Already defined — TanStack Query's `onError` receives this |
| `<Badge />` component | `frontend/src/components/ui/badge.tsx` | shadcn/ui Badge — can use for status dot-with-text display |
| `<Link />` from TanStack Router | `@tanstack/react-router` | Use for "Configure →" link to `/settings` |
| `IconSidebar` footer area | `frontend/src/components/layout/IconSidebar.tsx:44-47` | Placeholder comment already at line 44 — replace it |
| `settings.tsx` route stub | `frontend/src/routes/settings.tsx` | Basic stub — add SSI to header for mobile |
| `QueryClient` + `QueryClientProvider` | `frontend/src/main.tsx` | Already configured globally — no need to add |
| `get_credential()` | `src/lingosips/services/credentials.py` | ONLY reader of keyring — registry.py already imports this |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | `src/lingosips/services/credentials.py` | Constants for keyring service/key names — already imported in `registry.py` |
| `DEFAULT_OPENROUTER_MODEL` | `src/lingosips/services/registry.py:26` | `"openai/gpt-4o-mini"` — the fallback model name |
| `services/registry.py` imports | `src/lingosips/services/registry.py:1-25` | All credential and provider imports already present |
| TanStack Query key convention | project-context.md | `["services", "status"]` follows existing pattern (`["models", "status"]` is `GET /models/status`) |

### §BackendDesign — Exact API Shape

**Endpoint:** `GET /services/status` → registered under `/services` prefix → full path: `/services/status`

**Response shape (snake_case, direct Pydantic — no wrapper):**
```json
{
  "llm": {
    "provider": "openrouter",
    "model": "openai/gpt-4o-mini",
    "last_latency_ms": null,
    "last_success_at": null
  },
  "speech": {
    "provider": "pyttsx3",
    "last_latency_ms": null,
    "last_success_at": null
  }
}
```

**When OpenRouter key is configured:**
```json
{ "llm": { "provider": "openrouter", "model": "<configured-model-or-default>", ... } }
```

**When no key configured:**
```json
{ "llm": { "provider": "qwen_local", "model": null, ... } }
```

**Critical implementation rules:**
- `get_service_status()` endpoint **MUST NOT** have `Depends(get_session)` — no DB access needed
- **MUST NOT** log credential values — only log `"provider"` names
- **MUST NOT** raise HTTP errors — always return 200 with current status
- `get_service_status_info()` in `registry.py` only reads credentials (via `get_credential()`), never writes or modifies provider state
- File location: `src/lingosips/api/services.py` (new file)
- Router registration in `app.py` goes BEFORE the static files mount — same pattern as other routers

**Test mock pattern for credentials:**
```python
from unittest.mock import patch

@pytest.fixture
def mock_no_credentials():
    """All get_credential() calls return empty string."""
    with patch("lingosips.services.registry.get_credential", return_value="") as m:
        yield m

@pytest.fixture
def mock_openrouter_credentials():
    def _side_effect(service: str, key: str) -> str:
        if (service, key) == ("lingosips", "openrouter_api_key"):
            return "sk-test-key"
        if (service, key) == ("lingosips", "openrouter_model"):
            return "openai/gpt-4o-mini"
        return ""
    with patch("lingosips.services.registry.get_credential", side_effect=_side_effect) as m:
        yield m
```

### §StateMapping — Query Data → Indicator State

```typescript
function deriveIndicatorState(
  isLoading: boolean,
  isError: boolean,
  data: ServiceStatusData | undefined
): ServiceIndicatorState {
  if (isLoading) return "switching"    // first load
  if (isError || !data) return "error"
  if (data.llm.provider === "openrouter") return "cloud-active"
  if (data.llm.provider === "qwen_local") return "local-active"
  return "error"  // unknown provider — defensive
}
```

**`cloud-degraded` state trigger:**
For MVP, `cloud-degraded` is reached ONLY when the query returns openrouter but `isStale === true` AND `isFetching === false` (data is old, re-fetch failed). This state covers the case where OpenRouter was responding but recent re-fetches are failing.

```typescript
function deriveIndicatorState(
  isLoading: boolean,
  isError: boolean,
  isStale: boolean,
  isFetching: boolean,
  data: ServiceStatusData | undefined
): ServiceIndicatorState {
  if (isLoading && !data) return "switching"
  if (isError && !data) return "error"
  if (!data) return "switching"
  if (data.llm.provider === "openrouter") {
    if (isStale && !isFetching && isError) return "cloud-degraded"
    return "cloud-active"
  }
  if (data.llm.provider === "qwen_local") return "local-active"
  return "error"
}
```

**Display text and dot color per state:**
```typescript
const STATE_DISPLAY: Record<ServiceIndicatorState, { label: string; dotClass: string; textClass: string }> = {
  "cloud-active":   { label: `OpenRouter · ${data?.llm.model ?? "..."}`, dotClass: "bg-emerald-500", textClass: "text-zinc-300" },
  "local-active":   { label: "Local Qwen",                               dotClass: "bg-amber-500",   textClass: "text-zinc-300" },
  "cloud-degraded": { label: "OpenRouter · slow",                        dotClass: "bg-amber-500",   textClass: "text-zinc-300" },
  "switching":      { label: "Connecting...",                            dotClass: "bg-zinc-500",    textClass: "text-zinc-400" },
  "error":          { label: "AI unavailable",                           dotClass: "bg-red-400",     textClass: "text-zinc-400" },
}
```

**Typography:** `text-xs` (12px) per UX spec — "service status indicator" uses the smallest type scale.

### §AriaLivePattern — CRITICAL Lesson from Story 1.9 Review

**WRONG** (from Story 1.9 review patch #9 — aria-live containers must NOT be removed from DOM):
```tsx
{state !== "idle" && (
  <div aria-live="polite">{content}</div>  // ❌ removed from DOM in idle — screen readers miss first announcement
)}
```

**CORRECT** — always in DOM, use `sr-only` for visual hiding:
```tsx
{/* Always in DOM — sr-only hides visually but keeps aria-live region registered */}
<div aria-live="polite" aria-atomic="true" className="sr-only">
  {statusAnnouncement}
</div>
```

The `ServiceStatusIndicator` must use this same pattern. The `statusAnnouncement` string is updated whenever `indicatorState` changes. The aria-live region stays in the DOM at all times.

### §AnnouncementPattern — State Change Detection

```typescript
const prevStateRef = useRef<ServiceIndicatorState | null>(null)
const [statusAnnouncement, setStatusAnnouncement] = useState("")

useEffect(() => {
  if (prevStateRef.current !== null && prevStateRef.current !== indicatorState) {
    // State changed — announce it
    const { label } = STATE_DISPLAY[indicatorState]
    setStatusAnnouncement(`AI service: ${label}`)
    // Clear after 3 seconds so it doesn't keep announcing on re-render
    const t = setTimeout(() => setStatusAnnouncement(""), 3_000)
    return () => clearTimeout(t)
  }
  prevStateRef.current = indicatorState
}, [indicatorState])
```

**Cleanup:** `clearTimeout` in the effect return to prevent state updates after unmount.

### §ZustandIntegration — Updating useAppStore

The `useAppStore.activeServiceStatus` is UI-only state for tracking which provider is conceptually active globally. Update it when `indicatorState` changes:

```typescript
const setServiceStatus = useAppStore((s) => s.setServiceStatus)

useEffect(() => {
  if (!data) return
  const llmStatus = data.llm.provider === "openrouter" ? "cloud" : "local"
  const speechStatus = data.speech.provider === "azure" ? "cloud" : "local"
  setServiceStatus("llm", llmStatus)
  setServiceStatus("speech", speechStatus)
}, [data, setServiceStatus])
```

**CRITICAL:** Do NOT store the full `ServiceStatusData` response in Zustand — only the simplified `"local" | "cloud" | "unavailable"` flag. The rich data lives in TanStack Query cache.

### §ComponentLayout — Visual Structure

```
┌─────────────────────────────────────────────┐
│ [dot] Local Qwen                   [toggle] │  ← compact badge, always visible in sidebar footer
└─────────────────────────────────────────────┘

When expanded (click/Enter):
┌─────────────────────────────────────────────┐
│ [dot] Local Qwen                            │  ← status badge
├─────────────────────────────────────────────┤
│ Provider:     Local Qwen (Qwen model)       │  ← expanded panel
│ Latency:      —                             │
│ Last success: —                             │
│ [Configure →]                               │  ← TanStack Router Link to /settings
└─────────────────────────────────────────────┘
```

**Container structure:**
```tsx
<div ref={containerRef} className="relative w-full px-2">
  {/* Always-in-DOM aria-live region */}
  <div aria-live="polite" aria-atomic="true" className="sr-only">
    {statusAnnouncement}
  </div>

  {/* Status badge button */}
  <button
    role="status"
    aria-expanded={expanded}
    aria-label={`AI service: ${displayLabel}. ${expanded ? "Click to collapse" : "Click to expand details"}`}
    onClick={() => setExpanded((prev) => !prev)}
    onKeyDown={handleKeyDown}
    className="flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
  >
    <span className={cn("h-2 w-2 shrink-0 rounded-full", dotClass)} aria-hidden="true" />
    <span className="min-w-0 truncate">{displayLabel}</span>
  </button>

  {/* Expanded detail panel — outside-click collapses */}
  {expanded && (
    <div className="absolute bottom-full left-0 mb-2 w-52 rounded-md border border-zinc-700 bg-zinc-900 p-3 shadow-lg text-xs">
      ...
    </div>
  )}
</div>
```

**Placement:** The expanded panel uses `absolute bottom-full` to appear ABOVE the badge (it's in the sidebar footer — panel must not clip below the viewport). Adjust if the component appears in a settings header (use `top-full` in that context).

### §ProjectStructureNotes — File Locations

**New files to create:**
```
src/lingosips/api/
├── services.py                                     ← NEW: GET /services/status router

src/lingosips/services/
├── registry.py                                     ← MODIFIED: add ServiceStatusInfo + get_service_status_info()

tests/
├── test_registry_service_status.py                 ← NEW: unit tests for get_service_status_info()
├── test_services_api.py                            ← NEW: integration tests for GET /services/status

frontend/src/components/
├── ServiceStatusIndicator.tsx                      ← NEW: component (in components/ root, not features/ or ui/)
├── ServiceStatusIndicator.test.tsx                 ← NEW: co-located tests (100% branch coverage required)

frontend/src/components/layout/
├── IconSidebar.tsx                                 ← MODIFIED: render <ServiceStatusIndicator /> in footer

frontend/src/routes/
├── settings.tsx                                    ← MODIFIED: add SSI in mobile header

frontend/src/lib/
├── api.d.ts                                        ← REGENERATED: after adding backend endpoint (never manually edit)
```

**Component location:** `src/components/ServiceStatusIndicator.tsx` — NOT in `features/` (it's a shared custom component used in both sidebar and settings), NOT in `ui/` (it's project-specific, not a shadcn primitive). Architecture explicitly places it in `src/components/` alongside the `layout/` and `ui/` subdirectories.

**Import paths from `IconSidebar.tsx`:**
```typescript
import { ServiceStatusIndicator } from "../ServiceStatusIndicator"
// or with @/ alias:
import { ServiceStatusIndicator } from "@/components/ServiceStatusIndicator"
```

### §TestStrategy — Three-Layer Testing

**Layer 1 — `test_registry_service_status.py`** (Python unit tests):
- Mock `get_credential` via `unittest.mock.patch`
- Test 6 cases (see T1.3)
- No DB, no HTTP — pure function tests

**Layer 2 — `test_services_api.py`** (Python integration tests — httpx + FastAPI test client):
- Use existing `AsyncClient` fixture pattern from other test files
- Mock `get_service_status_info` (not `get_credential`) to avoid keyring dependency in API tests
- Test happy paths + always-200 guarantee

**Layer 3 — `ServiceStatusIndicator.test.tsx`** (Vitest + React Testing Library):
- Wrap in `QueryClientProvider` with fresh `QueryClient`
- Mock `get` from `@/lib/client`
- Control `useQuery` responses via controlled `get` mock
- Cover all 5 state machine branches: 100% required
- Use `waitFor` for async query resolution
- Use `userEvent.setup()` for interaction tests

**Note on mocking TanStack Query in RTL tests:**
```typescript
// DO NOT mock @tanstack/react-query directly — it breaks core hooks
// INSTEAD: mock the underlying fetch function and let TQ handle the rest
vi.mock("@/lib/client", () => ({
  get: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(status: number, type: string, title: string, detail?: string) {
      super(title)
      Object.assign(this, { status, type, title, detail })
    }
  },
}))

// In test:
vi.mocked(get).mockResolvedValue({ llm: { provider: "qwen_local", model: null, ... }, speech: { ... } })
await render(<ServiceStatusIndicator />, { wrapper: QueryClientWrapper })
await screen.findByText("Local Qwen")  // findBy waits for async resolution
```

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `const [isCloud, setIsCloud] = useState(false)` | `type ServiceIndicatorState = "cloud-active" \| "local-active" \| ...` |
| Placing SSI in `src/features/` | `src/components/ServiceStatusIndicator.tsx` — it's a shared component used in 2+ places |
| Placing SSI in `src/components/ui/` | `src/components/` root — `ui/` is only for shadcn primitives |
| Storing `ServiceStatusData` in Zustand | TanStack Query owns the server data — Zustand only gets the simplified `"local" \| "cloud"` flag |
| Conditional rendering of `aria-live` region | Always in DOM — use `sr-only` class to hide visually (Story 1.9 review fix) |
| `Depends(get_session)` in `GET /services/status` | No DB needed — the endpoint only reads keyring via `get_service_status_info()` |
| Reading keyring in `api/services.py` directly | Only `services/credentials.py` reads keyring — call via `get_service_status_info()` in `services/registry.py` |
| Instantiating providers in `get_service_status_info()` | Check credentials only — do NOT call `QwenLocalProvider()` or `OpenRouterProvider()` |
| Polling with `setInterval` in component | Use TanStack Query's built-in `refetchInterval: 30_000` |
| `useEventListener` or custom click-outside hook | Inline `useRef` + `useEffect` on `mousedown` — same pattern used by shadcn popover |
| `vi.mock("@tanstack/react-query")` in tests | Mock `get` from `@/lib/client` — let TanStack Query work normally |
| Hard-coding `"openai/gpt-4o-mini"` in frontend | Render `data.llm.model` from server — the backend resolves the actual model |

### §PreviousStoryIntelligence — Learnings from Story 1.9 (and its code review)

**Directly applicable to this story:**

1. **aria-live containers must ALWAYS be in DOM** (Review patch #9): Conditional rendering removes the live region, causing screen readers to miss the first announcement. Use `sr-only` Tailwind class instead of conditional render. **This is the most critical lesson for SSI.**

2. **State machines, not boolean flags** (Review patch #10, Project-context anti-patterns): `ServiceIndicatorState` enum — never `const [isExpanded, setIsExpanded, isCloud, setIsCloud]`.

3. **100% branch coverage required** (Project-context): SSI is listed as one of the 5 primary custom components alongside `CardCreationPanel`. All 5 state branches must be covered in tests.

4. **`AbortController` / timeout cleanup**: `clearTimeout` in useEffect return; `document.removeEventListener` cleanup for outside-click.

5. **`vi.mocked(get)` pattern**: Use `vi.mocked()` to get typed mock access — don't use `(get as jest.Mock)` TypeScript casts.

6. **`queryClient.clear()` in afterEach**: Prevents test bleed when sharing QueryClient across tests.

7. **`findByText` not `getByText` for async queries**: TanStack Query is async — use `await screen.findByText(...)` after rendering, not `getByText`.

**From Story 1.8 review (backend TDD patterns):**
- Patch at the correct module path: `lingosips.services.registry.get_credential`, NOT `lingosips.services.credentials.get_credential` (patch where it's imported, not defined)
- Test class structure: `class TestGetServiceStatus:` with `async def test_...`

### References

- Story 1.10 acceptance criteria: [Source: _bmad-output/planning-artifacts/epics.md#Story 1.10]
- UX-DR4 `ServiceStatusIndicator` anatomy and states: [Source: _bmad-output/planning-artifacts/ux-design-specification.md#4. ServiceStatusIndicator]
- `role="status"` requirement: [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Accessibility]
- `ServiceIndicatorState` 5 states: [Source: _bmad-output/planning-artifacts/epics.md#UX-DR4]
- Component location `src/components/ServiceStatusIndicator.tsx`: [Source: _bmad-output/planning-artifacts/architecture.md#Frontend directory structure]
- `IconSidebar.tsx` footer placeholder at line 44-47: [Source: frontend/src/components/layout/IconSidebar.tsx:44]
- `useAppStore.activeServiceStatus` shape `{ llm: "local" | "cloud" | "unavailable", ... }`: [Source: frontend/src/lib/stores/useAppStore.ts:7-8]
- `useAppStore.setServiceStatus()` action: [Source: frontend/src/lib/stores/useAppStore.ts:24]
- `get_credential()` imports and credential constants in `registry.py`: [Source: src/lingosips/services/registry.py:11-17]
- `DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"`: [Source: src/lingosips/services/registry.py:26]
- TanStack Query key convention `["services", "status"]`: [Source: _bmad-output/project-context.md#TanStack Query key conventions]
- TanStack Query `refetchInterval` for polling: [Source: _bmad-output/project-context.md#Technology Stack — TanStack Query v5.99.2]
- Never store server data in Zustand: [Source: _bmad-output/project-context.md#Frontend state boundary]
- 100% branch coverage for 5 primary custom components: [Source: _bmad-output/project-context.md#Frontend components — Vitest + React Testing Library]
- `services/credentials.py` is ONLY keyring reader: [Source: _bmad-output/project-context.md#Layer Architecture & Boundaries]
- aria-live always-in-DOM: [Source: 1-9-cardcreationpanel-component.md#Review Findings — patch #9]
- RFC 7807 error shape: [Source: _bmad-output/project-context.md#API Design Rules]
- Router registration before static mount: [Source: src/lingosips/api/app.py:176-179]
- `settings.tsx` is currently a stub: [Source: frontend/src/routes/settings.tsx]
- Mobile: `md:hidden` shows on <768px, hidden on md+: [Source: _bmad-output/project-context.md#Technology Stack — Tailwind CSS v4]
- `text-xs` for service status indicator: [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Typography System]
- `amber-500` for warning/local-active (not error): [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Color Palette]

---

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5)

### Debug Log References

- T1: `get_service_status_info()` — added defensive try-except wrap since `get_credential` is patched to raise Exception in one test; caught via structured fallback returning qwen_local defaults.
- T5/T6 error state: component uses `retry: 2` which overrides QueryClient `retry: false`; fixed by adding `retryDelay: 0` in error test's QueryClient so retries complete instantly.
- T5/T6 cloud-degraded coverage: state requires `isStale && !isFetching && isError` simultaneously; resolved by exporting `deriveIndicatorState` and `getStateDisplay` as pure functions for direct unit testing.
- T4: regenerated `api.d.ts` via ephemeral server on port 7843 (killed existing stale server first).

### Completion Notes List

- **T1 (registry.py)**: Added `ServiceStatusInfo` dataclass and `get_service_status_info()` to `services/registry.py`. Function reads credentials via `get_credential()` (never instantiates providers), wraps in try-except for robustness. 8 passing tests.
- **T2 (api/services.py)**: Created new router with `GET /services/status`. Three Pydantic models: `LLMServiceStatus`, `SpeechServiceStatus`, `ServiceStatusResponse`. No DB dependency. 9 passing tests.
- **T3 (app.py)**: Registered services router under `/services` prefix, before static files mount.
- **T4 (api.d.ts)**: Regenerated from live FastAPI OpenAPI schema — includes `ServiceStatusResponse`, `LLMServiceStatus`, `SpeechServiceStatus`.
- **T5+T6 (ServiceStatusIndicator)**: Component with 5-state machine (`cloud-active`, `local-active`, `cloud-degraded`, `switching`, `error`). Uses TanStack Query with 30s poll, Zustand for simplified status flag, always-in-DOM `aria-live` region, outside-click via `mousedown` listener, keyboard Enter/Space/Escape. Exported `deriveIndicatorState` and `getStateDisplay` pure functions for 100% branch coverage. 26 passing tests, 100% branch coverage.
- **T7 (IconSidebar)**: Replaced placeholder comment with `<ServiceStatusIndicator />` in `border-t border-zinc-800` footer.
- **T8 (settings.tsx)**: Added `md:hidden` mobile-only SSI header above `<h1>`.
- **T9**: `tsc --noEmit` → zero errors. `npm run test --coverage` → 122 passing, 100% branch on SSI. Backend: 244 passing, 93.48% coverage (above 90% gate).

### File List

- `src/lingosips/services/registry.py` — MODIFIED: added `ServiceStatusInfo` dataclass + `get_service_status_info()` function
- `src/lingosips/api/services.py` — NEW: `GET /services/status` router with `LLMServiceStatus`, `SpeechServiceStatus`, `ServiceStatusResponse`
- `src/lingosips/api/app.py` — MODIFIED: registered services router under `/services` prefix
- `tests/services/test_registry_service_status.py` — NEW: 8 unit tests for `get_service_status_info()`
- `tests/api/test_services_api.py` — NEW: 9 integration tests for `GET /services/status`
- `frontend/src/lib/api.d.ts` — REGENERATED: includes new service status schemas
- `frontend/src/components/ServiceStatusIndicator.tsx` — NEW: 5-state machine component with aria-live, keyboard, outside-click, expansion panel
- `frontend/src/components/ServiceStatusIndicator.test.tsx` — NEW: 26 tests, 100% branch coverage
- `frontend/src/components/layout/IconSidebar.tsx` — MODIFIED: renders `<ServiceStatusIndicator />` in sidebar footer
- `frontend/src/routes/settings.tsx` — MODIFIED: adds mobile-only SSI header

### Review Findings

- [x] [Review][Patch] Imports not at top of file (E402) — `ServiceStatusInfo` dataclass placed between two import blocks in `registry.py`, causing ruff E402 on all subsequent `from lingosips.services.*` imports [src/lingosips/services/registry.py:36-42]
- [x] [Review][Patch] Import block unsorted (I001) — `import structlog` / `from dataclasses import dataclass` were out of isort order; fixed by placing stdlib before third-party [src/lingosips/services/registry.py:9]
- [x] [Review][Patch] Missing blank line before `_qwen_provider` module variable — ruff E302/E303 style violation after end of `get_service_status_info()` function [src/lingosips/services/registry.py:84]
- [x] [Review][Patch] `logger.debug()` call too long (E501, 103 chars > 100) — split onto two lines [src/lingosips/services/registry.py:70]
- [x] [Review][Patch] Registration order comment too long (E501, 108 chars > 100) — shortened to fit [src/lingosips/api/app.py:176]
- [x] [Review][Patch] Unused `import pytest` (F401) in test file — `pytest` was imported but never referenced [tests/api/test_services_api.py:9]
- [x] [Review][Patch] Test docstring too long (E501, 102 chars > 100) — shortened [tests/api/test_services_api.py:63]
- [x] [Review][Patch] Module docstring too long (E501, 101 chars > 100) — shortened [tests/services/test_registry_service_status.py:1]
- [x] [Review][Patch] Test docstring too long (E501, 110 chars > 100) — shortened [tests/services/test_registry_service_status.py:34]
- [x] [Review][Patch] `prevStateRef` not updated after aria-live announcement fires — `prevStateRef.current = indicatorState` was only in the `else` path (unreachable when `return () => clearTimeout(t)` exits early), causing re-announcements on every 30s TanStack Query data refresh even when `indicatorState` hadn't changed; fixed by updating ref before the `return` [frontend/src/components/ServiceStatusIndicator.tsx:127]

## Change Log

- 2026-05-01: Story 1.10 implemented — added `GET /services/status` backend endpoint, `ServiceStatusIndicator` React component with 5-state machine (cloud-active, local-active, cloud-degraded, switching, error), aria-live announcements, keyboard expansion, outside-click collapse, 100% branch coverage (26 tests). Backend: 8 registry unit tests + 9 API integration tests. IconSidebar footer and Settings mobile header updated.
- 2026-05-01: Code review — fixed 10 issues: ruff linter violations in registry.py (E402 import ordering, I001 import sort, E302/E303 blank lines, E501 line length), app.py (E501), test_services_api.py (F401 unused import, E501), test_registry_service_status.py (E501 ×2); aria-live prevStateRef announcement re-fire bug in ServiceStatusIndicator.tsx.
