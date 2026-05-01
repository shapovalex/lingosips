"""Speech provider package — exports the public contract for all speech providers."""

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableDetail, SyllableResult

__all__ = ["AbstractSpeechProvider", "SyllableDetail", "SyllableResult"]
