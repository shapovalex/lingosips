"""Tests for core/cards.py — card creation pipeline.

TDD: these tests are written BEFORE implementation to drive core/cards.py.
AC: 1, 2, 4, 5, 6
"""

import json
from unittest.mock import AsyncMock

import pytest


@pytest.mark.anyio
class TestParseCardResponse:
    """Tests for _parse_llm_response() helper."""

    def test_clean_json_parsed_correctly(self) -> None:
        """Clean JSON object returned without code fences."""
        from lingosips.core.cards import _parse_llm_response

        raw = json.dumps(
            {
                "translation": "melancholic",
                "forms": {
                    "gender": "masculine",
                    "article": "el",
                    "plural": "melancólicos",
                    "conjugations": {},
                },
                "example_sentences": ["Sentence one.", "Sentence two."],
            }
        )
        result = _parse_llm_response(raw)
        assert result["translation"] == "melancholic"
        assert result["forms"]["gender"] == "masculine"
        assert len(result["example_sentences"]) == 2

    def test_json_in_markdown_code_block_parsed(self) -> None:
        """JSON wrapped in ```json ... ``` code fence is handled."""
        from lingosips.core.cards import _parse_llm_response

        payload = json.dumps(
            {
                "translation": "sad",
                "forms": {"gender": None, "article": None, "plural": None, "conjugations": {}},
                "example_sentences": ["Es triste.", "Fue muy triste."],
            }
        )
        raw = f"```json\n{payload}\n```"
        result = _parse_llm_response(raw)
        assert result["translation"] == "sad"

    def test_invalid_json_raises_value_error(self) -> None:
        """Non-JSON content raises ValueError."""
        from lingosips.core.cards import _parse_llm_response

        with pytest.raises(ValueError, match="No JSON object found"):
            _parse_llm_response("This is not JSON at all")

    def test_missing_fields_get_defaults(self) -> None:
        """Missing fields in LLM response are filled with defaults."""
        from lingosips.core.cards import _parse_llm_response

        raw = json.dumps({"translation": "hello"})  # missing forms and example_sentences
        result = _parse_llm_response(raw)
        assert result["translation"] == "hello"
        expected_forms = {
            "gender": None,
            "article": None,
            "plural": None,
            "conjugations": {},
            "register_context": None,
        }
        assert result["forms"] == expected_forms
        assert result["example_sentences"] == []

    def test_preamble_and_trailing_text_handled(self) -> None:
        """JSON wrapped by preamble/trailing text is extracted correctly."""
        from lingosips.core.cards import _parse_llm_response

        payload = json.dumps(
            {
                "translation": "test",
                "forms": {"gender": None, "article": None, "plural": None, "conjugations": {}},
                "example_sentences": ["A.", "B."],
            }
        )
        raw = f"Here is the answer: {payload} Hope that helps!"
        result = _parse_llm_response(raw)
        assert result["translation"] == "test"

    def test_trailing_brace_in_surrounding_text_handled(self) -> None:
        """Trailing text containing '}' after the JSON object is ignored correctly.

        rfind('}') would select the last '}' in the string, breaking the JSON slice.
        JSONDecoder.raw_decode() finds the matching closing brace correctly.
        """
        from lingosips.core.cards import _parse_llm_response

        payload = json.dumps(
            {
                "translation": "happy",
                "forms": {"gender": None, "article": None, "plural": None, "conjugations": {}},
                "example_sentences": ["Es feliz.", "Fue feliz."],
            }
        )
        # Trailing text that itself ends with '}' — would break rfind-based extraction
        raw = f"{payload} (see grammar note {{end}})"
        result = _parse_llm_response(raw)
        assert result["translation"] == "happy"

    def test_sentence_card_type_extracted(self) -> None:
        """LLM returns card_type=sentence → extracted and returned."""
        from lingosips.core.cards import _parse_llm_response

        raw = json.dumps(
            {
                "card_type": "sentence",
                "translation": "don't play dumb",
                "forms": {
                    "gender": None,
                    "article": None,
                    "plural": None,
                    "conjugations": {},
                    "register_context": "informal, River Plate Spanish",
                },
                "example_sentences": ["No te hagas el tonto, te vi.", "Siempre se hace el tonto."],
            }
        )
        result = _parse_llm_response(raw)
        assert result["card_type"] == "sentence"
        assert result["forms"]["register_context"] == "informal, River Plate Spanish"

    def test_collocation_card_type_extracted(self) -> None:
        """LLM returns card_type=collocation → extracted."""
        from lingosips.core.cards import _parse_llm_response

        raw = json.dumps(
            {
                "card_type": "collocation",
                "translation": "to bite the dust",
                "forms": {
                    "gender": None,
                    "article": None,
                    "plural": None,
                    "conjugations": {},
                    "register_context": "informal",
                },
                "example_sentences": [
                    "El proyecto mordió el polvo.",
                    "Muchos proyectos muerden el polvo.",
                ],
            }
        )
        result = _parse_llm_response(raw)
        assert result["card_type"] == "collocation"

    def test_missing_card_type_defaults_to_word(self) -> None:
        """Old-format LLM response without card_type → defaults to 'word'."""
        from lingosips.core.cards import _parse_llm_response

        raw = json.dumps(
            {
                "translation": "sad",
                "forms": {"gender": None, "article": None, "plural": None, "conjugations": {}},
                "example_sentences": ["A.", "B."],
            }
        )
        result = _parse_llm_response(raw)
        assert result["card_type"] == "word"

    def test_register_context_key_always_present(self) -> None:
        """forms always has register_context key (None for word cards)."""
        from lingosips.core.cards import _parse_llm_response

        raw = json.dumps(
            {
                "card_type": "word",
                "translation": "happy",
                "forms": {
                    "gender": "masculine",
                    "article": "el",
                    "plural": "felices",
                    "conjugations": {},
                },
                "example_sentences": ["A.", "B."],
            }
        )
        result = _parse_llm_response(raw)
        assert "register_context" in result["forms"]
        assert result["forms"]["register_context"] is None


@pytest.mark.anyio
class TestSseEvent:
    """Tests for _sse_event() helper — AC5."""

    def test_produces_correct_format(self) -> None:
        """SSE event formatted as: event: X\\ndata: Y\\n\\n"""
        from lingosips.core.cards import _sse_event

        result = _sse_event("field_update", {"field": "translation", "value": "melancholic"})
        assert result.startswith("event: field_update\n")
        assert "data: " in result
        assert result.endswith("\n\n")

    def test_exact_envelope_format(self) -> None:
        """Exact envelope: 'event: {type}\\ndata: {json}\\n\\n'"""
        from lingosips.core.cards import _sse_event

        result = _sse_event("complete", {"card_id": 42})
        lines = result.split("\n")
        assert lines[0] == "event: complete"
        assert lines[1].startswith("data: ")
        data = json.loads(lines[1][6:])
        assert data == {"card_id": 42}
        # The event ends with \n\n → split gives ['event: ...', 'data: ...', '', '']
        assert lines[2] == ""
        assert lines[3] == ""

    def test_snake_case_keys_preserved(self) -> None:
        """JSON payload must use snake_case keys — never camelCase."""
        from lingosips.core.cards import _sse_event

        result = _sse_event("field_update", {"field": "example_sentences", "value": ["A.", "B."]})
        data_line = [line for line in result.split("\n") if line.startswith("data: ")][0]
        data = json.loads(data_line[6:])
        assert "field" in data
        assert "value" in data
        # No camelCase keys
        assert "exampleSentences" not in str(data)

    def test_error_event_format(self) -> None:
        """Error event with message field."""
        from lingosips.core.cards import _sse_event

        result = _sse_event("error", {"message": "Local Qwen timeout after 10s"})
        assert result == 'event: error\ndata: {"message": "Local Qwen timeout after 10s"}\n\n'


@pytest.mark.anyio
class TestCreateCardStream:
    """Tests for create_card_stream() — AC: 1, 2, 4, 5, 6."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        """Ensure a clean cards table before each test."""
        from sqlalchemy import text

        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        """Mock LLM provider returning a clean JSON card response."""
        from lingosips.services.llm.base import AbstractLLMProvider

        mock = AsyncMock(spec=AbstractLLMProvider)
        mock.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "card_type": "word",
                    "translation": "melancholic",
                    "forms": {
                        "gender": "masculine",
                        "article": "el",
                        "plural": "melancólicos",
                        "conjugations": {},
                        "register_context": None,
                    },
                    "example_sentences": [
                        "Tenía un aire melancólico.",
                        "Era un día melancólico.",
                    ],
                }
            )
        )
        mock.provider_name = "MockLLM"
        mock.model_name = "mock-model"
        return mock

    @pytest.fixture
    def mock_llm_sentence(self) -> AsyncMock:
        """Mock LLM provider returning a sentence card JSON response."""
        from lingosips.services.llm.base import AbstractLLMProvider

        mock = AsyncMock(spec=AbstractLLMProvider)
        mock.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "card_type": "sentence",
                    "translation": "don't play dumb",
                    "forms": {
                        "gender": None,
                        "article": None,
                        "plural": None,
                        "conjugations": {},
                        "register_context": "informal, River Plate Spanish",
                    },
                    "example_sentences": [
                        "No te hagas el tonto, te vi.",
                        "Siempre se hace el tonto.",
                    ],
                }
            )
        )
        mock.provider_name = "MockLLM"
        mock.model_name = "mock-model"
        return mock

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

    async def _collect_events(self, gen) -> list[dict]:
        """Collect all SSE events from an async generator into parsed dicts."""
        events = []
        async for chunk in gen:
            for block in chunk.split("\n\n"):
                block = block.strip()
                if not block:
                    continue
                event_type = "message"
                data_str = ""
                for line in block.splitlines():
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

    async def test_field_update_events_emitted_in_order(
        self, mock_llm, mock_speech, session
    ) -> None:
        """AC1 + AC4: field_update events emitted in order:
        translation → forms → example_sentences → audio.
        """
        from lingosips.core.cards import CardCreateRequest, create_card_stream

        request = CardCreateRequest(target_word="melancólico")
        gen = create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
        events = await self._collect_events(gen)

        field_updates = [e for e in events if e["event"] == "field_update"]
        assert len(field_updates) == 5  # card_type, translation, forms, example_sentences, audio
        assert field_updates[0]["data"]["field"] == "card_type"
        assert field_updates[1]["data"]["field"] == "translation"
        assert field_updates[2]["data"]["field"] == "forms"
        assert field_updates[3]["data"]["field"] == "example_sentences"
        assert field_updates[4]["data"]["field"] == "audio"

    async def test_complete_event_emitted_with_card_id(
        self, mock_llm, mock_speech, session
    ) -> None:
        """AC1: complete event emitted with integer card_id."""
        from lingosips.core.cards import CardCreateRequest, create_card_stream

        request = CardCreateRequest(target_word="melancólico")
        events = await self._collect_events(
            create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
        )

        complete_events = [e for e in events if e["event"] == "complete"]
        assert len(complete_events) == 1
        assert isinstance(complete_events[0]["data"]["card_id"], int)

    async def test_card_persisted_to_db(self, mock_llm, mock_speech, session) -> None:
        """AC1: card is saved to the cards table."""
        from sqlalchemy import select

        from lingosips.core.cards import CardCreateRequest, create_card_stream
        from lingosips.db.models import Card

        request = CardCreateRequest(target_word="melancólico")
        events = await self._collect_events(
            create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
        )

        card_id = next(e["data"]["card_id"] for e in events if e["event"] == "complete")
        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        assert card is not None
        assert card.target_word == "melancólico"
        assert card.translation == "melancholic"

    async def test_fsrs_initial_state_set_on_card(self, mock_llm, mock_speech, session) -> None:
        """AC6: FSRS initial state is correct on newly created card."""
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
        assert card.stability == 0.0
        assert card.difficulty == 0.0
        assert card.fsrs_state == "New"
        assert card.reps == 0
        assert card.lapses == 0
        assert card.last_review is None

    async def test_llm_timeout_emits_error_event(self, mock_speech, session) -> None:
        """AC4: asyncio.TimeoutError → error event with exact message."""
        from unittest.mock import AsyncMock

        from lingosips.services.llm.base import AbstractLLMProvider

        mock = AsyncMock(spec=AbstractLLMProvider)
        mock.complete = AsyncMock(side_effect=TimeoutError())

        from lingosips.core.cards import CardCreateRequest, create_card_stream

        request = CardCreateRequest(target_word="test")
        events = await self._collect_events(
            create_card_stream(request, mock, session, "es", speech=mock_speech)
        )

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["message"] == "Local Qwen timeout after 10s"

    async def test_safety_blocked_emits_error_no_card(self, mock_llm, mock_speech, session) -> None:
        """AC2: blocked field → error event, no card persisted."""
        from unittest.mock import patch

        from sqlalchemy import select

        from lingosips.core.cards import CardCreateRequest, create_card_stream
        from lingosips.db.models import Card

        request = CardCreateRequest(target_word="test")
        with patch("lingosips.core.cards.safety.check_text", return_value=(False, "blocked")):
            events = await self._collect_events(
                create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
            )

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "safety filter" in error_events[0]["data"]["message"]

        # No card should be persisted
        result = await session.execute(select(Card))
        assert result.scalars().all() == []

    async def test_invalid_llm_response_emits_error(self, mock_speech, session) -> None:
        """Parse failure → error event emitted."""
        from unittest.mock import AsyncMock

        from lingosips.services.llm.base import AbstractLLMProvider

        mock = AsyncMock(spec=AbstractLLMProvider)
        mock.complete = AsyncMock(return_value="not json at all, no braces")

        from lingosips.core.cards import CardCreateRequest, create_card_stream

        request = CardCreateRequest(target_word="test")
        events = await self._collect_events(
            create_card_stream(request, mock, session, "es", speech=mock_speech)
        )

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "parse" in error_events[0]["data"]["message"].lower()

    async def test_audio_field_update_emitted_after_card_persist(
        self, mock_llm, mock_speech, session
    ) -> None:
        """AC4: field_update for 'audio' emitted before complete event."""
        from lingosips.core.cards import CardCreateRequest, create_card_stream

        request = CardCreateRequest(target_word="melancólico")
        events = await self._collect_events(
            create_card_stream(request, mock_llm, session, "es", speech=mock_speech)
        )

        audio_events = [
            e for e in events if e["event"] == "field_update" and e["data"].get("field") == "audio"
        ]
        complete_events = [e for e in events if e["event"] == "complete"]

        assert len(audio_events) == 1
        assert len(complete_events) == 1
        # audio field_update comes before complete
        audio_idx = next(
            i
            for i, e in enumerate(events)
            if e["event"] == "field_update" and e["data"].get("field") == "audio"
        )
        complete_idx = next(i for i, e in enumerate(events) if e["event"] == "complete")
        assert audio_idx < complete_idx
        # Value is relative URL
        assert audio_events[0]["data"]["value"].startswith("/cards/")
        assert audio_events[0]["data"]["value"].endswith("/audio")

    async def test_audio_url_persisted_to_card_in_db(self, mock_llm, mock_speech, session) -> None:
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

    async def test_tts_failure_does_not_fail_card_creation(
        self, mock_llm, session, tmp_path, monkeypatch
    ) -> None:
        """AC5: TTS RuntimeError → complete event still emitted, no SSE error, card saved."""
        import lingosips.core.cards as core_cards_module
        from lingosips.services.speech.base import AbstractSpeechProvider

        audio_dir = tmp_path / "audio_fail"
        audio_dir.mkdir()
        monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)

        mock_speech_fail = AsyncMock(spec=AbstractSpeechProvider)
        mock_speech_fail.synthesize = AsyncMock(side_effect=RuntimeError("pyttsx3 init failed"))

        from sqlalchemy import select

        from lingosips.core.cards import CardCreateRequest, create_card_stream
        from lingosips.db.models import Card

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
        audio_updates = [
            e for e in events if e["event"] == "field_update" and e["data"].get("field") == "audio"
        ]
        assert len(audio_updates) == 0
        # AC5: audio_url remains None in DB — card saved without audio
        card_id = complete_events[0]["data"]["card_id"]
        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one()
        assert card.audio_url is None

    async def test_tts_empty_audio_bytes_does_not_fail_card_creation(
        self, mock_llm, session, tmp_path, monkeypatch
    ) -> None:
        """AC5: synthesize() returning b"" → treated as failure, card saved with audio_url=None."""
        import lingosips.core.cards as core_cards_module
        from lingosips.services.speech.base import AbstractSpeechProvider

        audio_dir = tmp_path / "audio_empty_bytes"
        audio_dir.mkdir()
        monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)

        mock_speech_empty = AsyncMock(spec=AbstractSpeechProvider)
        mock_speech_empty.synthesize = AsyncMock(return_value=b"")  # empty bytes

        from sqlalchemy import select

        from lingosips.core.cards import CardCreateRequest, create_card_stream
        from lingosips.db.models import Card

        request = CardCreateRequest(target_word="test")
        events = await self._collect_events(
            create_card_stream(request, mock_llm, session, "es", speech=mock_speech_empty)
        )

        # No error event — empty bytes is non-fatal like any TTS failure
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 0
        # Complete event still emitted
        complete_events = [e for e in events if e["event"] == "complete"]
        assert len(complete_events) == 1
        # No audio field_update — empty WAV not written to disk
        audio_updates = [
            e for e in events if e["event"] == "field_update" and e["data"].get("field") == "audio"
        ]
        assert len(audio_updates) == 0
        # No empty file written to disk
        assert not any(audio_dir.iterdir())
        # AC5: audio_url remains None in DB
        card_id = complete_events[0]["data"]["card_id"]
        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one()
        assert card.audio_url is None

    async def test_tts_timeout_does_not_fail_card_creation(
        self, mock_llm, session, tmp_path, monkeypatch
    ) -> None:
        """AC5: TTS TimeoutError → complete event still emitted, no SSE error, card saved."""
        import lingosips.core.cards as core_cards_module
        from lingosips.services.speech.base import AbstractSpeechProvider

        audio_dir = tmp_path / "audio_timeout"
        audio_dir.mkdir()
        monkeypatch.setattr(core_cards_module, "AUDIO_DIR", audio_dir)

        mock_speech_timeout = AsyncMock(spec=AbstractSpeechProvider)
        mock_speech_timeout.synthesize = AsyncMock(side_effect=TimeoutError("TTS timeout"))

        from sqlalchemy import select

        from lingosips.core.cards import CardCreateRequest, create_card_stream
        from lingosips.db.models import Card

        request = CardCreateRequest(target_word="test")
        events = await self._collect_events(
            create_card_stream(request, mock_llm, session, "es", speech=mock_speech_timeout)
        )

        # No error event
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 0
        # Complete event still emitted
        complete_events = [e for e in events if e["event"] == "complete"]
        assert len(complete_events) == 1
        # No audio field_update
        audio_updates = [
            e for e in events if e["event"] == "field_update" and e["data"].get("field") == "audio"
        ]
        assert len(audio_updates) == 0
        # AC5: audio_url remains None in DB — card saved without audio
        card_id = complete_events[0]["data"]["card_id"]
        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one()
        assert card.audio_url is None

    async def test_sentence_card_type_persisted(
        self, mock_llm_sentence, mock_speech, session
    ) -> None:
        """Sentence card: card_type='sentence' saved to DB and emitted as field_update."""
        from sqlalchemy import select

        from lingosips.core.cards import CardCreateRequest, create_card_stream
        from lingosips.db.models import Card

        request = CardCreateRequest(target_word="no te hagas el tonto")
        events = await self._collect_events(
            create_card_stream(request, mock_llm_sentence, session, "es", speech=mock_speech)
        )

        # Verify card_type field_update emitted
        field_updates = [e for e in events if e["event"] == "field_update"]
        card_type_event = next(
            (f for f in field_updates if f["data"]["field"] == "card_type"), None
        )
        assert card_type_event is not None
        assert card_type_event["data"]["value"] == "sentence"

        # Verify DB card has card_type="sentence"
        card_id = next(e["data"]["card_id"] for e in events if e["event"] == "complete")
        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one()
        assert card.card_type == "sentence"


@pytest.mark.anyio
class TestCardCreateRequest:
    """Tests for CardCreateRequest Pydantic model — whitespace stripping + validation."""

    def test_valid_word_accepted(self) -> None:
        from lingosips.core.cards import CardCreateRequest

        req = CardCreateRequest(target_word="melancólico")
        assert req.target_word == "melancólico"

    def test_whitespace_stripped(self) -> None:
        from lingosips.core.cards import CardCreateRequest

        req = CardCreateRequest(target_word="  melancólico  ")
        assert req.target_word == "melancólico"

    def test_empty_string_raises(self) -> None:
        from pydantic import ValidationError

        from lingosips.core.cards import CardCreateRequest

        with pytest.raises(ValidationError):
            CardCreateRequest(target_word="")

    def test_whitespace_only_raises(self) -> None:
        from pydantic import ValidationError

        from lingosips.core.cards import CardCreateRequest

        with pytest.raises(ValidationError):
            CardCreateRequest(target_word="   ")

    def test_too_long_word_raises(self) -> None:
        """target_word exceeding max_length=500 → ValidationError."""
        from pydantic import ValidationError

        from lingosips.core.cards import CardCreateRequest

        with pytest.raises(ValidationError):
            CardCreateRequest(target_word="x" * 501)

    def test_word_at_max_length_accepted(self) -> None:
        """target_word of exactly max_length=500 characters is accepted."""
        from lingosips.core.cards import CardCreateRequest

        req = CardCreateRequest(target_word="x" * 500)
        assert len(req.target_word) == 500


# ── Image generation tests ────────────────────────────────────────────────────

# Minimal valid 1×1 PNG bytes
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x11\x00\x01n\xfe\xc5S\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.anyio
class TestGenerateCardImage:
    """Tests for generate_card_image() in core/cards.py — AC: 2, 5, 6."""

    async def test_generate_card_image_success(self, session, tmp_path) -> None:
        """Mock ImageService returns PNG bytes → card.image_url set, file written."""
        import shutil

        import lingosips.core.cards as core_cards_module
        from lingosips.core.cards import generate_card_image
        from lingosips.db.models import Card

        # Seed a card
        card = Card(target_word="melancólico", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(return_value=_PNG_1X1)

        tmp_image_dir = tmp_path / "images"
        original_dir = core_cards_module.IMAGE_DIR
        core_cards_module.IMAGE_DIR = tmp_image_dir
        try:
            result = await generate_card_image(card.id, mock_service, session)
            assert result.image_url == f"/cards/{card.id}/image"
            assert result.image_skipped is False
            image_file = tmp_image_dir / f"{card.id}.png"
            assert image_file.exists()
        finally:
            core_cards_module.IMAGE_DIR = original_dir
            shutil.rmtree(tmp_image_dir, ignore_errors=True)

    async def test_generate_card_image_safety_rejected_non_image_bytes(self, session) -> None:
        """Mock ImageService returns non-image bytes → raises ValueError('Image filtered')."""
        from lingosips.core.cards import generate_card_image
        from lingosips.db.models import Card

        card = Card(target_word="test", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(return_value=b"not an image at all")

        with pytest.raises(ValueError, match="Image filtered"):
            await generate_card_image(card.id, mock_service, session)

    async def test_generate_card_image_timeout(self, session) -> None:
        """Mock ImageService raises httpx.TimeoutException → ValueError with timeout message."""
        import httpx

        from lingosips.core.cards import generate_card_image
        from lingosips.db.models import Card

        card = Card(target_word="test", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with pytest.raises(ValueError, match="timed out|timeout"):
            await generate_card_image(card.id, mock_service, session)

    async def test_generate_card_image_api_error(self, session) -> None:
        """Mock ImageService raises RuntimeError → ValueError with error message."""
        from lingosips.core.cards import generate_card_image
        from lingosips.db.models import Card

        card = Card(target_word="test", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(side_effect=RuntimeError("Image endpoint returned 500"))

        with pytest.raises(ValueError, match="Image generation failed"):
            await generate_card_image(card.id, mock_service, session)

    async def test_generate_card_image_card_not_found(self, session) -> None:
        """Card ID 9999 not found → ValueError."""
        from lingosips.core.cards import generate_card_image

        mock_service = AsyncMock()
        with pytest.raises(ValueError, match="does not exist"):
            await generate_card_image(9999, mock_service, session)


@pytest.mark.anyio
class TestUpdateCardImageFields:
    """Tests for update_card() image_skipped and image_url handling — AC: 5."""

    async def test_update_card_image_skipped_true_clears_image_url(self, session) -> None:
        """update_card() with image_skipped=True clears image_url."""
        from lingosips.core.cards import update_card
        from lingosips.db.models import Card

        card = Card(
            target_word="test",
            target_language="es",
            image_url="/cards/1/image",
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        result = await update_card(card.id, {"image_skipped": True}, session)
        assert result.image_skipped is True
        assert result.image_url is None

    async def test_update_card_image_skipped_false_leaves_image_url_unchanged(
        self, session
    ) -> None:
        """update_card() with image_skipped=False does NOT clear image_url."""
        from lingosips.core.cards import update_card
        from lingosips.db.models import Card

        card = Card(
            target_word="test",
            target_language="es",
            image_url="/cards/1/image",
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        result = await update_card(card.id, {"image_skipped": False}, session)
        assert result.image_skipped is False
        assert result.image_url == "/cards/1/image"
