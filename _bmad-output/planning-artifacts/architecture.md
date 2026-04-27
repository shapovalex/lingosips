---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-04-26'
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/ux-design-specification.md"
workflowType: 'architecture'
project_name: 'lingosips'
user_name: 'Oleksii'
date: '2026-04-26'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

50 FRs across 8 domains:
- **Card Management (FR1–8):** AI-powered card creation pipeline; manual edit by exception; optional image generation
- **Deck Management (FR9–16):** Multi-deck, multi-language; import from Anki/.apkg/text/URL with AI enrichment; file-based deck sharing
- **Practice & Learning (FR17–25):** Three practice modes (self-assess, write, speak); AI feedback on write answers; per-syllable speech evaluation; FSRS scheduling and failure-triggered rescheduling
- **AI & Speech Services (FR26–29):** Cloud/local routing for LLM and speech; token-by-token streaming; on-demand service connection testing
- **Settings & Configuration (FR30–37):** Full BYOK configuration (OpenRouter, Azure Speech, image endpoint, Whisper model); OS keychain credential storage; system-wide and deck-level defaults
- **Onboarding (FR38–40):** Guided per-service setup; fully functional before any key is configured; first card within 60 seconds
- **Progress & Analytics (FR41–43):** Dashboard (vocabulary size, review activity); per-session stats; FSRS state surfacing
- **Learner Intelligence (FR44–47):** Continuous CEFR knowledge profile built from breadth, grammar forms, performance, and recall history; explanatory level assessment with gap analysis

**Non-Functional Requirements (architecturally decisive):**

- **Performance:** Card creation <3s cloud / <5s local; speech eval <2s; first token visible <500ms; 60fps practice transitions; background batch enrichment non-blocking
- **Security:** OS keychain for all credentials; never plaintext, never in logs, never in crash reports; zero telemetry
- **Reliability:** All core features fully offline; external service failure → silent local fallback with user notification; writes durable before confirmation
- **Accessibility:** WCAG 2.1 AA; full keyboard navigation; screen reader support; `prefers-reduced-motion` compliance
- **Integration:** OpenRouter (streaming REST), Azure Speech (real-time pronunciation assessment), Qwen via Ollama-compatible API, Whisper (local process), image gen (OpenAI-format REST), Anki .apkg import
- **Maintainability:** AI service abstraction (LLM + speech behind swappable interfaces); storage abstraction (SQLite for desktop, browser-compatible abstraction for web)

**Scale & Complexity:**

- Primary domain: Full-stack desktop-web hybrid (Python backend + React SPA)
- Complexity level: Medium-High — AI/speech integration with dual fallback chains, offline-first architecture, five distinct user journeys, FSRS domain engine, CEFR profile aggregation
- Estimated architectural components: 8–10 distinct subsystems

### Technical Constraints & Dependencies

**Platform (decided in UX spec):**
- Runtime: Python backend (local server) + SPA frontend served to Chrome
- Storage: SQLite managed by Python backend — no browser storage dependency
- Local AI: Python manages Qwen (Ollama-compatible API) and Whisper directly — no separate user-managed inference server
- Frontend: React + Tailwind CSS + shadcn/ui

**Key constraints:**
- Storage abstraction must be decided before writing any UI that touches data — SQLite (desktop) with browser-compatible abstraction (web) is the canonical model
- Credentials must flow through OS keychain (where available) / encrypted local store — never through env vars or plaintext config
- All outbound API calls limited to explicitly configured services — no implicit third-party transmission
- Local fallback must deliver a complete, working product — not a degraded mode

### Cross-Cutting Concerns Identified

1. **AI Service Routing Layer** — LLM and speech each need a cloud/local fallback router; service health, fallback decision, and user notification must be centralized, not scattered across call sites
2. **Credential Security Layer** — OS keychain access, log redaction, and credential validation touch storage, logging, and every outbound service
3. **FSRS Scheduling Engine** — scheduling state on every card; drives queue calculation, failure rescheduling, and session summary; a first-class domain engine, not a utility
4. **Background Job Queue** — import AI enrichment, batch audio generation; must run without blocking UI; progress must be observable from the frontend
5. **Content Safety Filter** — gates all AI-generated text and images before display; a cross-cutting middleware concern
6. **Offline Detection & Service Degradation** — network state affects card creation, speech eval, and import enrichment; degradation logic (fall to local, notify user) must be uniform
7. **CEFR Profile Aggregation Engine** — continuously updated read model built from vocabulary breadth, grammar forms, practice performance, and recall history; query performance matters at scale
8. **Streaming Response Handler** — structured JSON card creation with staggered field reveal; distinct from token-streaming but requires a consistent async response pattern

## Starter Template Evaluation

### Primary Technology Domain

Python web application: FastAPI local server + Vite React SPA bundled into a single installable Python package. No desktop wrapper. User installs once, runs a command, opens a browser. `uv` is the only prerequisite.

### Starter Options Considered

**Single-command full-stack starters evaluated:**
- `vintasoftware/nextjs-fastapi-template` — Next.js (SSR); wrong deployment model
- `create-fastapi-project` (PyPI) — backend only; no frontend bundling story
- Manual monorepo (FastAPI + Vite) — matches requirements exactly; chosen

**Conclusion:** No existing template covers this combination. Two-part manual init with a defined build pipeline is the correct approach.

### Selected Starter: FastAPI + Vite React TS (uv-managed monorepo)

**Rationale:** The app is a Python process the user runs locally — the browser is the UI, not a wrapper. Distribution via PyPI + `uv tool install` gives a single install command, isolated environment, and `uv tool upgrade lingosips` for updates. Frontend assets are compiled into the Python wheel so the package is self-contained.

**Project Layout:**
```
lingosips/
├── src/
│   └── lingosips/
│       ├── __main__.py          # CLI entry: start FastAPI + open browser
│       ├── api/                 # FastAPI routers (cards, practice, settings, import, progress)
│       ├── core/                # FSRS engine, CEFR profiler, content safety filter
│       ├── db/                  # SQLModel table definitions, SQLite session
│       ├── services/
│       │   ├── llm/             # AbstractLLMProvider → OpenRouterProvider, QwenLocalProvider
│       │   ├── speech/          # AbstractSpeechProvider → AzureSpeechProvider, WhisperLocalProvider
│       │   └── image.py         # Image generation (OpenAI-format REST)
│       ├── models/              # Local model download + lifecycle manager
│       └── static/              # Built Vite assets (generated at build time, not git-tracked)
├── frontend/                    # Vite React TypeScript (dev source only)
│   ├── src/
│   │   ├── features/            # cards/, practice/, settings/, progress/, import/
│   │   ├── components/ui/       # shadcn/ui owned components
│   │   └── lib/                 # API client, utils
│   └── dist/ → copied to src/lingosips/static/ at build time
├── pyproject.toml               # uv project: metadata, deps, scripts, package-data
├── uv.lock
└── Makefile                     # dev, build, publish targets
```

**Initialization Commands:**

```bash
# Prerequisites: uv installed (https://docs.astral.sh/uv/getting-started/installation/)

# Bootstrap project
uv init lingosips --package
cd lingosips

# Backend dependencies
uv add fastapi "uvicorn[standard]" sqlmodel aiosqlite python-multipart httpx
uv add llama-cpp-python faster-whisper
uv add --dev pytest httpx ruff

# Frontend scaffold
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npx shadcn@latest init   # Zinc base · dark mode default · CSS variables on
npx shadcn@latest add button input card skeleton progress tabs tooltip toast dialog dropdown-menu separator badge
cd ..
```

**pyproject.toml essentials:**
```toml
[project.scripts]
lingosips = "lingosips.__main__:main"

[tool.uv]
package = true

[tool.hatch.build.targets.wheel]
include = ["src/lingosips/static/**"]   # Bundle compiled frontend
```

**Build pipeline:**
```bash
# Full build (runs before uv build / uv publish)
cd frontend && npm run build            # outputs frontend/dist/
cp -r frontend/dist/* src/lingosips/static/
uv build                                # produces wheel with static/ included
uv publish                              # push to PyPI
```

**User installation:**
```bash
uv tool install lingosips    # installs from PyPI, isolated env, adds to PATH
lingosips                    # starts server on localhost:7842, opens browser
uv tool upgrade lingosips    # update to latest release
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
- Python 3.12+ (uv manages Python version; no system Python required)
- TypeScript strict mode for frontend — type-safe API contracts
- `uv` as the sole Python toolchain — replaces pip, venv, poetry

**Local AI Libraries:**
- LLM: `llama-cpp-python` — GGUF format, CPU + GPU inference; Qwen GGUF models downloaded to `~/.lingosips/models/` on first local-model use
- Speech: `faster-whisper` — CTranslate2-based reimplementation; faster than openai-whisper on CPU; models auto-downloaded from HuggingFace on first use

**Styling Solution:**
- Tailwind CSS v4 + shadcn/ui (Zinc palette, `zinc-950` background, dark-mode default)
- Components owned in `frontend/src/components/ui/` — no version lock-in

**Build Tooling:**
- Vite 6 for frontend; FastAPI serves `static/` in production, proxies to Vite dev server in dev
- `uv build` + `uv publish` for package distribution

**Testing Framework:**
- Frontend: Vitest + React Testing Library
- Backend: pytest + httpx async client

**Auto-Update:**
- On startup, async check PyPI JSON API (`https://pypi.org/pypi/lingosips/json`) for latest version; compare with `importlib.metadata.version("lingosips")`
- If newer: surface "Update available — run `uv tool upgrade lingosips`" banner in browser UI (non-blocking; dismissible)

**Local Model Management (no Ollama):**
- `services/models/manager.py` owns all model download, verification, and lifecycle
- Models stored in `~/.lingosips/models/{model_name}/`
- First-use download shows progress in browser via SSE stream
- Model selection exposed in Settings UI (Qwen model size, Whisper model size)
- Hash verification on download; resume-capable via HTTP Range requests

**Development Experience:**
- `make dev` — starts `uvicorn --reload` + `vite dev` concurrently
- `make build` — builds frontend, copies to static/, runs `uv build`
- `make publish` — build + `uv publish` to PyPI

**Note:** Project initialization using the commands above is the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Schema migration strategy (Alembic) — must exist before first data model is written
- FSRS library selection (`fsrs` v6.3.1) — core scheduling engine; affects card table schema
- Real-time communication pattern (SSE) — affects API design and frontend client
- Credential storage strategy (`keyring`) — must be wired before any external service call

**Important Decisions (Shape Architecture):**
- Frontend state split: TanStack Query (server state) + Zustand (UI state)
- Frontend routing: TanStack Router
- API client: openapi-typescript auto-generated from FastAPI OpenAPI schema
- Structured logging: structlog with credential-scrubbing processor

**Deferred Decisions (Post-MVP):**
- Desktop packaging (Tauri v2 sidecar) — Phase 2; no structural changes needed
- PWA / service worker — Phase 2 mobile optimization
- Community deck repository — Phase 3 backend

---

### Data Architecture

**Database:** SQLite via SQLModel + aiosqlite
- Single file at `~/.lingosips/lingosips.db`
- All reads/writes through async SQLModel sessions
- WAL mode enabled for concurrent read performance

**Schema Migrations:** Alembic
- Migrations run automatically on app startup before server accepts requests
- Versioned migration scripts in `src/lingosips/db/migrations/`
- Safe for users upgrading via `uv tool upgrade` — existing data preserved
- Rollback support for development; forward-only in production

**FSRS Scheduling Engine:** `fsrs` v6.3.1 (PyPI package `fsrs`)
- Reference Python implementation by open-spaced-repetition
- FSRS state stored as columns on the card table: `stability`, `difficulty`, `due`, `last_review`, `reps`, `lapses`, `state`
- Review log stored in a separate `reviews` table for CEFR profile aggregation
- No external FSRS state — all computed and stored locally

**Data Validation:** Pydantic v2 (via FastAPI + SQLModel)
- Request/response models separate from table models — no leaking of DB internals to API
- Pydantic validators enforce content constraints at the boundary

**Caching:** None
- SQLite on local disk is fast enough for all read patterns at single-user scale
- TanStack Query handles frontend cache; no server-side cache layer needed

---

### Authentication & Security

**User Authentication:** None
- Single-user, local-only app; no login, no sessions, no tokens
- FastAPI server bound to `127.0.0.1` exclusively — no LAN or internet exposure

**Credential Storage:** `keyring` Python library
- Stores OpenRouter API key, Azure Speech credentials, image endpoint credentials
- Uses OS keychain on macOS (Keychain), Windows (Credential Locker), Linux (libsecret/kwallet)
- Falls back to encrypted file store if OS keychain unavailable
- Credentials never written to SQLite, never appear in logs or error responses

**Logging:** `structlog` with credential-scrubbing processor
- Structured JSON log output
- Custom processor strips any string matching known credential patterns before emission
- Log level configurable via `LINGOSIPS_LOG_LEVEL` env var; default `WARNING` in production
- No log shipping, no remote log collection — local file only

**Zero Telemetry:** Enforced at the network layer
- All outbound connections require explicit user configuration
- No background pings, no analytics, no crash reporting
- Auto-update check (PyPI JSON API) is the only uninstructed outbound call — disclosed in README

---

### API & Communication Patterns

**API Design:** REST with FastAPI auto-generated OpenAPI 3.1
- Resource-based routes: `/cards`, `/decks`, `/practice`, `/settings`, `/progress`, `/import`
- FastAPI serves OpenAPI schema at `/openapi.json`
- `openapi-typescript` generates TypeScript types from schema at build time — frontend always in sync with backend

**Error Format:** RFC 7807 Problem Details
```json
{ "type": "/errors/card-not-found", "title": "Card not found", "status": 404, "detail": "Card 42 does not exist" }
```

**Real-Time Communication:** Server-Sent Events (SSE)
- Used for: card creation AI streaming, import enrichment progress, model download progress
- FastAPI `StreamingResponse` with `text/event-stream` content type
- Three SSE event channels:
  - `POST /cards/stream` — card creation field-by-field reveal
  - `GET /import/{job_id}/progress` — background enrichment progress
  - `GET /models/download/progress` — local model download progress
- WebSockets explicitly rejected — all real-time flows are unidirectional server→client

**Frontend API Client:** openapi-typescript + native fetch
- `npx openapi-typescript http://localhost:7842/openapi.json -o src/lib/api.d.ts`
- Thin typed fetch wrapper in `src/lib/client.ts` — no axios, no extra dependency
- Regenerated as part of `make build`; enforced in CI if schema drifts

**Background Jobs:** FastAPI BackgroundTasks + asyncio
- Import AI enrichment and batch audio generation run as `BackgroundTasks`
- Job state tracked in SQLite (`jobs` table): id, status, progress, total, error
- Frontend polls `/import/{job_id}` or subscribes to SSE progress stream
- Jobs survive server restarts — status persisted before any async work begins

---

### Frontend Architecture

**Server State:** TanStack Query v5 (v5.99.2)
- All API data (cards, decks, queue, progress) fetched and cached via `useQuery` / `useMutation`
- Optimistic updates for card save and FSRS rating submission — 60fps practice flow, no blocking spinners
- Cache invalidation on mutation — deck list, queue count, and progress dashboard stay current automatically

**UI / Local State:** Zustand v5 (v5.0.12)
- Global store for UI-only state: current practice session, active service status, pending notifications, onboarding step
- Separate slices per domain; no mixing of server and UI state
- Persisted slices (last practice mode, dismissed banners) via `zustand/middleware` localStorage persist

**Routing:** TanStack Router (latest, March 2026 release)
- File-based route tree: `routes/index.tsx`, `routes/practice.tsx`, `routes/settings.tsx`, `routes/import.tsx`, `routes/progress.tsx`
- Type-safe route params and search params — no string-typed navigation
- Shallow hierarchy (max 2 levels); no nested layouts needed beyond root shell

**Component Architecture:** Feature-based
- `src/features/{domain}/` owns components, hooks, and types for each domain
- `src/components/ui/` — shadcn/ui owned components (shared primitives)
- Custom components (`CardCreationPanel`, `SyllableFeedback`, `PracticeCard`, `ServiceStatusIndicator`, `QueueWidget`) each have explicit state machine (enum-driven, not boolean flags)

**Bundle Optimization:**
- Vite code-splitting by route — practice session and settings loaded lazily
- `llama-cpp-python` and `faster-whisper` are Python-side; no WASM models in the browser bundle

---

### Infrastructure & Deployment

**Versioning:** Semantic versioning (semver)
- `pyproject.toml` version is the single source of truth
- Git tag `v{major}.{minor}.{patch}` triggers PyPI publish

**CI/CD:** GitHub Actions
- On PR: `ruff check`, `pytest`, `vitest run` — all must pass before merge
- On tag push: build frontend → copy to static/ → `uv build` → `uv publish` to PyPI

**Local Server Port:** `7842` (fixed; not configurable in MVP)
- Chosen to avoid conflicts with common dev ports (3000, 5173, 8000, 8080)

**Startup Sequence:**
1. Run Alembic migrations
2. Verify `~/.lingosips/` data directory exists (create if not)
3. Check PyPI for update (async, non-blocking)
4. Start uvicorn on `127.0.0.1:7842`
5. Open system default browser to `http://localhost:7842`

### Decision Impact Analysis

**Implementation Sequence (order matters):**
1. `db/` — SQLModel models + Alembic setup (everything depends on schema)
2. `services/llm/` + `services/speech/` — provider abstractions (card creation depends on these)
3. `core/fsrs.py` — FSRS engine wrapping `fsrs` library (practice depends on this)
4. `api/cards.py` + SSE streaming — first user-visible feature
5. `api/practice.py` — depends on FSRS and card data
6. `core/cefr.py` — depends on review log accumulation (can be stubbed initially)
7. Frontend features built against running backend; openapi-typescript keeps types in sync

**Cross-Component Dependencies:**
- Every API router depends on `db/session.py` and `services/` provider registry
- FSRS engine is called by `api/practice.py` and read by `api/progress.py`
- Credential `keyring` access is isolated to `services/settings.py` — no other module reads credentials directly
- SSE streams share the same `BackgroundTasks` + job-state pattern — implement once, reuse for cards/import/models

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

7 areas where AI agents could make incompatible choices without explicit rules.

---

### Naming Patterns

**Database (SQLModel / SQLite):**
- Tables: plural snake_case — `cards`, `decks`, `reviews`, `jobs`
- Columns: snake_case — `card_id`, `target_word`, `last_review`
- Foreign keys: `{table_singular}_id` — `card_id`, `deck_id`
- Indexes: `ix_{table}_{column}` — `ix_cards_due`, `ix_reviews_card_id`

```python
# CORRECT
class Card(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    target_word: str
    deck_id: int = Field(foreign_key="decks.id")

# WRONG
class Card(SQLModel, table=True):
    targetWord: str   # ❌ never camelCase columns
    DeckId: int       # ❌ never PascalCase columns
```

**API Routes:**
- Resources: plural snake_case — `/cards`, `/decks`, `/practice`
- Sub-resources: `/cards/{card_id}/audio`, `/decks/{deck_id}/cards`
- Path params: snake_case — `{card_id}`, `{deck_id}`, `{job_id}`
- Query params: snake_case — `?deck_id=1&include_due=true`

**JSON Field Naming:**
- All JSON fields: **snake_case** throughout — no camelCase, no aliasing
- `openapi-typescript` generates TypeScript types with snake_case property names; this is intentional

```json
// CORRECT
{ "card_id": 42, "target_word": "melancólico", "last_review": "2026-04-26T10:00:00Z" }

// WRONG
{ "cardId": 42, "targetWord": "melancólico" }  // ❌ never camelCase in JSON
```

**Python Code:** modules/functions/variables `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`

**TypeScript / React Code:**
- Components: `PascalCase` files — `CardCreationPanel.tsx`
- Hooks: `camelCase` with `use` prefix — `useCardCreation.ts`
- Route files: kebab-case — `routes/card-detail.tsx`
- Types/interfaces: `PascalCase` — `CardResponse`, `PracticeSession`

---

### Structure Patterns

**Backend — module responsibilities:**
```
src/lingosips/
├── api/{domain}.py          # FastAPI router only — no business logic
├── core/{domain}.py         # Business logic — no FastAPI, no DB imports
├── db/
│   ├── models.py            # All SQLModel table definitions in one file
│   └── session.py           # Async engine + get_session dependency
├── services/
│   ├── llm/base.py          # AbstractLLMProvider (ABC)
│   ├── llm/openrouter.py    # OpenRouterProvider
│   ├── llm/qwen_local.py    # QwenLocalProvider
│   ├── speech/base.py       # AbstractSpeechProvider (ABC)
│   ├── speech/azure.py      # AzureSpeechProvider
│   ├── speech/whisper_local.py
│   └── registry.py          # get_llm_provider() / get_speech_provider() — Depends() targets
└── models/manager.py        # Model download + lifecycle
```

**Backend — router must never contain business logic:**
```python
# CORRECT — router delegates to core
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
    response = await httpx.post("https://openrouter.ai/...")  # ❌
```

**Backend — tests:**
```
tests/
├── conftest.py              # shared fixtures: test client, DB session, mock providers
├── api/
│   ├── test_cards.py
│   ├── test_decks.py
│   ├── test_practice.py
│   ├── test_settings.py
│   ├── test_import.py
│   └── test_progress.py
├── core/
│   ├── test_fsrs.py
│   ├── test_cefr.py
│   └── test_safety.py
└── services/
    ├── test_llm_routing.py
    └── test_speech_routing.py
```

**Frontend — feature structure:**
```
src/features/cards/
├── CardCreationPanel.tsx
├── CardCreationPanel.test.tsx   # co-located component test
├── useCardStream.ts
└── index.ts                     # public exports only
```

**Frontend — shared vs feature:**
- `src/components/ui/` — shadcn/ui primitives only
- `src/features/{domain}/` — everything domain-specific
- `src/lib/` — api client, utilities with no domain affiliation
- Never import from one feature into another — route through `lib/` if needed

---

### Format Patterns

**API Response:** Direct Pydantic model — no wrapper envelope

**Error Response:** RFC 7807 Problem Details
```python
raise HTTPException(
    status_code=404,
    detail={"type": "/errors/card-not-found", "title": "Card not found", "detail": f"Card {card_id} does not exist"}
)
```

**Date/Time:** ISO 8601 UTC strings — `"2026-04-26T15:30:00Z"`. Frontend displays via `Intl.DateTimeFormat` — no date libraries.

**IDs:** Integer primary keys exposed as integers — no UUIDs, no slugs.

**SSE Event Envelope:** Identical structure across all channels:
```
event: {event_type}
data: {json_payload}

```
Event types: `field_update` | `progress` | `complete` | `error`

```json
// field_update
{ "field": "translation", "value": "melancholic" }
// progress
{ "done": 23, "total": 400, "current_item": "enriching audio..." }
// error
{ "message": "Local Qwen timeout after 10s" }
```

---

### Communication Patterns

**FastAPI Dependency Injection — always use `Depends()`:**
```python
# CORRECT
async def create_card(llm: AbstractLLMProvider = Depends(get_llm_provider)): ...

# WRONG — never instantiate providers directly
llm = OpenRouterProvider(api_key="...")  # ❌
```

**TanStack Query Key Conventions:**
```typescript
["cards"]                        // list
["cards", cardId]                // single
["decks", deckId, "cards"]      // nested
["practice", "queue"]
["progress", "dashboard"]
["settings"]
["models", "status"]

// WRONG
["getCards"]           // ❌ never verb-prefixed
[{ resource: "cards" }]  // ❌ never object keys
```

**Zustand — server state never in Zustand:**
```typescript
// CORRECT — UI-only state
const useAppStore = create<AppStore>((set) => ({
  activeServiceStatus: { llm: "local", speech: "local" },
  practiceSession: null,
  pendingNotifications: [],
}))

// WRONG
const useCardStore = create(() => ({
  cards: [],       // ❌ server state belongs in TanStack Query
}))
```

**Zustand store files:**
```
src/lib/stores/
├── useAppStore.ts       # service status, notifications, onboarding
├── usePracticeStore.ts  # active session state
└── useSettingsStore.ts  # persisted local preferences
```

---

### Process Patterns

**Service provider fallback — single location only:**
```python
# services/registry.py — all fallback logic lives here exclusively
def get_llm_provider(settings: Settings = Depends(get_settings)) -> AbstractLLMProvider:
    if settings.openrouter_key:
        return OpenRouterProvider(settings.openrouter_key, settings.openrouter_model)
    return QwenLocalProvider(settings.qwen_model_path)
```

**Background job lifecycle — persist before starting:**
```python
# CORRECT
async def enrich_import(job_id: int, cards: list, session: AsyncSession):
    await update_job_status(session, job_id, "running", total=len(cards))  # persist first
    for i, card in enumerate(cards):
        enriched = await llm.enrich(card)
        await update_job_progress(session, job_id, done=i+1)

# WRONG — work before persistence
async def enrich_import(cards: list):
    for card in cards:
        await llm.enrich(card)  # ❌ lost on restart
```

**Frontend error flow:**
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

**Loading states:**
- Use TanStack Query `isLoading` / `isPending` — never duplicate with `useState`
- Skeleton components for content areas; optimistic updates for FSRS ratings
- Never show spinner during practice card transitions

**Component state machines — enum-driven, no boolean flags:**
```typescript
// CORRECT
type CardCreationState = "idle" | "loading" | "populated" | "saving" | "error"
const [state, setState] = useState<CardCreationState>("idle")

// WRONG
const [isLoading, setIsLoading] = useState(false)
const [hasError, setHasError] = useState(false)  // ❌ boolean flag soup
```

---

### Testing Strategy & Requirements

**This is a non-negotiable architectural constraint:** all functionality is covered by tests. Stories are not complete until tests pass. Test-Driven Development (TDD) is the required development process.

#### TDD Process — no exceptions

Every implementation story follows this sequence:
1. Read the story acceptance criteria
2. Write failing tests that encode those criteria
3. Write the minimum implementation to make tests pass
4. Refactor with tests green

A story with passing implementation but no tests is **not done**.

#### Test Layers & Responsibilities

| Layer | Tool | Covers | Runs in |
|---|---|---|---|
| Unit | pytest / Vitest | Core logic (FSRS, CEFR, safety filter, provider abstractions) | PR + local |
| API | pytest + httpx | Every endpoint — positive, negative, edge cases | PR + local |
| Component | Vitest + RTL | Custom components and their state machines | PR + local |
| E2E / UI | Playwright | All user stories and journeys end-to-end | PR + nightly |

#### API Test Requirements

Every FastAPI endpoint **must** have tests covering:

**Positive scenarios:**
- Happy path with valid input returns correct response shape and status code
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
- SSE streams: complete event sequence, mid-stream error

```python
# Example structure — tests/api/test_cards.py
class TestCreateCard:
    async def test_create_card_success(self, client, mock_llm_provider): ...
    async def test_create_card_missing_target_word_returns_422(self, client): ...
    async def test_create_card_llm_timeout_falls_back_to_local(self, client, mock_openrouter_timeout): ...
    async def test_create_card_empty_target_word_returns_422(self, client): ...
    async def test_create_card_stream_emits_all_field_events(self, client, mock_llm_provider): ...
    async def test_create_card_stream_emits_error_event_on_failure(self, client, mock_llm_failure): ...

class TestGetCard:
    async def test_get_card_success(self, client, seed_card): ...
    async def test_get_card_not_found_returns_404_problem_detail(self, client): ...
    async def test_delete_card_removes_from_fsrs_queue(self, client, seed_card): ...
```

#### Playwright E2E Requirements

Every user story maps to at least one Playwright spec. The five PRD journeys map directly to test files:

```
frontend/e2e/
├── journeys/
│   ├── first-launch-card-creation.spec.ts
│   ├── vocabulary-capture.spec.ts
│   ├── speak-mode-session.spec.ts
│   ├── import-and-enrichment.spec.ts
│   └── service-configuration.spec.ts
├── features/
│   ├── card-management.spec.ts          # FR1–FR8
│   ├── deck-management.spec.ts          # FR9–FR16
│   ├── practice-self-assess.spec.ts     # FR17–FR18, FR24–FR25
│   ├── practice-write-mode.spec.ts      # FR19–FR20
│   ├── practice-speak-mode.spec.ts      # FR21–FR22
│   ├── fsrs-scheduling.spec.ts          # FR23–FR25
│   ├── settings-and-onboarding.spec.ts  # FR30–FR40
│   └── progress-and-cefr.spec.ts        # FR41–FR47
└── fixtures/
    └── index.ts                         # shared page objects, seed helpers
```

Every Playwright spec must test:
- The happy path to completion
- At least one error/degraded state
- Keyboard navigation of the primary flow
- Correct UI state after the action

**Critical rule:** Playwright tests run against a **real running backend** with a test SQLite database — not a mocked server.

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

#### Component Test Requirements

Each custom component must have Vitest + RTL tests covering:
- Every state in the component's state machine
- Keyboard interactions from the UX spec
- `aria-label` and `aria-live` announcements

```typescript
// CardCreationPanel.test.tsx
describe("CardCreationPanel", () => {
  it("starts in idle state with focused input", ...)
  it("transitions to loading state on Enter", ...)
  it("shows skeleton placeholders during loading", ...)
  it("reveals fields sequentially on populated state", ...)
  it("shows specific error message on failure, not generic spinner", ...)
  it("refocuses input after card save", ...)
  it("announces field population to screen readers via aria-live", ...)
})
```

#### CI Enforcement

```yaml
jobs:
  backend-tests:
    - run: uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90

  frontend-tests:
    - run: npm run test -- --coverage

  e2e-tests:
    - run: make test-server &
    - run: npx playwright test
```

**Coverage gates:**
- Backend: 90% line coverage minimum (CI hard gate)
- Frontend components: 100% state machine branch coverage for the 5 custom components
- E2E: every FR (FR1–FR50) touched by at least one Playwright spec

---

### Enforcement Guidelines

**All AI agents MUST:**
- Use snake_case in all JSON API fields — no camelCase aliasing
- Route through `Depends()` for all provider access — never instantiate providers directly
- Persist background job status to SQLite before beginning async work
- Use TanStack Query for all server data — never store API responses in Zustand
- Use state enums for all custom component states — never boolean flag combinations
- Follow RFC 7807 for all error responses
- Use the standard SSE event envelope for all streaming channels
- Write tests before implementation (TDD) — no story is done without passing tests
- Cover every API endpoint with positive, negative, and edge case tests
- Cover every user story with at least one Playwright spec

**Verification:**
- `ruff` enforces Python naming and import order automatically
- TypeScript strict mode catches type mismatches between API types and component props
- `openapi-typescript` regeneration in CI catches API contract drift
- CI hard gates: pytest 90% coverage, Playwright full journey suite

## Project Structure & Boundaries

### Requirements to Structure Mapping

| FR Category | Backend | Frontend |
|---|---|---|
| Card Management (FR1–8) | `api/cards.py` · `core/cards.py` | `features/cards/` |
| Deck Management (FR9–16) | `api/decks.py` · `core/decks.py` | `features/decks/` |
| Practice & Learning (FR17–25) | `api/practice.py` · `core/practice.py` · `core/fsrs.py` | `features/practice/` |
| AI & Speech Services (FR26–29) | `services/llm/` · `services/speech/` · `services/registry.py` | `lib/stores/useAppStore.ts` (status) |
| Settings & Configuration (FR30–37) | `api/settings.py` · `core/settings.py` · `services/credentials.py` | `features/settings/` |
| Onboarding (FR38–40) | `api/settings.py` (language setup) | `features/onboarding/` |
| Progress & Analytics (FR41–43) | `api/progress.py` · `core/progress.py` | `features/progress/` |
| Learner Intelligence (FR44–47) | `core/cefr.py` | `features/cefr/` |
| Data & Privacy (FR48–50) | `core/safety.py` · `services/credentials.py` · `__main__.py` (127.0.0.1 bind) | N/A |
| Import (FR13–15) | `api/import_.py` · `core/import_.py` | `features/import/` |
| Local Model Management | `services/models/manager.py` | `features/settings/ModelManager.tsx` |

---

### Complete Project Directory Structure

```
lingosips/
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # PR: ruff + pytest + vitest + playwright
│       └── publish.yml               # On tag: build frontend → uv build → uv publish
│
├── src/
│   └── lingosips/
│       ├── __init__.py               # version = importlib.metadata.version("lingosips")
│       ├── __main__.py               # CLI entry: migrations → check update → start uvicorn → open browser
│       │
│       ├── api/                      # FastAPI routers — no business logic
│       │   ├── __init__.py
│       │   ├── app.py                # FastAPI app factory: mounts routers, exception handlers, static files
│       │   ├── cards.py              # FR1–8: CRUD + SSE streaming endpoint
│       │   ├── decks.py              # FR9–12, FR16: deck CRUD + multi-language
│       │   ├── practice.py           # FR17–25: session start, card evaluation, FSRS rating submission
│       │   ├── import_.py            # FR13–15: Anki/.apkg, text, URL import + enrichment jobs
│       │   ├── settings.py           # FR30–37: language config, API key management, defaults
│       │   ├── progress.py           # FR41–43: dashboard stats, session history
│       │   ├── cefr.py               # FR44–47: CEFR profile retrieval
│       │   ├── models.py             # Local model download + status endpoints (SSE progress)
│       │   └── updates.py            # Auto-update check endpoint
│       │
│       ├── core/                     # Business logic — no FastAPI, no direct DB access
│       │   ├── __init__.py
│       │   ├── cards.py              # Card creation pipeline: call LLM → parse → validate → safety check
│       │   ├── decks.py              # Deck operations, multi-language management
│       │   ├── practice.py           # Practice session orchestration, write-mode evaluation
│       │   ├── fsrs.py               # FSRS wrapper: schedule(), rate(), get_due_queue()
│       │   ├── import_.py            # Import parsing (Anki .apkg, TSV, text), unknown word detection
│       │   ├── enrichment.py         # Batch AI enrichment pipeline for imported cards
│       │   ├── progress.py           # Dashboard stats aggregation, session summary calculation
│       │   ├── cefr.py               # CEFR profile computation from review log
│       │   ├── safety.py             # Content safety filter for AI-generated text and images
│       │   └── settings.py           # Settings validation, defaults merging, service status
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py             # All SQLModel table definitions: Card, Deck, Review, Job, Settings
│       │   ├── session.py            # Async SQLite engine + get_session Depends()
│       │   └── migrations/
│       │       ├── env.py            # Alembic env config
│       │       ├── script.py.mako
│       │       └── versions/
│       │           └── 001_initial_schema.py
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── registry.py           # get_llm_provider() / get_speech_provider() — all fallback logic
│       │   ├── credentials.py        # keyring read/write/delete for all API keys
│       │   │
│       │   ├── llm/
│       │   │   ├── __init__.py
│       │   │   ├── base.py           # AbstractLLMProvider ABC: generate_card(), evaluate_answer(), stream()
│       │   │   ├── openrouter.py     # OpenRouterProvider: httpx streaming, model enumeration, connection test
│       │   │   └── qwen_local.py     # QwenLocalProvider: llama-cpp-python, GGUF model loading
│       │   │
│       │   ├── speech/
│       │   │   ├── __init__.py
│       │   │   ├── base.py           # AbstractSpeechProvider ABC: evaluate_pronunciation() → SyllableResult
│       │   │   ├── azure.py          # AzureSpeechProvider: pronunciation assessment API
│       │   │   └── whisper_local.py  # WhisperLocalProvider: faster-whisper inference
│       │   │
│       │   ├── image.py              # Image generation: OpenAI-format REST, safety-filtered
│       │   └── models/
│       │       └── manager.py        # Model download, hash verify, resume, lifecycle for Qwen + Whisper
│       │
│       └── static/                   # Built Vite frontend (generated — not git-tracked)
│           └── .gitkeep
│
├── frontend/                         # Vite React TypeScript SPA (dev source)
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── tailwind.config.ts
│   ├── components.json               # shadcn/ui config
│   ├── playwright.config.ts
│   ├── package.json
│   │
│   ├── src/
│   │   ├── main.tsx                  # React root, TanStack Router provider, TanStack Query client
│   │   ├── routeTree.gen.ts          # Auto-generated by TanStack Router CLI
│   │   │
│   │   ├── routes/
│   │   │   ├── __root.tsx            # Root layout: icon sidebar + ServiceStatusIndicator
│   │   │   ├── index.tsx             # Home: CardCreationPanel + QueueWidget (D2 layout)
│   │   │   ├── practice.tsx          # Practice session (D4/D5 layout)
│   │   │   ├── decks.tsx             # Deck browser
│   │   │   ├── decks.$deckId.tsx     # Deck detail + card list
│   │   │   ├── import.tsx            # Import screen
│   │   │   ├── progress.tsx          # Progress dashboard + CEFR profile
│   │   │   └── settings.tsx          # Settings: language, API keys, defaults
│   │   │
│   │   ├── features/
│   │   │   ├── cards/
│   │   │   │   ├── CardCreationPanel.tsx
│   │   │   │   ├── CardCreationPanel.test.tsx
│   │   │   │   ├── CardDetail.tsx              # FR3–4: edit fields, personal note
│   │   │   │   ├── useCardStream.ts            # SSE hook for card creation stream
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── decks/
│   │   │   │   ├── DeckGrid.tsx
│   │   │   │   ├── DeckGrid.test.tsx
│   │   │   │   ├── DeckCard.tsx
│   │   │   │   ├── DeckExportImport.tsx        # FR11–12
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── practice/
│   │   │   │   ├── PracticeCard.tsx
│   │   │   │   ├── PracticeCard.test.tsx
│   │   │   │   ├── SyllableFeedback.tsx
│   │   │   │   ├── SyllableFeedback.test.tsx
│   │   │   │   ├── QueueWidget.tsx
│   │   │   │   ├── QueueWidget.test.tsx
│   │   │   │   ├── SessionSummary.tsx
│   │   │   │   ├── usePracticeSession.ts
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── import/
│   │   │   │   ├── ImportScreen.tsx
│   │   │   │   ├── ImportScreen.test.tsx
│   │   │   │   ├── EnrichmentProgress.tsx
│   │   │   │   ├── useImportJob.ts
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── settings/
│   │   │   │   ├── LanguageSettings.tsx
│   │   │   │   ├── ServiceSettings.tsx
│   │   │   │   ├── ServiceSettings.test.tsx
│   │   │   │   ├── DefaultsSettings.tsx
│   │   │   │   ├── ModelManager.tsx
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── onboarding/
│   │   │   │   ├── OnboardingWizard.tsx
│   │   │   │   ├── OnboardingWizard.test.tsx
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── progress/
│   │   │   │   ├── ProgressDashboard.tsx
│   │   │   │   ├── ProgressDashboard.test.tsx
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   └── cefr/
│   │   │       ├── CefrProfile.tsx
│   │   │       ├── CefrProfile.test.tsx
│   │   │       └── index.ts
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                             # shadcn/ui owned components
│   │   │   │   ├── button.tsx
│   │   │   │   ├── input.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── skeleton.tsx
│   │   │   │   ├── progress.tsx
│   │   │   │   ├── tabs.tsx
│   │   │   │   ├── tooltip.tsx
│   │   │   │   ├── toast.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── dropdown-menu.tsx
│   │   │   │   ├── separator.tsx
│   │   │   │   └── badge.tsx
│   │   │   ├── ServiceStatusIndicator.tsx
│   │   │   └── ServiceStatusIndicator.test.tsx
│   │   │
│   │   └── lib/
│   │       ├── api.d.ts                        # Auto-generated from FastAPI OpenAPI schema
│   │       ├── client.ts                       # Typed fetch wrapper
│   │       ├── queryClient.ts                  # TanStack Query client instance + defaults
│   │       └── stores/
│   │           ├── useAppStore.ts
│   │           ├── usePracticeStore.ts
│   │           └── useSettingsStore.ts
│   │
│   └── e2e/
│       ├── journeys/
│       │   ├── first-launch-card-creation.spec.ts
│       │   ├── vocabulary-capture.spec.ts
│       │   ├── speak-mode-session.spec.ts
│       │   ├── import-and-enrichment.spec.ts
│       │   └── service-configuration.spec.ts
│       ├── features/
│       │   ├── card-management.spec.ts
│       │   ├── deck-management.spec.ts
│       │   ├── practice-self-assess.spec.ts
│       │   ├── practice-write-mode.spec.ts
│       │   ├── practice-speak-mode.spec.ts
│       │   ├── fsrs-scheduling.spec.ts
│       │   ├── settings-and-onboarding.spec.ts
│       │   └── progress-and-cefr.spec.ts
│       └── fixtures/
│           └── index.ts
│
├── tests/
│   ├── conftest.py
│   ├── api/
│   │   ├── test_cards.py
│   │   ├── test_decks.py
│   │   ├── test_practice.py
│   │   ├── test_import.py
│   │   ├── test_settings.py
│   │   └── test_progress.py
│   ├── core/
│   │   ├── test_cards.py
│   │   ├── test_fsrs.py
│   │   ├── test_cefr.py
│   │   ├── test_enrichment.py
│   │   └── test_safety.py
│   └── services/
│       ├── test_llm_routing.py
│       ├── test_speech_routing.py
│       └── test_model_manager.py
│
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── Makefile
├── .gitignore
├── .env.example
└── README.md
```

---

### Architectural Boundaries

**API Boundary:**
- All state reads and mutations go through FastAPI REST endpoints
- SSE streams at `/cards/stream`, `/import/{job_id}/progress`, `/models/download/progress`
- Frontend has zero direct access to SQLite, `keyring`, or AI providers
- OpenAPI schema at `/openapi.json` is the contract; `api.d.ts` is the enforced client type

**Service Provider Boundary:**
- `services/registry.py` is the sole entry point for AI provider selection
- No code outside `services/` instantiates `AbstractLLMProvider` or `AbstractSpeechProvider`
- `services/credentials.py` is the sole reader/writer of `keyring`

**Core Business Logic Boundary:**
- `core/` modules take primitive inputs and return domain objects — no FastAPI, no SQLModel imports
- `api/` routers call `core/` functions, passing resolved DB sessions and providers via `Depends()`
- `core/fsrs.py` wraps the `fsrs` library — `api/practice.py` never calls `fsrs` directly

**Data Boundary:**
- All DB access through `db/session.py` `get_session` dependency
- Alembic owns schema evolution — no `SQLModel.metadata.create_all()` in production
- `~/.lingosips/lingosips.db` — SQLite file; `~/.lingosips/models/` — local AI models

**Frontend State Boundary:**
- TanStack Query owns all server-sourced data
- Zustand owns UI-only state — nothing from TanStack Query duplicated in Zustand
- `lib/client.ts` is the only module that calls `fetch()`

---

### Integration Points

**Card creation data flow:**
```
Browser → POST /cards/stream
  → api/cards.py (Depends injection)
    → core/cards.py (validate → LLM → safety → parse)
      → services/registry.py → AbstractLLMProvider
      → core/safety.py
    → db/session.py (persist card + FSRS initial state)
  → SSE: field_update events → CardCreationPanel
```

**Practice session data flow:**
```
Browser → POST /practice/session/start
  → api/practice.py → core/fsrs.py → get_due_queue()
    → db: SELECT cards WHERE due <= now

Browser → POST /practice/cards/{card_id}/rate
  → api/practice.py → core/fsrs.py → rate(card, rating)
    → db: UPDATE card FSRS state + INSERT review row
    → core/cefr.py → invalidate_cache() [async, non-blocking]
```

**External service integration points:**
- OpenRouter: `POST https://openrouter.ai/api/v1/chat/completions`
- Azure Speech: pronunciation assessment endpoint
- Image gen: configurable OpenAI-format REST endpoint
- Model downloads: HuggingFace Hub HTTPS
- Auto-update: `GET https://pypi.org/pypi/lingosips/json`

**Development workflow:**
```makefile
dev:         uvicorn src.lingosips.api.app:app --reload & vite dev --port 5173
build:       cd frontend && npm run build && cp -r dist/* ../src/lingosips/static/
test:        uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90 && npm run test
test-server: uv run uvicorn src.lingosips.api.app:app --port 7842 --env-file .env.test
e2e:         npx playwright test
publish:     make build && uv build && uv publish
```

## Architecture Validation Results

### Gaps Identified & Resolved

**Critical — Audio Generation (TTS) for Cards (FR2)**
Gap: Architecture covered Azure Speech for pronunciation assessment and faster-whisper for
recognition, but no TTS service was specified for generating card pronunciation audio.

Resolution: `AbstractSpeechProvider` gains a `synthesize(text, lang) → bytes` method alongside
`evaluate_pronunciation()`. Azure Speech serves both TTS (card audio) and pronunciation
assessment (practice). Local fallback: `pyttsx3` (system TTS, zero model download).
`pyttsx3` added to backend dependencies.

Updated `services/speech/base.py` contract:
- `synthesize(text: str, language: str) -> bytes` — card audio generation
- `evaluate_pronunciation(audio: bytes, target: str) -> SyllableResult` — speak mode

**Important — Anki .apkg parsing library**
Gap: `core/import_.py` handles `.apkg` import but no parsing library was listed.
Resolution: `genanki` added to backend dependencies for `.apkg` read/write.

**Important — Deck export/import file format**
Gap: FR11–12 require file-based deck sharing but format was unspecified.
Resolution: `.lingosips` file format — a renamed ZIP containing `deck.json` (card metadata,
FSRS state) and `audio/` folder (pronunciation audio files). Human-readable, no binary
dependencies, importable by any future tool.

**Minor — Native build prerequisites**
`llama-cpp-python` and `faster-whisper` require cmake and a C++ compiler.
Resolution: README documents these as prerequisites. CI matrix includes a build-tools
installation step before `uv tool install` verification.

**Minor — Content safety filter implementation**
`core/safety.py` was defined without implementation approach.
Resolution: Keyword/pattern blocklist for MVP (no external API, no extra model).
Single-user local app with BYOK AI — adequate safety posture. Upgradeable post-MVP.

---

### Updated Dependencies

```toml
# pyproject.toml additions from validation
uv add pyttsx3        # local TTS fallback for card audio
uv add genanki        # Anki .apkg import/export parsing
```

---

### Coherence Validation ✅

**Decision Compatibility:**
- Python 3.12+ / FastAPI / SQLModel / aiosqlite / Alembic: fully compatible; standard async FastAPI stack
- llama-cpp-python / faster-whisper / pyttsx3: independent Python packages; no version conflicts
- React / Vite 6 / TanStack Query v5 / TanStack Router / Zustand v5 / shadcn/ui: all current, actively maintained, no peer dependency conflicts
- `fsrs` v6.3.1 wraps cleanly inside `core/fsrs.py`; no framework coupling
- `keyring` integrates with OS keychain without conflicting with any other dependency

**Pattern Consistency:**
- snake_case naming enforced uniformly: DB columns, JSON fields, Python code, API routes
- `Depends()` injection used consistently — no direct provider instantiation anywhere in routers
- RFC 7807 error format applied at the FastAPI exception handler level — all errors covered automatically
- SSE envelope structure identical across card creation, import progress, and model download

**Structure Alignment:**
- `api/` → routers only; `core/` → logic only; `services/` → external provider abstractions — clean separation
- `db/models.py` is the single source of truth for schema; Alembic is the single migration path
- `lib/client.ts` is the only fetch caller in the frontend; `openapi-typescript` keeps types in sync
- TanStack Query / Zustand boundary is explicit: server data never in Zustand

---

### Requirements Coverage Validation ✅

**Functional Requirements — all 50 FRs covered:**

| FR Range | Domain | Architectural Support |
|---|---|---|
| FR1–8 | Card Management | `api/cards.py` + `core/cards.py` + SSE streaming + `features/cards/` |
| FR9–16 | Deck Management | `api/decks.py` + `core/decks.py` + `.lingosips` file format + `features/decks/` |
| FR17–25 | Practice & Learning | `api/practice.py` + `core/practice.py` + `core/fsrs.py` + `features/practice/` |
| FR26–29 | AI & Speech Services | `services/registry.py` + `services/llm/` + `services/speech/` |
| FR30–37 | Settings & Config | `api/settings.py` + `services/credentials.py` (keyring) + `features/settings/` |
| FR38–40 | Onboarding | `features/onboarding/` + language setup in `api/settings.py` |
| FR41–43 | Progress & Analytics | `api/progress.py` + `core/progress.py` + `features/progress/` |
| FR44–47 | Learner Intelligence | `core/cefr.py` + review log in `db/models.py` + `features/cefr/` |
| FR48–50 | Data & Privacy | `core/safety.py` + `services/credentials.py` + 127.0.0.1 binding + zero telemetry |

**Non-Functional Requirements:**

| NFR | Architectural Support |
|---|---|
| Card creation < 3s cloud / < 5s local | Async FastAPI + SSE streaming; first token < 500ms |
| Speech eval < 2s | Azure Speech async API; faster-whisper CPU inference |
| App shell load < 2s | Vite 6 code-splitting; FastAPI serves pre-built static assets |
| 60fps practice transitions | Optimistic updates via TanStack Query `onMutate`; no blocking spinners |
| Credentials never plaintext | `keyring` OS keychain; structlog credential-scrubbing processor |
| Zero telemetry | 127.0.0.1 binding; no uninstructed outbound except PyPI version check (disclosed) |
| Fully offline | SQLite local; llama-cpp-python + faster-whisper + pyttsx3 require no network |
| WCAG 2.1 AA | shadcn/ui Radix primitives; aria attributes per component; axe-core in CI |
| Durable writes | SQLite WAL mode; writes confirmed before SSE `complete` event sent |
| Open-source maintainability | Provider abstraction; ruff + TypeScript strict mode |

---

### Implementation Readiness Validation ✅

**Decision Completeness:** All critical decisions documented with verified library versions. No ambiguous "TBD" decisions remain that block implementation.

**Structure Completeness:** Complete directory tree defined to individual file level. Every FR maps to a specific file. All integration boundaries, data flows, and external service touchpoints specified.

**Pattern Completeness:** 7 conflict areas identified and resolved with concrete rules and examples. TDD process, API test requirements, Playwright E2E coverage, and CI gates documented as hard constraints.

---

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] 50 FRs across 8 domains analyzed for architectural implications
- [x] NFRs mapped to specific architectural decisions
- [x] Technical constraints identified (offline-first, no auth, single-user, BYOK)
- [x] 8 cross-cutting concerns mapped

**✅ Starter Template & Distribution**
- [x] uv-based PyPI distribution with frontend bundled in wheel
- [x] Auto-update via PyPI JSON API
- [x] Initialization commands documented
- [x] Build and publish pipeline defined

**✅ Architectural Decisions**
- [x] Database: SQLite + SQLModel + Alembic
- [x] FSRS: `fsrs` v6.3.1
- [x] LLM: OpenRouter (cloud) + llama-cpp-python/Qwen (local fallback)
- [x] Speech: Azure Speech (cloud) + faster-whisper (recognition) + pyttsx3 (TTS fallback)
- [x] Frontend: TanStack Query v5.99.2 + Zustand v5.0.12 + TanStack Router
- [x] Security: keyring + structlog scrubber + 127.0.0.1 binding
- [x] CI/CD: GitHub Actions + semver tag publishing

**✅ Implementation Patterns**
- [x] snake_case JSON + DB; PascalCase React components
- [x] Router/core separation enforced
- [x] Dependency injection via `Depends()` only
- [x] SSE event envelope standardised
- [x] TanStack Query key conventions defined
- [x] Zustand/TanStack Query state boundary enforced
- [x] Component state machine pattern (enum-driven)

**✅ Testing Strategy**
- [x] TDD as mandatory process
- [x] API tests: positive + negative + edge cases per endpoint
- [x] Playwright E2E: all 5 journeys + all FR categories
- [x] Component tests: all state machine states + keyboard + accessibility
- [x] CI hard gates: 90% backend coverage + Playwright suite

**✅ Project Structure**
- [x] Complete directory tree to file level
- [x] All 50 FRs mapped to specific files
- [x] Integration boundaries and data flows documented
- [x] Development, build, test, and publish workflows defined

---

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Clean api/core/services/db separation prevents logic bleed between layers
- Provider abstraction means cloud→local fallback is a one-line registry decision, not scattered conditionals
- SSE-first streaming delivers responsive UX without WebSocket complexity
- TDD + Playwright mandate means quality is architectural, not optional
- `uv tool install` distribution removes all setup friction for end users

**Areas for Future Enhancement (Post-MVP):**
- Tauri v2 desktop packaging as optional wrapper (no structural changes required)
- Content safety filter upgrade from keyword blocklist to local model
- PWA / service worker for mobile browser offline support
- Community deck repository (Phase 3 backend service)

---

### Implementation Handoff

**First implementation story:** Project initialization
```bash
uv init lingosips --package
npm create vite@latest frontend -- --template react-ts
```
Follow full init sequence from Starter Template section.

**Implementation sequence (strict order for first 3 stories):**
1. `db/models.py` + Alembic setup — all subsequent stories depend on schema
2. `services/registry.py` + `services/llm/` + `services/speech/` — provider abstractions
3. `core/fsrs.py` wrapping `fsrs` v6.3.1 — practice depends on this

**AI Agent Guidelines:**
- This document is the single source of truth for all architectural questions
- Follow naming patterns exactly — enforced by ruff and TypeScript strict mode
- Write failing tests before any implementation code (TDD)
- Never put business logic in `api/` routers — delegate to `core/`
- Never instantiate providers directly — always use `Depends(get_llm_provider)`
- All JSON fields are snake_case — no exceptions
