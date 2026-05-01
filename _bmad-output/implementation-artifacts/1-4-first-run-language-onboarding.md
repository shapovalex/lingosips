# Story 1.4: First-Run Language Onboarding

Status: done

## Story

As a first-time user,
I want a simple language selection wizard on first launch (native language + target language only),
so that I can reach the card creation interface in under 60 seconds with zero configuration and no account creation.

## Acceptance Criteria

1. **Given** I launch the app for the first time (no Settings record in the DB)
   **When** the app opens
   **Then** the `OnboardingWizard` is shown with native language and target language selectors
   **And** no account, email, or password is required

2. **Given** I select my languages and click "Start learning"
   **When** the wizard completes
   **Then** the language selections are persisted to the Settings table (Alembic migration `001_initial_schema` has run)
   **And** I land on the home dashboard with the creation input focused and ready

3. **Given** I am on the onboarding wizard
   **When** I choose to skip (click "Skip for now")
   **Then** I reach the home dashboard immediately
   **And** the app is fully functional with local AI fallback active

4. **Given** I return to the app after completing onboarding
   **When** the app loads on subsequent launches
   **Then** the wizard does not appear
   **And** the home dashboard loads directly

5. **Given** the Settings table does not yet exist
   **When** the app starts
   **Then** Alembic runs `001_initial_schema` migration automatically before the server accepts requests
   **And** `GET /settings` creates and returns a default Settings row if none exists

## Tasks / Subtasks

- [x] **T1: Create `core/settings.py`** (AC: 1, 2, 3, 4, 5) — TDD: write failing tests first
  - [x] T1.1: Define `SUPPORTED_LANGUAGES: dict[str, str]` — BCP 47 code → display name (see Dev Notes §SupportedLanguages)
  - [x] T1.2: Define `DEFAULT_NATIVE_LANGUAGE = "en"` and `DEFAULT_TARGET_LANGUAGE = "es"` constants
  - [x] T1.3: Implement `async def get_or_create_settings(session: AsyncSession) -> Settings` — see Dev Notes §GetOrCreate
  - [x] T1.4: Implement `async def update_settings(session: AsyncSession, **kwargs: Any) -> Settings` — see Dev Notes §UpdateSettings
  - [x] T1.5: Implement `def validate_language_code(code: str) -> None` — raises `ValueError` if not in `SUPPORTED_LANGUAGES`

- [x] **T2: Create `api/settings.py`** (AC: 1, 2, 3, 4, 5) — TDD: write failing tests first
  - [x] T2.1: Define `SettingsResponse` Pydantic model (see Dev Notes §APIShapes)
  - [x] T2.2: Define `SettingsUpdateRequest` Pydantic model (see Dev Notes §APIShapes)
  - [x] T2.3: Implement `GET /settings` — calls `core.settings.get_or_create_settings(session)`; returns `SettingsResponse`
  - [x] T2.4: Implement `PUT /settings` — validates language codes via `core.settings.validate_language_code`; on invalid code raises `HTTPException(422, RFC7807 detail)`; calls `core.settings.update_settings`; returns `SettingsResponse`
  - [x] T2.5: Create APIRouter: `router = APIRouter()`, prefix `/settings` applied at registration in `app.py`

- [x] **T3: Register settings router in `api/app.py`** (AC: 1, 2)
  - [x] T3.1: Add `from lingosips.api.settings import router as settings_router` inside `create_app()`
  - [x] T3.2: Add `application.include_router(settings_router, prefix="/settings", tags=["settings"])`
  - [x] T3.3: Verify registration order: health endpoint first, then domain routers, then static files mount last
  - [x] T3.4: After running backend, confirm `GET /openapi.json` lists `/settings` and `/settings` (PUT) endpoints

- [x] **T4: Backend tests — TDD (write BEFORE implementing T1/T2)** (AC: 1, 2, 3, 4, 5)
  - [x] T4.1: Create `tests/api/test_settings.py`
  - [x] T4.2: `TestGetSettings::test_get_settings_creates_default_on_empty_db` — empty DB → 200, `onboarding_completed=false`, `native_language="en"`, `active_target_language="es"`
  - [x] T4.3: `TestGetSettings::test_get_settings_returns_existing_row` — seed a Settings row → 200 returns it unchanged
  - [x] T4.4: `TestGetSettings::test_get_settings_is_idempotent` — two sequential GETs on empty DB → only one row in DB (no duplicate insert)
  - [x] T4.5: `TestPutSettings::test_put_settings_updates_native_language` — PUT `{"native_language": "fr"}` → 200, persisted
  - [x] T4.6: `TestPutSettings::test_put_settings_updates_target_language` — PUT `{"active_target_language": "de"}` → 200, persisted
  - [x] T4.7: `TestPutSettings::test_put_settings_marks_onboarding_complete` — PUT `{"onboarding_completed": true}` → 200, field persisted
  - [x] T4.8: `TestPutSettings::test_put_settings_invalid_native_language_returns_422` — PUT `{"native_language": "xx"}` → 422 RFC 7807
  - [x] T4.9: `TestPutSettings::test_put_settings_invalid_target_language_returns_422` — PUT `{"active_target_language": "zz"}` → 422 RFC 7807
  - [x] T4.10: `TestPutSettings::test_put_settings_partial_update_preserves_other_fields` — PUT only `native_language` → `active_target_language` and `onboarding_completed` unchanged

- [x] **T5: Create `OnboardingWizard.tsx` and tests** (AC: 1, 2, 3) — TDD: write `.test.tsx` BEFORE component
  - [x] T5.1: Create `frontend/src/features/onboarding/OnboardingWizard.test.tsx` first (see Dev Notes §WizardTests)
  - [x] T5.2: Create `frontend/src/features/onboarding/OnboardingWizard.tsx` (see Dev Notes §WizardComponent)
  - [x] T5.3: Create `frontend/src/features/onboarding/index.ts` — `export { OnboardingWizard } from "./OnboardingWizard"`
  - [x] T5.4: Implement state machine: `type WizardState = "idle" | "submitting" | "error"` (see Dev Notes §WizardStateMachine)
  - [x] T5.5: Define `SUPPORTED_LANGUAGES_FRONTEND` constant in the component file (matches backend list — see Dev Notes §LanguageConstantFrontend)
  - [x] T5.6: Two `<select>` elements populated from the constant; default native="en", target="es"
  - [x] T5.7: "Start learning" button → `useMutation` PUT `/settings` → on success `queryClient.invalidateQueries(["settings"])` → wizard disappears
  - [x] T5.8: "Skip for now" button → same mutation with defaults (en/es) + `onboarding_completed: true`
  - [x] T5.9: Error state: show specific message with what failed and what to do (UX-DR13); retry clears error and re-enables form
  - [x] T5.10: Accessibility: `role="main"`, `aria-label="Language setup"`, `aria-live="polite"` on error region; Tab order: native select → target select → "Start learning" → "Skip for now"
  - [x] T5.11: Focus the native language select on mount (`useEffect(() => ref.current?.focus(), [])`)

- [x] **T6: Update `routes/__root.tsx` — onboarding gate** (AC: 1, 4)
  - [x] T6.1: Import `useQuery` from `@tanstack/react-query` and `get` from `@/lib/client`
  - [x] T6.2: Import `OnboardingWizard` from `@/features/onboarding`
  - [x] T6.3: Define local `SettingsResponse` interface (see Dev Notes §TypesNote)
  - [x] T6.4: In `RootLayout`, add: `const { data: settings, isLoading } = useQuery({ queryKey: ["settings"], queryFn: () => get<SettingsResponse>("/settings") })`
  - [x] T6.5: Loading branch: return `<div className="flex h-screen bg-zinc-950" role="status" aria-label="Loading..." />`
  - [x] T6.6: Onboarding branch: if `!settings?.onboarding_completed` return `<TooltipProvider><OnboardingWizard /></TooltipProvider>`
  - [x] T6.7: Normal branch: existing app shell JSX (unchanged)
  - [x] T6.8: The `OnboardingWizard` mutation calls `queryClient.invalidateQueries({ queryKey: ["settings"] })` → `RootLayout` re-fetches → `onboarding_completed` is `true` → normal app renders

- [x] **T7: Playwright E2E tests** (AC: 1, 2, 3, 4)
  - [x] T7.1: Create `frontend/e2e/features/settings-and-onboarding.spec.ts` (see Dev Notes §PlaywrightStrategy)
  - [x] T7.2: `test("first launch shows OnboardingWizard, no sidebar, no bottom nav")`
  - [x] T7.3: `test("completing wizard with language selection navigates to home dashboard")`
  - [x] T7.4: `test("skip button navigates to home dashboard with default languages")`
  - [x] T7.5: `test("return visit after onboarding — wizard does NOT appear")`
  - [x] T7.6: `test("keyboard navigation through wizard — Tab order correct, Enter submits")`
  - [x] T7.7: Update `frontend/e2e/journeys/first-launch-card-creation.spec.ts` — existing tests that assert home page elements must first complete onboarding; add `completeOnboarding(page)` helper (see Dev Notes §PlaywrightHelper)
  - [x] T7.8: **Update `frontend/e2e/features/app-shell.spec.ts`** — all tests navigate to `/` and assert `Main navigation` / `Bottom navigation`; these will BREAK because the wizard now shows first. Add `completeOnboarding(page)` call in `beforeEach` for all app-shell tests

- [x] **T8: Regenerate `api.d.ts`** (Dev tooling — do last)
  - [x] T8.1: With backend running: `cd frontend && npx openapi-typescript http://localhost:7842/openapi.json -o src/lib/api.d.ts`
  - [x] T8.2: Remove local `SettingsResponse` interface from `__root.tsx` and import generated type instead
  - [x] T8.3: Run `npm run build` to verify no TypeScript errors

## Dev Notes

### ⚠️ DO NOT Recreate — Already Exists

- **`settings` table** — defined in `db/models.py` (`Settings` model). Alembic migration `001_initial_schema` already creates it. **Do NOT create a new migration for this story.** Do NOT call `SQLModel.metadata.create_all()`.
- **`services/credentials.py`** — created in Story 1.3. Not relevant to this story. Do NOT touch.
- **`api/app.py`** — only ADD a `include_router` call. Do not restructure existing handlers.
- **`tests/conftest.py`** — already wires in-memory SQLite DB and `get_session` override. Your tests inherit this via `client` fixture.

### §SupportedLanguages — `SUPPORTED_LANGUAGES` Constant

Define in `core/settings.py`. This is the authoritative list for both backend validation and (duplicated as a constant) the frontend component:

```python
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
    "ko": "Korean",
    "ar": "Arabic",
    "tr": "Turkish",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "cs": "Czech",
    "uk": "Ukrainian",
}

DEFAULT_NATIVE_LANGUAGE = "en"
DEFAULT_TARGET_LANGUAGE = "es"
```

### §GetOrCreate — `get_or_create_settings` Pattern

This is an upsert pattern. The Settings table holds a single row (singleton). Query for the first row; if none, insert defaults and return:

```python
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from lingosips.db.models import Settings
import structlog

logger = structlog.get_logger(__name__)

async def get_or_create_settings(session: AsyncSession) -> Settings:
    """Return the singleton Settings row, creating defaults on first call."""
    result = await session.exec(select(Settings).limit(1))
    settings = result.first()
    if settings is None:
        settings = Settings(
            native_language=DEFAULT_NATIVE_LANGUAGE,
            active_target_language=DEFAULT_TARGET_LANGUAGE,
            target_languages=f'["{DEFAULT_TARGET_LANGUAGE}"]',
            onboarding_completed=False,
        )
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
        logger.info("settings.created_defaults")
    return settings
```

**CRITICAL**: The idempotency test (T4.4) verifies that two GETs on an empty DB produce exactly one row. The `select().limit(1)` approach handles this correctly because the second GET finds the row inserted by the first GET.

### §UpdateSettings — `update_settings` Pattern

```python
async def update_settings(session: AsyncSession, **kwargs: Any) -> Settings:
    """Apply partial updates to the singleton Settings row."""
    settings = await get_or_create_settings(session)
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    from datetime import UTC, datetime
    settings.updated_at = datetime.now(UTC)
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings
```

**Do NOT accept arbitrary `kwargs` without validation** — the router validates `native_language` and `active_target_language` via `validate_language_code` before calling this function. Only validated/allowed fields from `SettingsUpdateRequest` are passed through.

### §APIShapes — Pydantic Models for `api/settings.py`

```python
from pydantic import BaseModel, Field

class SettingsResponse(BaseModel):
    id: int
    native_language: str
    target_languages: str          # JSON string: '["es"]'
    active_target_language: str
    auto_generate_audio: bool
    auto_generate_images: bool
    default_practice_mode: str
    cards_per_session: int
    onboarding_completed: bool

class SettingsUpdateRequest(BaseModel):
    native_language: str | None = None
    active_target_language: str | None = None
    onboarding_completed: bool | None = None
    auto_generate_audio: bool | None = None
    auto_generate_images: bool | None = None
    default_practice_mode: str | None = None
    cards_per_session: int | None = Field(default=None, ge=1, le=100)
```

**Router implementation pattern:**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from lingosips.db.session import get_session
from lingosips.core import settings as core_settings

router = APIRouter()

@router.get("", response_model=SettingsResponse)
async def get_settings(session: AsyncSession = Depends(get_session)) -> SettingsResponse:
    s = await core_settings.get_or_create_settings(session)
    return SettingsResponse.model_validate(s, from_attributes=True)

@router.put("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    # Validate language codes before any DB work
    if body.native_language is not None:
        try:
            core_settings.validate_language_code(body.native_language)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "/errors/invalid-language",
                    "title": "Invalid language code",
                    "detail": f"'{body.native_language}' is not a supported language code.",
                    "status": 422,
                },
            )
    if body.active_target_language is not None:
        try:
            core_settings.validate_language_code(body.active_target_language)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "/errors/invalid-language",
                    "title": "Invalid language code",
                    "detail": f"'{body.active_target_language}' is not a supported language code.",
                    "status": 422,
                },
            )
    # Build kwargs dict excluding None values
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    s = await core_settings.update_settings(session, **updates)
    return SettingsResponse.model_validate(s, from_attributes=True)
```

### §WizardStateMachine — Component State

```typescript
type WizardState = "idle" | "submitting" | "error"
```

- `"idle"` → form visible, selects enabled, "Start learning" and "Skip for now" active
- `"submitting"` → button shows spinner, selects disabled, "Skip" link hidden
- `"error"` → error message shown in `aria-live` region, retry button, selects re-enabled

State transitions:
- `idle` → `submitting`: user clicks "Start learning" or "Skip for now"
- `submitting` → `idle` (success): `queryClient.invalidateQueries(["settings"])` → parent re-renders, wizard unmounts
- `submitting` → `error`: API call fails
- `error` → `idle`: user clicks "Try again"

### §WizardComponent — `OnboardingWizard.tsx` Structure

```tsx
import { useState, useRef, useEffect } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { put } from "@/lib/client"

// Mirrors backend SUPPORTED_LANGUAGES (keep in sync manually until api.d.ts generated)
const SUPPORTED_LANGUAGES: Array<{ code: string; label: string }> = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "it", label: "Italian" },
  { code: "pt", label: "Portuguese" },
  { code: "nl", label: "Dutch" },
  { code: "pl", label: "Polish" },
  { code: "ru", label: "Russian" },
  { code: "ja", label: "Japanese" },
  { code: "zh", label: "Chinese (Simplified)" },
  { code: "ko", label: "Korean" },
  { code: "ar", label: "Arabic" },
  { code: "tr", label: "Turkish" },
  { code: "sv", label: "Swedish" },
  { code: "da", label: "Danish" },
  { code: "no", label: "Norwegian" },
  { code: "cs", label: "Czech" },
  { code: "uk", label: "Ukrainian" },
]

interface SettingsUpdateRequest {
  native_language?: string
  active_target_language?: string
  onboarding_completed?: boolean
}

type WizardState = "idle" | "submitting" | "error"

export function OnboardingWizard() {
  const queryClient = useQueryClient()
  const [wizardState, setWizardState] = useState<WizardState>("idle")
  const [nativeLang, setNativeLang] = useState("en")
  const [targetLang, setTargetLang] = useState("es")
  const [errorMessage, setErrorMessage] = useState("")
  const nativeSelectRef = useRef<HTMLSelectElement>(null)

  // Focus native language select on mount (FR40: reach creation in <60s)
  useEffect(() => {
    nativeSelectRef.current?.focus()
  }, [])

  const mutation = useMutation({
    mutationFn: (data: SettingsUpdateRequest) =>
      put<unknown>("/settings", data),
    onSuccess: () => {
      // Invalidate settings query → RootLayout re-fetches → wizard unmounts
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
    onError: (error: Error) => {
      setWizardState("error")
      setErrorMessage(
        `Settings could not be saved. ${error.message}. Please try again or check your connection.`
      )
    },
    onMutate: () => {
      setWizardState("submitting")
      setErrorMessage("")
    },
  })

  function handleStartLearning() {
    mutation.mutate({
      native_language: nativeLang,
      active_target_language: targetLang,
      onboarding_completed: true,
    })
  }

  function handleSkip() {
    mutation.mutate({
      native_language: "en",
      active_target_language: "es",
      onboarding_completed: true,
    })
  }

  function handleRetry() {
    setWizardState("idle")
  }

  const isSubmitting = wizardState === "submitting"

  return (
    <div
      className="flex h-screen flex-col items-center justify-center bg-zinc-950 p-8"
      role="main"
      aria-label="Language setup"
    >
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-semibold text-zinc-50">Welcome to lingosips</h1>
          <p className="mt-3 text-zinc-400">
            Choose your languages to get started. You can change these anytime in Settings.
          </p>
        </div>

        {/* Error region — aria-live for screen readers */}
        <div aria-live="polite" aria-atomic="true">
          {wizardState === "error" && (
            <div
              role="alert"
              className="rounded-md border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-400"
            >
              {errorMessage}
            </div>
          )}
        </div>

        <div className="space-y-6">
          {/* Native language selector */}
          <div className="space-y-2">
            <label
              htmlFor="native-language"
              className="text-sm font-medium text-zinc-300"
            >
              I speak (native language)
            </label>
            <select
              id="native-language"
              ref={nativeSelectRef}
              value={nativeLang}
              onChange={(e) => setNativeLang(e.target.value)}
              disabled={isSubmitting}
              aria-label="Native language"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2
                         text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500
                         focus:ring-offset-2 focus:ring-offset-zinc-950 disabled:opacity-50"
            >
              {SUPPORTED_LANGUAGES.map(({ code, label }) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Target language selector */}
          <div className="space-y-2">
            <label
              htmlFor="target-language"
              className="text-sm font-medium text-zinc-300"
            >
              I'm learning (target language)
            </label>
            <select
              id="target-language"
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              disabled={isSubmitting}
              aria-label="Target language"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2
                         text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500
                         focus:ring-offset-2 focus:ring-offset-zinc-950 disabled:opacity-50"
            >
              {SUPPORTED_LANGUAGES.map(({ code, label }) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-3">
          {wizardState === "error" ? (
            <button
              onClick={handleRetry}
              className="w-full rounded-md bg-indigo-500 px-4 py-3 font-medium
                         text-white hover:bg-indigo-400 focus:outline-none focus:ring-2
                         focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950"
            >
              Try again
            </button>
          ) : (
            <button
              onClick={handleStartLearning}
              disabled={isSubmitting}
              className="w-full rounded-md bg-indigo-500 px-4 py-3 font-medium
                         text-white hover:bg-indigo-400 focus:outline-none focus:ring-2
                         focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950
                         disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Starting..." : "Start learning"}
            </button>
          )}

          {wizardState !== "submitting" && (
            <button
              onClick={handleSkip}
              className="w-full rounded-md px-4 py-2 text-sm text-zinc-400
                         hover:text-zinc-300 focus:outline-none focus:ring-2
                         focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950"
            >
              Skip for now
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
```

### §TypesNote — `SettingsResponse` in `__root.tsx`

Until `api.d.ts` is regenerated (T8), define a local interface in `__root.tsx`:

```typescript
// Temporary until api.d.ts is regenerated in T8
interface SettingsResponse {
  id: number
  native_language: string
  target_languages: string
  active_target_language: string
  auto_generate_audio: boolean
  auto_generate_images: boolean
  default_practice_mode: string
  cards_per_session: number
  onboarding_completed: boolean
}
```

Remove this interface in T8 after regenerating `api.d.ts`.

### §TestingNotes — Backend Test Patterns

Use the existing `client` fixture from `tests/conftest.py`. Mark all tests `@pytest.mark.anyio`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.anyio
class TestGetSettings:
    async def test_get_settings_creates_default_on_empty_db(self, client: AsyncClient) -> None:
        response = await client.get("/settings")
        assert response.status_code == 200
        body = response.json()
        assert body["native_language"] == "en"
        assert body["active_target_language"] == "es"
        assert body["onboarding_completed"] is False

    async def test_get_settings_is_idempotent(self, client: AsyncClient) -> None:
        await client.get("/settings")  # First call creates row
        await client.get("/settings")  # Second call must find existing row
        # Verify only one row exists by checking that ID is consistent
        r1 = await client.get("/settings")
        r2 = await client.get("/settings")
        assert r1.json()["id"] == r2.json()["id"]

@pytest.mark.anyio
class TestPutSettings:
    async def test_put_settings_invalid_native_language_returns_422(
        self, client: AsyncClient
    ) -> None:
        response = await client.put("/settings", json={"native_language": "xx"})
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "/errors/invalid-language"
        assert "xx" in body["detail"]
```

**Test isolation — critical**: The shared in-memory test engine (`scope="session"`) persists committed rows across tests. `get_or_create_settings` commits when creating a default row. Tests that require an empty `settings` table (T4.2, T4.4) must truncate it first. Add an autouse fixture to your test class:

```python
@pytest.fixture(autouse=True)
async def truncate_settings(test_engine) -> None:
    """Ensure empty settings table before each test."""
    from sqlalchemy import text
    async with test_engine.begin() as conn:
        await conn.execute(text("DELETE FROM settings"))
```

Place this fixture inside `TestGetSettings` class or in a `conftest.py` specific to `tests/api/`. Do NOT add it globally to the root `conftest.py` as it would truncate settings for ALL tests.

**Coverage gate**: Both `core/settings.py` and `api/settings.py` must be fully covered. The 90% CI gate must remain passing.

### §WizardTests — `OnboardingWizard.test.tsx` Pattern

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi } from "vitest"
import { OnboardingWizard } from "./OnboardingWizard"
import * as client from "@/lib/client"

function renderWizard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <OnboardingWizard />
    </QueryClientProvider>
  )
}

describe("OnboardingWizard", () => {
  it("renders in idle state with selects and buttons", () => {
    renderWizard()
    expect(screen.getByLabelText("Native language")).toBeInTheDocument()
    expect(screen.getByLabelText("Target language")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Start learning" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Skip for now" })).toBeEnabled()
    expect(screen.getByRole("main", { name: "Language setup" })).toBeInTheDocument()
  })

  it("disables inputs and button during submission", async () => {
    vi.spyOn(client, "put").mockImplementation(() => new Promise(() => {})) // never resolves
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))
    expect(screen.getByLabelText("Native language")).toBeDisabled()
    expect(screen.getByLabelText("Target language")).toBeDisabled()
    expect(screen.getByRole("button", { name: "Starting..." })).toBeDisabled()
  })

  it("shows error state when PUT fails", async () => {
    vi.spyOn(client, "put").mockRejectedValue(new Error("Network error"))
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument()
      expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled()
    })
  })

  it("skip sends default languages with onboarding_completed=true", async () => {
    const mockPut = vi.spyOn(client, "put").mockResolvedValue({})
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Skip for now" }))
    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith("/settings", {
        native_language: "en",
        active_target_language: "es",
        onboarding_completed: true,
      })
    })
  })
})
```

### §PlaywrightStrategy — E2E Test Considerations

**Test isolation challenge**: The Playwright backend uses a real SQLite DB (`make test-server`). After one test completes onboarding, subsequent tests will see `onboarding_completed=true`. Reset the DB between tests using a `beforeEach` that calls a test-only reset endpoint OR truncates the `settings` table via the test server.

**Recommended approach**: Add a test fixture or `beforeEach` hook that sends `PUT /settings` with `{"onboarding_completed": false}` to reset state between tests. This is simpler than DB truncation.

```typescript
// e2e/features/settings-and-onboarding.spec.ts
import { test, expect, Page } from "@playwright/test"

async function resetOnboarding(page: Page) {
  await page.request.put("http://localhost:7842/settings", {
    data: { onboarding_completed: false },
  })
}

test.describe("First-Run Onboarding", () => {
  test.beforeEach(async ({ page }) => {
    await resetOnboarding(page)
  })

  test("first launch shows OnboardingWizard", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByRole("main", { name: "Language setup" })).toBeVisible()
    // Sidebar and nav must NOT appear during onboarding
    await expect(page.getByRole("navigation", { name: "Main navigation" })).not.toBeVisible()
    await expect(page.getByRole("navigation", { name: "Bottom navigation" })).not.toBeVisible()
  })

  test("completing wizard navigates to home dashboard", async ({ page }) => {
    await page.goto("/")
    // Select French as target
    await page.selectOption('select[aria-label="Target language"]', "fr")
    await page.click('button:has-text("Start learning")')
    // Home dashboard should render — sidebar visible
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible()
    await expect(page.getByRole("main", { name: "Language setup" })).not.toBeVisible()
  })

  test("skip navigates to home dashboard", async ({ page }) => {
    await page.goto("/")
    await page.click('button:has-text("Skip for now")')
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible()
  })
})
```

### §PlaywrightHelper — Update Existing Journey Spec

The `first-launch-card-creation.spec.ts` currently assumes the home page loads directly. After this story, a first launch hits the onboarding wizard. Add a helper to complete onboarding before existing test assertions:

```typescript
// e2e/fixtures/index.ts — add this helper
export async function completeOnboarding(page: Page): Promise<void> {
  // Reset and complete via API to avoid UI interaction overhead
  await page.request.put("http://localhost:7842/settings", {
    data: {
      native_language: "en",
      active_target_language: "es",
      onboarding_completed: true,
    },
  })
}
```

Update `first-launch-card-creation.spec.ts` to call `completeOnboarding(page)` in `beforeEach` before navigating to `/`.

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `SQLModel.metadata.create_all()` anywhere | Alembic only — table already exists from Story 1.1 |
| Creating a new Alembic migration for this story | `settings` table already exists in `001_initial_schema` |
| `import fastapi` in `core/settings.py` | Only in `api/settings.py` |
| `onboarding_completed` stored in Zustand | It lives in `["settings"]` TanStack Query — the server is the source of truth |
| Storing the wizard's `native_language` state in Zustand | Local `useState` in the component is correct |
| Using `window.location.href` to navigate after completion | Invalidate `["settings"]` query → React re-renders → wizard unmounts naturally |
| Multiple Settings rows | `get_or_create_settings` enforces singleton via `select().limit(1)` |
| Manually editing `api.d.ts` | Only `openapi-typescript` generates it (T8) |

### §FileStructure — New and Modified Files

```
src/lingosips/
├── api/
│   ├── app.py              ← UPDATED: include_router(settings_router.router, ...)
│   └── settings.py         ← NEW: GET /settings, PUT /settings
└── core/
    └── settings.py         ← NEW: SUPPORTED_LANGUAGES, get_or_create_settings, update_settings, validate_language_code

tests/
└── api/
    └── test_settings.py    ← NEW (10 tests)

frontend/src/
├── features/
│   └── onboarding/
│       ├── OnboardingWizard.tsx       ← NEW
│       ├── OnboardingWizard.test.tsx  ← NEW
│       └── index.ts                  ← NEW
└── routes/
    └── __root.tsx                    ← UPDATED: onboarding gate added

frontend/e2e/
├── features/
│   └── settings-and-onboarding.spec.ts  ← NEW
├── journeys/
│   └── first-launch-card-creation.spec.ts  ← UPDATED: completeOnboarding helper
└── fixtures/
    └── index.ts                           ← UPDATED: add completeOnboarding helper
```

### §RuffCompliance

After implementing Python changes, run:
```bash
uv run ruff check --fix src/lingosips/api/settings.py src/lingosips/core/settings.py tests/api/test_settings.py
```

Common ruff issues to pre-empt:
- Import order: stdlib → sqlalchemy/sqlmodel → fastapi → local lingosips
- `from __future__ import annotations` not needed if Python 3.12
- `Any` import: `from typing import Any`

### Previous Story Intelligence

From Story 1.3 (last completed):
- **Test pattern**: All tests use `@pytest.mark.anyio` + `client` fixture from `conftest.py`. Inject `async def` test methods into `class TestX:` blocks.
- **RFC 7807 error format**: `{"type": "/errors/...", "title": "...", "detail": "...", "status": 422}` — used in `api/app.py` handler and must match in tests.
- **Dynamic route test cleanup**: Avoid injecting test-only routes into the live app — use proper test client mocking instead.
- **Coverage gate**: 90% backend line coverage is a hard CI gate. New files must be fully tested.
- **`_scrub_detail` exception handler**: Already in `app.py`. Any `HTTPException` with dict detail is automatically scrubbed — your 422 dict detail is safe.
- **structlog**: Use `logger = structlog.get_logger(__name__)` at module level. Log events in snake_case: `logger.info("settings.created_defaults")`.

From Story 1.2 (app shell):
- **`__root.tsx` is the gate for all routes** — all UI renders through it. Adding the onboarding query here is the correct interception point.
- **TanStack Query `["settings"]` key** — per project-context.md: `["settings"]` is the established key for settings data. Do not use `["settings", "list"]` or any other variation.
- **TanStack Router** — file-based routing; `__root.tsx` wraps everything. The wizard replaces the full layout before Outlet renders, which is correct.

### References

- Story 1.4 acceptance criteria: [Source: epics.md#Story 1.4]
- `Settings` model: `native_language`, `target_languages`, `active_target_language`, `onboarding_completed`: [Source: db/models.py lines 56–70]
- Layer architecture (core vs api): [Source: project-context.md#Layer Architecture & Boundaries]
- TanStack Query key convention `["settings"]`: [Source: project-context.md#Frontend Architecture Rules]
- `lib/client.ts` is the ONLY fetch caller: [Source: project-context.md#Frontend Architecture Rules, frontend/src/lib/client.ts]
- Onboarding = language selection only, service config optional: [Source: epics.md#UX-DR11]
- UX-DR13: Error messages name what failed + why + what to do: [Source: epics.md#UX-DR13]
- FR38: Guided onboarding wizard; FR39: functional before any config; FR40: first card within 60 seconds: [Source: epics.md#FR Coverage Map]
- `useAppStore.onboardingStep` already declared in `useAppStore.ts` (may be repurposed or kept separate): [Source: frontend/src/lib/stores/useAppStore.ts line 22]
- TDD mandatory — write failing tests before implementation: [Source: project-context.md#Testing Rules]
- 90% backend coverage CI hard gate: [Source: project-context.md#CI gates]
- Playwright runs against real backend on port 7842: [Source: project-context.md#Testing Rules]
- API field names must be snake_case (not camelCase): [Source: project-context.md#Naming Conventions]
- RFC 7807 error format: [Source: project-context.md#API Design Rules]
- Component state machines must be enum-driven (not boolean flags): [Source: project-context.md#Frontend Architecture Rules]
- `"Start learning"` UX copy and wizard flow: [Source: ux-design-specification.md, Journey 1 flowchart]
- `onboardingStep` in `useAppStore` is a separate concern (for service configuration onboarding in future stories) — do NOT use it for the `OnboardingWizard` state machine; keep wizard state in local `useState`: [Source: frontend/src/lib/stores/useAppStore.ts line 22, UX-DR11]
- `app-shell.spec.ts` will break after this story without the `completeOnboarding` fix: [Source: frontend/e2e/features/app-shell.spec.ts]
- Font, color tokens (zinc-950 bg, indigo-500 accent, zinc-50 text): [Source: project-context.md#Technology Stack, UX-DR8]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5)

### Debug Log References

- **Debug 1**: `session.exec()` not available on SQLAlchemy `AsyncSession` — switched to `session.execute()` + `.scalars().first()` since the project uses SQLAlchemy's `AsyncSession` (not SQLModel's). All 10 backend tests then passed.
- **Debug 2**: `TestSPAFallback::test_browser_404_serves_index_html` in `test_app.py` used `/settings` as the test URL for 404 fallback. Now that `/settings` is a real endpoint, updated test to use `/react-client-route` instead.
- **Debug 3**: `BottomNav.test.tsx` and `IconSidebar.test.tsx` rendered `RouterProvider` without `QueryClientProvider`. After adding `useQuery` to `RootLayout`, these tests threw "No QueryClient set". Fixed by: (1) importing `QueryClientProvider`, (2) wrapping `RouterProvider` in `QueryClientProvider`, (3) pre-seeding `["settings"]` cache with `onboarding_completed: true` so the onboarding gate passes in unit tests.

### Completion Notes List

- **TDD followed throughout**: T4 backend tests written before T1/T2 implementation; T5.1 test written before T5.2 component.
- **`session.execute()` vs `session.exec()`**: Project uses SQLAlchemy's `AsyncSession` (not SQLModel's). Dev Notes showed `session.exec()` but actual code requires `session.execute().scalars().first()`.
- **Coverage gate maintained**: All new code fully tested; total backend coverage 90.37% (gate is 90%).
- **api.d.ts regenerated**: `SettingsResponse` now imported from generated types in `__root.tsx` instead of local interface.
- **No regressions**: 70 backend tests + 38 frontend tests all pass after implementation.
- **Playwright E2E updated**: `app-shell.spec.ts` and `first-launch-card-creation.spec.ts` updated with `completeOnboarding()` in `beforeEach` to prevent wizard blocking existing test assertions.

### File List

**New files:**
- `src/lingosips/core/settings.py`
- `src/lingosips/api/settings.py`
- `tests/api/test_settings.py`
- `frontend/src/features/onboarding/OnboardingWizard.tsx`
- `frontend/src/features/onboarding/OnboardingWizard.test.tsx`
- `frontend/src/features/onboarding/index.ts`
- `frontend/e2e/features/settings-and-onboarding.spec.ts`

**Modified files:**
- `src/lingosips/api/app.py` — registered settings router
- `frontend/src/routes/__root.tsx` — onboarding gate added
- `frontend/src/lib/api.d.ts` — regenerated with SettingsResponse/SettingsUpdateRequest types
- `frontend/e2e/fixtures/index.ts` — added `completeOnboarding()` helper
- `frontend/e2e/journeys/first-launch-card-creation.spec.ts` — added `completeOnboarding` in beforeEach
- `frontend/e2e/features/app-shell.spec.ts` — added `completeOnboarding` in beforeEach for all groups
- `frontend/src/components/layout/__tests__/BottomNav.test.tsx` — pre-seed settings cache + QueryClientProvider
- `frontend/src/components/layout/__tests__/IconSidebar.test.tsx` — pre-seed settings cache + QueryClientProvider
- `tests/api/test_app.py` — updated SPA 404 test URL (was `/settings`, now `/react-client-route`)

### Review Findings

- [x] [Review][Patch] Missing `isError` guard in `__root.tsx` — network failure showed wizard to returning users [`frontend/src/routes/__root.tsx`]
- [x] [Review][Patch] `onSuccess` in `OnboardingWizard` never reset `wizardState` to `"idle"` — form permanently disabled during slow refetch [`frontend/src/features/onboarding/OnboardingWizard.tsx:68`]
- [x] [Review][Patch] E2E `resetOnboarding` only reset `onboarding_completed`, not language fields — cross-test contamination [`frontend/e2e/features/settings-and-onboarding.spec.ts:17`]
- [x] [Review][Patch] E2E T7.3 missing positive `Main navigation` assertion (AC2 weak coverage) [`frontend/e2e/features/settings-and-onboarding.spec.ts:66`]
- [x] [Review][Patch] E2E T7.4 missing positive `Main navigation` assertion (AC3 weak coverage) [`frontend/e2e/features/settings-and-onboarding.spec.ts:74`]
- [x] [Review][Patch] Duplicate language validation blocks — extracted `_raise_invalid_language()` helper [`src/lingosips/api/settings.py:49`]
- [x] [Review][Patch] `model_dump()` dict comprehension replaced with idiomatic `model_dump(exclude_none=True)` [`src/lingosips/api/settings.py:87`]
- [x] [Review][Patch] Missing test for `PUT /settings` with `onboarding_completed: false` — validates `False` passes `exclude_none` filter [`tests/api/test_settings.py`]
- [x] [Review][Defer] Race condition in `get_or_create_settings` concurrent inserts — pre-existing, very unlikely for local single-process SQLite app — deferred, pre-existing
- [x] [Review][Defer] `target_languages` field not updated when `active_target_language` changes — separate multi-language concern for future story — deferred, pre-existing
- [x] [Review][Defer] `api.d.ts` 422 response type is `HTTPValidationError` rather than actual RFC 7807 Problem Detail shape — OpenAPI schema limitation, not a runtime bug — deferred, pre-existing

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-04-30 | Implemented Story 1.4: first-run language onboarding wizard. Created `core/settings.py` and `api/settings.py` with GET/PUT /settings endpoints. Created `OnboardingWizard.tsx` with full state machine. Wired onboarding gate into `__root.tsx`. Added 10 backend tests and 13 frontend component tests. Created Playwright E2E spec. Regenerated `api.d.ts`. Updated existing tests to add `completeOnboarding()` helper for test isolation. | Dev Agent |
| 2026-04-30 | Code review (Story 1.4): Fixed 8 patch findings — added `isError` branch in `__root.tsx`, fixed `onSuccess` state machine transition in wizard, improved E2E test isolation and assertions, refactored duplicate validation logic, used `model_dump(exclude_none=True)`, added `onboarding_completed: false` reset test. 71 backend + 38 frontend tests pass. Coverage 90.43%. | Code Review Agent |
