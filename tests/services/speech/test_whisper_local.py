"""Tests for services/speech/whisper_local.py — TDD for Story 4.1.

Tests written BEFORE implementation (TDD).
Covers WhisperLocalProvider.evaluate_pronunciation() and helpers.
"""

import pytest

from lingosips.services.speech.base import SyllableDetail, SyllableResult
from lingosips.services.speech.whisper_local import (
    WhisperLocalProvider,
    _build_syllable_result,
    _syllabify,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def provider():
    return WhisperLocalProvider()


@pytest.fixture
def mock_whisper_model(monkeypatch):
    """Mock WhisperModel to avoid actual model loading in tests."""

    class MockSegment:
        text = "target_word"

    class MockModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path, **kwargs):
            return [MockSegment()], None

    monkeypatch.setattr("lingosips.services.speech.whisper_local.WhisperModel", MockModel)


@pytest.fixture
def mock_whisper_model_mismatch(monkeypatch):
    """Mock WhisperModel that returns a different word — simulates wrong pronunciation."""

    class MockSegment:
        text = "wrong_word"

    class MockModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path, **kwargs):
            return [MockSegment()], None

    monkeypatch.setattr("lingosips.services.speech.whisper_local.WhisperModel", MockModel)


@pytest.fixture
def mock_whisper_timeout(monkeypatch):
    """Mock WhisperModel that raises TimeoutError to simulate a slow model."""

    async def _fake_wait_for(coro, timeout):
        raise TimeoutError()

    monkeypatch.setattr("asyncio.wait_for", _fake_wait_for)


# ── Provider metadata ─────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestWhisperLocalProvider:
    def test_provider_name(self, provider):
        assert provider.provider_name == "Local Whisper"

    def test_model_name(self, provider):
        assert provider.model_name == "faster-whisper"

    async def test_synthesize_raises_not_implemented(self, provider):
        with pytest.raises(NotImplementedError, match="does not support TTS synthesis"):
            await provider.synthesize("hello", "en")

    def test_no_model_loading_at_instantiation(self):
        """WhisperLocalProvider constructor takes no args — no model loading at init."""
        provider = WhisperLocalProvider()
        assert provider is not None


# ── evaluate_pronunciation() — main tests ────────────────────────────────────


@pytest.mark.anyio
class TestWhisperLocalEvaluate:
    async def test_exact_match_returns_all_correct(self, provider, mock_whisper_model):
        """Mock returns 'target_word' → target 'target_word' → overall_correct=True."""
        result = await provider.evaluate_pronunciation(b"audio_bytes", "target_word", "en")
        assert isinstance(result, SyllableResult)
        assert result.overall_correct is True
        assert result.correction_message is None
        assert all(d.correct for d in result.syllables)

    async def test_mismatch_returns_incorrect(self, provider, mock_whisper_model_mismatch):
        """Mock returns 'wrong_word' → target 'hello' → overall_correct=False."""
        result = await provider.evaluate_pronunciation(b"audio_bytes", "hello", "en")
        assert isinstance(result, SyllableResult)
        assert result.overall_correct is False
        assert result.correction_message is not None

    async def test_empty_audio_raises_value_error(self, provider):
        """Empty audio bytes → ValueError."""
        with pytest.raises(ValueError, match="audio bytes must not be empty"):
            await provider.evaluate_pronunciation(b"", "hello", "en")

    async def test_result_shape_matches_syllable_result(self, provider, mock_whisper_model):
        """Result must be a SyllableResult with correct shape."""
        result = await provider.evaluate_pronunciation(b"audio_bytes", "agua", "es")
        assert isinstance(result, SyllableResult)
        assert isinstance(result.syllables, list)
        assert len(result.syllables) >= 1
        for detail in result.syllables:
            assert isinstance(detail, SyllableDetail)
            assert isinstance(detail.syllable, str)
            assert isinstance(detail.correct, bool)
            assert isinstance(detail.score, float)

    async def test_timeout_raises_runtime_error(self, provider, mock_whisper_timeout):
        """If evaluation times out → RuntimeError raised."""
        with pytest.raises(RuntimeError, match="timed out"):
            await provider.evaluate_pronunciation(b"audio_bytes", "hello", "en")

    async def test_synthesize_still_raises(self, provider):
        """synthesize() must still raise NotImplementedError after Story 4.1 changes."""
        with pytest.raises(NotImplementedError):
            await provider.synthesize("hello", "en")

    async def test_language_short_code_accepted(self, provider, mock_whisper_model):
        """Short language codes like 'es' must be accepted without error."""
        result = await provider.evaluate_pronunciation(b"audio_bytes", "hola", "es")
        assert isinstance(result, SyllableResult)

    async def test_language_bcp47_accepted(self, provider, mock_whisper_model):
        """BCP-47 codes like 'es-MX' must be accepted (region stripped internally)."""
        result = await provider.evaluate_pronunciation(b"audio_bytes", "hola", "es-MX")
        assert isinstance(result, SyllableResult)

    async def test_correction_message_none_on_correct(self, provider, mock_whisper_model):
        """correction_message is None when overall_correct=True."""
        result = await provider.evaluate_pronunciation(b"audio_bytes", "target_word", "en")
        assert result.correction_message is None

    async def test_correction_message_set_on_incorrect(self, provider, mock_whisper_model_mismatch):
        """correction_message is a non-empty string when overall_correct=False."""
        result = await provider.evaluate_pronunciation(b"audio_bytes", "hello", "en")
        assert result.correction_message is not None
        assert len(result.correction_message) > 0


# ── _syllabify helper ─────────────────────────────────────────────────────────


class TestSyllabify:
    def test_simple_spanish_word(self):
        result = _syllabify("agua")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "".join(result) == "agua"

    def test_single_consonant_cluster(self):
        """Words with no vowels → returned as single syllable."""
        result = _syllabify("gym")
        assert result == ["gym"]

    def test_empty_string(self):
        result = _syllabify("")
        assert result == [""]

    def test_result_is_list_of_strings(self):
        for word in ["hola", "melancólico", "agua", "perro"]:
            result = _syllabify(word)
            assert isinstance(result, list)
            for s in result:
                assert isinstance(s, str)

    def test_all_syllables_non_empty(self):
        """Syllables must not be empty strings for non-empty input."""
        result = _syllabify("hola")
        for s in result:
            assert len(s) > 0

    def test_syllabify_strips_punctuation(self):
        """Words with trailing punctuation must strip it before syllabification."""
        result = _syllabify("hello.")
        assert "." not in "".join(result)


# ── _build_syllable_result helper ────────────────────────────────────────────


class TestBuildSyllableResult:
    def test_exact_match(self):
        result = _build_syllable_result("hello", "hello")
        assert result.overall_correct is True
        assert result.correction_message is None
        assert all(d.correct for d in result.syllables)

    def test_case_insensitive_match(self):
        result = _build_syllable_result("Hello", "hello")
        assert result.overall_correct is True

    def test_mismatch(self):
        result = _build_syllable_result("bye", "hello")
        assert result.overall_correct is False
        assert result.correction_message is not None

    def test_partial_match_in_transcription(self):
        """Target word contained in transcription → overall_correct=True."""
        result = _build_syllable_result("yes hello world", "hello")
        assert result.overall_correct is True

    def test_empty_transcription_is_incorrect(self):
        result = _build_syllable_result("", "hello")
        assert result.overall_correct is False
        assert result.correction_message is not None

    def test_syllables_list_non_empty(self):
        result = _build_syllable_result("agua", "agua")
        assert len(result.syllables) >= 1

    def test_score_values_are_floats(self):
        result = _build_syllable_result("hola", "hola")
        for d in result.syllables:
            assert isinstance(d.score, float)
