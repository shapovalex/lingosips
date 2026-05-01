"""Tests for services/speech/pyttsx3_local.py — written BEFORE implementation (TDD).

Covers Pyttsx3Provider: synthesize(), _synthesize_sync(), evaluate_pronunciation(), properties.
All pyttsx3 calls are mocked to avoid real audio I/O in unit tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider


@pytest.mark.anyio
class TestPyttsx3Provider:
    def test_provider_name(self):
        provider = Pyttsx3Provider()
        assert provider.provider_name == "Local pyttsx3"

    def test_model_name(self):
        provider = Pyttsx3Provider()
        assert provider.model_name == "pyttsx3"

    async def test_evaluate_pronunciation_raises_not_implemented(self):
        provider = Pyttsx3Provider()
        with pytest.raises(NotImplementedError, match="does not support pronunciation evaluation"):
            await provider.evaluate_pronunciation(b"audio", "hello", "en")

    async def test_synthesize_returns_bytes(self, tmp_path):
        """Mocking pyttsx3.init() to avoid real audio I/O in unit tests."""
        fake_audio = b"RIFF fake wav content"
        mock_engine = MagicMock()

        def fake_save_to_file(text, path):
            Path(path).write_bytes(fake_audio)

        mock_engine.save_to_file.side_effect = fake_save_to_file
        mock_engine.runAndWait.return_value = None
        mock_engine.stop.return_value = None

        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            mock_pyttsx3.init.return_value = mock_engine
            provider = Pyttsx3Provider()
            result = await provider.synthesize("hello world", "en")

        assert result == fake_audio
        mock_engine.save_to_file.assert_called_once()
        mock_engine.runAndWait.assert_called_once()
        mock_engine.stop.assert_called_once()

    async def test_synthesize_cleans_up_temp_file_on_success(self, tmp_path):
        """Verify no temp files are left behind after synthesis."""
        import tempfile

        fake_audio = b"RIFF wav"
        mock_engine = MagicMock()

        created_files = []
        original_named_temp = tempfile.NamedTemporaryFile

        def track_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            created_files.append(f.name)
            return f

        def fake_save(text, path):
            Path(path).write_bytes(fake_audio)

        mock_engine.save_to_file.side_effect = fake_save
        mock_engine.runAndWait.return_value = None
        mock_engine.stop.return_value = None

        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            with patch(
                "lingosips.services.speech.pyttsx3_local.tempfile.NamedTemporaryFile",
                side_effect=track_temp,
            ):
                mock_pyttsx3.init.return_value = mock_engine
                provider = Pyttsx3Provider()
                await provider.synthesize("cleanup test", "en")

        # All temp files cleaned up
        for f in created_files:
            assert not Path(f).exists(), f"Temp file {f} was not cleaned up"

    async def test_synthesize_raises_runtime_error_on_pyttsx3_init_failure(self):
        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            mock_pyttsx3.init.side_effect = Exception("no audio driver")
            provider = Pyttsx3Provider()
            with pytest.raises(RuntimeError, match="pyttsx3 init failed"):
                await provider.synthesize("test", "en")

    async def test_synthesize_raises_runtime_error_on_synthesis_failure(self):
        """RuntimeError raised when save_to_file fails, not raw exception."""
        mock_engine = MagicMock()
        mock_engine.save_to_file.side_effect = OSError("disk write error")
        mock_engine.stop.return_value = None

        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            mock_pyttsx3.init.return_value = mock_engine
            provider = Pyttsx3Provider()
            with pytest.raises(RuntimeError, match="pyttsx3 synthesis failed"):
                await provider.synthesize("test", "en")

    async def test_synthesize_engine_stop_called_even_on_failure(self):
        """Engine.stop() must be called in finally block even when synthesis fails."""
        mock_engine = MagicMock()
        mock_engine.save_to_file.side_effect = OSError("disk full")
        mock_engine.stop.return_value = None

        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            mock_pyttsx3.init.return_value = mock_engine
            provider = Pyttsx3Provider()
            with pytest.raises(RuntimeError):
                await provider.synthesize("test", "en")

        mock_engine.stop.assert_called_once()

    def test_no_pyttsx3_init_at_class_instantiation(self):
        """pyttsx3.init() must NOT be called at class __init__ time."""
        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            Pyttsx3Provider()
            mock_pyttsx3.init.assert_not_called()
