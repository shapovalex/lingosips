"""Tests for services/llm/openrouter.py — written BEFORE implementation (TDD).

Covers OpenRouterProvider: complete(), stream_complete(), security of API key.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingosips.services.llm.openrouter import OpenRouterProvider


@pytest.mark.anyio
class TestOpenRouterProvider:
    async def test_complete_sends_correct_headers_and_body(self):
        provider = OpenRouterProvider(api_key="sk-test-key", model="openai/gpt-4o-mini")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "melancólico"}}]
        }
        mock_post_fn = AsyncMock(return_value=mock_response)
        with patch("httpx.AsyncClient.post", new=mock_post_fn) as mock_post:
            result = await provider.complete(
                [{"role": "user", "content": "translate: melancholic"}]
            )
        assert result == "melancólico"
        call_kwargs = mock_post.call_args
        assert "Bearer sk-test-key" in call_kwargs.kwargs["headers"]["Authorization"]
        assert call_kwargs.kwargs["json"]["model"] == "openai/gpt-4o-mini"

    async def test_complete_raises_on_non_200_response(self):
        provider = OpenRouterProvider(api_key="sk-test", model="openai/gpt-4o-mini")
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(RuntimeError, match="OpenRouter error 401"):
                await provider.complete([{"role": "user", "content": "test"}])

    async def test_api_key_not_in_error_message(self):
        """API key must never appear in error messages or logs."""
        provider = OpenRouterProvider(api_key="sk-very-secret-key", model="test")
        mock_response = MagicMock(status_code=403, text="forbidden")
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(RuntimeError) as exc_info:
                await provider.complete([{"role": "user", "content": "test"}])
        assert "sk-very-secret-key" not in str(exc_info.value)

    def test_provider_name_and_model_name(self):
        provider = OpenRouterProvider(api_key="key", model="anthropic/claude-haiku")
        assert provider.provider_name == "OpenRouter"
        assert provider.model_name == "anthropic/claude-haiku"

    async def test_stream_complete_yields_tokens(self):
        """stream_complete should yield each token from SSE data lines."""
        import json

        provider = OpenRouterProvider(api_key="sk-test-key", model="openai/gpt-4o-mini")

        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": " world"}}]}),
            "data: [DONE]",
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        # aiter_lines() must return an async iterator (not a coroutine)
        mock_response.aiter_lines = lambda: aiter(lines)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient.stream", return_value=mock_cm):
            tokens = []
            async for token in provider.stream_complete(
                [{"role": "user", "content": "test"}]
            ):
                tokens.append(token)

        assert tokens == ["Hello", " world"]

    async def test_stream_complete_raises_on_non_200(self):
        """stream_complete raises RuntimeError on non-200 status code."""
        provider = OpenRouterProvider(api_key="sk-test", model="test")

        mock_response = AsyncMock()
        mock_response.status_code = 500

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient.stream", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="OpenRouter stream error 500"):
                async for _ in provider.stream_complete(
                    [{"role": "user", "content": "test"}]
                ):
                    pass


    async def test_stream_complete_skips_non_data_lines(self):
        """Lines not starting with 'data: ' are silently skipped."""
        import json

        provider = OpenRouterProvider(api_key="sk-key", model="test-model")

        lines = [
            ": heartbeat",
            "",
            "data: " + json.dumps({"choices": [{"delta": {"content": "token"}}]}),
            "data: [DONE]",
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = lambda: aiter(lines)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient.stream", return_value=mock_cm):
            tokens = []
            async for token in provider.stream_complete([{"role": "user", "content": "test"}]):
                tokens.append(token)

        assert tokens == ["token"]

    async def test_stream_complete_skips_malformed_json(self):
        """Malformed JSON in SSE data is silently skipped — no crash."""
        provider = OpenRouterProvider(api_key="sk-key", model="test-model")

        import json

        lines = [
            "data: {not-valid-json}",
            "data: " + json.dumps({"choices": [{"delta": {"content": "ok"}}]}),
            "data: [DONE]",
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = lambda: aiter(lines)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient.stream", return_value=mock_cm):
            tokens = []
            async for token in provider.stream_complete([{"role": "user", "content": "test"}]):
                tokens.append(token)

        assert tokens == ["ok"]


async def aiter(lst):
    """Helper: convert list to async iterator."""
    for item in lst:
        yield item
