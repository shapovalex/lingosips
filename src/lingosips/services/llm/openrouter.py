"""OpenRouter LLM provider — routes requests to cloud models via OpenRouter API."""

import json
from collections.abc import AsyncIterator

import httpx
import structlog

from lingosips.services.llm.base import AbstractLLMProvider, LLMMessage

logger = structlog.get_logger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(AbstractLLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key  # NEVER log this
        self._model = model

    @property
    def provider_name(self) -> str:
        return "OpenRouter"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(self, messages: list[LLMMessage], *, max_tokens: int = 1024) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "messages": messages, "max_tokens": max_tokens},
            )
            if response.status_code != 200:
                # DO NOT include API key in error message
                raise RuntimeError(
                    f"OpenRouter error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def stream_complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                OPENROUTER_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"OpenRouter stream error {response.status_code}")
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        return
                    try:
                        chunk = json.loads(payload)
                        token = chunk["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
