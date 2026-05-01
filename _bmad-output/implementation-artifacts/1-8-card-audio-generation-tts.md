# Story 1.8: Card Audio Generation (TTS)

Status: done

## Story

As a user,
I want pronunciation audio automatically generated for each new card,
so that I can hear the correct pronunciation of new vocabulary without leaving the app.

## Acceptance Criteria

1. **Given** a card creation completes
   **When** the AI pipeline finishes
   **Then** `AbstractSpeechProvider.synthesize(text, language)` is called with the target word
   **And** the resulting audio bytes are stored and associated with the card

2. **Given** no Azure Speech credentials are configured
   **When** TTS is requested
   **Then** `pyttsx3` handles synthesis as the local fallback
   **And** audio is generated without error

3. **Given** Azure Speech credentials are configured
   **When** TTS is requested
   **Then** `AzureSpeechProvider.synthesize()` is used for higher-quality audio

4. **Given** audio generation succeeds
   **When** the SSE stream emits the `complete` event
   **Then** a `field_update` event for `"audio"` has been emitted with the audio URL (before `complete`)
   **And** an audio player renders in the card result and auto-plays once on creation

5. **Given** TTS synthesis fails entirely (any exception or timeout)
   **When** the error occurs
   **Then** the card is saved without audio (`audio_url` remains `null`)
   **And** the audio field displays a muted "Not available" state
   **And** card creation does not fail or roll back — the SSE `complete` event is still emitted

## Tasks / Subtasks

> **TDD MANDATORY**: Write failing tests for each task BEFORE writing implementation. A story without passing tests is not done.

---

- [x] **T1: Update failing tests in `tests/core/test_cards.py`** (AC: 1, 4, 5)
  - [x] T1.1: Add `mock_speech` fixture to `TestCreateCardStream` — returns `AsyncMock(spec=AbstractSpeechProvider)` with `synthesize = AsyncMock(return_value=b"FAKEAUDIO")`
  - [x] T1.2: Update ALL existing `create_card_stream()` calls in `TestCreateCardStream` to pass `speech=mock_speech` (currently positional — they break after signature change)
  - [x] T1.3: Add `test_audio_field_update_emitted_after_card_persist` — verify `field_update` for `"audio"` is emitted, value matches `/cards/{card_id}/audio` pattern, and it comes BEFORE the `complete` event
  - [x] T1.4: Add `test_audio_url_persisted_to_card_in_db` — after streaming, card in DB has non-null `audio_url` matching `/cards/{card_id}/audio`
  - [x] T1.5: Add `test_tts_failure_does_not_fail_card_creation` — when `speech.synthesize` raises `RuntimeError`, complete event is still emitted, no `error` event in stream, card is persisted with `audio_url=None`
  - [x] T1.6: Add `test_tts_timeout_does_not_fail_card_creation` — when `speech.synthesize` raises `TimeoutError`, same behavior as T1.5
  - [x] T1.7: All tests pass `speech` argument as keyword (`speech=mock_speech`) — function signature uses keyword-only style in calls for clarity

- [x] **T2: Modify `core/cards.py` to make T1 pass** (AC: 1, 4, 5)
  - [x] T2.1: Add `from pathlib import Path` and `from lingosips.services.speech.base import AbstractSpeechProvider` imports
  - [x] T2.2: Add module-level constants: `AUDIO_DIR = Path.home() / ".lingosips" / "audio"` and `AUDIO_SYNTHESIS_TIMEOUT = 30.0`
  - [x] T2.3: Add `speech: AbstractSpeechProvider` as a **required** parameter to `create_card_stream()` — add AFTER `target_language` to minimize diff
  - [x] T2.4: After `await session.refresh(card)` (card has its integer `id`), insert new Step 5 — TTS generation (see §AudioGenerationStep)
  - [x] T2.5: Emit `field_update` for `"audio"` (only if TTS succeeds) BEFORE the `complete` event — emit `complete` unconditionally after the try/except block
  - [x] T2.6: The new TTS step is wrapped in broad `try/except Exception` — any failure (synthesis error, file I/O, timeout) is logged as `logger.warning(...)` and skipped; no `error` SSE event is emitted for TTS failures
  - [x] T2.7: Rearrange `logger.info("cards.created", ...)` to appear AFTER the TTS block (not before it)

- [x] **T3: Write failing tests in `tests/api/test_cards.py`** (AC: 1, 2, 3, 4, 5)
  - [x] T3.1: Add `mock_speech_provider` fixture to `tests/api/test_cards.py` (see §MockSpeechFixture)
  - [x] T3.2: Add `autouse=True` class-level fixture to `TestPostCardsStream` that injects `mock_speech_provider` automatically (all existing tests in this class now need speech mocked to avoid real pyttsx3 calls)
  - [x] T3.3: Add `test_audio_field_update_emitted_before_complete` — stream POST `/cards/stream`, verify `field_update` event with `field="audio"` precedes `complete` event
  - [x] T3.4: Add `test_audio_url_value_matches_endpoint_pattern` — audio field_update `value` starts with `/cards/` and ends with `/audio`
  - [x] T3.5: Add `test_tts_failure_card_created_no_stream_error` — when speech mock raises `RuntimeError`, POST `/cards/stream` still returns `complete` event (no `error` event), no 500 response
  - [x] T3.6: Add new `TestGetCardAudio` class (see §TestGetCardAudio)

- [x] **T4: Modify `api/cards.py` to make T3 pass** (AC: 1, 2, 3, 4)
  - [x] T4.1: Add imports: `from fastapi.responses import FileResponse`, `from lingosips.services.speech.base import AbstractSpeechProvider`, `from lingosips.services.registry import get_speech_provider`, `from lingosips.core.cards import AUDIO_DIR`
  - [x] T4.2: Add `speech: AbstractSpeechProvider = Depends(get_speech_provider)` to `create_card_stream` endpoint parameters (add between `llm` and `session` for readability)
  - [x] T4.3: Pass `speech=speech` to `core_cards.create_card_stream()` call
  - [x] T4.4: Add `GET /{card_id}/audio` endpoint (see §AudioServingEndpoint) — returns `FileResponse` with `audio/wav` media type; 404 with RFC 7807 body if file not found

- [x] **T5: Update `src/lingosips/__main__.py`** (prevent startup failures)
  - [x] T5.1: Add `(data_dir / "audio").mkdir(exist_ok=True)` after the existing `(data_dir / "models").mkdir(exist_ok=True)` line — audio dir must exist before first TTS call

- [x] **T6: Ruff compliance check**
  - [x] T6.1: `uv run ruff check --fix src/lingosips/core/cards.py src/lingosips/api/cards.py src/lingosips/__main__.py tests/core/test_cards.py tests/api/test_cards.py`
  - [x] T6.2: Import order in `core/cards.py`: `stdlib` (`asyncio`, `json`, `pathlib`) → `third-party` (`pydantic`, `sqlalchemy`, `structlog`) → `local` (`lingosips.*`)
  - [x] T6.3: `Path` is in `pathlib` — add to stdlib group in import order; `AbstractSpeechProvider` is a local import

---

## Dev Notes

### ⚠️ DO NOT Recreate — Already Exists

| Existing | Location | What it provides |
|---|---|---|
| `AbstractSpeechProvider` | `src/lingosips/services/speech/base.py` | `synthesize(text, language) → bytes` already defined |
| `Pyttsx3Provider` | `src/lingosips/services/speech/pyttsx3_local.py` | `synthesize()` writes WAV bytes via executor; already works |
| `AzureSpeechProvider` | `src/lingosips/services/speech/azure.py` | `synthesize()` via Azure TTS REST; already works |
| `get_speech_provider()` | `src/lingosips/services/registry.py` | Returns `AzureSpeechProvider` if Azure creds set; `Pyttsx3Provider` otherwise |
| `_pyttsx3_provider` singleton | `src/lingosips/services/registry.py:30` | Cached after first creation — tests must use `.pop()` not `.clear()` |
| `core/cards.py` | `src/lingosips/core/cards.py` | `create_card_stream()` generator — MODIFY (add `speech` param + TTS step) |
| `api/cards.py` | `src/lingosips/api/cards.py` | `POST /stream` endpoint — MODIFY (add speech Depends, new audio endpoint) |
| `__main__.py` | `src/lingosips/__main__.py` | Startup sequence — MODIFY (add audio dir creation) |
| `tests/conftest.py` | `tests/conftest.py` | `client`, `session`, `test_engine` fixtures — do NOT modify |

**CRITICAL — Story 1.7 established NO speech provider in `core/cards.py`:**
> "CRITICAL: `get_speech_provider()` is NOT needed in Story 1.7 — TTS/audio is Story 1.8."

This story resolves that deferred item.

---

### §AudioGenerationStep — Core Implementation

Insert this block in `core/cards.py` between `await session.refresh(card)` and the `complete` event:

```python
# Step 5: Audio generation (TTS) — soft failure — never blocks card creation
try:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_bytes = await asyncio.wait_for(
        speech.synthesize(request.target_word, target_language),
        timeout=AUDIO_SYNTHESIS_TIMEOUT,
    )
    audio_path = AUDIO_DIR / f"{card.id}.wav"
    audio_path.write_bytes(audio_bytes)
    card.audio_url = f"/cards/{card.id}/audio"
    await session.commit()
    logger.info(
        "cards.audio_generated",
        card_id=card.id,
        audio_bytes=len(audio_bytes),
    )
    yield _sse_event("field_update", {"field": "audio", "value": card.audio_url})
except Exception as exc:
    logger.warning(
        "cards.audio_failed",
        card_id=card.id,
        exc_type=type(exc).__name__,
    )
    # TTS failure is non-fatal: card is already saved with audio_url=None

logger.info("cards.created", card_id=card.id, target_word=request.target_word)
yield _sse_event("complete", {"card_id": card.id})
```

**Updated `create_card_stream()` signature:**
```python
async def create_card_stream(
    request: CardCreateRequest,
    llm: AbstractLLMProvider,
    session: AsyncSession,
    target_language: str,
    speech: AbstractSpeechProvider,  # ← NEW required parameter
) -> AsyncGenerator[str, None]:
```

**New module-level constants to add at top of `core/cards.py`** (after existing imports):
```python
from pathlib import Path
from lingosips.services.speech.base import AbstractSpeechProvider

AUDIO_DIR = Path.home() / ".lingosips" / "audio"
AUDIO_SYNTHESIS_TIMEOUT = 30.0  # seconds — generous for slow local TTS
```

---

### §AudioServingEndpoint — `GET /cards/{card_id}/audio`

Add to `api/cards.py` (after the `POST /stream` endpoint):

```python
@router.get("/{card_id}/audio")
async def get_card_audio(card_id: int) -> FileResponse:
    """Serve WAV audio for a card.

    Returns the pre-generated WAV file from the local audio directory.
    404 RFC 7807 if no audio was generated (TTS failed or card has no audio).
    Does NOT require a DB session — audio presence is determined by file existence.
    """
    audio_path = AUDIO_DIR / f"{card_id}.wav"
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/audio-not-found",
                "title": "Audio not found",
                "detail": f"No audio file for card {card_id}",
                "status": 404,
            },
        )
    return FileResponse(str(audio_path), media_type="audio/wav")
```

**Import additions for `api/cards.py`:**
```python
from fastapi import APIRouter, Depends, HTTPException  # add HTTPException
from fastapi.responses import FileResponse, StreamingResponse  # add FileResponse

from lingosips.core.cards import AUDIO_DIR, CardCreateRequest  # add AUDIO_DIR
from lingosips.services.speech.base import AbstractSpeechProvider  # new
from lingosips.services.registry import get_llm_provider, get_speech_provider  # add get_speech_provider
```

**Updated `POST /stream` endpoint signature:**
```python
@router.post("/stream")
async def create_card_stream(
    request: CardCreateRequest,
    llm: AbstractLLMProvider = Depends(get_llm_provider),
    speech: AbstractSpeechProvider = Depends(get_speech_provider),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
```

**Updated call to core:**
```python
async for event in core_cards.create_card_stream(
    request=request,
    llm=llm,
    session=session,
    target_language=target_language,
    speech=speech,  # ← NEW
):
```

---

### §MockSpeechFixture — Test Setup for `tests/api/test_cards.py`

```python
# In tests/api/test_cards.py — add at module level alongside mock_llm_provider

from lingosips.services.registry import get_speech_provider

@pytest.fixture
async def mock_speech_provider(tmp_path, monkeypatch):
    """Override get_speech_provider with a mock; redirect AUDIO_DIR to tmp_path.

    Uses .pop() at teardown — NOT .clear() — to avoid removing the session
    override set by the conftest client fixture.
    """
    import lingosips.core.cards as core_cards_module
    from lingosips.services.speech.base import AbstractSpeechProvider

    # Redirect audio file writes to tmp dir so tests don't pollute ~/.lingosips/audio/
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)

    mock = AsyncMock(spec=AbstractSpeechProvider)
    mock.synthesize = AsyncMock(return_value=b"FAKE_WAV_AUDIO_BYTES")
    mock.provider_name = "MockSpeech"
    mock.model_name = "mock-tts"

    app.dependency_overrides[get_speech_provider] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_speech_provider, None)  # NOT .clear()
```

**Make speech mock autouse for `TestPostCardsStream`** so all existing tests don't call real pyttsx3:

```python
@pytest.mark.anyio
class TestPostCardsStream:
    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine): ...  # existing

    @pytest.fixture(autouse=True)
    def _auto_mock_speech(self, mock_speech_provider):
        """Auto-inject speech mock for all tests in this class."""
        return mock_speech_provider
    
    # Existing tests unchanged — they now get speech mocked automatically
```

---

### §TestGetCardAudio — Required Test Cases

```python
@pytest.mark.anyio
class TestGetCardAudio:
    """Tests for GET /cards/{card_id}/audio."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        from sqlalchemy import text
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_audio_served_when_file_exists(
        self, client: AsyncClient, tmp_path, monkeypatch
    ) -> None:
        """200 + audio/wav content-type when audio file present."""
        import lingosips.core.cards as core_cards_module

        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)
        # Also patch AUDIO_DIR in api/cards.py (it imports the constant at load time)
        import lingosips.api.cards as api_cards_module
        monkeypatch.setattr(api_cards_module, "AUDIO_DIR", audio_dir)

        # Write a fake WAV file
        fake_wav = b"RIFF....WAVEfmt "
        (audio_dir / "42.wav").write_bytes(fake_wav)

        response = await client.get("/cards/42/audio")
        assert response.status_code == 200
        assert "audio/wav" in response.headers.get("content-type", "")
        assert response.content == fake_wav

    async def test_audio_not_found_returns_404_rfc7807(
        self, client: AsyncClient, tmp_path, monkeypatch
    ) -> None:
        """404 with RFC 7807 body when no audio file exists."""
        import lingosips.api.cards as api_cards_module
        audio_dir = tmp_path / "audio_empty"
        audio_dir.mkdir()
        monkeypatch.setattr(api_cards_module, "AUDIO_DIR", audio_dir)

        response = await client.get("/cards/999/audio")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/audio-not-found"
        assert body["status"] == 404
```

---

### §CoreTestUpdate — Updating Existing `tests/core/test_cards.py`

The existing `TestCreateCardStream` calls `create_card_stream()` without the `speech` parameter. This BREAKS after adding the required `speech` argument.

**Add `mock_speech` fixture to `TestCreateCardStream`:**
```python
@pytest.fixture
def mock_speech(self, tmp_path, monkeypatch) -> AsyncMock:
    """Mock speech provider — redirects AUDIO_DIR to tmp_path."""
    import lingosips.core.cards as core_cards_module
    from lingosips.services.speech.base import AbstractSpeechProvider

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)

    mock = AsyncMock(spec=AbstractSpeechProvider)
    mock.synthesize = AsyncMock(return_value=b"FAKE_WAV_AUDIO")
    return mock
```

**Update ALL existing `create_card_stream()` calls** (5 places) by adding `speech=mock_speech` as a keyword argument:
```python
# BEFORE (will fail after T2.3):
gen = create_card_stream(request, mock_llm, session, "es")

# AFTER:
gen = create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
```

Affected test methods:
- `test_field_update_events_emitted_in_order`
- `test_complete_event_emitted_with_card_id`
- `test_card_persisted_to_db`
- `test_fsrs_initial_state_set_on_card`
- `test_safety_blocked_emits_error_no_card`

Tests that do NOT use `mock_llm` (create their own mock) also need updating:
- `test_llm_timeout_emits_error_event` — add `speech=mock_speech`
- `test_invalid_llm_response_emits_error` — add `speech=mock_speech`

---

### §TestNewCoreAudioTests — Add to `TestCreateCardStream`

```python
async def test_audio_field_update_emitted_after_card_persist(
    self, mock_llm, mock_speech, session
) -> None:
    """AC4: field_update for 'audio' emitted before complete event."""
    from lingosips.core.cards import CardCreateRequest, create_card_stream

    request = CardCreateRequest(target_word="melancólico")
    events = await self._collect_events(
        create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
    )

    field_updates = [e for e in events if e["event"] == "field_update"]
    audio_events = [e for e in field_updates if e["data"]["field"] == "audio"]
    complete_events = [e for e in events if e["event"] == "complete"]

    assert len(audio_events) == 1
    assert complete_events[0]["data"]["card_id"] > 0
    # audio field_update comes before complete
    audio_idx = next(i for i, e in enumerate(events) if e["event"] == "field_update" and e["data"].get("field") == "audio")
    complete_idx = next(i for i, e in enumerate(events) if e["event"] == "complete")
    assert audio_idx < complete_idx
    # Value is relative URL
    assert audio_events[0]["data"]["value"].startswith("/cards/")
    assert audio_events[0]["data"]["value"].endswith("/audio")

async def test_audio_url_persisted_to_db(
    self, mock_llm, mock_speech, session
) -> None:
    """AC1: card.audio_url is set in DB after successful TTS."""
    from sqlalchemy import select
    from lingosips.core.cards import CardCreateRequest, create_card_stream
    from lingosips.db.models import Card

    request = CardCreateRequest(target_word="melancólico")
    events = await self._collect_events(
        create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
    )

    card_id = next(e["data"]["card_id"] for e in events if e["event"] == "complete")
    result = await session.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one()
    assert card.audio_url == f"/cards/{card_id}/audio"

async def test_tts_failure_card_created_no_error_event(
    self, mock_llm, session, tmp_path, monkeypatch
) -> None:
    """AC5: TTS exception → complete event still emitted, no SSE error, card saved."""
    import lingosips.core.cards as core_cards_module
    from lingosips.services.speech.base import AbstractSpeechProvider

    audio_dir = tmp_path / "audio_fail"
    audio_dir.mkdir()
    monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)

    mock_speech_fail = AsyncMock(spec=AbstractSpeechProvider)
    mock_speech_fail.synthesize = AsyncMock(side_effect=RuntimeError("pyttsx3 init failed"))

    from lingosips.core.cards import CardCreateRequest, create_card_stream

    request = CardCreateRequest(target_word="test")
    events = await self._collect_events(
        create_card_stream(request, mock_llm, session, "es", speech=mock_speech_fail)
    )

    # No error event
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 0
    # Complete event still emitted
    complete_events = [e for e in events if e["event"] == "complete"]
    assert len(complete_events) == 1
    # No audio field_update
    audio_updates = [e for e in events if e["event"] == "field_update" and e["data"].get("field") == "audio"]
    assert len(audio_updates) == 0
```

---

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `app.dependency_overrides.clear()` in test teardown | `app.dependency_overrides.pop(get_speech_provider, None)` — preserves session override |
| Instantiating `Pyttsx3Provider()` directly in core | `Depends(get_speech_provider)` in `api/cards.py`, then pass to core |
| Raising an error SSE event when TTS fails | `logger.warning(...)` and continue — TTS failure is non-fatal |
| `get_event_loop()` | `get_running_loop()` — deprecated in Python 3.10+ |
| Writing audio to `~/.lingosips/audio/` directly in tests | `monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)` with `tmp_path` |
| Sharing `pyttsx3.init()` engine across calls | `Pyttsx3Provider` already creates a fresh engine per call — do not change this |
| `speech.evaluate_pronunciation()` anywhere in this story | `synthesize()` only — pronunciation evaluation is Story 4.1 |
| Setting a default `speech=None` parameter | `speech` is required — update all callers |
| `await session.execute(...)` for audio URL update | Set `card.audio_url` and `await session.commit()` — card is already attached to session |
| `monkeypatch` scope mismatch in async fixtures | `monkeypatch` is function-scoped — matches `async def test_...()` scope correctly |

---

### §FileStructure — Modified Files

```
src/lingosips/
├── __main__.py         ← MODIFIED: add (data_dir / "audio").mkdir(exist_ok=True)
├── api/
│   └── cards.py        ← MODIFIED: add speech Depends injection; add GET /{card_id}/audio endpoint
├── core/
│   └── cards.py        ← MODIFIED: add AUDIO_DIR, AUDIO_SYNTHESIS_TIMEOUT constants,
│                                   speech param, TTS generation step
tests/
├── core/
│   └── test_cards.py   ← MODIFIED: add mock_speech fixture, update 7 existing calls,
│                                   add 3 new audio tests
├── api/
│   └── test_cards.py   ← MODIFIED: add mock_speech_provider fixture, autouse in class,
│                                   3 new stream tests, new TestGetCardAudio class
```

No new Python package dependencies required — all libraries already in `pyproject.toml`:
`pyttsx3`, `httpx`, `fastapi`, `structlog`, `asyncio`, `pathlib` all present.

---

### §ImportantArchitecturalDecisions

**Why `AUDIO_DIR` is a module-level constant in `core/cards.py` (not a service):**
The project uses `MODELS_DIR = Path.home() / ".lingosips" / "models"` in `services/models/manager.py`. Defining `AUDIO_DIR` similarly in `core/cards.py` follows the established pattern for MVP. A dedicated `AudioManager` is overkill at this stage.

**Why audio is stored as WAV files, not in SQLite:**
The `Card.audio_url` column stores a URL, not bytes. The Story 2.5 export format already assumes audio as files in an `audio/` folder within `.lingosips` format. File-based storage is the intended design.

**Why TTS failure uses broad `except Exception` (not specific exceptions):**
`Pyttsx3Provider.synthesize()` raises `RuntimeError` on init failure and synthesis failure (wrapping various platform-specific errors). `AzureSpeechProvider.synthesize()` raises `RuntimeError` on HTTP errors. `asyncio.wait_for()` raises `TimeoutError`. Catching all `Exception` types is intentional — any TTS failure is non-fatal.

**Why the audio field_update comes BEFORE `complete`:**
The frontend relies on SSE order: it needs the audio URL before the `complete` event fires so it can render the audio player and auto-play. The `complete` event signals the UI to finalize the card display.

**Why `GET /cards/{card_id}/audio` does NOT check the DB:**
Audio presence is determined by file existence — simpler and avoids an unnecessary DB query on every audio playback. If the card exists but TTS failed, the file won't exist and `404` is correct behavior. This is consistent with how `GET /models/download/progress` checks model file state via the ModelManager.

---

### Previous Story Intelligence

From Story 1.7 (code review completed 2026-05-01):

- **`app.dependency_overrides.pop()` NOT `.clear()`** — `.clear()` removes the session override set by `conftest.client` fixture, causing test failures. Always use `.pop(get_key, None)` in fixture teardown.
- **`@pytest.mark.anyio` on the CLASS, not individual methods** — all async methods inherit the mark.
- **`session.execute(select(...)).scalars().all()`** — this project uses SQLAlchemy `AsyncSession` directly, NOT `session.exec()`.
- **`asyncio.get_running_loop()` NOT `get_event_loop()`** — deprecated in Python 3.10+. `Pyttsx3Provider` already uses `get_running_loop()` correctly — do not change it.
- **`structlog` pattern**: `logger.warning("cards.audio_failed", card_id=..., exc_type=...)` — snake_case event names, structured key-value pairs.
- **90% backend coverage CI hard gate** — all new branches in modified files must be exercised. TTS success AND failure paths must both be tested.
- **Ruff import order**: `stdlib` (`asyncio`, `json`, `pathlib`) → `third-party` (`pydantic`, `sqlalchemy`, `structlog`) → `local` (`lingosips.*`). Run `uv run ruff check --fix` before committing.
- **Module-level singleton `_pyttsx3_provider`** in `registry.py:30` persists between tests. If a test needs a clean provider state, reset: `import lingosips.services.registry as reg; reg._pyttsx3_provider = None`. For this story, mocking via `app.dependency_overrides` is sufficient — no need to reset the singleton.
- **AUDIO_DIR monkeypatching scope** — `monkeypatch` is function-scoped. The constant is defined as `AUDIO_DIR` at module level in `core/cards.py` and imported (not re-evaluated) in `api/cards.py`. Patch BOTH modules when testing the API endpoint: `monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)` and `monkeypatch.setattr(api_cards_module, "AUDIO_DIR", audio_dir)`.

From Story 1.5 (deferred):
- `Depends(get_speech_provider)` is the ONLY way to get a speech provider in routers — never instantiate `Pyttsx3Provider()` or `AzureSpeechProvider()` directly in `api/` or `core/`.

---

### References

- Story 1.8 acceptance criteria: [Source: _bmad-output/planning-artifacts/epics.md#Story 1.8]
- FR2: AI auto-generation includes audio: [Source: _bmad-output/planning-artifacts/epics.md#FR2]
- `AbstractSpeechProvider.synthesize()` signature `(text: str, language: str) → bytes`: [Source: src/lingosips/services/speech/base.py:47]
- `get_speech_provider()` — returns Pyttsx3Provider or AzureSpeechProvider based on creds: [Source: src/lingosips/services/registry.py:70-93]
- `Pyttsx3Provider.synthesize()` runs in executor, creates engine per call (thread-safe): [Source: src/lingosips/services/speech/pyttsx3_local.py:35-77]
- `AzureSpeechProvider.synthesize()` — Azure TTS REST API: [Source: src/lingosips/services/speech/azure.py:78-112]
- `Card.audio_url: str | None = None` — already in DB schema: [Source: src/lingosips/db/models.py:25]
- `MODELS_DIR = Path.home() / ".lingosips" / "models"` — pattern for AUDIO_DIR: [Source: src/lingosips/services/models/manager.py:25]
- Data dir created at startup: [Source: src/lingosips/__main__.py:24-26]
- SSE envelope format: [Source: src/lingosips/core/cards.py:42-51]
- Provider fallback exclusively in `services/registry.py`: [Source: _bmad-output/project-context.md#Layer Architecture & Boundaries]
- `Depends(get_speech_provider)` — never instantiate providers directly: [Source: _bmad-output/project-context.md#Dependency Injection — Depends() Always]
- TDD mandatory — failing tests before implementation: [Source: _bmad-output/project-context.md#Testing Rules]
- 90% backend coverage CI hard gate: [Source: _bmad-output/project-context.md#CI gates]
- RFC 7807 Problem Details for all errors: [Source: _bmad-output/project-context.md#API Design Rules]
- `.pop()` not `.clear()` for dependency override teardown: [Source: _bmad-output/implementation-artifacts/1-7-card-creation-api-sse-streaming.md#§MockLLMFixture]

---

## Review Findings

> Code review by bmad-code-review (2026-05-01). 3 layers: Blind Hunter + Edge Case Hunter + Acceptance Auditor. 15 raw findings → 4 patch, 3 defer, 8 dismissed.

- [x] [Review][Patch] Blocking `write_bytes()` in async generator — wrapped with `asyncio.to_thread` [`src/lingosips/core/cards.py:236`]
- [x] [Review][Patch] Empty audio bytes `b""` written without guard — added `if not audio_bytes` check before disk write [`src/lingosips/core/cards.py:234`]
- [x] [Review][Patch] Missing DB assertion for `audio_url=None` after TTS failure — added `card.audio_url is None` DB query to both failure tests [`tests/core/test_cards.py:405,440`]
- [x] [Review][Patch] `str(audio_path)` conversion unnecessary — `FileResponse` accepts `Path` directly [`src/lingosips/api/cards.py:79`]
- [x] [Review][Defer] Business logic in `get_card_audio` router (path construction + exists check) [`src/lingosips/api/cards.py:68`] — deferred, spec explicitly defines this design; consistent with ModelManager pattern
- [x] [Review][Defer] TOCTOU race between `exists()` check and `FileResponse` delivery [`src/lingosips/api/cards.py:69`] — deferred, negligible for local single-user app; `FileResponse` lazy-loads during ASGI response
- [x] [Review][Defer] Autouse fixture ordering fragility in `test_tts_failure_card_created_no_stream_error` [`tests/api/test_cards.py:316`] — deferred, works correctly via safe-pop semantics but teardown order dependency is fragile

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5 (2026-05-01)

### Debug Log References

- Two existing tests (`test_field_update_events_emitted_in_order` in both core and API) asserted `len(field_updates) == 3`, which needed updating to `4` after audio field_update was added. Updated assertions to also verify the 4th event is the `audio` field. This is correct behavior per AC4.

### Completion Notes List

- **T1**: Added `mock_speech` fixture to `TestCreateCardStream`; updated 7 existing `create_card_stream()` call sites to pass `speech=mock_speech`; added 4 new audio-specific tests (T1.3–T1.6). Updated existing `test_field_update_events_emitted_in_order` assertion from 3 → 4 field updates (now includes audio).
- **T2**: Added `pathlib.Path`, `AbstractSpeechProvider` imports and `AUDIO_DIR`, `AUDIO_SYNTHESIS_TIMEOUT` constants to `core/cards.py`. Added `speech` required parameter to `create_card_stream()`. Inserted TTS generation step (Step 5) with `asyncio.wait_for()` wrapping `speech.synthesize()`, broad `except Exception` for non-fatal error handling, and `field_update` for `"audio"` emitted before `complete`.
- **T3**: Added `mock_speech_provider` fixture with `tmp_path` monkeypatching, `_auto_mock_speech` autouse to `TestPostCardsStream`, 3 new stream tests, and `TestGetCardAudio` class with 2 tests (200 + 404 RFC 7807).
- **T4**: Updated `api/cards.py` with all required imports (`FileResponse`, `HTTPException`, `AbstractSpeechProvider`, `get_speech_provider`, `AUDIO_DIR`), `speech` Depends parameter, and new `GET /{card_id}/audio` endpoint.
- **T5**: Added `(data_dir / "audio").mkdir(exist_ok=True)` to `__main__.py` startup sequence.
- **T6**: Ruff clean — fixed 2 E501 line-length errors in test method signatures.
- **Tests**: 226/226 passing, 93% coverage (90% CI gate satisfied). No regressions.

### File List

- `src/lingosips/core/cards.py` — Modified: added `Path` import, `AbstractSpeechProvider` import, `AUDIO_DIR` + `AUDIO_SYNTHESIS_TIMEOUT` constants, `speech` parameter, TTS Step 5 block
- `src/lingosips/api/cards.py` — Modified: added `FileResponse`, `HTTPException`, `AUDIO_DIR`, `AbstractSpeechProvider`, `get_speech_provider` imports; added `speech` Depends; added `GET /{card_id}/audio` endpoint
- `src/lingosips/__main__.py` — Modified: added `(data_dir / "audio").mkdir(exist_ok=True)`
- `tests/core/test_cards.py` — Modified: added `mock_speech` fixture; updated 7 call sites; updated `test_field_update_events_emitted_in_order` assertion; added 4 new audio tests
- `tests/api/test_cards.py` — Modified: added `get_speech_provider` import; added `mock_speech_provider` fixture; added `_auto_mock_speech` autouse; updated `test_success_emits_field_update_events_in_order` assertion; added 3 new stream tests; added `TestGetCardAudio` class

### Change Log

- 2026-05-01: Implemented Story 1.8 — Card Audio Generation (TTS). Added TTS step to card creation pipeline (non-fatal, soft failure), `GET /cards/{card_id}/audio` endpoint serving WAV files, audio dir startup creation, and full test coverage (226 tests passing, 93% coverage).
