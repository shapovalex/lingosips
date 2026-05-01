"""Abstract base class and result dataclasses for all speech providers.

Rules:
- Never import fastapi, SQLModel, or AsyncSession here — pure service layer
- synthesize() returns raw audio bytes (WAV for pyttsx3; as returned by Azure TTS)
- evaluate_pronunciation() returns SyllableResult with per-syllable detail
- provider_name and model_name are used by ServiceStatusIndicator (Story 1.10)
- TTS-only providers raise NotImplementedError for evaluate_pronunciation()
- Eval-only providers raise NotImplementedError for synthesize()
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SyllableDetail:
    """Per-syllable pronunciation result — used by SyllableFeedback component (Story 4.2)."""

    syllable: str  # e.g., "a", "gua", "ca", "te"
    correct: bool  # True if correct pronunciation
    score: float = 1.0  # pronunciation accuracy 0.0–1.0


@dataclass
class SyllableResult:
    """Full pronunciation evaluation result returned by AbstractSpeechProvider."""

    overall_correct: bool
    syllables: list[SyllableDetail]
    correction_message: str | None


class AbstractSpeechProvider(ABC):
    """Base class for all speech providers.

    Contract rules:
    - Never import fastapi, SQLModel, or AsyncSession — this is a pure service
    - synthesize() returns raw audio bytes (WAV format for pyttsx3; as returned by Azure TTS)
    - evaluate_pronunciation() returns SyllableResult with per-syllable detail
    - provider_name and model_name are used by ServiceStatusIndicator (Story 1.10)
    - TTS-only providers raise NotImplementedError for evaluate_pronunciation()
    - Eval-only providers raise NotImplementedError for synthesize()
    """

    @abstractmethod
    async def synthesize(self, text: str, language: str) -> bytes:
        """Synthesize text to audio bytes.

        Returns raw audio bytes (format depends on provider: WAV for pyttsx3,
        provider-dependent for Azure Speech).
        Raises NotImplementedError if provider does not support TTS.
        """
        ...

    @abstractmethod
    async def evaluate_pronunciation(
        self, audio: bytes, target: str, language: str
    ) -> SyllableResult:
        """Evaluate spoken audio against target text.

        Returns SyllableResult with per-syllable correctness data.
        Raises NotImplementedError if provider does not support evaluation.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for ServiceStatusIndicator."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model/service identifier for display in ServiceStatusIndicator."""
        ...
