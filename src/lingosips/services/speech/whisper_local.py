"""Local speech evaluation using faster-whisper.

synthesize() is not supported — WhisperLocalProvider is evaluation-only.
evaluate_pronunciation() is implemented in Story 4.1.
"""

import structlog

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableResult

logger = structlog.get_logger(__name__)


class WhisperLocalProvider(AbstractSpeechProvider):
    """Local speech evaluation using faster-whisper.

    synthesize() is not supported — WhisperLocalProvider is evaluation-only.
    evaluate_pronunciation() is implemented in Story 4.1.
    """

    @property
    def provider_name(self) -> str:
        return "Local Whisper"

    @property
    def model_name(self) -> str:
        return "faster-whisper"

    async def synthesize(self, text: str, language: str) -> bytes:
        raise NotImplementedError("WhisperLocalProvider does not support TTS synthesis")

    async def evaluate_pronunciation(
        self, audio: bytes, target: str, language: str
    ) -> SyllableResult:
        raise NotImplementedError(
            "WhisperLocalProvider.evaluate_pronunciation() is implemented in Story 4.1"
        )
