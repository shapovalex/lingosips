# Story 1.7: Card Creation API & SSE Streaming

Status: done

## Story

As a user,
I want to submit a word or phrase and receive a complete AI-generated card with translation, grammatical forms, and example sentences streamed field-by-field,
so that I can build vocabulary in seconds with real-time visual feedback.

## Acceptance Criteria

1. **Given** I submit a valid word or phrase to `POST /cards/stream`
   **When** the AI pipeline runs
   **Then** an SSE stream emits `field_update` events in order: translation → gender/article/forms → example sentences
   **And** a final `complete` event is emitted when all fields are populated
   **And** the card is persisted to the `cards` table in SQLite

2. **Given** the AI returns content
   **When** the response is parsed
   **Then** `core/safety.py` filters content through the keyword blocklist before fields are streamed
   **And** any blocked content triggers an `error` SSE event with a specific message

3. **Given** I submit an empty or whitespace-only string
   **When** the endpoint processes the request
   **Then** a `422 Unprocessable Entity` response is returned with field-level detail in RFC 7807 format

4. **Given** the LLM times out mid-stream
   **When** the timeout occurs
   **Then** an SSE `error` event is emitted: `{"message": "Local Qwen timeout after 10s"}`
   **And** the stream closes gracefully — no crash, no hanging connection

5. **Given** any SSE event is emitted
   **Then** the envelope is exactly: `event: {event_type}\ndata: {json_payload}\n\n`
   **And** the JSON payload uses snake_case field names throughout

6. **Given** a card is created
   **When** it is first saved
   **Then** FSRS initial state is set on the card: `stability=0`, `difficulty=0`, `fsrs_state="New"`, `due=now`, `reps=0`, `lapses=0`, `last_review=null`
   **And** the card appears immediately in `GET /practice/queue`

7. **Given** the LLM returns a response and the card is ready to stream
   **When** the SSE stream starts
   **Then** when using OpenRouter: the first `field_update` event is emitted within 500ms of the initial request (NFR4 cloud SLA)
   **And** when using local Qwen: the first `field_update` event is emitted within 2 seconds of the initial request (NFR4 local SLA)

## Tasks / Subtasks

> **TDD MANDATORY**: Write failing tests for each task BEFORE writing implementation code. A story without passing tests is not done.

---

- [x] **T1: Write failing tests for `core/safety.py`** (AC: 2) — create `tests/core/test_safety.py` BEFORE implementing safety.py
  - [x] T1.1: `tests/core/__init__.py` already exists — DO NOT recreate
  - [x] T1.2: Write `TestSafetyFilter` class with `@pytest.mark.anyio` — covers: safe text returns True, blocked term returns False, case-insensitive match, empty text is safe, partial word match, check_text returns (is_safe, blocked_term|None) tuple

- [x] **T2: Implement `core/safety.py` to make T1 pass** (AC: 2)
  - [x] T2.1: Define `BLOCKED_TERMS: list[str]` — a minimal MVP keyword blocklist (see Dev Notes §SafetyFilter)
  - [x] T2.2: Implement `check_text(text: str) → tuple[bool, str | None]` — returns `(True, None)` if safe; `(False, matched_term)` if blocked
  - [x] T2.3: Case-insensitive matching only — no regex needed for MVP
  - [x] T2.4: `check_text("")` returns `(True, None)` — empty string is safe

- [x] **T3: Write failing tests for `core/cards.py`** (AC: 1, 2, 4, 5, 6) — create `tests/core/test_cards.py` BEFORE implementing cards.py
  - [x] T3.1: `TestParseCardResponse` — valid JSON, JSON in markdown code block, invalid JSON raises ValueError, missing fields get defaults
  - [x] T3.2: `TestSseEvent` — `_sse_event()` produces exact `event: X\ndata: Y\n\n` format, snake_case keys preserved
  - [x] T3.3: `TestCreateCardStream` — use `AsyncMock` for LLM; collect yielded strings; verify field_update events emitted in order; verify complete event with card_id; verify card persisted in DB

- [x] **T4: Implement `core/cards.py` to make T3 pass** (AC: 1, 2, 4, 5, 6)
  - [x] T4.1: Define `CardCreateRequest` Pydantic model with `target_word: str = Field(min_length=1)` and whitespace-stripping validator (see Dev Notes §CardCreateRequest)
  - [x] T4.2: Implement `_sse_event(event_type: str, data: dict) → str` helper (see Dev Notes §SSEFormat)
  - [x] T4.3: Implement `_parse_llm_response(raw: str) → dict` — strip markdown code fences, find outermost `{...}`, `json.loads()`, raise `ValueError` on failure (see Dev Notes §ParseLLMResponse)
  - [x] T4.4: Implement `_build_messages(target_word: str, target_language: str) → list[LLMMessage]` — system prompt + user message (see Dev Notes §LLMPrompt)
  - [x] T4.5: Implement `create_card_stream(request, llm, session, target_language) → AsyncGenerator[str, None]` (see Dev Notes §CreateCardStream)
  - [x] T4.6: Wrap LLM `complete()` in `asyncio.wait_for(..., timeout=10.0)` — `TimeoutError` → emit `error` event `{"message": "Local Qwen timeout after 10s"}` and return
  - [x] T4.7: Apply `core.safety.check_text()` to each text field before emitting `field_update` — blocked field → emit `error` event and return (no card persisted)
  - [x] T4.8: Persist card using `session.add(card)` + `await session.commit()` + `await session.refresh(card)` — card gets its integer `id`
  - [x] T4.9: Emit `complete` event with `{"card_id": card.id}` after successful persist
  - [x] T4.10: Wrap entire generator in `try/except Exception` — unknown errors emit `error` event (never raise through to the transport)

- [x] **T5: Write failing tests for `api/cards.py`** (AC: 1, 2, 3, 4, 5, 6) — create `tests/api/test_cards.py` BEFORE implementing
  - [x] T5.1: `TestPostCardsStream` — see Dev Notes §TestCardsAPI for the full required test list
  - [x] T5.2: Add `mock_llm_provider` fixture to `tests/api/test_cards.py` (or `conftest.py`) — returns pre-built JSON response string (see Dev Notes §MockLLMFixture)
  - [x] T5.3: Add SSE parsing helper `parse_sse_events(content: bytes) → list[dict]` to test file (see Dev Notes §SSEParsingHelper)

- [x] **T6: Implement `api/cards.py` to make T5 pass** (AC: 1, 2, 3, 4, 5, 6)
  - [x] T6.1: Create `src/lingosips/api/cards.py` with `router = APIRouter()`
  - [x] T6.2: `POST /stream` endpoint using `StreamingResponse` with `media_type="text/event-stream"` and headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`
  - [x] T6.3: Fetch `target_language` from Settings via `core.settings.get_or_create_settings(session)` BEFORE starting the stream — pass it into `core.cards.create_card_stream()`
  - [x] T6.4: Override `get_llm_provider` in test via `app.dependency_overrides` (see Dev Notes §MockLLMFixture)
  - [x] T6.5: Router handles `CardCreateRequest` validated at the Pydantic layer — empty/whitespace → 422 before generator starts

- [x] **T7: Write failing tests for `api/practice.py`** (AC: 6) — create `tests/api/test_practice.py` BEFORE implementing
  - [x] T7.1: `TestGetPracticeQueue` — due cards returned, no-due-cards returns `[]`, future-due cards excluded, response shape has required fields

- [x] **T8: Implement `api/practice.py` — minimal `GET /practice/queue`** (AC: 6)
  - [x] T8.1: Create `src/lingosips/api/practice.py` with `router = APIRouter()`
  - [x] T8.2: `GET /queue` — query `Card` table for all rows where `Card.due <= datetime.now(UTC)` ordered by `Card.due.asc()` — use `session.execute(select(...))` pattern
  - [x] T8.3: Response model `QueueCard` — at minimum: `id`, `target_word`, `translation`, `target_language`, `due`, `fsrs_state`, `stability`, `difficulty`, `reps`, `lapses`
  - [x] T8.4: Filter by `active_target_language` from Settings (call `get_or_create_settings`)
  - [x] T8.5: Empty result → return `[]` (never `null`)

- [x] **T9: Update `api/app.py` — register new routers** (AC: 1, 6)
  - [x] T9.1: Import and register `cards_router` at prefix `/cards`
  - [x] T9.2: Import and register `practice_router` at prefix `/practice`
  - [x] T9.3: Keep existing `settings_router` and `models_router` registrations intact — DO NOT remove them

- [x] **T10: Ruff compliance check**
  - [x] T10.1: `uv run ruff check --fix src/lingosips/api/cards.py src/lingosips/api/practice.py src/lingosips/core/cards.py src/lingosips/core/safety.py tests/api/test_cards.py tests/api/test_practice.py tests/core/test_safety.py tests/core/test_cards.py`
  - [x] T10.2: Import order: `stdlib` (`asyncio`, `collections.abc`, `datetime`, `json`) → `third-party` (`fastapi`, `pydantic`, `sqlalchemy`, `structlog`) → `local` (`lingosips.*`)
  - [x] T10.3: `AsyncGenerator` and `AsyncIterator` from `collections.abc`, NOT `typing`
  - [x] T10.4: No `asyncio.get_event_loop()` — use `asyncio.get_running_loop()` only

---

## Dev Notes

### ⚠️ DO NOT Recreate — Already Exists

| Existing | Location | What it provides |
|---|---|---|
| `db/models.py` | `src/lingosips/db/models.py` | `Card` table with ALL FSRS columns already defined — do NOT add schema |
| `services/registry.py` | `src/lingosips/services/registry.py` | `get_llm_provider()` already implemented — import via `Depends()` |
| `services/registry.py` | same | `get_speech_provider()` already implemented — NOT needed in this story (TTS is Story 1.8) |
| `services/credentials.py` | `src/lingosips/services/credentials.py` | `get_credential()`, all key constants — import only |
| `core/settings.py` | `src/lingosips/core/settings.py` | `get_or_create_settings(session)` — call this to get active language |
| `api/app.py` | `src/lingosips/api/app.py` | EXISTS — UPDATE by adding router registrations |
| `tests/conftest.py` | `tests/conftest.py` | `client`, `session`, `test_engine` fixtures — use these in new tests |
| `tests/api/__init__.py` | already exists | DO NOT recreate |
| `tests/core/__init__.py` | already exists (test_logging.py is there) | DO NOT recreate |

**CRITICAL**: `core/cards.py`, `core/safety.py`, `api/cards.py`, `api/practice.py` do NOT exist — create them new.

**CRITICAL**: `get_speech_provider()` is NOT needed in Story 1.7 — TTS/audio is Story 1.8. Do not inject speech provider into the card creation endpoint.

**RESOLVED DEFERRED**: Story 1.5 deferred: "AC4 `Depends(get_llm_provider)` not wired to any router". **This story resolves it** — `api/cards.py` is the first router to use `Depends(get_llm_provider)`.

---

### §CardCreateRequest — Pydantic Model with Whitespace Validator

```python
# src/lingosips/core/cards.py (or a shared request models file)
from pydantic import BaseModel, Field, field_validator


class CardCreateRequest(BaseModel):
    target_word: str = Field(min_length=1, description="Word or phrase to create a card for")

    @field_validator("target_word")
    @classmethod
    def not_whitespace_only(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be whitespace only")
        return stripped  # strip leading/trailing whitespace
```

**Why `@field_validator` and `@classmethod`**: Pydantic v2 requires both decorators. `field_validator("target_word")` runs AFTER the type check, so the value is guaranteed to be a string. The returned value (`stripped`) replaces the original — callers always get a trimmed word.

**Validation behaviour**: FastAPI converts Pydantic `ValueError` to a `422 Unprocessable Entity` with field-level detail automatically — no custom exception handler needed for this.

---

### §SSEFormat — Standard SSE Envelope

All SSE events across ALL channels must use this exact helper. Copy it verbatim:

```python
# src/lingosips/core/cards.py

import json


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event string.

    Exact envelope required by the architecture spec and frontend SSE parser:
        event: {event_type}
        data: {json_payload}

    (blank line terminates the event)
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
```

**Event types for this story**: `field_update` | `complete` | `error`

**Event payloads**:
```python
# field_update:
{"field": "translation", "value": "melancholic"}
{"field": "forms", "value": {"gender": "masculine", "article": "el", "plural": "melancólicos", "conjugations": {}}}
{"field": "example_sentences", "value": ["Tenía un aire melancólico.", "Era un día melancólico."]}

# complete:
{"card_id": 42}

# error:
{"message": "Local Qwen timeout after 10s"}
{"message": "Content blocked by safety filter in field: translation"}
{"message": "Failed to parse LLM response"}
```

**CRITICAL**: All JSON keys are **snake_case** — never camelCase in data payloads.

---

### §LLMPrompt — Card Generation Prompt

```python
# src/lingosips/core/cards.py

from lingosips.services.llm.base import LLMMessage

CARD_SYSTEM_PROMPT = """\
You are a language learning assistant. Given a word or phrase in a target language, \
return ONLY a JSON object with these exact fields. No markdown, no explanation, no extra text.

{
  "translation": "English translation or meaning",
  "forms": {
    "gender": "masculine | feminine | neuter | null",
    "article": "definite article or null",
    "plural": "plural form or null",
    "conjugations": {}
  },
  "example_sentences": ["Example sentence 1 using the word.", "Example sentence 2."]
}

Rules:
- Return ONLY the JSON object
- example_sentences must have exactly 2 sentences
- For verbs, populate conjugations: {"infinitive": "...", "present_1s": "...", "present_3s": "..."}
- For nouns with gender, populate gender and article
- For other word types, set gender/article/plural to null
- Sentences must be in the target language, not English
"""


def _build_messages(target_word: str, target_language: str) -> list[LLMMessage]:
    """Build OpenAI-compatible messages for card generation."""
    return [
        {"role": "system", "content": CARD_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Target language: {target_language}\nWord/phrase: {target_word}",
        },
    ]
```

---

### §ParseLLMResponse — Handle LLM Output Quirks

LLMs often wrap JSON in markdown code fences. This parser handles the common cases:

```python
# src/lingosips/core/cards.py

import json


def _parse_llm_response(raw: str) -> dict:
    """Extract and parse JSON from LLM response.

    Handles:
    - Clean JSON: {"translation": "..."}
    - Markdown fenced: ```json\n{"translation": "..."}\n```
    - Extra preamble/trailing text around JSON object

    Raises ValueError if no valid JSON object found.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Find closing fence
        end_fence = next(
            (i for i, line in enumerate(lines[1:], 1) if line.strip() == "```"),
            len(lines),
        )
        text = "\n".join(lines[1:end_fence]).strip()

    # Find outermost JSON object (handles leading/trailing text)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object found in LLM response (got: {raw[:100]!r})")

    try:
        parsed = json.loads(text[start:end])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in LLM response: {exc}") from exc

    # Apply defaults for missing fields
    return {
        "translation": parsed.get("translation", ""),
        "forms": parsed.get("forms", {"gender": None, "article": None, "plural": None, "conjugations": {}}),
        "example_sentences": parsed.get("example_sentences", []),
    }
```

---

### §CreateCardStream — Core Generator Implementation

```python
# src/lingosips/core/cards.py

import asyncio
import json
import structlog
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import safety
from lingosips.db.models import Card
from lingosips.services.llm.base import AbstractLLMProvider

logger = structlog.get_logger(__name__)


async def create_card_stream(
    request: "CardCreateRequest",
    llm: AbstractLLMProvider,
    session: AsyncSession,
    target_language: str,
) -> AsyncGenerator[str, None]:
    """Card creation pipeline — yields SSE-formatted event strings.

    Sequence:
    1. Call LLM.complete() with timeout → yields field_update events
    2. Apply safety filter to each field
    3. Persist card to DB with FSRS initial state
    4. Yield complete event with card_id

    On any failure: yield error event and return (never raise).
    """
    try:
        # Step 1: Call LLM with 10s timeout (NFR4 — local Qwen SLA)
        messages = _build_messages(request.target_word, target_language)
        try:
            raw_response = await asyncio.wait_for(
                llm.complete(messages, max_tokens=512),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning("cards.llm_timeout", target_word=request.target_word)
            yield _sse_event("error", {"message": "Local Qwen timeout after 10s"})
            return
        except Exception as exc:
            logger.error("cards.llm_error", exc_type=type(exc).__name__)
            yield _sse_event("error", {"message": f"LLM error: {type(exc).__name__}"})
            return

        # Step 2: Parse LLM response
        try:
            card_data = _parse_llm_response(raw_response)
        except ValueError:
            logger.error("cards.parse_failed", raw_preview=raw_response[:100])
            yield _sse_event("error", {"message": "Failed to parse LLM response"})
            return

        # Step 3: Safety filter + emit field_update events (in order per spec)
        fields_to_emit: list[tuple[str, str | dict | list]] = [
            ("translation", card_data["translation"]),
            ("forms", card_data["forms"]),
            ("example_sentences", card_data["example_sentences"]),
        ]

        for field_name, value in fields_to_emit:
            text_for_check = value if isinstance(value, str) else json.dumps(value)
            is_safe, blocked_term = safety.check_text(text_for_check)
            if not is_safe:
                logger.warning("cards.safety_blocked", field=field_name, term=blocked_term)
                yield _sse_event(
                    "error",
                    {"message": f"Content blocked by safety filter in field: {field_name}"},
                )
                return
            yield _sse_event("field_update", {"field": field_name, "value": value})

        # Step 4: Persist card — FSRS initial state is all defaults from Card model
        card = Card(
            target_word=request.target_word,
            translation=card_data["translation"],
            forms=json.dumps(card_data["forms"]),
            example_sentences=json.dumps(card_data["example_sentences"]),
            target_language=target_language,
            # FSRS columns: all default values from db/models.py are correct
            # stability=0.0, difficulty=0.0, fsrs_state="New", due=now, reps=0, lapses=0
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        logger.info("cards.created", card_id=card.id, target_word=request.target_word)
        yield _sse_event("complete", {"card_id": card.id})

    except Exception as exc:
        # Catch-all: never let exceptions escape the generator (would corrupt SSE stream)
        logger.error("cards.unexpected_error", exc_type=type(exc).__name__)
        yield _sse_event("error", {"message": "Unexpected error during card creation"})
```

---

### §CardsRouter — FastAPI SSE Endpoint

```python
# src/lingosips/api/cards.py

from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import cards as core_cards
from lingosips.core import settings as core_settings
from lingosips.core.cards import CardCreateRequest
from lingosips.db.session import get_session
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.registry import get_llm_provider

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/stream")
async def create_card_stream(
    request: CardCreateRequest,
    llm: AbstractLLMProvider = Depends(get_llm_provider),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream AI-generated card fields as SSE events.

    422 is returned by FastAPI BEFORE this function runs if target_word is
    empty or whitespace-only — the Pydantic validator in CardCreateRequest handles this.
    """
    # Fetch active target language from settings — pass as parameter to core (not fetched in core)
    settings = await core_settings.get_or_create_settings(session)
    target_language = settings.active_target_language

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in core_cards.create_card_stream(
            request=request,
            llm=llm,
            session=session,
            target_language=target_language,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
```

**CRITICAL**: The 422 validation for `target_word` is handled entirely by Pydantic BEFORE the endpoint function runs. No manual validation is needed inside the endpoint.

---

### §PracticeQueueEndpoint — Minimal `GET /practice/queue`

```python
# src/lingosips/api/practice.py

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import settings as core_settings
from lingosips.db.models import Card
from lingosips.db.session import get_session

router = APIRouter()
logger = structlog.get_logger(__name__)


class QueueCard(BaseModel):
    id: int
    target_word: str
    translation: str | None
    target_language: str
    due: datetime
    fsrs_state: str
    stability: float
    difficulty: float
    reps: int
    lapses: int

    model_config = {"from_attributes": True}


@router.get("/queue", response_model=list[QueueCard])
async def get_practice_queue(
    session: AsyncSession = Depends(get_session),
) -> list[QueueCard]:
    """Return all due cards ordered by due date ascending.

    Filters by active_target_language from Settings.
    Returns [] (never null) when no cards are due.
    Full FSRS state per card + session management added in Story 3.1.
    """
    settings = await core_settings.get_or_create_settings(session)
    active_lang = settings.active_target_language
    now = datetime.now(UTC)

    result = await session.execute(
        select(Card)
        .where(Card.due <= now, Card.target_language == active_lang)
        .order_by(Card.due.asc())
    )
    cards = result.scalars().all()
    return [QueueCard.model_validate(c) for c in cards]
```

**Note on `datetime.now(UTC)`**: The `Card.due` column stores UTC-aware datetimes (uses `_now()` factory from `db/models.py` which calls `datetime.now(UTC)`). The comparison must also use UTC-aware datetime. Never use `datetime.utcnow()` — it returns a naive datetime.

**Note on `session.execute(select(...))` vs `session.exec(...)`**: This project uses SQLAlchemy's `AsyncSession` directly (not SQLModel's `Session`). Always use `session.execute(select(...))` and `.scalars().all()`. **Never** use `session.exec()`.

---

### §AppRegistration — Update `api/app.py`

In `create_app()`, add the new routers alongside the existing ones. The order matters — health endpoint first, then domain routers, then static mount last:

```python
# INSIDE create_app() in src/lingosips/api/app.py
# ADD these imports alongside existing ones:
from lingosips.api.cards import router as cards_router
from lingosips.api.practice import router as practice_router

# ADD these registrations alongside existing include_router calls:
application.include_router(cards_router, prefix="/cards", tags=["cards"])
application.include_router(practice_router, prefix="/practice", tags=["practice"])
```

**CRITICAL**: Keep the existing `settings_router` and `models_router` registrations — do NOT remove or reorder them. The static mount MUST remain last.

---

### §SafetyFilter — Implementation Pattern

```python
# src/lingosips/core/safety.py

"""Content safety filter for AI-generated card fields.

MVP implementation: keyword/pattern blocklist only.
No external API, no ML model — adequate safety posture for a single-user
local app where the user controls which AI service is called.
Post-MVP: replace with local content moderation model.
"""

import structlog

logger = structlog.get_logger(__name__)

# MVP keyword blocklist — lowercase for case-insensitive matching
BLOCKED_TERMS: list[str] = [
    # Add words here as needed for MVP
    # Keep this list minimal — false positives break card creation
]


def check_text(text: str) -> tuple[bool, str | None]:
    """Check whether text is safe to display.

    Returns:
        (True, None) if text passes the safety filter
        (False, matched_term) if text contains a blocked term

    Empty text is always safe (returns True, None).
    Matching is case-insensitive.
    """
    if not text:
        return True, None

    lower_text = text.lower()
    for term in BLOCKED_TERMS:
        if term in lower_text:
            logger.warning("safety.blocked_term_detected", term=term)
            return False, term

    return True, None
```

**Why BLOCKED_TERMS is empty for MVP**: The architecture explicitly states "Keyword/pattern blocklist for MVP — no external API or extra model required." The list can be populated without code changes. Tests verify the mechanism works, not specific terms.

---

### §MockLLMFixture — Test Setup

Add this fixture to `tests/api/test_cards.py`. **Critical**: use `app.dependency_overrides.pop()` (NOT `.clear()`) to remove only the LLM override — `.clear()` would also remove the session override set by the `client` fixture from `conftest.py`.

```python
# In tests/api/test_cards.py

import json
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from lingosips.api.app import app
from lingosips.services.registry import get_llm_provider

MOCK_LLM_JSON_RESPONSE = json.dumps({
    "translation": "melancholic",
    "forms": {
        "gender": "masculine",
        "article": "el",
        "plural": "melancólicos",
        "conjugations": {},
    },
    "example_sentences": [
        "Tenía un aire melancólico.",
        "Era un día melancólico.",
    ],
})


@pytest.fixture
async def mock_llm_provider():
    """Override get_llm_provider with a mock that returns MOCK_LLM_JSON_RESPONSE.

    Uses .pop() at teardown — NOT .clear() — to avoid removing the session
    override set by the conftest client fixture. The client fixture calls
    .clear() at its own teardown; this fixture only manages its own override.
    """
    from lingosips.services.llm.base import AbstractLLMProvider

    mock = AsyncMock(spec=AbstractLLMProvider)
    mock.complete = AsyncMock(return_value=MOCK_LLM_JSON_RESPONSE)
    mock.provider_name = "MockLLM"
    mock.model_name = "mock-model"

    app.dependency_overrides[get_llm_provider] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_llm_provider, None)  # NOT .clear()
```

**Fixture lifecycle**: `conftest.client` fixture sets `get_session` override and clears ALL overrides at teardown. `mock_llm_provider` sets only `get_llm_provider` and removes only that key at teardown. Both coexist correctly during the test.

---

### §SSEParsingHelper — Test Utility

Add this helper to `tests/api/test_cards.py`:

```python
def parse_sse_events(content: bytes) -> list[dict]:
    """Parse a raw SSE byte stream into a list of event dicts.

    Returns list of {"event": event_type, "data": parsed_json} dicts.
    Skips blank/comment lines per SSE spec.
    """
    events = []
    raw = content.decode("utf-8")
    for chunk in raw.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        event_type = "message"
        data_str = ""
        for line in chunk.splitlines():
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:].strip()
        if data_str:
            try:
                events.append({"event": event_type, "data": json.loads(data_str)})
            except json.JSONDecodeError:
                events.append({"event": event_type, "data": data_str})
    return events
```

---

### §TestCardsAPI — Required Test Cases

```python
@pytest.mark.anyio
class TestPostCardsStream:
    """Tests for POST /cards/stream (AC: 1, 2, 3, 4, 5, 6)."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine):
        """Clean card table before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_success_emits_field_update_events_in_order(
        self, client: AsyncClient, mock_llm_provider
    ) -> None:
        """AC1: field_update events emitted in order: translation → forms → example_sentences."""
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        assert response.status_code == 200
        events = parse_sse_events(response.content)
        field_updates = [e for e in events if e["event"] == "field_update"]
        assert len(field_updates) >= 3
        assert field_updates[0]["data"]["field"] == "translation"
        assert field_updates[1]["data"]["field"] == "forms"
        assert field_updates[2]["data"]["field"] == "example_sentences"

    async def test_success_emits_complete_event_with_card_id(
        self, client: AsyncClient, mock_llm_provider
    ) -> None:
        """AC1: final complete event contains integer card_id."""
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        events = parse_sse_events(response.content)
        complete_events = [e for e in events if e["event"] == "complete"]
        assert len(complete_events) == 1
        assert isinstance(complete_events[0]["data"]["card_id"], int)

    async def test_success_persists_card_to_db(
        self, client: AsyncClient, mock_llm_provider, session
    ) -> None:
        """AC1: card is persisted to the cards table in SQLite."""
        from sqlalchemy import select
        from lingosips.db.models import Card
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        events = parse_sse_events(response.content)
        card_id = next(e["data"]["card_id"] for e in events if e["event"] == "complete")
        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        assert card is not None
        assert card.target_word == "melancólico"

    async def test_success_card_has_fsrs_initial_state(
        self, client: AsyncClient, mock_llm_provider, session
    ) -> None:
        """AC6: FSRS initial state: stability=0, difficulty=0, fsrs_state=New, reps=0, lapses=0."""
        from sqlalchemy import select
        from lingosips.db.models import Card
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        events = parse_sse_events(response.content)
        card_id = next(e["data"]["card_id"] for e in events if e["event"] == "complete")
        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one()
        assert card.stability == 0.0
        assert card.difficulty == 0.0
        assert card.fsrs_state == "New"
        assert card.reps == 0
        assert card.lapses == 0
        assert card.last_review is None

    async def test_missing_target_word_returns_422(self, client: AsyncClient) -> None:
        """AC3: missing target_word → 422 Unprocessable Entity."""
        response = await client.post("/cards/stream", json={})
        assert response.status_code == 422

    async def test_empty_target_word_returns_422(self, client: AsyncClient) -> None:
        """AC3: empty string → 422."""
        response = await client.post("/cards/stream", json={"target_word": ""})
        assert response.status_code == 422

    async def test_whitespace_only_target_word_returns_422(self, client: AsyncClient) -> None:
        """AC3: whitespace-only string → 422."""
        response = await client.post("/cards/stream", json={"target_word": "   "})
        assert response.status_code == 422

    async def test_llm_timeout_emits_error_event(self, client: AsyncClient) -> None:
        """AC4: LLM timeout → error SSE event with exact message."""
        import asyncio

        mock = AsyncMock()
        mock.complete = AsyncMock(side_effect=asyncio.TimeoutError())
        app.dependency_overrides[get_llm_provider] = lambda: mock

        try:
            response = await client.post("/cards/stream", json={"target_word": "test"})
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)  # NOT .clear()

        events = parse_sse_events(response.content)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["message"] == "Local Qwen timeout after 10s"

    async def test_safety_filter_blocks_content_emits_error(
        self, client: AsyncClient
    ) -> None:
        """AC2: blocked content → error event emitted, no card persisted."""
        from unittest.mock import patch
        mock = AsyncMock()
        mock.complete = AsyncMock(return_value=MOCK_LLM_JSON_RESPONSE)
        app.dependency_overrides[get_llm_provider] = lambda: mock

        try:
            with patch("lingosips.core.cards.safety.check_text", return_value=(False, "blocked-term")):
                response = await client.post("/cards/stream", json={"target_word": "test"})
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)  # NOT .clear()

        events = parse_sse_events(response.content)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "safety filter" in error_events[0]["data"]["message"]

    async def test_sse_response_content_type_is_event_stream(
        self, client: AsyncClient, mock_llm_provider
    ) -> None:
        """AC5: Content-Type must be text/event-stream."""
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        assert "text/event-stream" in response.headers.get("content-type", "")

    async def test_card_appears_in_practice_queue_after_creation(
        self, client: AsyncClient, mock_llm_provider
    ) -> None:
        """AC6: newly created card with due=now appears immediately in GET /practice/queue."""
        create_resp = await client.post("/cards/stream", json={"target_word": "melancólico"})
        create_events = parse_sse_events(create_resp.content)
        card_id = next(e["data"]["card_id"] for e in create_events if e["event"] == "complete")

        queue_resp = await client.get("/practice/queue")
        assert queue_resp.status_code == 200
        queue_ids = [c["id"] for c in queue_resp.json()]
        assert card_id in queue_ids
```

---

### §TestPracticeQueue — Required Test Cases

```python
# tests/api/test_practice.py
import pytest
from datetime import UTC, datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import text


@pytest.mark.anyio
class TestGetPracticeQueue:
    """Tests for GET /practice/queue (AC: 6)."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_returns_empty_list_when_no_due_cards(
        self, client: AsyncClient
    ) -> None:
        """Empty DB → 200 with []."""
        response = await client.get("/practice/queue")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_due_cards_ordered_by_due_date(
        self, client: AsyncClient, session
    ) -> None:
        """Due cards returned, ordered by due date ascending."""
        from lingosips.db.models import Card, Settings
        # Set active language
        settings = Settings(active_target_language="es")
        session.add(settings)
        # Add two cards with different due dates
        now = datetime.now(UTC)
        card1 = Card(target_word="word1", target_language="es", due=now - timedelta(hours=2))
        card2 = Card(target_word="word2", target_language="es", due=now - timedelta(hours=1))
        session.add(card1)
        session.add(card2)
        await session.commit()

        response = await client.get("/practice/queue")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["target_word"] == "word1"  # earlier due date first
        assert data[1]["target_word"] == "word2"

    async def test_excludes_future_due_cards(
        self, client: AsyncClient, session
    ) -> None:
        """Cards with future due date must NOT appear in queue."""
        from lingosips.db.models import Card, Settings
        settings = Settings(active_target_language="es")
        session.add(settings)
        future_card = Card(
            target_word="future_word",
            target_language="es",
            due=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(future_card)
        await session.commit()

        response = await client.get("/practice/queue")
        assert response.status_code == 200
        assert response.json() == []

    async def test_response_has_required_fields(
        self, client: AsyncClient, session
    ) -> None:
        """Queue cards include all required fields including FSRS state."""
        from lingosips.db.models import Card, Settings
        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="test", target_language="es", due=datetime.now(UTC))
        session.add(card)
        await session.commit()

        response = await client.get("/practice/queue")
        data = response.json()
        assert len(data) == 1
        item = data[0]
        for field in ["id", "target_word", "target_language", "due", "fsrs_state",
                      "stability", "difficulty", "reps", "lapses"]:
            assert field in item, f"Missing field: {field}"
```

---

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `asyncio.get_event_loop()` | `asyncio.get_running_loop()` — deprecated in 3.10+ |
| `session.exec(select(...))` | `session.execute(select(...))` — this project uses SQLAlchemy `AsyncSession` |
| Business logic in `api/cards.py` router | Delegate to `core.cards.create_card_stream()` |
| Instantiating `QwenLocalProvider()` directly in `api/cards.py` | `Depends(get_llm_provider)` only |
| Calling `get_speech_provider()` in this story | Speech/TTS is Story 1.8 — do NOT add it here |
| Emitting `{"cardId": 42}` in SSE events | `{"card_id": 42}` — all JSON keys are snake_case |
| Wrapping response in envelope: `{"data": {...}, "status": "ok"}` | Direct model: `{"card_id": 42}` |
| `datetime.utcnow()` | `datetime.now(UTC)` — utcnow() returns naive datetime |
| `SQLModel.metadata.create_all()` | Alembic only — schema already exists |
| `raise` inside the async generator | `yield _sse_event("error", {...})` then `return` — never raise |
| Mocking `core.cards.create_card_stream` in API tests | Mock the LLM dependency via `app.dependency_overrides` — exercise the real pipeline |
| `from typing import AsyncGenerator` | `from collections.abc import AsyncGenerator` (Python 3.12) |

---

### §FileStructure — New and Modified Files

```
src/lingosips/
├── api/
│   ├── app.py              ← UPDATED: add cards_router + practice_router registrations
│   ├── cards.py            ← NEW: POST /cards/stream endpoint
│   └── practice.py         ← NEW: GET /practice/queue endpoint (minimal)
├── core/
│   ├── cards.py            ← NEW: create_card_stream(), CardCreateRequest, helpers
│   └── safety.py           ← NEW: check_text(), BLOCKED_TERMS blocklist

tests/
├── api/
│   ├── test_cards.py       ← NEW
│   └── test_practice.py    ← NEW
├── core/
│   ├── __init__.py         ← NEW (empty, if not already present)
│   ├── test_cards.py       ← NEW
│   └── test_safety.py      ← NEW
```

No new Python dependencies needed — `asyncio`, `json`, `fastapi`, `pydantic`, `sqlalchemy`, `structlog` are all already in `pyproject.toml`.

---

### §FsrsStateNote — Column Name Discrepancy

The epics AC says `state=New` but the DB column in `db/models.py` is named **`fsrs_state`** (not `state`). This was a deliberate naming choice to avoid conflicts with SQLite reserved words. When creating a card, set `fsrs_state="New"` — this is the default in the model so no explicit assignment is needed. The `QueueCard` response model should expose the field as `fsrs_state` (snake_case, matching the DB column).

---

### Previous Story Intelligence

From Story 1.6 (most recent — code review completed 2026-05-01):

- **`asyncio.get_running_loop()` NOT `asyncio.get_event_loop()`** — `get_event_loop()` is deprecated in Python 3.10+. Review #6 patched this in Story 1.5. Do NOT use `get_event_loop()` anywhere.
- **`session.execute()` NOT `session.exec()`** — this project uses SQLAlchemy `AsyncSession` directly. All queries: `result = await session.execute(select(Model))` → `result.scalars().all()` or `result.scalar_one_or_none()`.
- **`@pytest.mark.anyio` on the CLASS, not individual methods** — all async test methods inherit it from the class-level mark.
- **`app.dependency_overrides` must be cleared after each test** — use `try/finally` or a fixture with cleanup. Leaving overrides in place causes test pollution between test classes.
- **Module-level singleton isolation in tests** — `_qwen_provider` and `_pyttsx3_provider` singletons in `registry.py` persist between tests. If any test needs a clean provider state, reset them: `import lingosips.services.registry as reg; reg._qwen_provider = None`.
- **SSE f-string issue from Story 1.5**: Ruff rejects dict literals split across multi-line f-strings. Pre-compute `json.dumps(...)` into a local variable before using in f-strings.
- **structlog pattern**: `logger = structlog.get_logger(__name__)` at module level. Log events are snake_case: `logger.info("cards.created", card_id=card.id)`.
- **`get_or_create_settings()` already tested and working** — call it from `api/cards.py` to get `active_target_language`. Do NOT duplicate settings logic.
- **90% backend coverage CI hard gate** — all new files under `src/lingosips/` must be covered by tests. The entire `create_card_stream()` flow must be exercised including error paths.
- **Ruff import order**: `stdlib` first (`asyncio`, `collections.abc`, `datetime`, `json`) → `third-party` (`fastapi`, `pydantic`, `sqlalchemy`, `structlog`) → `local` (`lingosips.*`). Run `uv run ruff check --fix` before committing.

From Story 1.5 (deferred resolved in this story):
- `Depends(get_llm_provider)` must be used in `api/cards.py` — this is the first router to wire it up. The deferred item from Story 1.5 is now resolved.
- 503 from `get_llm_provider()` (model not downloaded) propagates through to the client as a 503 HTTP response. The SSE generator is never reached — no special handling needed in `api/cards.py` for this case.

---

### References

- Story 1.7 acceptance criteria: [Source: _bmad-output/planning-artifacts/epics.md#Story 1.7]
- SSE event envelope spec: `event: {type}\ndata: {json}\n\n`: [Source: _bmad-output/planning-artifacts/architecture.md#SSE Event Envelope]
- Three SSE channels — `POST /cards/stream` is channel 1: [Source: _bmad-output/planning-artifacts/epics.md#Additional Requirements — Real-time communication]
- `core/cards.py` owns card creation pipeline: [Source: _bmad-output/planning-artifacts/architecture.md#Structure Patterns]
- `api/cards.py` router only — no business logic: [Source: _bmad-output/project-context.md#Layer Architecture & Boundaries]
- `core/safety.py` — keyword blocklist MVP: [Source: _bmad-output/planning-artifacts/epics.md#Additional Requirements — Content safety filter]
- `Depends(get_llm_provider)` — never instantiate providers directly: [Source: _bmad-output/project-context.md#Dependency Injection — Depends() Always]
- `session.execute(select(...))` pattern: [Source: Story 1.6 Dev Agent Record — previous story intelligence]
- `asyncio.get_running_loop()` not deprecated: [Source: Story 1.5 Dev Agent Record — Review Finding #6]
- `datetime.now(UTC)` for UTC-aware datetime: [Source: src/lingosips/db/models.py#_now()]
- FSRS initial state columns: `stability=0, difficulty=0, fsrs_state="New"`: [Source: src/lingosips/db/models.py#Card]
- `fsrs_state` column name (not `state`): [Source: src/lingosips/db/models.py:Card.fsrs_state]
- Snake_case all JSON fields — no camelCase: [Source: _bmad-output/project-context.md#Naming Conventions]
- RFC 7807 error format for 422/404/etc: [Source: _bmad-output/project-context.md#API Design Rules]
- TDD mandatory — failing tests before implementation: [Source: _bmad-output/project-context.md#Testing Rules]
- 90% backend coverage CI hard gate: [Source: _bmad-output/project-context.md#CI gates]
- `openrouter` timeout SLA 500ms first token; local Qwen 2s: [Source: _bmad-output/planning-artifacts/epics.md#NFR4]
- FR1: card creation — single word/phrase input: [Source: _bmad-output/planning-artifacts/epics.md#FR1]
- FR2: AI auto-generation of translation, forms, examples: [Source: _bmad-output/planning-artifacts/epics.md#FR2]
- FR28: AI content streaming (SSE): [Source: _bmad-output/planning-artifacts/epics.md#FR28]
- FR50: Content safety filter for AI-generated content: [Source: _bmad-output/planning-artifacts/epics.md#FR50]
- `GET /practice/queue` response shape: [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1]
- Deferred from 1.5 resolved: `Depends(get_llm_provider)` wired in api/cards.py: [Source: _bmad-output/implementation-artifacts/deferred-work.md]

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

- Session test isolation: Added `autouse` truncate fixture to `TestCreateCardStream` to clear the cards table before each test. The in-memory SQLite with `StaticPool` shares a single connection; committed rows from previous tests persisted across sessions despite the rollback fixture. Truncating via `test_engine` before each test ensures clean isolation.
- Ruff auto-fix: `asyncio.TimeoutError` was replaced with bare `TimeoutError` (Python 3.12+ alias). Updated tests and `core/cards.py` accordingly. `from datetime import UTC, datetime` removed from `core/cards.py` because the `datetime` module is unused there (Card model uses `_now()` default factory from `db/models.py`).

### Completion Notes List

- **T1/T2 — `core/safety.py`**: Implemented `check_text()` with `BLOCKED_TERMS` (empty for MVP). Case-insensitive substring matching. 7 tests all pass, 100% coverage.
- **T3/T4 — `core/cards.py`**: Implemented `CardCreateRequest` (Pydantic v2, field_validator), `_sse_event()`, `_parse_llm_response()` (handles clean JSON + markdown fenced + preamble/trailing text), `_build_messages()`, and `create_card_stream()` async generator. Timeout uses `asyncio.wait_for()` with 10s. Safety filter applied per field. Card persisted with FSRS defaults. 20 tests all pass, 88% coverage on the module.
- **T5/T6 — `api/cards.py`**: `POST /cards/stream` using `StreamingResponse` with `text/event-stream` media type. Dependency injection via `Depends(get_llm_provider)`. `target_language` fetched from settings before starting generator. `app.dependency_overrides.pop()` (not `.clear()`) used in test teardown per Dev Notes §MockLLMFixture. 11 tests all pass.
- **T7/T8 — `api/practice.py`**: `GET /practice/queue` queries cards where `due <= now` and `target_language == active_lang`, ordered by `due.asc()`. `QueueCard` response model with all required FSRS fields. Returns `[]` when empty. 6 tests all pass including language filter test.
- **T9 — `api/app.py`**: Registered `cards_router` at `/cards` and `practice_router` at `/practice`. Existing `settings_router` and `models_router` untouched.
- **T10 — Ruff**: All 11 issues resolved (8 auto-fixed + 3 manual E501 line-length fixes). All checks pass.
- **Full suite**: 213 tests pass, 92.83% coverage (exceeds 90% CI gate). Zero regressions.

### File List

- `src/lingosips/core/safety.py` — NEW
- `src/lingosips/core/cards.py` — NEW
- `src/lingosips/api/cards.py` — NEW
- `src/lingosips/api/practice.py` — NEW
- `src/lingosips/api/app.py` — MODIFIED (added cards_router + practice_router imports and registrations)
- `tests/core/test_safety.py` — NEW
- `tests/core/test_cards.py` — NEW
- `tests/api/test_cards.py` — NEW
- `tests/api/test_practice.py` — NEW

### Review Findings

- [x] [Review][Patch] AC3 — 422 response not RFC 7807; add RequestValidationError handler [src/lingosips/api/app.py]
- [x] [Review][Patch] AC3 — 422 tests assert only status code, not RFC 7807 body shape [tests/api/test_cards.py]
- [x] [Review][Patch] Unused `logger` in `api/practice.py` — dead import and assignment [src/lingosips/api/practice.py]
- [x] [Review][Patch] Unused `logger` in `api/cards.py` — dead import and assignment [src/lingosips/api/cards.py]
- [x] [Review][Patch] `_parse_llm_response` rfind bug — trailing `}` in surrounding text breaks JSON extraction [src/lingosips/core/cards.py:117]
- [x] [Review][Patch] API test uses `>= 3` (weaker than core's `== 3`) for field_update count [tests/api/test_cards.py:109]
- [x] [Review][Patch] No test for `translation=None` in queue response — unvalidated API contract [tests/api/test_practice.py]
- [x] [Review][Patch] No `max_length` on `target_word` — unbounded input reaches DB and LLM prompt [src/lingosips/core/cards.py:26]
- [x] [Review][Patch] Add test for trailing-`}` edge case in `_parse_llm_response` [tests/core/test_cards.py]
- [x] [Review][Defer] No pagination on `GET /practice/queue` [src/lingosips/api/practice.py:47] — deferred, Story 3.1
- [x] [Review][Defer] Empty LLM response persists card with `translation=""` — product decision needed [src/lingosips/core/cards.py:128] — deferred, pre-existing
- [x] [Review][Defer] AC7 latency SLA not enforced or measured — deferred, pre-existing NFR gap

## Change Log

- 2026-05-01: Code review of Story 1.7. Applied 9 patches: RFC 7807 RequestValidationError handler, removed dead logger imports from api/cards.py and api/practice.py, fixed _parse_llm_response to use JSONDecoder.raw_decode() (trailing brace edge case), tightened API test assertion >= 3 → == 3, added translation=None queue test, added max_length=500 to target_word, added trailing-brace parser test and max_length boundary tests. 217 tests pass, 92.84% coverage. 3 items deferred.
- 2026-05-01: Implemented Story 1.7 — Card Creation API & SSE Streaming. Created `core/safety.py` (content safety filter), `core/cards.py` (card creation pipeline with SSE streaming, safety filter, FSRS initial state), `api/cards.py` (`POST /cards/stream` endpoint), `api/practice.py` (`GET /practice/queue` endpoint). Updated `api/app.py` to register new routers. Added 44 new tests across 4 test files. All 213 tests pass, 92.83% coverage.
