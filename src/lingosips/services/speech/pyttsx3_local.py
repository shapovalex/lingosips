"""Local TTS fallback using pyttsx3 (system TTS engine — espeak/nsss/sapi5).

CRITICAL: pyttsx3 is synchronous and NOT thread-safe across shared engine instances.
- Always use asyncio.get_running_loop().run_in_executor() — NOT get_event_loop() (deprecated 3.10+)
- Create a NEW pyttsx3.init() engine per call — do NOT share engine instances across threads
"""

import asyncio
import tempfile
from pathlib import Path

import pyttsx3
import structlog

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableResult

logger = structlog.get_logger(__name__)


class Pyttsx3Provider(AbstractSpeechProvider):
    """Local TTS fallback using pyttsx3 (system TTS engine — espeak/nsss/sapi5).

    Creates a fresh pyttsx3 engine per synthesis call — this is intentionally
    thread-safe by avoiding shared state. pyttsx3 engines are NOT safe to share.
    """

    @property
    def provider_name(self) -> str:
        return "Local pyttsx3"

    @property
    def model_name(self) -> str:
        return "pyttsx3"

    async def synthesize(self, text: str, language: str) -> bytes:
        """Synthesize text using pyttsx3 — runs in thread executor (blocking I/O)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text, language)

    def _synthesize_sync(self, text: str, language: str) -> bytes:
        """Blocking synthesis — runs in background thread. Creates engine per call.

        Note: the `language` parameter is accepted for interface compliance but pyttsx3
        uses the system default voice. Platform-specific voice selection is not implemented
        here — language-specific voices require AzureSpeechProvider.
        """
        engine = None
        tmp_path = None
        try:
            engine = pyttsx3.init()
        except Exception as exc:
            raise RuntimeError(f"pyttsx3 init failed: {exc}") from exc

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            audio_bytes = Path(tmp_path).read_bytes()
            logger.info("pyttsx3.synthesized", text_length=len(text), audio_bytes=len(audio_bytes))
            return audio_bytes

        except Exception as exc:
            logger.error("pyttsx3.synthesis_failed", error=str(exc))
            raise RuntimeError(f"pyttsx3 synthesis failed: {exc}") from exc
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink()
                except FileNotFoundError:
                    pass

    async def evaluate_pronunciation(
        self, audio: bytes, target: str, language: str
    ) -> SyllableResult:
        raise NotImplementedError("Pyttsx3Provider does not support pronunciation evaluation")
