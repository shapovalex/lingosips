"""Tests for api/cards.py — POST /cards/stream SSE endpoint.

TDD: these tests are written BEFORE implementation to drive api/cards.py.
AC: 1, 2, 3, 4, 5, 6
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.api.app import app
from lingosips.db.models import Card
from lingosips.services.registry import get_llm_provider, get_speech_provider

# ── Mock LLM response ─────────────────────────────────────────────────────────

MOCK_LLM_JSON_RESPONSE = json.dumps(
    {
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
    }
)


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

    async def test_safety_filter_blocks_content_emits_error(self, client: AsyncClient) -> None:
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


# ── Seed fixture ──────────────────────────────────────────────────────────────


@pytest.fixture
async def seed_card(session: AsyncSession) -> Card:
    """Insert a Card directly into the test DB — no LLM mock needed."""
    card = Card(
        target_word="melancólico",
        translation="melancholic",
        forms=json.dumps(
            {"gender": "masculine", "article": "el", "plural": "melancólicos", "conjugations": {}}
        ),
        example_sentences=json.dumps(["Tenía un aire melancólico.", "Era un día melancólico."]),
        target_language="es",
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)
    return card


# ── T2: GET /cards/{card_id} ──────────────────────────────────────────────────


@pytest.mark.anyio
class TestGetCard:
    """Tests for GET /cards/{card_id} (AC: 1, 6)."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        """Clean card and settings tables before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_get_card_success(self, client: AsyncClient, seed_card: Card) -> None:
        """200 + all fields returned for existing card."""
        response = await client.get(f"/cards/{seed_card.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == seed_card.id
        assert body["target_word"] == "melancólico"
        assert body["translation"] == "melancholic"
        assert isinstance(body["forms"], dict)
        assert isinstance(body["example_sentences"], list)
        assert body["target_language"] == "es"
        assert "fsrs_state" in body
        assert "due" in body
        assert "stability" in body
        assert "difficulty" in body
        assert "reps" in body
        assert "lapses" in body
        assert "created_at" in body
        assert "updated_at" in body

    async def test_get_card_not_found_returns_404_rfc7807(self, client: AsyncClient) -> None:
        """404 with RFC 7807 body when card does not exist."""
        response = await client.get("/cards/99999")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/card-not-found"
        assert body["status"] == 404
        assert "99999" in body["detail"]

    async def test_get_card_forms_parsed_as_object_not_string(
        self, client: AsyncClient, seed_card: Card
    ) -> None:
        """forms field must be a dict (not a raw JSON string)."""
        response = await client.get(f"/cards/{seed_card.id}")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["forms"], dict)
        assert body["forms"]["gender"] == "masculine"
        assert body["forms"]["article"] == "el"

    async def test_get_card_example_sentences_parsed_as_list(
        self, client: AsyncClient, seed_card: Card
    ) -> None:
        """example_sentences must be a list (not a raw JSON string)."""
        response = await client.get(f"/cards/{seed_card.id}")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["example_sentences"], list)
        assert len(body["example_sentences"]) == 2

    async def test_get_card_fields_are_snake_case(
        self, client: AsyncClient, seed_card: Card
    ) -> None:
        """Response uses snake_case keys only — no camelCase."""
        response = await client.get(f"/cards/{seed_card.id}")
        assert response.status_code == 200
        body = response.json()
        # These should exist (snake_case)
        assert "target_word" in body
        assert "target_language" in body
        assert "fsrs_state" in body
        assert "last_review" in body
        assert "created_at" in body
        assert "updated_at" in body
        # These must NOT exist (camelCase)
        assert "targetWord" not in body
        assert "targetLanguage" not in body
        assert "fsrsState" not in body
        assert "lastReview" not in body
        assert "createdAt" not in body
        assert "updatedAt" not in body


# ── T3: PATCH /cards/{card_id} ────────────────────────────────────────────────


@pytest.mark.anyio
class TestPatchCard:
    """Tests for PATCH /cards/{card_id} (AC: 2, 3, 7)."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        """Clean card and settings tables before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_patch_translation_updates_field(
        self, client: AsyncClient, session: AsyncSession, seed_card: Card
    ) -> None:
        """PATCH translation → 200 + updated translation in response + DB updated."""
        from sqlalchemy import select

        from lingosips.db.models import Card

        response = await client.patch(f"/cards/{seed_card.id}", json={"translation": "gloomy"})
        assert response.status_code == 200
        body = response.json()
        assert body["translation"] == "gloomy"

        # Verify DB updated
        await session.refresh(seed_card)
        result = await session.execute(select(Card).where(Card.id == seed_card.id))
        db_card = result.scalar_one()
        assert db_card.translation == "gloomy"

    async def test_patch_personal_note_persists(
        self, client: AsyncClient, session: AsyncSession, seed_card: Card
    ) -> None:
        """PATCH personal_note → 200 + note stored in DB."""
        from sqlalchemy import select

        from lingosips.db.models import Card

        response = await client.patch(f"/cards/{seed_card.id}", json={"personal_note": "my note"})
        assert response.status_code == 200
        body = response.json()
        assert body["personal_note"] == "my note"

        result = await session.execute(select(Card).where(Card.id == seed_card.id))
        db_card = result.scalar_one()
        assert db_card.personal_note == "my note"

    async def test_patch_example_sentences_updates_list(
        self, client: AsyncClient, seed_card: Card
    ) -> None:
        """PATCH example_sentences → 200 + response has the updated list."""
        response = await client.patch(
            f"/cards/{seed_card.id}",
            json={"example_sentences": ["New sentence."]},
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["example_sentences"], list)
        assert body["example_sentences"] == ["New sentence."]

    async def test_patch_forms_updates_object(self, client: AsyncClient, seed_card: Card) -> None:
        """PATCH forms → 200 + response forms.gender updated."""
        new_forms = {
            "gender": "feminine",
            "article": "la",
            "plural": "melancólicas",
            "conjugations": {},
        }
        response = await client.patch(f"/cards/{seed_card.id}", json={"forms": new_forms})
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["forms"], dict)
        assert body["forms"]["gender"] == "feminine"

    async def test_patch_only_updates_provided_fields(
        self, client: AsyncClient, session: AsyncSession, seed_card: Card
    ) -> None:
        """PATCH only translation → personal_note and example_sentences unchanged in DB."""
        from sqlalchemy import select

        from lingosips.db.models import Card

        response = await client.patch(f"/cards/{seed_card.id}", json={"translation": "sad"})
        assert response.status_code == 200

        result = await session.execute(select(Card).where(Card.id == seed_card.id))
        db_card = result.scalar_one()
        assert db_card.translation == "sad"
        # personal_note was None and stays None
        assert db_card.personal_note is None
        # example_sentences unchanged — still the original JSON
        assert db_card.example_sentences is not None

    async def test_patch_card_not_found_returns_404(self, client: AsyncClient) -> None:
        """PATCH non-existent card → 404 RFC 7807."""
        response = await client.patch("/cards/99999", json={"translation": "gloomy"})
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/card-not-found"
        assert body["status"] == 404

    async def test_patch_empty_translation_returns_422(
        self, client: AsyncClient, seed_card: Card
    ) -> None:
        """PATCH empty translation → 422 (min_length=1 validation)."""
        response = await client.patch(f"/cards/{seed_card.id}", json={"translation": ""})
        assert response.status_code == 422

    async def test_patch_returns_updated_card_response(
        self, client: AsyncClient, seed_card: Card
    ) -> None:
        """PATCH returns full CardResponse shape (not just the changed field)."""
        response = await client.patch(f"/cards/{seed_card.id}", json={"translation": "gloomy"})
        assert response.status_code == 200
        body = response.json()
        # Verify full CardResponse shape
        assert "id" in body
        assert "target_word" in body
        assert "translation" in body
        assert "forms" in body
        assert "example_sentences" in body
        assert "fsrs_state" in body
        assert "due" in body


# ── T4: DELETE /cards/{card_id} ───────────────────────────────────────────────


@pytest.mark.anyio
class TestDeleteCard:
    """Tests for DELETE /cards/{card_id} (AC: 5, 7)."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        """Clean card, settings, and reviews tables before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_delete_card_returns_204(self, client: AsyncClient, seed_card: Card) -> None:
        """DELETE existing card → 204 No Content."""
        response = await client.delete(f"/cards/{seed_card.id}")
        assert response.status_code == 204
        assert response.content == b""

    async def test_delete_card_removes_from_db(
        self, client: AsyncClient, session: AsyncSession, seed_card: Card
    ) -> None:
        """DELETE card → subsequent GET returns 404."""
        await client.delete(f"/cards/{seed_card.id}")
        get_response = await client.get(f"/cards/{seed_card.id}")
        assert get_response.status_code == 404

    async def test_delete_card_not_found_returns_404(self, client: AsyncClient) -> None:
        """DELETE non-existent card → 404 RFC 7807."""
        response = await client.delete("/cards/99999")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/card-not-found"
        assert body["status"] == 404

    async def test_delete_card_removes_from_practice_queue(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """DELETE card → card no longer in GET /practice/queue (AC: 7)."""
        import json
        from datetime import UTC, datetime, timedelta

        from lingosips.db.models import Card

        # Create a card that is due now (immediately in practice queue)
        past_due = datetime.now(UTC) - timedelta(minutes=1)
        card = Card(
            target_word="prueba",
            translation="test",
            forms=json.dumps({"gender": None, "article": None, "plural": None, "conjugations": {}}),
            example_sentences=json.dumps(["Una prueba.", "Otra prueba."]),
            target_language="es",
            due=past_due,
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        # Verify card is in practice queue
        queue_resp = await client.get("/practice/queue")
        assert queue_resp.status_code == 200
        queue_ids = [c["id"] for c in queue_resp.json()]
        assert card.id in queue_ids

        # Delete the card
        del_resp = await client.delete(f"/cards/{card.id}")
        assert del_resp.status_code == 204

        # Verify card is no longer in practice queue
        queue_resp2 = await client.get("/practice/queue")
        assert queue_resp2.status_code == 200
        queue_ids2 = [c["id"] for c in queue_resp2.json()]
        assert card.id not in queue_ids2


# ── Image generation endpoints ────────────────────────────────────────────────

# Minimal valid 1×1 PNG bytes
_PNG_1X1_API = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x11\x00\x01n\xfe\xc5S\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.anyio
class TestGenerateCardImage:
    """Tests for POST /cards/{card_id}/generate-image — AC: 1, 2, 3, 6."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    @pytest.fixture
    async def mock_image_service(self):
        """Mock ImageService that returns valid PNG bytes."""
        from unittest.mock import AsyncMock
        service = AsyncMock()
        service.generate = AsyncMock(return_value=_PNG_1X1_API)
        return service

    async def test_generate_card_image_success(
        self, client: AsyncClient, seed_card, mock_image_service, tmp_path
    ) -> None:
        """Configured ImageService + PNG bytes → 200, image_url in response."""
        import lingosips.core.cards as core_cards_module
        from lingosips.api.app import app
        from lingosips.services.registry import get_image_service

        original_dir = core_cards_module.IMAGE_DIR
        core_cards_module.IMAGE_DIR = tmp_path / "images"
        app.dependency_overrides[get_image_service] = lambda: mock_image_service
        try:
            resp = await client.post(f"/cards/{seed_card.id}/generate-image")
            assert resp.status_code == 200
            data = resp.json()
            assert data["image_url"] == f"/cards/{seed_card.id}/image"
        finally:
            app.dependency_overrides.pop(get_image_service, None)
            core_cards_module.IMAGE_DIR = original_dir

    async def test_generate_card_image_endpoint_not_configured(
        self, client: AsyncClient, seed_card
    ) -> None:
        """No IMAGE_ENDPOINT_URL credential → 422, type /errors/image-endpoint-not-configured."""
        # Don't override get_image_service — it will raise 422 since no credential is set
        from fastapi import HTTPException

        from lingosips.api.app import app
        from lingosips.services.registry import get_image_service

        def _raise_not_configured():
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "/errors/image-endpoint-not-configured",
                    "title": "Image endpoint not configured",
                    "detail": "Configure an image generation endpoint in Settings",
                    "status": 422,
                },
            )

        app.dependency_overrides[get_image_service] = _raise_not_configured
        try:
            resp = await client.post(f"/cards/{seed_card.id}/generate-image")
            assert resp.status_code == 422
            body = resp.json()
            assert body["type"] == "/errors/image-endpoint-not-configured"
        finally:
            app.dependency_overrides.pop(get_image_service, None)

    async def test_generate_card_image_safety_rejected(
        self, client: AsyncClient, seed_card, tmp_path
    ) -> None:
        """ImageService returns non-image bytes → 422 with 'Image filtered' message."""
        from unittest.mock import AsyncMock

        import lingosips.core.cards as core_cards_module
        from lingosips.api.app import app
        from lingosips.services.registry import get_image_service

        bad_service = AsyncMock()
        bad_service.generate = AsyncMock(return_value=b"not an image")

        original_dir = core_cards_module.IMAGE_DIR
        core_cards_module.IMAGE_DIR = tmp_path / "images"
        app.dependency_overrides[get_image_service] = lambda: bad_service
        try:
            resp = await client.post(f"/cards/{seed_card.id}/generate-image")
            assert resp.status_code == 422
            body = resp.json()
            assert "Image filtered" in body.get("detail", "")
        finally:
            app.dependency_overrides.pop(get_image_service, None)
            core_cards_module.IMAGE_DIR = original_dir

    async def test_generate_card_image_timeout(
        self, client: AsyncClient, seed_card
    ) -> None:
        """ImageService raises TimeoutException → 422 with timeout detail."""
        from unittest.mock import AsyncMock

        import httpx as _httpx

        from lingosips.api.app import app
        from lingosips.services.registry import get_image_service

        timeout_service = AsyncMock()
        timeout_service.generate = AsyncMock(side_effect=_httpx.TimeoutException("timed out"))

        app.dependency_overrides[get_image_service] = lambda: timeout_service
        try:
            resp = await client.post(f"/cards/{seed_card.id}/generate-image")
            assert resp.status_code == 422
            body = resp.json()
            detail_lower = body.get("detail", "").lower()
            assert "timeout" in detail_lower or "timed out" in detail_lower
        finally:
            app.dependency_overrides.pop(get_image_service, None)

    async def test_generate_card_image_card_not_found(
        self, client: AsyncClient, mock_image_service
    ) -> None:
        """card_id=9999 → 404 RFC 7807."""
        from lingosips.api.app import app
        from lingosips.services.registry import get_image_service

        app.dependency_overrides[get_image_service] = lambda: mock_image_service
        try:
            resp = await client.post("/cards/9999/generate-image")
            assert resp.status_code == 404
            body = resp.json()
            assert body["type"] == "/errors/card-not-found"
        finally:
            app.dependency_overrides.pop(get_image_service, None)

    async def test_generate_card_image_api_error(
        self, client: AsyncClient, seed_card
    ) -> None:
        """ImageService raises RuntimeError → 422 with error detail."""
        from unittest.mock import AsyncMock

        from lingosips.api.app import app
        from lingosips.services.registry import get_image_service

        error_service = AsyncMock()
        error_service.generate = AsyncMock(side_effect=RuntimeError("Image endpoint returned 503"))

        app.dependency_overrides[get_image_service] = lambda: error_service
        try:
            resp = await client.post(f"/cards/{seed_card.id}/generate-image")
            assert resp.status_code == 422
            body = resp.json()
            assert "Image generation failed" in body.get("detail", "")
        finally:
            app.dependency_overrides.pop(get_image_service, None)


@pytest.mark.anyio
class TestGetCardImage:
    """Tests for GET /cards/{card_id}/image — AC: 7."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_get_card_image_success(
        self, client: AsyncClient, seed_card, tmp_path
    ) -> None:
        """Image file exists → 200 with image/png content-type."""
        import lingosips.core.cards as core_cards_module

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        image_file = image_dir / f"{seed_card.id}.png"
        image_file.write_bytes(_PNG_1X1_API)

        # Patch IMAGE_DIR in core.cards so the endpoint uses our tmp dir
        original_dir = core_cards_module.IMAGE_DIR
        core_cards_module.IMAGE_DIR = image_dir

        # Also patch in api.cards module
        import lingosips.api.cards as api_cards_module
        original_api_dir = getattr(api_cards_module, "IMAGE_DIR", None)
        api_cards_module.IMAGE_DIR = image_dir  # type: ignore[attr-defined]
        try:
            resp = await client.get(f"/cards/{seed_card.id}/image")
            assert resp.status_code == 200
            assert "image/" in resp.headers.get("content-type", "")
        finally:
            core_cards_module.IMAGE_DIR = original_dir
            if original_api_dir is not None:
                api_cards_module.IMAGE_DIR = original_api_dir  # type: ignore[attr-defined]

    async def test_get_card_image_not_found(self, client: AsyncClient, seed_card) -> None:
        """No image file → 404 RFC 7807."""
        from pathlib import Path

        import lingosips.core.cards as core_cards_module

        # Point IMAGE_DIR at a directory that won't have any image
        empty_dir = Path("/tmp/lingosips_test_empty_images_xyz")
        empty_dir.mkdir(exist_ok=True)

        original_dir = core_cards_module.IMAGE_DIR
        import lingosips.api.cards as api_cards_module
        original_api_dir = getattr(api_cards_module, "IMAGE_DIR", None)
        core_cards_module.IMAGE_DIR = empty_dir
        api_cards_module.IMAGE_DIR = empty_dir  # type: ignore[attr-defined]
        try:
            resp = await client.get(f"/cards/{seed_card.id}/image")
            assert resp.status_code == 404
            body = resp.json()
            assert body["type"] == "/errors/image-not-found"
        finally:
            core_cards_module.IMAGE_DIR = original_dir
            if original_api_dir is not None:
                api_cards_module.IMAGE_DIR = original_api_dir  # type: ignore[attr-defined]


@pytest.mark.anyio
class TestPatchCardImageSkipped:
    """Tests for PATCH /cards/{card_id} with image_skipped — AC: 5."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_patch_card_image_skipped_true(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """PATCH with {image_skipped: true} → 200, image_skipped=true, image_url=null."""
        from lingosips.db.models import Card

        card = Card(
            target_word="test",
            target_language="es",
            image_url="/cards/1/image",
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        resp = await client.patch(f"/cards/{card.id}", json={"image_skipped": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["image_skipped"] is True
        assert data["image_url"] is None

    async def test_patch_card_image_skipped_false_undo(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """PATCH with {image_skipped: false} → 200, image_skipped=false."""
        from lingosips.db.models import Card

        card = Card(
            target_word="test",
            target_language="es",
            image_skipped=True,
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        resp = await client.patch(f"/cards/{card.id}", json={"image_skipped": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["image_skipped"] is False
