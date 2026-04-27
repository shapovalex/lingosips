---
project_name: 'lingosips'
user_name: 'Oleksii'
date: '2026-04-26'
sections_completed: ['technology_stack', 'naming_conventions', 'layer_architecture', 'api_design', 'frontend_architecture', 'testing_rules', 'critical_anti_patterns', 'security_rules', 'workflow']
status: 'complete'
rule_count: 47
optimized_for_llm: true
---

# Project Context for AI Agents — lingosips

_Critical rules and patterns AI agents must follow when implementing code. Focus on unobvious details that would otherwise be missed._

---

## Technology Stack & Versions

**Backend (Python — managed by `uv`):**
- Python 3.12+ (`uv` manages the Python version; no system Python required)
- FastAPI + uvicorn (async REST + SSE)
- SQLModel + aiosqlite — ORM and async SQLite driver
- Alembic — schema migrations (run on startup, never `create_all()` in production)
- `fsrs` v6.3.1 — FSRS scheduling engine (PyPI package `fsrs`)
- `llama-cpp-python` — local LLM (Qwen GGUF format)
- `faster-whisper` — local speech recognition (CTranslate2)
- `pyttsx3` — local TTS fallback for card audio
- `genanki` — Anki `.apkg` import/export
- `keyring` — OS keychain credential storage
- `structlog` — structured logging with credential scrubbing
- `httpx` — async HTTP client for external services
- `ruff` — linter + formatter (enforces naming and import order)
- `pytest` + `httpx` async client — backend tests

**Frontend (TypeScript strict mode — `npm`):**
- Vite 6 — bundler; dev server proxies to FastAPI
- React + TypeScript (strict mode enforced)
- Tailwind CSS v4 + shadcn/ui (Zinc palette, `zinc-950` bg, dark-mode default)
- TanStack Query v5.99.2 — server state
- TanStack Router (latest) — file-based routing, type-safe params
- Zustand v5.0.12 — UI-only state
- `openapi-typescript` — generates `src/lib/api.d.ts` from FastAPI OpenAPI schema at build time
- Vitest + React Testing Library — component tests
- Playwright — E2E tests (run against a real backend, not mocked)

**Distribution:**
- Packaged as a Python wheel; `uv tool install lingosips` is the user install command
- Frontend assets compiled into `src/lingosips/static/` and bundled into the wheel
- Server runs on `127.0.0.1:7842` (fixed; not configurable in MVP)

---

## Naming Conventions

**CRITICAL — these are enforced by ruff and TypeScript strict mode:**

### All JSON API fields: snake_case (no exceptions, no aliasing)
```json
// CORRECT
{ "card_id": 42, "target_word": "melancólico", "last_review": "2026-04-26T10:00:00Z" }

// WRONG — never camelCase in JSON, even from TypeScript
{ "cardId": 42, "targetWord": "melancólico" }
```
`openapi-typescript` generates TS types with snake_case property names intentionally.

### Database (SQLModel)
- Tables: plural snake_case — `cards`, `decks`, `reviews`, `jobs`
- Columns: snake_case — `card_id`, `target_word`, `last_review`
- Foreign keys: `{table_singular}_id` — `card_id`, `deck_id`
- Indexes: `ix_{table}_{column}` — `ix_cards_due`, `ix_reviews_card_id`
- **Never camelCase columns. Never PascalCase columns.**

### API Routes
- Resources: plural snake_case — `/cards`, `/decks`, `/practice`
- Sub-resources: `/cards/{card_id}/audio`, `/decks/{deck_id}/cards`
- Path params: snake_case — `{card_id}`, `{deck_id}`, `{job_id}`
- Query params: snake_case — `?deck_id=1&include_due=true`

### Python Code
- Modules, functions, variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

### TypeScript / React
- Component files: `PascalCase` — `CardCreationPanel.tsx`
- Hook files: `camelCase` with `use` prefix — `useCardStream.ts`
- Route files: kebab-case — `routes/card-detail.tsx`
- Types/interfaces: `PascalCase` — `CardResponse`, `PracticeSession`
- Store files: `use{Name}Store.ts` — `useAppStore.ts`

---

## Layer Architecture & Boundaries

**This is the single most important structural rule:**

### Backend — strict layer separation
```
api/{domain}.py     → FastAPI router ONLY — no business logic, no direct DB queries
core/{domain}.py    → Business logic ONLY — no FastAPI imports, no SQLModel imports
services/           → External provider abstractions only
db/models.py        → ALL SQLModel table definitions in ONE file
db/session.py       → Async engine + get_session Depends() — the only DB entry point
services/registry.py → ONLY location for provider fallback logic
services/credentials.py → ONLY reader/writer of keyring — no other module touches keyring
```

### Router must delegate to core — never contain logic:
```python
# CORRECT
@router.post("/cards/stream")
async def create_card(
    request: CardCreateRequest,
    llm: AbstractLLMProvider = Depends(get_llm_provider),
    session: AsyncSession = Depends(get_session),
):
    async for event in core.cards.create_card_stream(request, llm, session):
        yield event

# WRONG — business logic in router
@router.post("/cards/stream")
async def create_card(request: CardCreateRequest):
    response = await httpx.post("https://openrouter.ai/...")  # ❌ never
```

### Core modules take primitives, return domain objects:
- `core/` never imports `fastapi`, `SQLModel`, or `AsyncSession` directly
- `api/` routers pass resolved sessions and providers via `Depends()`
- `core/fsrs.py` wraps the `fsrs` library — `api/practice.py` never calls `fsrs` directly

### Frontend state boundary:
- **TanStack Query** owns ALL server-sourced data — cards, decks, queue, progress, settings
- **Zustand** owns UI-only state — active session, service status, notifications, onboarding step
- **NEVER** store API responses in Zustand
- **NEVER** duplicate TanStack Query data in Zustand
- `lib/client.ts` is the ONLY module that calls `fetch()`

---

## Dependency Injection — Depends() Always

**Never instantiate providers directly:**
```python
# CORRECT — always use Depends()
async def create_card(llm: AbstractLLMProvider = Depends(get_llm_provider)): ...

# WRONG — never instantiate providers outside services/registry.py
llm = OpenRouterProvider(api_key="...")  # ❌ never
```

**Provider fallback lives exclusively in `services/registry.py`:**
```python
def get_llm_provider(settings: Settings = Depends(get_settings)) -> AbstractLLMProvider:
    if settings.openrouter_key:
        return OpenRouterProvider(settings.openrouter_key, settings.openrouter_model)
    return QwenLocalProvider(settings.qwen_model_path)
```

---

## API Design Rules

### Error responses — RFC 7807 Problem Details (all errors):
```python
raise HTTPException(
    status_code=404,
    detail={"type": "/errors/card-not-found", "title": "Card not found", "detail": f"Card {card_id} does not exist"}
)
```

### Response shape: direct Pydantic model — no wrapper envelope
```json
// CORRECT — direct model
{ "id": 42, "target_word": "melancólico", "translation": "melancholic" }

// WRONG — never wrap
{ "data": { "id": 42 }, "status": "ok" }
```

### IDs: integer primary keys — no UUIDs, no slugs
### Dates: ISO 8601 UTC — `"2026-04-26T15:30:00Z"` — frontend uses `Intl.DateTimeFormat`, no date libraries
### Empty collections: return `[]` not `null`

### SSE Event Envelope — identical across ALL streaming channels:
```
event: {event_type}
data: {json_payload}

```
Event types: `field_update` | `progress` | `complete` | `error`
```json
// field_update: { "field": "translation", "value": "melancholic" }
// progress:     { "done": 23, "total": 400, "current_item": "enriching audio..." }
// error:        { "message": "Local Qwen timeout after 10s" }
```
Three SSE channels: `POST /cards/stream`, `GET /import/{job_id}/progress`, `GET /models/download/progress`

### Background jobs — persist status before starting async work:
```python
# CORRECT — persist first
async def enrich_import(job_id: int, cards: list, session: AsyncSession):
    await update_job_status(session, job_id, "running", total=len(cards))  # persisted first
    for i, card in enumerate(cards):
        enriched = await llm.enrich(card)
        await update_job_progress(session, job_id, done=i+1)

# WRONG — work before persistence = data lost on restart
async def enrich_import(cards: list):
    for card in cards:
        await llm.enrich(card)  # ❌
```

---

## Frontend Architecture Rules

### TanStack Query key conventions:
```typescript
["cards"]                    // list
["cards", cardId]            // single
["decks", deckId, "cards"]  // nested
["practice", "queue"]
["progress", "dashboard"]
["settings"]
["models", "status"]

// WRONG
["getCards"]                 // ❌ never verb-prefixed
[{ resource: "cards" }]     // ❌ never object keys
```

### Zustand store files and scope:
```typescript
// src/lib/stores/
// useAppStore.ts       → service status, notifications, onboarding
// usePracticeStore.ts  → active session state
// useSettingsStore.ts  → persisted local preferences (zustand/middleware localStorage)

// CORRECT — UI state only
const useAppStore = create<AppStore>((set) => ({
  activeServiceStatus: { llm: "local", speech: "local" },
  practiceSession: null,
  pendingNotifications: [],
}))

// WRONG — server data in Zustand
const useCardStore = create(() => ({ cards: [] }))  // ❌ belongs in TanStack Query
```

### Component state machines — enum-driven, never boolean flags:
```typescript
// CORRECT
type CardCreationState = "idle" | "loading" | "populated" | "saving" | "error"
const [state, setState] = useState<CardCreationState>("idle")

// WRONG
const [isLoading, setIsLoading] = useState(false)
const [hasError, setHasError] = useState(false)  // ❌ boolean flag soup
```

### Error flow pattern:
```typescript
// API error → TanStack Query onError → Zustand notification → Toast
useMutation({
  mutationFn: createCard,
  onError: (error: ApiError) => {
    useAppStore.getState().addNotification({ type: "error", message: error.detail })
  },
})
// WRONG
onError: (e) => { alert(e.message) }  // ❌
```

### Loading states:
- Use TanStack Query `isLoading` / `isPending` — never duplicate with `useState`
- Skeleton components for content areas; optimistic updates for FSRS ratings
- Never show spinner during practice card transitions (60fps target)

### Feature isolation:
- `src/features/{domain}/` — never import from one feature into another
- Route through `src/lib/` if cross-feature data is needed
- Each feature directory must have an `index.ts` that exports only its public surface

---

## Testing Rules — Non-Negotiable

**TDD is mandatory. Stories are not complete until tests pass. Write failing tests before any implementation.**

### Backend — pytest + httpx (90% line coverage CI hard gate)

#### Every FastAPI endpoint MUST have tests covering:

**Positive scenarios:**
- Happy path with valid input → correct response shape + status code
- All optional fields behave correctly when present

**Negative scenarios:**
- Missing required fields → `422 Unprocessable Entity`
- Invalid field types/formats → `422` with field-level detail
- Resource not found → `404` with RFC 7807 body
- Conflicting state → `409`
- External service unavailable → graceful fallback, correct response

**Edge cases:**
- Empty collections return `[]` not `null`
- Boundary values (0 cards, 1 card, max-length strings)
- Concurrent mutations
- SSE streams: complete event sequence verified; mid-stream error emits `error` event

```python
# Required test class structure for every endpoint:
class TestCreateCard:
    async def test_create_card_success(self, client, mock_llm_provider): ...
    async def test_create_card_missing_target_word_returns_422(self, client): ...
    async def test_create_card_llm_timeout_falls_back_to_local(self, client, mock_openrouter_timeout): ...
    async def test_create_card_stream_emits_all_field_events(self, client, mock_llm_provider): ...
    async def test_create_card_stream_emits_error_event_on_failure(self, client, mock_llm_failure): ...

class TestGetCard:
    async def test_get_card_success(self, client, seed_card): ...
    async def test_get_card_not_found_returns_404_problem_detail(self, client): ...
```

### Frontend components — Vitest + React Testing Library

Each custom component must cover:
- Every state in the component's state machine enum
- Keyboard interactions from the UX spec
- `aria-label` and `aria-live` announcements
- 100% state machine branch coverage required for the 5 primary custom components:
  `CardCreationPanel`, `PracticeCard`, `SyllableFeedback`, `QueueWidget`, `ServiceStatusIndicator`

### E2E — Playwright (run against real backend with test SQLite DB — NEVER mocked server)

**Every user story and functional requirement must be covered by at least one Playwright spec.**

FR1–FR50 must each be touched by at least one spec. The five PRD journeys map directly to test files:
```
frontend/e2e/journeys/
├── first-launch-card-creation.spec.ts
├── vocabulary-capture.spec.ts
├── speak-mode-session.spec.ts
├── import-and-enrichment.spec.ts
└── service-configuration.spec.ts

frontend/e2e/features/
├── card-management.spec.ts          # FR1–8
├── deck-management.spec.ts          # FR9–16
├── practice-self-assess.spec.ts     # FR17–18, FR24–25
├── practice-write-mode.spec.ts      # FR19–20
├── practice-speak-mode.spec.ts      # FR21–22
├── fsrs-scheduling.spec.ts          # FR23–25
├── settings-and-onboarding.spec.ts  # FR30–40
└── progress-and-cefr.spec.ts        # FR41–47
```

Every Playwright spec must test:
- The happy path to completion
- At least one error/degraded state
- Keyboard navigation of the primary flow
- Correct UI state after the action

**Playwright runs against a real running backend:**
```typescript
// playwright.config.ts
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:7842" },
  webServer: {
    command: "make test-server",  // starts backend with test DB
    url: "http://localhost:7842",
    reuseExistingServer: false,
  },
})
```

### CI gates (hard — PRs blocked if failing):
```yaml
backend-tests:   uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90
frontend-tests:  npm run test -- --coverage
e2e-tests:       make test-server & npx playwright test
```

---

## Security Rules

- **All credentials** go through `services/credentials.py` → `keyring` OS keychain only
- **No other module reads keyring** — not routers, not core, not tests
- Credentials must never appear in logs, error messages, error responses, or crash reports
- `structlog` is configured with a credential-scrubbing processor — always use `structlog`, never `print()` or `logging` directly
- FastAPI server bound to `127.0.0.1:7842` exclusively — never `0.0.0.0`
- No telemetry, no analytics, no background pings — the only uninstructed outbound call is the PyPI version check (async, non-blocking)
- Log level: `LINGOSIPS_LOG_LEVEL` env var; default `WARNING` in production

---

## Database Rules

- **Alembic owns schema evolution** — never use `SQLModel.metadata.create_all()` in production code
- Migrations run automatically on app startup before server accepts requests
- All DB access through `db/session.py` `get_session` dependency — no raw SQLite connections
- SQLite WAL mode enabled — all writes confirmed before SSE `complete` event is sent
- DB file location: `~/.lingosips/lingosips.db` — never configurable, never relative path
- All reads/writes through async SQLModel sessions — no synchronous DB calls in async endpoints

---

## Development Workflow

### Makefile targets:
```makefile
dev:         uvicorn src.lingosips.api.app:app --reload & vite dev --port 5173
build:       cd frontend && npm run build && cp -r dist/* ../src/lingosips/static/
test:        uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90 && npm run test
test-server: uv run uvicorn src.lingosips.api.app:app --port 7842 --env-file .env.test
e2e:         npx playwright test
publish:     make build && uv build && uv publish
```

### API types must stay in sync:
- `openapi-typescript` regenerates `src/lib/api.d.ts` from the live FastAPI OpenAPI schema at build time
- CI enforces that `api.d.ts` is not stale — if schema drifts, CI fails
- **Never manually edit `api.d.ts`** — it is always generated

### Versioning:
- `pyproject.toml` version is the single source of truth
- Git tag `v{major}.{minor}.{patch}` triggers the publish GitHub Action

---

## Critical Anti-Patterns (AI Agents Must NOT Do)

| Anti-Pattern | Rule |
|---|---|
| camelCase in JSON fields | All JSON is snake_case — `openapi-typescript` types match |
| Business logic in `api/` routers | Routers delegate to `core/` — no exceptions |
| Direct provider instantiation | Always `Depends(get_llm_provider)` / `Depends(get_speech_provider)` |
| Server data in Zustand | TanStack Query owns all server state |
| Boolean flag state in components | Always enum-driven state machines |
| `SQLModel.metadata.create_all()` | Alembic only — never create_all in production |
| Plaintext credentials anywhere | `keyring` via `services/credentials.py` only |
| Fallback logic outside `services/registry.py` | All cloud→local fallback in registry only |
| Starting async work before persisting job status | Persist job status to SQLite first |
| Cross-feature imports | Features are isolated; share through `src/lib/` only |
| Mocked server in Playwright tests | E2E runs against real backend on port 7842 |
| Writing tests after implementation | TDD: failing test first, then implementation |
| Implementing an endpoint without positive + negative + edge tests | All three test categories required per endpoint |

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — these are architectural decisions, not suggestions
- When in doubt, prefer the more restrictive option
- The architecture document at `_bmad-output/planning-artifacts/architecture.md` is the authoritative source for any question not answered here

**For Humans:**
- Keep this file lean and focused on unobvious agent pitfalls
- Update when technology stack or patterns change
- Remove rules that become obvious over time

_Last Updated: 2026-04-26_
