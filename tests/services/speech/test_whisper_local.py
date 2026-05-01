"""Tests for services/speech/whisper_local.py — written BEFORE implementation (TDD).

Covers WhisperLocalProvider: synthesize() raises NotImplementedError,
evaluate_pronunciation() raises NotImplementedError, properties.
"""

import pytest

from lingosips.services.speech.whisper_local import WhisperLocalProvider


@pytest.mark.anyio
class TestWhisperLocalProvider:
    def test_provider_name(self):
        provider = WhisperLocalProvider()
        assert provider.provider_name == "Local Whisper"

    def test_model_name(self):
        provider = WhisperLocalProvider()
        assert provider.model_name == "faster-whisper"

    async def test_synthesize_raises_not_implemented(self):
        provider = WhisperLocalProvider()
        with pytest.raises(NotImplementedError, match="does not support TTS synthesis"):
            await provider.synthesize("hello", "en")

    async def test_evaluate_pronunciation_raises_not_implemented(self):
        """Story 4.1 implements this — must raise NotImplementedError for now."""
        provider = WhisperLocalProvider()
        with pytest.raises(NotImplementedError, match="Story 4.1"):
            await provider.evaluate_pronunciation(b"audio", "hello", "en")

    def test_no_model_loading_at_instantiation(self):
        """WhisperLocalProvider constructor takes no args — model loading is Story 4.1."""
        # Should instantiate without any model loading
        provider = WhisperLocalProvider()
        assert provider is not None
