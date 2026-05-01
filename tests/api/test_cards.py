"""Tests for api/cards.py — POST /cards/stream SSE endpoint.

TDD: these tests are written BEFORE implementation to drive api/cards.py.
AC: 1, 2, 3, 4, 5, 6
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from lingosips.api.app import app
from lingosips.services.registry import get_llm_provider, get_speech_provider

# ── Mock LLM response ─────────────────────────────────────────────────────────

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


# ── Fixtures ──────────────────────────────────────────────────────────────────


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


# ── SSE parsing helper ────────────────────────────────────────────────────────


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


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestPostCardsStream:
    """Tests for POST /cards/stream (AC: 1, 2, 3, 4, 5, 6)."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine):
        """Clean card table before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    @pytest.fixture(autouse=True)
    def _auto_mock_speech(self, mock_speech_provider):
        """Auto-inject speech mock for all tests in this class."""
        return mock_speech_provider

    async def test_success_emits_field_update_events_in_order(
        self, client: AsyncClient, mock_llm_provider
    ) -> None:
        """AC1 + AC4: field_update events emitted in order:
        translation → forms → example_sentences → audio.
        """
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        assert response.status_code == 200
        events = parse_sse_events(response.content)
        field_updates = [e for e in events if e["event"] == "field_update"]
        assert len(field_updates) == 4  # translation, forms, example_sentences, audio
        assert field_updates[0]["data"]["field"] == "translation"
        assert field_updates[1]["data"]["field"] == "forms"
        assert field_updates[2]["data"]["field"] == "example_sentences"
        assert field_updates[3]["data"]["field"] == "audio"

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
        """AC3: missing target_word → 422 with RFC 7807 Problem Details body."""
        response = await client.post("/cards/stream", json={})
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "/errors/validation"
        assert body["status"] == 422
        assert "errors" in body

    async def test_empty_target_word_returns_422(self, client: AsyncClient) -> None:
        """AC3: empty string → 422 with RFC 7807 Problem Details body."""
        response = await client.post("/cards/stream", json={"target_word": ""})
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "/errors/validation"
        assert body["status"] == 422
        assert "errors" in body

    async def test_whitespace_only_target_word_returns_422(self, client: AsyncClient) -> None:
        """AC3: whitespace-only string → 422 with RFC 7807 Problem Details body."""
        response = await client.post("/cards/stream", json={"target_word": "   "})
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "/errors/validation"
        assert body["status"] == 422
        assert "errors" in body

    async def test_llm_timeout_emits_error_event(self, client: AsyncClient) -> None:
        """AC4: LLM timeout → error SSE event with exact message."""

        mock = AsyncMock()
        mock.complete = AsyncMock(side_effect=TimeoutError())
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
        mock = AsyncMock()
        mock.complete = AsyncMock(return_value=MOCK_LLM_JSON_RESPONSE)
        app.dependency_overrides[get_llm_provider] = lambda: mock

        blocked = (False, "blocked-term")
        try:
            with patch("lingosips.core.cards.safety.check_text", return_value=blocked):
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

    async def test_audio_field_update_emitted_before_complete(
        self, client: AsyncClient, mock_llm_provider
    ) -> None:
        """AC4: field_update event for 'audio' is emitted before the complete event."""
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        assert response.status_code == 200
        events = parse_sse_events(response.content)

        audio_events = [
            e for e in events if e["event"] == "field_update" and e["data"].get("field") == "audio"
        ]
        complete_events = [e for e in events if e["event"] == "complete"]

        assert len(audio_events) == 1
        assert len(complete_events) == 1

        audio_idx = next(
            i
            for i, e in enumerate(events)
            if e["event"] == "field_update" and e["data"].get("field") == "audio"
        )
        complete_idx = next(i for i, e in enumerate(events) if e["event"] == "complete")
        assert audio_idx < complete_idx

    async def test_audio_url_value_matches_endpoint_pattern(
        self, client: AsyncClient, mock_llm_provider
    ) -> None:
        """AC4: audio field_update value starts with '/cards/' and ends with '/audio'."""
        response = await client.post("/cards/stream", json={"target_word": "melancólico"})
        events = parse_sse_events(response.content)

        audio_events = [
            e for e in events if e["event"] == "field_update" and e["data"].get("field") == "audio"
        ]
        assert len(audio_events) == 1
        url = audio_events[0]["data"]["value"]
        assert url.startswith("/cards/")
        assert url.endswith("/audio")

    async def test_tts_failure_card_created_no_stream_error(
        self, client: AsyncClient, mock_llm_provider, tmp_path, monkeypatch
    ) -> None:
        """AC5: TTS failure → complete event still emitted, no error event, no 500."""
        import lingosips.core.cards as core_cards_module
        from lingosips.services.speech.base import AbstractSpeechProvider

        audio_dir = tmp_path / "audio_fail_api"
        audio_dir.mkdir()
        monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)

        mock_speech_fail = AsyncMock(spec=AbstractSpeechProvider)
        mock_speech_fail.synthesize = AsyncMock(side_effect=RuntimeError("pyttsx3 init failed"))
        app.dependency_overrides[get_speech_provider] = lambda: mock_speech_fail

        try:
            response = await client.post("/cards/stream", json={"target_word": "test"})
        finally:
            app.dependency_overrides.pop(get_speech_provider, None)

        assert response.status_code == 200
        events = parse_sse_events(response.content)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 0

        complete_events = [e for e in events if e["event"] == "complete"]
        assert len(complete_events) == 1


@pytest.mark.anyio
class TestGetCardAudio:
    """Tests for GET /cards/{card_id}/audio (AC: 2, 3, 4)."""

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
        import lingosips.api.cards as api_cards_module
        import lingosips.core.cards as core_cards_module

        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)
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
