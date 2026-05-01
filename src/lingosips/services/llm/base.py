"""Abstract base classes for all LLM providers.

Contract rules:
- Never import fastapi, SQLModel, or AsyncSession — this is a pure service
- messages format is OpenAI-compatible (list of {"role": ..., "content": ...})
- stream_complete is an async generator — callers must async-for over it
- provider_name and model_name are used by ServiceStatusIndicator (Story 1.10)
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal, TypedDict


class LLMMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMModelNotReadyError(Exception):
    """Raised when the local model file is not yet downloaded."""


class AbstractLLMProvider(ABC):
    """Base class for all LLM providers.

    Contract rules:
    - Never import fastapi, SQLModel, or AsyncSession — this is a pure service
    - messages format is OpenAI-compatible (list of {"role": ..., "content": ...})
    - stream_complete is an async generator — callers must async-for over it
    - provider_name and model_name are used by ServiceStatusIndicator (Story 1.10)
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 1024,
    ) -> str:
        """Return full text response (non-streaming)."""
        ...

    @abstractmethod
    async def stream_complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Yield text tokens as they are generated (streaming)."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name: "OpenRouter" or "Local Qwen"."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier string for display in ServiceStatusIndicator."""
        ...
