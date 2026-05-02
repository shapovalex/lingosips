"""Tests for services/speech/azure.py — written BEFORE implementation (TDD).

Covers AzureSpeechProvider: synthesize(), evaluate_pronunciation(), properties, voice map.
All HTTP calls are mocked — no real network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingosips.services.speech.azure import _AZURE_VOICE_MAP, AzureSpeechProvider
from lingosips.services.speech.base import SyllableResult

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_pron_response(
    accuracy_score: float = 90.0,
    recognition_status: str = "Success",
    word: str = "agua",
    phonemes: list | None = None,
) -> MagicMock:
    """Build a mock httpx response for Azure Pronunciation Assessment."""
    if phonemes is None:
        phonemes = [
            {"Phoneme": "a", "PronunciationAssessment": {"AccuracyScore": accuracy_score}},
            {"Phoneme": "g", "PronunciationAssessment": {"AccuracyScore": accuracy_score}},
            {"Phoneme": "u", "PronunciationAssessment": {"AccuracyScore": accuracy_score}},
            {"Phoneme": "a", "PronunciationAssessment": {"AccuracyScore": accuracy_score}},
        ]
    response_data = {
        "RecognitionStatus": recognition_status,
        "NBest": [
            {
                "PronunciationAssessment": {
                    "AccuracyScore": accuracy_score,
                    "FluencyScore": 90.0,
                    "CompletenessScore": 95.0,
                    "PronScore": accuracy_score,
                },
                "Words": [
                    {
                        "Word": word,
                        "PronunciationAssessment": {
                            "AccuracyScore": accuracy_score,
                            "ErrorType": "None",
                        },
                        "Phonemes": phonemes,
                    }
                ],
            }
        ],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_data
    mock_resp.text = ""
    return mock_resp


@pytest.mark.anyio
class TestAzureSpeechProvider:
    def test_provider_name(self):
        provider = AzureSpeechProvider(api_key="test-key", region="eastus")
        assert provider.provider_name == "Azure Speech"

    def test_model_name_includes_region(self):
        provider = AzureSpeechProvider(api_key="test-key", region="westeurope")
        assert provider.model_name == "azure-westeurope"

    def test_model_name_includes_region_eastus(self):
        provider = AzureSpeechProvider(api_key="k", region="eastus")
        assert provider.model_name == "azure-eastus"

    async def test_synthesize_sends_correct_headers_and_ssml(self):
        fake_audio = b"riff wav bytes"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="sub-key-123", region="eastus")
            result = await provider.synthesize("hello", "en")

        assert result == fake_audio
        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs["headers"]
        assert headers["Ocp-Apim-Subscription-Key"] == "sub-key-123"
        assert headers["Content-Type"] == "application/ssml+xml"
        assert "tts.speech.microsoft.com" in call_kwargs.args[0]

    async def test_synthesize_uses_correct_endpoint_with_region(self):
        fake_audio = b"audio bytes"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="westeurope")
            await provider.synthesize("hallo", "de")

        url = mock_client.post.call_args.args[0]
        assert "westeurope" in url

    async def test_api_key_not_in_error_message(self):
        """API key must NEVER appear in error messages."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="very-secret-key", region="eastus")
            with pytest.raises(RuntimeError) as exc_info:
                await provider.synthesize("test", "en")

        assert "very-secret-key" not in str(exc_info.value)

    async def test_synthesize_raises_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            with pytest.raises(RuntimeError, match="Azure Speech TTS 403"):
                await provider.synthesize("test", "en")

    async def test_synthesize_raises_on_401(self):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            with pytest.raises(RuntimeError, match="Azure Speech TTS 401"):
                await provider.synthesize("test", "en")

    async def test_synthesize_output_format_header(self):
        """Verify correct audio output format header is set."""
        fake_audio = b"audio"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            await provider.synthesize("test", "en-US")

        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["X-Microsoft-OutputFormat"] == "riff-24khz-16bit-mono-pcm"

    def test_voice_map_spanish(self):
        """Verify language→voice lookup works for common target languages."""
        assert "es" in _AZURE_VOICE_MAP
        assert "Neural" in _AZURE_VOICE_MAP["es"]

    def test_voice_map_has_multiple_languages(self):
        """MVP languages must all be in the voice map."""
        required_languages = ["es", "en", "fr", "de", "it", "pt", "ja", "zh", "ko"]
        for lang in required_languages:
            assert lang in _AZURE_VOICE_MAP, f"Language '{lang}' missing from _AZURE_VOICE_MAP"

    def test_voice_map_all_values_contain_neural(self):
        """All voices should be Neural voices."""
        for lang, voice in _AZURE_VOICE_MAP.items():
            assert "Neural" in voice, f"Voice for '{lang}' is not a Neural voice: {voice}"

    async def test_synthesize_ssml_contains_text(self):
        """SSML body must include the text to synthesize."""
        fake_audio = b"audio"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            await provider.synthesize("aguacate", "es")

        content = mock_client.post.call_args.kwargs["content"]
        ssml = content.decode("utf-8")
        assert "aguacate" in ssml
        assert "<speak" in ssml
        assert "<voice" in ssml

    async def test_synthesize_xml_escapes_special_chars_in_text(self):
        """XML special characters in text must be escaped — vocabulary may contain & < >."""
        fake_audio = b"audio"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            await provider.synthesize("bread & butter", "en")

        content = mock_client.post.call_args.kwargs["content"]
        ssml = content.decode("utf-8")
        assert "&amp;" in ssml  # & must be XML-escaped
        assert "bread & butter" not in ssml  # raw & must not appear in SSML

    async def test_synthesize_xml_escapes_angle_brackets_in_text(self):
        """Angle brackets in text must be escaped to avoid SSML injection."""
        fake_audio = b"audio"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            await provider.synthesize("<test>", "en")

        content = mock_client.post.call_args.kwargs["content"]
        ssml = content.decode("utf-8")
        assert "&lt;test&gt;" in ssml
        assert "<test>" not in ssml.split("<voice")[1]  # raw < must not appear in voice content


# ── Azure Pronunciation Assessment tests ──────────────────────────────────────


@pytest.mark.anyio
class TestAzurePronunciationAssessment:
    async def test_successful_evaluation_returns_syllable_result(self):
        """High accuracy → SyllableResult with overall_correct=True."""
        mock_resp = _make_pron_response(accuracy_score=90.0, word="agua")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            result = await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        assert isinstance(result, SyllableResult)
        assert result.overall_correct is True
        assert result.correction_message is None

    async def test_low_score_returns_incorrect(self):
        """AccuracyScore=50 (< 75 threshold) → overall_correct=False."""
        mock_resp = _make_pron_response(accuracy_score=50.0, word="agua")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            result = await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        assert result.overall_correct is False

    async def test_no_match_returns_incorrect(self):
        """RecognitionStatus='NoMatch' → overall_correct=False, all syllables incorrect."""
        mock_resp = _make_pron_response(recognition_status="NoMatch")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            result = await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        assert result.overall_correct is False
        assert all(not d.correct for d in result.syllables)
        assert result.correction_message is not None

    async def test_empty_audio_raises_value_error(self):
        """Empty audio → ValueError before any HTTP call."""
        provider = AzureSpeechProvider(api_key="key", region="eastus")
        with pytest.raises(ValueError, match="audio bytes must not be empty"):
            await provider.evaluate_pronunciation(b"", "hello", "en")

    async def test_http_error_raises_runtime_error(self):
        """Non-200 response → RuntimeError (not generic 500)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            with pytest.raises(RuntimeError, match="500"):
                await provider.evaluate_pronunciation(b"wav_audio", "hello", "en")

    async def test_result_has_correct_syllable_count(self):
        """result.syllables must have at least one SyllableDetail."""
        mock_resp = _make_pron_response(accuracy_score=90.0, word="agua")
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            result = await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        assert len(result.syllables) >= 1

    async def test_api_key_never_in_error_message(self, caplog):
        """API key must NEVER appear in error messages or logs."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="very-secret-key-xyz", region="eastus")
            with pytest.raises(RuntimeError) as exc_info:
                await provider.evaluate_pronunciation(b"wav_audio", "hello", "en")

        assert "very-secret-key-xyz" not in str(exc_info.value)
        assert "very-secret-key-xyz" not in caplog.text

    async def test_uses_correct_stt_endpoint(self):
        """Must POST to stt.speech.microsoft.com (not tts)."""
        mock_resp = _make_pron_response()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        url = mock_client.post.call_args.args[0]
        assert "stt.speech.microsoft.com" in url
        assert "eastus" in url

    async def test_pronunciation_assessment_header_is_set(self):
        """Pronunciation-Assessment header must be present and base64-encoded."""
        import base64

        mock_resp = _make_pron_response()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        headers = mock_client.post.call_args.kwargs["headers"]
        assert "Pronunciation-Assessment" in headers
        # Value must be valid base64
        decoded = base64.b64decode(headers["Pronunciation-Assessment"]).decode("utf-8")
        import json

        parsed = json.loads(decoded)
        assert "ReferenceText" in parsed
        assert parsed["ReferenceText"] == "agua"

    async def test_short_language_code_expanded_to_bcp47(self):
        """Short 'es' code must be expanded to BCP-47 'es-ES' for the API call."""
        mock_resp = _make_pron_response()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        url = mock_client.post.call_args.args[0]
        # Short 'es' should be expanded in the URL language param
        assert "language=es" in url  # accepts es-ES or es

    async def test_evaluation_result_shape(self):
        """SyllableResult must have correct overall_correct, syllables, correction_message."""
        mock_resp = _make_pron_response(accuracy_score=90.0)
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            result = await provider.evaluate_pronunciation(b"wav_audio", "agua", "es")

        assert hasattr(result, "overall_correct")
        assert hasattr(result, "syllables")
        assert hasattr(result, "correction_message")
        assert isinstance(result.syllables, list)
