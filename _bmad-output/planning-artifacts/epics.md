---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/architecture.md"
  - "_bmad-output/planning-artifacts/ux-design-specification.md"
---

# lingosips - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for lingosips, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can create a card by entering a single word or phrase
FR2: System auto-generates translation, grammatical forms (gender, article, plural, conjugation), example sentences, and pronunciation audio for a card
FR3: User can add a personal note to any card
FR4: User can manually edit any AI-generated field on a card
FR5: User can assign a card to one or more decks
FR6: User can delete a card
FR7: System can generate an image for a card using a configured image generation endpoint
FR8: User can trigger or skip image generation per card
FR9: User can create, rename, and delete decks
FR10: User can browse and filter their deck collection
FR11: User can export a deck to a shareable file format
FR12: User can import a deck from a file
FR13: User can import vocabulary from plain text, a URL, or an Anki-formatted file
FR14: System detects unknown words in imported text and proposes them as new cards
FR15: System AI-enriches imported cards that are missing fields (translation, grammar forms, audio, examples)
FR16: User can manage multiple target languages simultaneously and switch between them
FR17: User can start a practice session for a deck or due-card queue
FR18: User can practice in self-assess mode (view card, self-rate recall)
FR19: User can practice in write mode (type the answer)
FR20: System evaluates a written answer and highlights errors with correction suggestions
FR21: User can practice in speak mode (record pronunciation of the target word or sentence)
FR22: System evaluates spoken pronunciation and provides specific feedback on errors including syllable-level detail
FR23: User can practice sentence and collocation translation
FR24: System schedules cards using the FSRS algorithm based on user recall ratings
FR25: System reschedules a card sooner when the user fails to recall it correctly
FR26: System routes LLM requests to OpenRouter when configured, falling back to local Qwen when not configured
FR27: System routes speech evaluation requests to Azure Speech when configured, falling back to local Whisper when not configured
FR28: System streams AI-generated content token-by-token during card creation
FR29: System tests connectivity and validity of a configured external service (OpenRouter, Azure Speech, image endpoint) on demand
FR30: User can set their native language and one or more target languages
FR31: User can configure OpenRouter API key and select a model
FR32: User can configure Azure Speech credentials
FR33: User can configure an image generation endpoint and credentials
FR34: User can configure Whisper model selection for local speech fallback
FR35: System stores all credentials securely in local storage — never plaintext
FR36: User can configure system-wide default behaviors (auto-generate audio for new cards, auto-generate images, default practice mode, cards per session)
FR37: User can override system-wide defaults at the deck level
FR38: System presents a guided onboarding flow for each external service (OpenRouter, Azure Speech, image generation) with step-by-step setup instructions
FR39: System is fully functional before any external service is configured (local fallback active)
FR40: User reaches a first completed card within 60 seconds of first app launch
FR41: User can view a progress dashboard showing vocabulary size, cards learned, and review activity over time
FR42: User can view per-session statistics (cards reviewed, correct rate, time spent)
FR43: System tracks FSRS scheduling state per card and surfaces cards due for review
FR44: System builds a continuous user knowledge profile based on vocabulary breadth, grammar forms encountered, practice performance, and recall history
FR45: System evaluates and displays the user's estimated CEFR level (A1–C2) derived from their knowledge profile
FR46: System displays a rich explanation of the assigned CEFR level — vocabulary ranges and grammar structures assessed, areas of confidence, and specific gaps to the next level
FR47: User can view knowledge profile breakdown by category (vocabulary size, grammar coverage, pronunciation accuracy, active vs. passive recall)
FR48: All user data (cards, decks, progress, settings, credentials) is stored locally on the user's device
FR49: System transmits no user data to external services beyond what the user explicitly configures (AI requests, speech evaluation)
FR50: System filters AI-generated content (example sentences, images) through a safety check before display

### NonFunctional Requirements

NFR1: Card creation pipeline < 3 seconds end-to-end (OpenRouter); < 5 seconds (local Qwen fallback)
NFR2: Speech evaluation < 2 seconds from utterance end to feedback display (Azure Speech or local Whisper)
NFR3: App shell initial load < 2 seconds on desktop; < 4 seconds on mobile
NFR4: AI streaming: first token visible within 500ms of request
NFR5: Practice session UI: 60fps card transitions; optimistic updates; no blocking spinners
NFR6: Import processing: batch AI enrichment runs in background without blocking UI
NFR7: All credentials stored using OS keychain where available; encrypted local store as fallback — never plaintext
NFR8: Credentials never appear in application logs, error messages, or crash reports
NFR9: No telemetry, analytics, or usage data transmitted to any party — silent on the network except for explicit user-configured service calls
NFR10: All core features (card creation, practice, FSRS scheduling) function fully offline — network never required
NFR11: External service failures degrade gracefully — fall back to local models with clear user notification; sessions never crash or block
NFR12: All writes are durable before confirmation is shown to user — no data loss on crash
NFR13: WCAG 2.1 AA compliance across all flows
NFR14: Full keyboard navigation — no mouse-only interactions
NFR15: Screen-reader compatibility for card creation, practice sessions, and settings
NFR16: Speak mode has a keyboard-accessible alternative for users without microphone access
NFR17: Color contrast minimum 4.5:1 for all text and UI elements
NFR18: OpenRouter: standard REST API; supports model enumeration, streaming completions, connection testing
NFR19: Azure Speech: real-time speech recognition and pronunciation assessment APIs
NFR20: Local Qwen: Ollama-compatible local inference API (via llama-cpp-python, no Ollama server)
NFR21: Local Whisper: faster-whisper local process with stable API interface
NFR22: Image generation: configurable REST endpoint (OpenAI image generation API format)
NFR23: Anki import: .apkg and plain text/TSV deck formats
NFR24: AI service abstraction: LLM and speech providers swappable behind a common interface — adding a new provider requires no changes to business logic
NFR25: Storage abstraction: data layer uses SQLite (desktop) managed by Python backend
NFR26: Open-source contribution-friendly: consistent code style, documented public interfaces

### Additional Requirements

- **Starter / project init:** No existing template covers this stack. Project initialization (FastAPI + Vite React TS uv-managed monorepo) is the first implementation story; initialization commands are documented in Architecture.
- **Schema migrations:** Alembic must be set up before the first data model is written; migrations run automatically on app startup.
- **FSRS library:** Use `fsrs` v6.3.1 (PyPI). Card table must include FSRS state columns: `stability`, `difficulty`, `due`, `last_review`, `reps`, `lapses`, `state`. Review log stored in a separate `reviews` table.
- **Real-time communication:** SSE (Server-Sent Events) only — no WebSockets. Three SSE channels: `POST /cards/stream` (card creation), `GET /import/{job_id}/progress` (enrichment progress), `GET /models/download/progress` (model download progress).
- **Credential storage:** `keyring` Python library (OS keychain on macOS/Windows/Linux; encrypted file fallback). Must be wired before any external service call. No credential reads outside `services/credentials.py`.
- **Frontend state split:** TanStack Query v5.99.2 (server state) + Zustand v5.0.12 (UI-only state). Server data never duplicated in Zustand.
- **Frontend routing:** TanStack Router (file-based route tree, type-safe params).
- **API client:** `openapi-typescript` generates TypeScript types from FastAPI OpenAPI schema at build time — no manual type sync.
- **Structured logging:** `structlog` with credential-scrubbing processor; log level via `LINGOSIPS_LOG_LEVEL` env var; default `WARNING` in production; no remote log shipping.
- **TTS service (Architecture gap resolved):** `AbstractSpeechProvider` gains `synthesize(text, lang) → bytes` method alongside `evaluate_pronunciation()`. `pyttsx3` added as local TTS fallback for card audio; `pyttsx3` is a required backend dependency.
- **Anki .apkg parsing:** `genanki` library added to backend dependencies.
- **Deck sharing file format:** `.lingosips` file — a renamed ZIP containing `deck.json` (card metadata + FSRS state) and `audio/` folder (pronunciation audio files).
- **Background job lifecycle:** Job status persisted to SQLite `jobs` table before any async work begins; jobs survive server restarts.
- **Content safety filter:** Keyword/pattern blocklist for MVP (`core/safety.py`) — no external API or extra model required.
- **Auto-update check:** On startup, async non-blocking check of PyPI JSON API (`https://pypi.org/pypi/lingosips/json`); surfaces "Update available" banner if newer version detected.
- **Server binding:** FastAPI server bound to `127.0.0.1:7842` exclusively — no LAN or internet exposure.
- **Startup sequence:** (1) Alembic migrations → (2) verify `~/.lingosips/` data directory → (3) async PyPI update check → (4) start uvicorn → (5) open browser.
- **CI/CD:** GitHub Actions — `ruff check` + `pytest` (90% coverage gate) + `vitest` + `playwright` on every PR; `uv build` + `uv publish` to PyPI on semver tag push.
- **TDD mandatory:** Write failing tests before any implementation code — a story without passing tests is not done.
- **API test coverage:** Every endpoint must have positive, negative, and edge case tests (missing fields → 422, not found → 404 RFC 7807, service unavailable → graceful fallback, SSE stream complete + error events).
- **Playwright E2E:** All 5 PRD journeys and all FR categories (FR1–FR50) covered by at least one Playwright spec; tests run against a real backend with a test SQLite database.
- **Local model management:** `services/models/manager.py` owns all model download, hash verification, and lifecycle for Qwen + Whisper; no Ollama server required by the user; first-use download shows progress via SSE.
- **Implementation sequence (strict order for first stories):** (1) project init, (2) `db/models.py` + Alembic, (3) `services/registry.py` + LLM/speech providers, (4) `core/fsrs.py`.

### UX Design Requirements

UX-DR1: Implement `CardCreationPanel` custom component with 5 enum-driven states (idle → loading → populated → saving → error); skeleton placeholders appear immediately on Enter before AI response arrives; fields reveal sequentially with 150ms stagger (translation → forms → example → audio); input refocuses after card save; `aria-label` on input; `aria-live="polite"` on field slots for screen reader announcements.
UX-DR2: Implement `SyllableFeedback` custom component with per-chip states (neutral / correct / wrong / pending) and 5 component states (awaiting / evaluating / result-correct / result-partial / fallback-notice); amber highlight (not red) on wrong syllable; correction text always visible as text — never color-only; `aria-live` on correction sentence; `aria-label` per chip including syllable text and status.
UX-DR3: Implement `PracticeCard` custom component handling all three practice modes (self-assess / write / speak) in a single component with 6 enum-driven states (front / revealed / write-active / write-result / speak-recording / speak-result); vertical slide transition for reveal (not 3D flip); FSRS rating row slides up from below on reveal; `prefers-reduced-motion` disables all transitions; keyboard shortcuts: Space (flip), Enter (submit write), R (record speak), 1–4 (FSRS ratings), Tab (navigate rating row), Escape (end session).
UX-DR4: Implement `ServiceStatusIndicator` custom component in icon sidebar footer (desktop) / settings header (mobile) with 5 states (cloud-active / local-active / cloud-degraded / switching / error); `aria-live="polite"` on status changes; status always machine-readable text — not color-only; expandable on click showing latency + last successful call timestamp + "Configure" link.
UX-DR5: Implement `QueueWidget` custom component with 3 states (due / empty / in-session); due count has `aria-label="X cards due for review"`; practice button is primary tab stop in right panel; mode selector chips use `role="radiogroup"` semantics; right panel collapses to thin status bar during active session.
UX-DR6: Implement composite layout system: D2 home layout (64px icon sidebar + fluid creation main panel + 360px fixed right queue column); D4 practice layout (centered single column, sidebar + right panel collapsed); D5 speak mode layout (full viewport, mic UI centered, syllable feedback above mic); animated collapse/restore transition between D2 and D4/D5 on session start/end.
UX-DR7: Implement responsive design breakpoints: 1024px+ = full D2 layout; 768–1023px = right column → collapsible drawer + bottom navigation bar replaces icon sidebar; <768px = single column, bottom nav, FSRS rating buttons full-width, session summary as modal bottom sheet (sole modal exception); minimum 44×44px touch targets on all interactive elements.
UX-DR8: Implement design token system via CSS custom properties mapped to Tailwind config: zinc-950 background, zinc-900 surface, zinc-800 border, zinc-400 muted text, zinc-50 primary text, indigo-500 accent (focus rings / active states / primary buttons), indigo-400 hover, emerald-500 success, amber-500 warning, red-400 error, amber-400 pronunciation error highlight.
UX-DR9: Implement dark-mode-first with light mode support via Tailwind `dark:` variants; dark mode is the default; light mode uses zinc-50 backgrounds with zinc-900 text.
UX-DR10: Implement typography system: Inter variable font with system font stack fallback; 7-level type scale 12px–36px using rem; line-height 1.6 for body text and examples, 1.2 for headings; font weights 400 (body) / 500 (labels) / 600 (primary headings, target word on practice card).
UX-DR11: Implement first-run onboarding wizard: language selection only (native + target language); service configuration optional — skip goes directly to home dashboard; guided API key setup panels open inline within Settings page (no modal, no navigation away); connection test generates a real sample card (not a ping).
UX-DR12: Implement FSRS rating row with keyboard shortcuts 1–4; label tooltips on first 3 sessions explaining Again/Hard/Good/Easy scheduling impact; keyboard shortcut labels visible on hover after first session; labels hidden (buttons remain) after session 3.
UX-DR13: Implement honest service status messaging throughout: every error message names (1) what failed, (2) why if known, (3) what to do next; service fallback announcements include service name and timing expectation; no generic "Something went wrong" messages or undifferentiated spinners anywhere in the app.
UX-DR14: Implement speak mode D5 full-viewport layout: tap-to-record mic button with pulsing recording state; one-time first-use tooltip ("Tap mic to record · release to evaluate"); skip action keyboard-accessible at all times via S key and Tab-to-Skip button; R keyboard shortcut to start recording.
UX-DR15: Implement import UI: three input sources (Anki .apkg file picker with drag-and-drop, plain text/TSV paste or file picker, URL input); background enrichment shows persistent progress ring on sidebar Import icon; navigation away from import screen is always safe (enrichment continues); completion surfaced as Toast notification with honest unresolved field count.

### FR Coverage Map

| FR | Epic | Domain |
|---|---|---|
| FR1 | Epic 1 | Card creation — single word/phrase input |
| FR2 | Epic 1 | AI auto-generation of translation, forms, audio, examples |
| FR3 | Epic 2 | Personal note on card |
| FR4 | Epic 2 | Manual edit of AI-generated fields |
| FR5 | Epic 2 | Card assignment to decks |
| FR6 | Epic 2 | Card deletion |
| FR7 | Epic 2 | Image generation via configured endpoint |
| FR8 | Epic 2 | Trigger or skip image generation per card |
| FR9 | Epic 2 | Deck create, rename, delete |
| FR10 | Epic 2 | Browse and filter deck collection |
| FR11 | Epic 2 | Deck export to .lingosips file |
| FR12 | Epic 2 | Deck import from .lingosips file |
| FR13 | Epic 2 | Import vocabulary from text, URL, Anki file |
| FR14 | Epic 2 | Unknown word detection in imported text |
| FR15 | Epic 2 | AI enrichment of imported cards |
| FR16 | Epic 2 | Multiple target languages simultaneously |
| FR17 | Epic 3 | Start practice session |
| FR18 | Epic 3 | Self-assess mode |
| FR19 | Epic 3 | Write mode |
| FR20 | Epic 3 | AI evaluation of written answer + correction |
| FR21 | Epic 4 | Speak mode — record pronunciation |
| FR22 | Epic 4 | Per-syllable pronunciation feedback |
| FR23 | Epic 3 | Sentence and collocation translation practice |
| FR24 | Epic 3 | FSRS scheduling |
| FR25 | Epic 3 | FSRS rescheduling on failure |
| FR26 | Epic 1 | LLM routing: OpenRouter → Qwen local fallback |
| FR27 | Epic 4 | Speech routing: Azure Speech → Whisper local fallback |
| FR28 | Epic 1 | AI content streaming (SSE) |
| FR29 | Epic 2 | External service connection testing |
| FR30 | Epic 1 | Native + target language configuration |
| FR31 | Epic 2 | OpenRouter API key + model selection |
| FR32 | Epic 2 | Azure Speech credentials |
| FR33 | Epic 2 | Image generation endpoint + credentials |
| FR34 | Epic 2 | Whisper model selection |
| FR35 | Epic 1 | Secure credential storage (keyring) |
| FR36 | Epic 2 | System-wide default behaviors |
| FR37 | Epic 2 | Deck-level default overrides |
| FR38 | Epic 1 | Guided onboarding wizard (language); Epic 2 (service panels) |
| FR39 | Epic 1 | Fully functional with zero configuration |
| FR40 | Epic 1 | First completed card within 60 seconds |
| FR41 | Epic 3 | Progress dashboard — vocab size, activity over time |
| FR42 | Epic 3 | Per-session stats |
| FR43 | Epic 3 | FSRS state tracking + due card surfacing |
| FR44 | Epic 5 | CEFR knowledge profile from review history |
| FR45 | Epic 5 | CEFR level display (A1–C2) |
| FR46 | Epic 5 | Explanatory CEFR assessment + gap analysis |
| FR47 | Epic 5 | Knowledge profile breakdown by category |
| FR48 | Epic 1 | All data stored locally on device |
| FR49 | Epic 1 | No transmission beyond explicit configuration |
| FR50 | Epic 1 | Content safety filter for AI-generated content |

## Epic List

### Epic 1: Working App & First Card
User can launch the app, select their languages, and create a complete AI-generated card (translation, forms, audio, examples) in under 60 seconds — no API keys required. This is the product's defining "wow" moment and the foundational experience everything else builds on.
**FRs covered:** FR1, FR2, FR26, FR28, FR30, FR35, FR38, FR39, FR40, FR48, FR49, FR50

### Epic 2: Vocabulary Ownership & Import
User can edit, organize, and import their vocabulary — from Anki decks, text, or URLs — configure cloud AI services for full quality, manage multiple target languages, and export decks for sharing.
**FRs covered:** FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR29, FR31, FR32, FR33, FR34, FR36, FR37

### Epic 3: Practice Loop & Progress Tracking
User can practice due cards in self-assess and write modes with inline AI feedback, trust FSRS to schedule the right reviews automatically, and see their progress — vocabulary size, session stats, recall rate — over time.
**FRs covered:** FR17, FR18, FR19, FR20, FR23, FR24, FR25, FR41, FR42, FR43

### Epic 4: Speak Mode & Pronunciation Mastery
User can practice pronunciation with per-syllable AI feedback, retry specific mistakes in one tap, and build speaking confidence — with Azure Speech delivering cloud quality and local Whisper as the fallback.
**FRs covered:** FR21, FR22, FR27

### Epic 5: CEFR Learner Intelligence
User can see their estimated CEFR level (A1–C2), understand exactly what they demonstrate confidently, and see the specific vocabulary and grammar gaps separating them from the next level.
**FRs covered:** FR44, FR45, FR46, FR47

## Epic 1: Working App & First Card

User can launch the app, select their languages, and create a complete AI-generated card (translation, forms, audio, examples) in under 60 seconds — no API keys required. This is the product's defining "wow" moment and the foundational experience everything else builds on.

### Story 1.1: Project Initialization & Dev Infrastructure

As a developer,
I want the project scaffolded as a uv-managed FastAPI + Vite React TypeScript monorepo with CI configured,
So that the full-stack development environment is ready for feature implementation.

**Acceptance Criteria:**

**Given** the repository is freshly cloned
**When** `make dev` is run
**Then** the FastAPI server starts on `127.0.0.1:7842` and Vite dev server starts on `localhost:5173`
**And** the browser opens automatically to `http://localhost:7842`

**Given** frontend source files change while `make dev` is running
**When** the change is saved
**Then** Vite hot-reloads the browser without a full page refresh

**Given** `make build` is run
**When** it completes
**Then** the Vite frontend compiles to `src/lingosips/static/` and `uv build` produces a distributable wheel with static assets bundled

**Given** a PR is opened
**When** GitHub Actions CI runs
**Then** `ruff check`, `pytest` (no failures), and `vitest run` all pass before merge is allowed

**Given** the FastAPI app starts via `__main__.py`
**Then** it binds exclusively to `127.0.0.1:7842` — never `0.0.0.0`
**And** the startup sequence runs in order: data directory check → uvicorn start → browser open

### Story 1.2: App Shell & Design System Foundation

As a user,
I want the application to open with a correct layout skeleton, design tokens, dark-mode-first, Inter typography, and responsive behavior,
So that all subsequent UI work builds on a consistent, accessible foundation.

**Acceptance Criteria:**

**Given** I open the app on desktop (1024px+)
**When** the shell loads
**Then** the D2 layout is present: 64px fixed icon sidebar, fluid main area, and 360px fixed right column
**And** CSS design tokens are applied: `zinc-950` background, `zinc-900` surface, `zinc-800` border, `indigo-500` accent, `zinc-50` primary text, `zinc-400` muted text

**Given** dark mode is the system default
**When** the app loads
**Then** dark mode is active by default with `zinc-950` background

**Given** I switch to light mode
**When** the Tailwind `dark:` variants resolve
**Then** `zinc-50` backgrounds and `zinc-900` text are applied correctly

**Given** I open the app on mobile (<768px)
**When** the viewport renders
**Then** the icon sidebar is replaced by a bottom navigation bar
**And** the right column stacks below the main content as a collapsed accordion

**Given** I tab through any interactive element
**When** it receives focus
**Then** a visible `indigo-500` 2px solid focus ring with 2px offset is shown — never removed

**Given** any text renders in the app
**Then** Inter variable font is loaded with the correct type scale (12px–36px using rem, body line-height 1.6, heading 1.2)
**And** font weights 400 (body) / 500 (labels) / 600 (primary headings) are applied

### Story 1.3: First-Run Language Onboarding

As a first-time user,
I want a simple language selection wizard on first launch (native language + target language only),
So that I can reach the card creation interface in under 60 seconds with zero configuration and no account creation.

**Acceptance Criteria:**

**Given** I launch the app for the first time (no Settings record in the DB)
**When** the app opens
**Then** the `OnboardingWizard` is shown with native language and target language selectors
**And** no account, email, or password is required

**Given** I select my languages and click "Start learning"
**When** the wizard completes
**Then** the language selections are persisted to the Settings table (Alembic migration `001_initial_schema` has run)
**And** I land on the home dashboard with the creation input focused and ready

**Given** I am on the onboarding wizard
**When** I choose to skip service configuration
**Then** I reach the home dashboard immediately
**And** the app is fully functional with local AI fallback active

**Given** I return to the app after completing onboarding
**When** the app loads on subsequent launches
**Then** the wizard does not appear
**And** the home dashboard loads directly

**Given** the Settings table does not yet exist
**When** the app starts
**Then** Alembic runs `001_initial_schema` migration automatically before the server accepts requests

### Story 1.4: AI Provider Abstraction & Local LLM Fallback

As a user,
I want card generation to work out-of-the-box using local Qwen when no API key is configured,
So that I get value from the app with zero configuration.

**Acceptance Criteria:**

**Given** no OpenRouter API key is configured
**When** a card creation request is made
**Then** `services/registry.py` returns `QwenLocalProvider`
**And** the request is processed via `llama-cpp-python` running the local Qwen GGUF model

**Given** an OpenRouter API key is configured in the keyring
**When** a card creation request is made
**Then** `services/registry.py` returns `OpenRouterProvider`
**And** the request routes to the OpenRouter API

**Given** the local Qwen model has not yet been downloaded
**When** a card creation request is made for the first time
**Then** model download begins automatically
**And** download progress is streamed to the browser via SSE (`event: progress`)
**And** card creation queues until the model is ready

**Given** `get_llm_provider()` is called anywhere
**Then** it is always resolved via FastAPI `Depends()` — direct instantiation of providers is never used outside `services/`

**Given** a new provider class is added to `services/llm/` implementing `AbstractLLMProvider`
**When** `get_llm_provider()` returns it
**Then** no changes to `core/` business logic are required

### Story 1.5: Card Creation API & SSE Streaming

As a user,
I want to submit a word or phrase and receive a complete AI-generated card with translation, grammatical forms, and example sentences streamed field-by-field,
So that I can build vocabulary in seconds with real-time visual feedback.

**Acceptance Criteria:**

**Given** I submit a valid word or phrase to `POST /cards/stream`
**When** the AI pipeline runs
**Then** an SSE stream emits `field_update` events in order: translation → gender/article/forms → example sentences
**And** a final `complete` event is emitted when all fields are populated
**And** the card is persisted to the `cards` table in SQLite

**Given** the AI returns content
**When** the response is parsed
**Then** `core/safety.py` filters content through the keyword blocklist before fields are streamed
**And** any blocked content triggers an `error` SSE event with a specific message

**Given** I submit an empty or whitespace-only string
**When** the endpoint processes the request
**Then** a `422 Unprocessable Entity` response is returned with field-level detail in RFC 7807 format

**Given** the LLM times out mid-stream
**When** the timeout occurs
**Then** an SSE `error` event is emitted: `{"message": "Local Qwen timeout after 10s"}`
**And** the stream closes gracefully — no crash, no hanging connection

**Given** any SSE event is emitted
**Then** the envelope is exactly: `event: {event_type}\ndata: {json_payload}\n\n`
**And** the JSON payload uses snake_case field names throughout

All card creation endpoints must have positive, negative, and edge case tests: missing fields → 422, LLM timeout → error event, SSE complete event sequence, safety filter blocking.

### Story 1.6: Card Audio Generation (TTS)

As a user,
I want pronunciation audio automatically generated for each new card,
So that I can hear the correct pronunciation of new vocabulary without leaving the app.

**Acceptance Criteria:**

**Given** a card creation completes
**When** the AI pipeline finishes
**Then** `AbstractSpeechProvider.synthesize(text, language)` is called with the target word
**And** the resulting audio bytes are stored and associated with the card

**Given** no Azure Speech credentials are configured
**When** TTS is requested
**Then** `pyttsx3` handles synthesis as the local fallback
**And** audio is generated without error

**Given** Azure Speech credentials are configured
**When** TTS is requested
**Then** `AzureSpeechProvider.synthesize()` is used for higher-quality audio

**Given** audio generation succeeds
**When** the SSE stream emits the `complete` event
**Then** a `field_update` event for `"audio"` has been emitted with the audio URL
**And** an audio player renders in the card result and auto-plays once on creation

**Given** TTS synthesis fails entirely
**When** the error occurs
**Then** the card is saved without audio
**And** the audio field displays a muted "Not available" state
**And** card creation does not fail or roll back due to the TTS failure

### Story 1.7: CardCreationPanel Component

As a user,
I want a creation input that instantly shows skeleton placeholders on Enter and reveals each card field sequentially as AI fills them,
So that card creation feels alive and fast — not like waiting for a spinner.

**Acceptance Criteria:**

**Given** I am on the home dashboard on desktop
**When** the page loads
**Then** the creation input is focused automatically with `aria-label="New card — type a word or phrase"`

**Given** I type a word and press Enter
**When** the request begins
**Then** skeleton placeholders appear immediately (zero delay) for translation, forms, example, and audio
**And** the input is disabled during generation
**And** no blocking spinner is displayed

**Given** the AI streams field data back
**When** each field is ready
**Then** it replaces the skeleton with a fade-in from slightly below, staggered 150ms between fields (translation → forms → example → audio)
**And** each field slot has `aria-live="polite"` so screen readers announce content as it populates

**Given** the card fully populates and I save it
**When** the save completes
**Then** the input clears and refocuses automatically — ready for the next word

**Given** the LLM request fails
**When** the error occurs
**Then** a specific inline error appears below the input (e.g., "Local Qwen is processing — this may take up to 5 seconds")
**And** the error is never the generic "Something went wrong"
**And** a retry action is available

**Given** a user has `prefers-reduced-motion` enabled
**When** fields populate
**Then** all stagger animations are disabled — fields appear instantly

Vitest + RTL tests must cover all 5 component states (idle, loading, populated, saving, error), keyboard flow (Enter submits, Tab navigates action buttons), and `aria-live` announcements.

### Story 1.8: Service Status Indicator

As a user,
I want to always see which AI service is active (cloud or local fallback) in the sidebar,
So that I understand the quality and speed of AI generation at a glance without navigating to Settings.

**Acceptance Criteria:**

**Given** no API keys are configured
**When** the home dashboard renders
**Then** `ServiceStatusIndicator` shows "Local Qwen" with an amber dot in the sidebar footer
**And** the status is communicated as text — not color alone

**Given** OpenRouter is configured and responding normally
**When** the indicator renders
**Then** it shows "OpenRouter · [model name]" with a green dot

**Given** a service switch occurs (e.g., OpenRouter → Local Qwen)
**When** the switch happens
**Then** `aria-live="polite"` announces the change to screen readers within 1 second
**And** the indicator updates to reflect the new active service

**Given** I click the ServiceStatusIndicator
**When** it expands
**Then** it shows: active service name, last call latency, last successful call timestamp, and a "Configure →" link to Settings
**And** it collapses on outside click

**Given** the app is on mobile (<768px)
**When** I navigate to Settings
**Then** the ServiceStatusIndicator appears in the Settings screen header

Vitest + RTL tests must cover all 5 states (cloud-active, local-active, cloud-degraded, switching, error) plus aria-live announcement and keyboard expansion.

### Story 1.9: Secure Credential Storage Foundation

As a user,
I want all API keys stored via the OS keychain (never plaintext) and all logs stripped of credential patterns,
So that my credentials are secure even if log files or config files are examined.

**Acceptance Criteria:**

**Given** any API key is saved in the app
**When** `services/credentials.py` writes it
**Then** the `keyring` library stores it in the OS keychain (macOS Keychain, Windows Credential Locker, Linux libsecret/kwallet)
**And** if no OS keychain is available, an encrypted file store is used as fallback
**And** the credential is never written to SQLite, `.env` files, or any plaintext config

**Given** the application produces any log output
**When** a string matching a credential pattern is present in the data
**Then** the `structlog` credential-scrubbing processor replaces it with `[REDACTED]` before emission

**Given** an unhandled exception occurs
**When** the Python traceback or error response is generated
**Then** no credential values appear in the traceback, error detail, or HTTP error response

**Given** any module needs to read a credential
**Then** it must call `services/credentials.py` — no module reads from `keyring` directly

**Given** `LINGOSIPS_LOG_LEVEL=DEBUG` is set
**When** verbose logging runs
**Then** credentials are still scrubbed — debug logging does not bypass the credential processor

## Epic 2: Vocabulary Ownership & Import

User can edit, organize, and import their vocabulary — from Anki decks, text, or URLs — configure cloud AI services for full quality, manage multiple target languages, and export decks for sharing.

### Story 2.1: Card Detail, Editing & Notes

As a user,
I want to view card details, add personal notes, edit any AI-generated field, and delete cards,
So that I can customize my vocabulary cards to match my learning context.

**Acceptance Criteria:**

**Given** a card exists in my collection
**When** I click on it
**Then** `CardDetail` opens showing all fields: target word, translation, grammatical forms, example sentences, audio player, personal note, and FSRS due status

**Given** I click any AI-generated field in CardDetail
**When** I edit the text
**Then** it saves inline on blur (`PATCH /cards/{card_id}` with the updated field)
**And** the updated value is reflected immediately without a page reload

**Given** I add or edit a personal note
**When** I finish editing
**Then** the note persists to the `cards` table and is shown on future card views

**Given** I click "Delete card"
**When** the delete action is triggered
**Then** a confirmation Dialog appears with text "Delete card · This cannot be undone" and Cancel / Delete actions

**Given** I confirm deletion
**When** `DELETE /cards/{card_id}` is called
**Then** the card is removed from SQLite and no longer appears in any deck or practice queue

**Given** `GET /cards/{card_id}` is called with a non-existent ID
**Then** a `404` response with RFC 7807 body is returned: `{"type": "/errors/card-not-found", ...}`

API tests must cover: successful fetch, successful update of each field, 404 on missing card, 422 on invalid field values, and deletion removing the card from FSRS queue.

### Story 2.2: Deck Management & Multi-Language

As a user,
I want to create, rename, delete, and browse decks — assign cards to decks and manage vocabulary across multiple target languages simultaneously,
So that I can organize my learning by topic, source, or language.

**Acceptance Criteria:**

**Given** I open the Decks screen
**When** it loads
**Then** `DeckGrid` shows all my decks with card count, due card count, and target language badge
**And** decks are filterable by name

**Given** I click "New deck"
**When** I submit a deck name
**Then** `POST /decks` creates the deck and it appears in DeckGrid immediately

**Given** I rename a deck
**When** I submit the new name
**Then** `PATCH /decks/{deck_id}` updates it; the new name renders without a page reload

**Given** I delete a deck
**When** I confirm deletion in the Dialog
**Then** `DELETE /decks/{deck_id}` removes the deck; cards that were in it remain in the card collection (not deleted)

**Given** I save a card from the CardCreationPanel
**When** the save action row is shown
**Then** a deck assignment dropdown lists my decks; selecting one assigns the card (`PATCH /cards/{card_id}` with `deck_id`)

**Given** I have multiple target languages configured
**When** I switch the active target language
**Then** the deck browser and creation panel show only decks and cards for the selected language
**And** I can switch languages without losing my place

**Given** `POST /decks` is called with a name that already exists for the same target language
**Then** a `409 Conflict` response is returned with an RFC 7807 body

API tests: successful CRUD, 404 on missing deck, 409 on duplicate name, empty deck returns `[]` not `null`, multi-language filtering.

### Story 2.3: Service Configuration & System Defaults

As a user,
I want to configure my OpenRouter key (with model selection), Azure Speech credentials, image endpoint, and Whisper model — all in guided inline panels with live connection testing — and set system-wide and deck-level defaults,
So that I can upgrade from local models to cloud quality without leaving the Settings page.

**Acceptance Criteria:**

**Given** I open Settings → AI section
**When** I click "Upgrade"
**Then** a guided configuration panel opens inline within the Settings page — no modal, no navigation away
**And** the panel shows step-by-step instructions: link to OpenRouter signup → paste API key (masked input) → model selector (pre-filtered list)

**Given** I enter an OpenRouter API key and selected model and click "Test connection"
**When** the test runs
**Then** a real sample card is generated using the configured key and the result is shown inline
**And** if the test succeeds, a "Save" button activates

**Given** I save valid OpenRouter credentials
**When** the save completes
**Then** `services/credentials.py` stores the key via keyring
**And** `ServiceStatusIndicator` updates to show "OpenRouter · [model name]" with a green dot

**Given** I enter an invalid API key and test connection
**When** the test fails
**Then** a specific error appears: "Invalid API key · Check your OpenRouter dashboard"
**And** no credential is saved

**Given** I configure system-wide defaults (auto-generate audio on new cards, auto-generate images, default practice mode, cards per session)
**When** I save
**Then** `GET /settings` returns the updated defaults
**And** new sessions use these defaults

**Given** I override defaults at the deck level
**When** I open deck settings and set deck-specific values
**Then** those values override system-wide defaults for that deck only

API tests: save + retrieve settings, invalid key format → 422, connection test with bad key → specific error body, deck-level defaults override verified.

### Story 2.4: Import Pipeline — Anki, Text & URL

As a user,
I want to import vocabulary from an Anki .apkg file, plain text/TSV, or a URL — with AI enriching missing fields in the background while I keep using the app — so that my existing vocabulary investments are upgraded instantly.

**Acceptance Criteria:**

**Given** I open the Import screen
**When** it loads
**Then** three input sources are displayed: Anki .apkg file picker (with drag-and-drop), plain text/TSV paste/file picker, and URL input

**Given** I upload an Anki .apkg file
**When** it is parsed using `genanki`
**Then** a deck preview shows: card count, fields present in the source, fields missing per card type

**Given** I paste text or provide a URL
**When** it is processed
**Then** unknown words are detected and shown as a preview list with checkboxes so I can select which to import

**Given** I approve import with AI enrichment
**When** the enrichment job starts
**Then** job status is persisted to the `jobs` table before any async enrichment work begins
**And** `BackgroundTasks` processes enrichment without blocking foreground requests

**Given** enrichment is running in the background
**When** I navigate to any other screen
**Then** enrichment continues uninterrupted
**And** a progress ring appears on the sidebar Import icon showing progress

**Given** enrichment completes
**When** the job finishes
**Then** a Toast notification appears: "N cards enriched · M fields could not be resolved"
**And** cards with unresolved fields are flagged in the deck for review — not silently dropped

**Given** `GET /import/{job_id}/progress` is subscribed via SSE
**Then** `progress` events are emitted: `{"done": 23, "total": 400, "current_item": "enriching audio..."}`
**And** a final `complete` event is emitted when the job finishes

API tests: job persists before work, progress SSE sequence, partial failure handling, navigate-away safety, 404 on unknown job_id.

### Story 2.5: Deck Export & Import (.lingosips Format)

As a user,
I want to export any deck to a shareable `.lingosips` file and import a `.lingosips` file from another user,
So that I can share curated vocabulary decks with others.

**Acceptance Criteria:**

**Given** I am on a deck detail page
**When** I click "Export deck"
**Then** a `.lingosips` file is downloaded — a ZIP containing `deck.json` (all card metadata + FSRS state) and `audio/` folder (pronunciation audio files)
**And** the file contains human-readable JSON inside the ZIP

**Given** I open Import and choose a `.lingosips` file
**When** it is parsed
**Then** a preview shows: deck name, card count, target language, and sample cards

**Given** I confirm the import
**When** it completes
**Then** all cards are added to a new deck with their FSRS state and audio intact
**And** the deck appears in DeckGrid immediately

**Given** the `.lingosips` file is malformed or missing required fields
**When** I try to import it
**Then** a specific error message describes what is invalid

**Given** a `.lingosips` file contains audio files
**When** it is imported
**Then** audio files are stored and linked to the imported cards correctly

API tests: export produces valid ZIP with correct structure, import from valid file succeeds, 422 on malformed file with field-level error detail.

### Story 2.6: Per-Card Image Generation

As a user,
I want to optionally generate an image for any card using a configured image generation endpoint,
So that visual memory hooks can strengthen my vocabulary retention.

**Acceptance Criteria:**

**Given** a card is open in CardDetail and an image endpoint is configured
**When** I click "Add image"
**Then** an image generation request is sent to the configured endpoint (OpenAI image generation REST format) with the target word as the prompt

**Given** image generation completes
**When** the image is received
**Then** `core/safety.py` filters the image before display
**And** if the image passes the safety check, it is stored and shown on the card

**Given** an image fails the safety check
**When** the filter rejects it
**Then** a message is shown: "Image filtered — please try again"
**And** the card is saved without an image

**Given** no image generation endpoint is configured
**When** I click "Add image"
**Then** a prompt directs me to configure the endpoint in Settings
**And** no request is made

**Given** I click "Skip image" on a card
**When** I skip
**Then** the image field is explicitly marked as skipped and no image generation is attempted in future auto-runs

**Given** image generation fails (API error or timeout)
**When** the error occurs
**Then** a specific error message is shown
**And** the card is saved without an image — image failure does not block card save

API tests: successful generation + safety pass, safety filter rejection, missing endpoint → 422, generation failure → specific error response.

## Epic 3: Practice Loop & Progress Tracking

User can practice due cards in self-assess and write modes with inline AI feedback, trust FSRS to schedule the right reviews automatically, and see their progress — vocabulary size, session stats, recall rate — over time.

### Story 3.1: FSRS Scheduling Engine & Practice Queue

As a user,
I want cards automatically scheduled by the FSRS algorithm and surfaced on the home dashboard when they are due,
So that I practice at scientifically optimal intervals without ever thinking about when to review.

**Acceptance Criteria:**

**Given** a card is created
**When** it is first saved
**Then** FSRS initial state is set on the card: `stability=0`, `difficulty=0`, `state=New`, `due=now`
**And** the card appears immediately in `GET /practice/queue`

**Given** `GET /practice/queue` is called
**When** it responds
**Then** it returns all cards with `due <= now`, ordered by due date ascending
**And** the response includes FSRS state (`stability`, `difficulty`, `reps`, `lapses`, `state`) for each card

**Given** `POST /practice/cards/{card_id}/rate` is called with a rating (1=Again, 2=Hard, 3=Good, 4=Easy)
**When** it processes
**Then** `core/fsrs.py` calls `fsrs` v6.3.1 to compute the new FSRS state
**And** the card's `stability`, `difficulty`, `due`, `last_review`, `reps`, `lapses`, and `state` are updated in SQLite
**And** a row is inserted into the `reviews` table with `card_id`, `rating`, `reviewed_at`, and post-review FSRS state

**Given** `core/fsrs.py` wraps `fsrs` v6.3.1
**Then** `api/practice.py` never calls the `fsrs` library directly — it always goes through `core/fsrs.py`

**Given** `QueueWidget` renders on the home dashboard
**When** there are N cards due
**Then** it shows the due count prominently with `aria-label="N cards due for review"` and a "Practice" primary button
**When** there are 0 cards due
**Then** it shows "All caught up · Next review in Xh" with the next due date

pytest coverage: get_due_queue returns correct cards, rating updates FSRS state correctly, review row inserted on each rating, queue empties after all cards rated Good.

### Story 3.2: Self-Assess Practice Mode

As a user,
I want to flip cards and rate my recall (Again / Hard / Good / Easy) with FSRS updating my schedule after each rating and the next card loading instantly,
So that I can build vocabulary retention through a fast, frictionless daily habit.

**Acceptance Criteria:**

**Given** I click "Practice" on the home dashboard
**When** the session starts
**Then** `POST /practice/session/start` returns the due card queue for the session
**And** the D4 layout activates: icon sidebar and right panel collapse with animation; the card expands to centered single-column

**Given** a `PracticeCard` is in `front` state
**When** it renders
**Then** the target word is shown at `text-4xl` with a "tap Space to reveal" hint below
**And** pressing Space or tapping flips to `revealed` state

**Given** the card is in `revealed` state
**When** it renders
**Then** translation, grammatical forms, and example sentence are shown
**And** the FSRS rating row slides up from below: Again · Hard · Good · Easy (keyboard: 1–4)

**Given** it is my first 3 practice sessions
**When** the FSRS rating row appears
**Then** each button shows a tooltip label explaining the scheduling impact

**Given** I press a rating key (1–4) or click a rating button
**When** the rating is submitted
**Then** an optimistic update loads the next card immediately at 60fps — no blocking spinner during card transitions
**And** `POST /practice/cards/{card_id}/rate` is called in the background
**And** if the API call fails, a notification is shown and the rating can be re-submitted

**Given** the session queue empties
**When** the last card is rated
**Then** `SessionSummary` is shown: cards reviewed, recall rate, next session due date
**And** after a brief pause the D2 home layout restores with animation

**Given** `prefers-reduced-motion` is enabled
**Then** all layout transition animations are instant

Playwright E2E: full session from queue → flip → rate × N cards → session summary → return to home.

### Story 3.3: Write Mode with AI Feedback

As a user,
I want to type the answer in write mode and receive inline AI feedback — showing exactly which characters were wrong, the correct form, and why — so that each mistake becomes a specific learning moment.

**Acceptance Criteria:**

**Given** write mode is selected for a practice session
**When** a `PracticeCard` renders
**Then** it starts in `write-active` state with an answer input field focused below the card and the target word visible above

**Given** I type my answer and press Enter
**When** `POST /practice/cards/{card_id}/evaluate` is called
**Then** `core/practice.py` compares the answer to the correct value
**And** calls the LLM provider to evaluate near-misses with linguistic context

**Given** my answer is correct
**When** evaluation completes
**Then** the card transitions to `write-result` state with an inline emerald success confirmation
**And** the FSRS rating row appears (pre-selected on Good, user can override)

**Given** my answer is wrong
**When** evaluation completes
**Then** incorrect characters are highlighted with `red-400` underline in my typed answer
**And** the correct answer appears below in `emerald-500`
**And** an explanation follows in `zinc-400` text (e.g., "Adjective agreement: use melancólica with feminine nouns")
**And** no modal or overlay is used — all feedback is inline on the card

**Given** evaluation fails (LLM timeout)
**When** the error occurs
**Then** a specific message appears inline: "Evaluation unavailable — rate manually"
**And** the FSRS rating row is shown so the session continues

Playwright E2E: correct answer → success state → Good rating; wrong answer → error highlighted → explanation shown → rating row appears.

### Story 3.4: Sentence & Collocation Practice

As a user,
I want to practice full sentence and collocation translation in all practice modes — not just isolated words — so that I develop the ability to use vocabulary in real linguistic context.

**Acceptance Criteria:**

**Given** I type a phrase or collocation into the card creation input
**When** the AI pipeline runs
**Then** the AI detects that the input is a phrase and sets `card_type = "sentence"` or `card_type = "collocation"` on the card
**And** the AI generates an idiomatic meaning explanation, register context, and a contextual example sentence

**Given** a sentence/collocation card is in the FSRS queue
**When** it appears in a practice session
**Then** the full phrase is shown as the card front at readable size
**And** self-assess reveals: idiomatic translation, register context, and example sentence

**Given** a sentence card is practiced in write mode
**When** the AI evaluates the typed translation
**Then** minor paraphrase variations are accepted as correct
**And** evaluation explains specific structural errors

**Given** a sentence card is included in a mixed session
**Then** FSRS scheduling applies identically regardless of `card_type`
**And** the same rating row (Again / Hard / Good / Easy) is used

API tests: sentence card created with correct card_type, appears in queue, evaluate endpoint accepts varied phrasing with LLM near-miss detection.

### Story 3.5: Progress Dashboard & Session Stats

As a user,
I want to see my vocabulary size, review activity over time, and per-session statistics after each practice session,
So that I can see genuine progress through real metrics — not gamified streaks or badges.

**Acceptance Criteria:**

**Given** I navigate to the Progress screen
**When** `GET /progress/dashboard` responds
**Then** `ProgressDashboard` shows: total cards in collection, cards "learned" (rated Good or Easy at least once), review count by day for the last 30 days, and overall recall rate

**Given** there are no reviews yet
**When** the dashboard loads
**Then** all metrics show zero or "No reviews yet" — no errors, no broken chart

**Given** a practice session ends
**When** `SessionSummary` renders
**Then** it shows exactly three data points: cards reviewed this session, recall rate, next session due date
**And** no stars, no congratulations copy, no streak counter — tone is neutral and factual

**Given** `GET /progress/sessions/{session_id}` is called
**When** it responds
**Then** it returns cards reviewed, per-card ratings, recall rate, time spent, and session start/end timestamps

**Given** `GET /progress/dashboard` is called when the FSRS review log is large (1000+ rows)
**When** it responds
**Then** it returns within the 2-second SLA — aggregation is performed efficiently with indexed queries

API tests: dashboard returns correct counts after seeded reviews, session stats accurate, empty state returns zeroes not null, large review log stays within latency SLA.

## Epic 4: Speak Mode & Pronunciation Mastery

User can practice pronunciation with per-syllable AI feedback, retry specific mistakes in one tap, and build speaking confidence — with Azure Speech delivering cloud quality and local Whisper as the fallback.

### Story 4.1: Speech Evaluation API — Whisper & Azure Speech

As a user,
I want my spoken pronunciation evaluated against the target word — using Azure Speech when configured and local Whisper as the fallback — with the result available within 2 seconds,
So that I get fast, accurate pronunciation feedback without requiring any cloud configuration.

**Acceptance Criteria:**

**Given** `AbstractSpeechProvider` is defined
**Then** it exposes `evaluate_pronunciation(audio: bytes, target: str, language: str) -> SyllableResult`
**And** `SyllableResult` contains: overall correctness, per-syllable breakdown (syllable text, is_correct, confidence), and a correction message for incorrect syllables

**Given** no Azure Speech credentials are configured
**When** `POST /practice/cards/{card_id}/speak` is called with audio bytes
**Then** `services/registry.py` returns `WhisperLocalProvider`
**And** `faster-whisper` evaluates the pronunciation locally

**Given** Azure Speech credentials are configured
**When** `POST /practice/cards/{card_id}/speak` is called
**Then** `services/registry.py` returns `AzureSpeechProvider`
**And** Azure Speech pronunciation assessment API is used

**Given** the speech evaluation completes
**When** the response is returned
**Then** it arrives within 2 seconds of the audio being submitted
**And** the response contains the `SyllableResult` with per-syllable correctness data

**Given** the Whisper model is not yet downloaded
**When** speak mode is first used
**Then** the model downloads automatically via the model manager with SSE progress
**And** speak mode is unavailable with a clear message until the download completes

**Given** the speech service fails mid-evaluation
**When** the error occurs
**Then** the endpoint returns a specific error response — never a generic 500
**And** the frontend can display: "Speech evaluation unavailable — skip or retry"

**Given** `get_speech_provider()` is called
**Then** it is always resolved via FastAPI `Depends()` — no direct provider instantiation outside `services/`

pytest coverage: Whisper fallback when Azure not configured, Azure used when configured, evaluation returns correct SyllableResult shape, timeout → specific error, empty audio → 422.

### Story 4.2: SyllableFeedback Component

As a user,
I want to see my pronunciation broken down syllable-by-syllable — correct syllables in emerald and wrong syllables highlighted in amber — alongside a specific correction I can act on,
So that I know exactly which part of the word to fix rather than just "wrong/right."

**Acceptance Criteria:**

**Given** `SyllableFeedback` renders in `awaiting` state
**When** it displays
**Then** all syllable chips are `neutral` (grey), the mic button is ready, and no correction text is shown

**Given** evaluation is in progress
**When** `SyllableFeedback` is in `evaluating` state
**Then** all chips pulse with a pending animation
**And** an "Evaluating..." label replaces the correction text area

**Given** evaluation returns all syllables correct
**When** `SyllableFeedback` transitions to `result-correct`
**Then** all chips show `correct` state (subtle emerald tint)
**And** the component header has a subtle emerald background tint

**Given** evaluation returns one or more syllables incorrect
**When** `SyllableFeedback` transitions to `result-partial`
**Then** correct chips show emerald tint; wrong chips show amber-400 highlight with amber border
**And** the correction text block shows a specific explanation (e.g., "a-gua-CA-te — stress on third syllable")
**And** a "Try again" button is the primary action; "Move on" is secondary

**Given** local Whisper is used as the fallback during evaluation
**When** `SyllableFeedback` is in `fallback-notice` state
**Then** an amber badge reads "Using local Whisper · ~3s" — visible but not alarming

**Given** any chip renders
**Then** it has `aria-label="{syllable} — {correct|incorrect}"` so screen readers announce each syllable's result
**And** the correction sentence is in an `aria-live="assertive"` region so it is announced on result

**Given** the correction shows an incorrect syllable
**Then** the error is conveyed by both color AND text — never color alone

Vitest + RTL tests must cover all 5 component states, all per-chip states, aria-live announcement of correction sentence, and keyboard navigation between "Try again" and "Move on."

### Story 4.3: Speak Mode Practice Session

As a user,
I want to practice in speak mode with a full-viewport layout dedicated to pronunciation — mic tap-to-record, SyllableFeedback inline, one-tap retry, keyboard skip if I have no mic — so that each session feels like a focused pronunciation drill.

**Acceptance Criteria:**

**Given** speak mode is selected for a practice session
**When** the session starts
**Then** the D5 full-viewport layout activates: sidebar hidden, card centered vertically, mic button centered below, SyllableFeedback area reserved above the mic

**Given** it is my first time using speak mode
**When** the session starts
**Then** a one-time tooltip appears: "Tap mic to record · release to evaluate"
**And** the tooltip does not appear on subsequent sessions

**Given** I tap/click the mic button
**When** recording begins
**Then** the mic button pulses to indicate recording
**And** recording state is announced via `aria-label="Recording — release to evaluate"`

**Given** I release the mic button
**When** audio is submitted to `POST /practice/cards/{card_id}/speak`
**Then** `SyllableFeedback` transitions to `evaluating` state
**And** if Azure Speech is unavailable, the `fallback-notice` state shows "Using local Whisper · ~3s"

**Given** evaluation returns correct pronunciation
**When** `SyllableFeedback` shows `result-correct`
**Then** `POST /practice/cards/{card_id}/rate` is called automatically with rating=3 (Good)
**And** the next card loads after a brief 1-second pause

**Given** evaluation returns incorrect pronunciation
**When** `SyllableFeedback` shows `result-partial`
**Then** the "Try again" button is the primary focus target
**And** pressing R starts a new recording
**And** pressing Tab then Enter on "Move on" rates as Again (1) and advances

**Given** I want to skip a card (no mic available)
**When** I press S or Tab to the "Skip" button
**Then** the card is skipped without rating and the next card loads
**And** no microphone access is required for this action

**Given** the session ends
**When** the last card resolves
**Then** `SessionSummary` shows results including speak-mode-specific stats (first-attempt success rate)
**And** the D2 home layout restores

Playwright E2E: first-use tooltip → record → correct → auto-advance; record → wrong → retry → correct → advance; skip via keyboard without mic.

## Epic 5: CEFR Learner Intelligence

User can see their estimated CEFR level (A1–C2), understand exactly what they demonstrate confidently, and see the specific vocabulary and grammar gaps separating them from the next level.

### Story 5.1: CEFR Profile Computation Engine

As a user,
I want the app to continuously analyze my vocabulary breadth, grammar forms, practice performance, and recall history to estimate where I sit on the A1–C2 scale,
So that I have an authoritative, data-driven picture of my language proficiency — not a self-reported guess.

**Acceptance Criteria:**

**Given** the `reviews` table has accumulated records
**When** `core/cefr.py` computes the knowledge profile
**Then** it aggregates four dimensions from the review log:
- **Vocabulary breadth:** number of unique cards with `state=Review` or `state=Mature`
- **Grammar forms coverage:** count of grammatical form types encountered across all saved cards
- **Practice performance:** recall rate by card type (word, sentence, collocation) over the last 30 days
- **Active vs. passive recall:** ratio of cards practiced in write/speak mode versus self-assess-only

**Given** the four dimensions are computed
**When** `core/cefr.py` maps the profile to a CEFR level
**Then** a heuristic mapping (vocabulary thresholds + grammar coverage) assigns A1 through C2
**And** the assigned level is cached so subsequent `GET /cefr/profile` calls return within 500ms without recomputing

**Given** the review log has fewer than 10 cards reviewed
**When** the CEFR profile is requested
**Then** the response returns `level: null` with an explanation: "Practice more cards to generate your profile"
**And** no invalid level estimate is shown

**Given** a `POST /practice/cards/{card_id}/rate` completes
**When** the CEFR cache is invalidated
**Then** the next `GET /cefr/profile` call triggers a fresh computation
**And** the invalidation is async and non-blocking — the rating response is not delayed

**Given** `GET /cefr/profile` is called when the review log has 1000+ rows
**When** it responds
**Then** it returns within 500ms — aggregation uses indexed queries on `reviews.card_id` and `reviews.reviewed_at`

pytest coverage: correct level assignment for seeded review data at A1/B1/C1 thresholds, null level when < 10 reviews, cache invalidation after new rating, large review log within 500ms SLA.

### Story 5.2: CEFR Level Display & Knowledge Profile Breakdown

As a user,
I want to see my current CEFR level with a rich explanation of what I demonstrate confidently and exactly what gaps separate me from the next level — plus a breakdown by vocabulary size, grammar coverage, pronunciation accuracy, and recall type — so that I know precisely what to focus on.

**Acceptance Criteria:**

**Given** I navigate to the Progress screen
**When** `GET /cefr/profile` returns a profile with a valid level
**Then** `CefrProfile` renders my current estimated level (e.g., "B1") prominently at `text-2xl`
**And** a one-line summary: "You have demonstrated solid B1 vocabulary and grammar coverage"

**Given** the CEFR level display renders
**When** the explanatory section loads
**Then** it shows three sub-sections:
1. **What you demonstrate confidently:** specific vocabulary ranges and grammar structures the data confirms
2. **Areas for development:** grammar forms or card types with low recall rates
3. **Gap to the next level:** concrete targets (e.g., "B2 requires ~1200 active words and subjunctive mood coverage — you have 680 words and 0 subjunctive cards")

**Given** the knowledge profile breakdown renders
**When** I view the four category rows
**Then** each shows a label, current value, and a progress indicator:
- **Vocabulary size:** total cards in `Review` or `Mature` FSRS state
- **Grammar coverage:** number of distinct grammar form types encountered
- **Pronunciation accuracy:** first-attempt success rate in speak mode
- **Active vs. passive recall:** % of cards practiced in write or speak mode vs. self-assess only

**Given** the user has no speak mode data
**When** the pronunciation accuracy row renders
**Then** it shows "No speak mode data yet" — not zero, not an error

**Given** `GET /cefr/profile` returns `level: null`
**When** `CefrProfile` renders
**Then** it shows: "Keep practicing — your profile will appear after you review at least 10 cards"
**And** a prominent link to the practice queue is shown

**Given** the CEFR profile section is on the Progress screen
**Then** it renders below the `ProgressDashboard` from Story 3.5 in the same route — no separate navigation required

Vitest + RTL tests: null level state, valid level with all three explanatory sections, all four breakdown rows, pronunciation row with no data.
Playwright E2E: navigate to Progress → CEFR section renders with correct level for seeded review data.
