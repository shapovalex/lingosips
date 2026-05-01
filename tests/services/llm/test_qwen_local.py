"""Tests for services/llm/qwen_local.py — written BEFORE implementation (TDD).

Covers QwenLocalProvider: lazy loading, complete(), stream_complete(), error cases.
"""

from unittest.mock import MagicMock, patch

import pytest

from lingosips.services.llm.base import LLMModelNotReadyError
from lingosips.services.llm.qwen_local import QwenLocalProvider


@pytest.mark.anyio
class TestQwenLocalProvider:
    async def test_raises_model_not_ready_when_file_missing(self, tmp_path):
        provider = QwenLocalProvider(model_path=tmp_path / "missing.gguf")
        with pytest.raises(LLMModelNotReadyError):
            await provider.complete([{"role": "user", "content": "test"}])

    async def test_complete_calls_create_chat_completion(self, tmp_path):
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake")  # file must exist
        provider = QwenLocalProvider(model_path=model_file)
        mock_llama = MagicMock()
        mock_llama.create_chat_completion.return_value = {
            "choices": [{"message": {"content": "respuesta"}}]
        }
        provider._llm = mock_llama  # inject mock directly
        result = await provider.complete([{"role": "user", "content": "translate"}])
        assert result == "respuesta"
        mock_llama.create_chat_completion.assert_called_once()

    def test_model_loads_lazily(self, tmp_path):
        """Llama must NOT be instantiated at __init__ time.

        Llama is imported inside _get_llm() to keep startup fast, so we
        patch at the llama_cpp module level rather than the qwen_local module.
        """
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake")
        with patch("llama_cpp.Llama") as mock_llama_cls:
            QwenLocalProvider(model_path=model_file)
            mock_llama_cls.assert_not_called()  # lazy!

    def test_provider_name_and_model_name(self, tmp_path):
        path = tmp_path / "qwen2.5-3b-instruct-q4_k_m.gguf"
        provider = QwenLocalProvider(model_path=path)
        assert provider.provider_name == "Local Qwen"
        assert provider.model_name == "qwen2.5-3b-instruct-q4_k_m"

    def test_llm_is_none_at_init(self, tmp_path):
        """_llm attribute must be None immediately after construction."""
        path = tmp_path / "qwen.gguf"
        provider = QwenLocalProvider(model_path=path)
        assert provider._llm is None

    async def test_raises_model_not_ready_for_stream_when_file_missing(self, tmp_path):
        """stream_complete also raises LLMModelNotReadyError when file missing."""
        provider = QwenLocalProvider(model_path=tmp_path / "missing.gguf")
        with pytest.raises(LLMModelNotReadyError):
            async for _ in provider.stream_complete([{"role": "user", "content": "test"}]):
                pass

    def test_get_llm_initializes_llama_on_first_call(self, tmp_path):
        """_get_llm() triggers Llama initialization on first call when file exists."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake-model")
        mock_llama_instance = MagicMock()
        with patch("llama_cpp.Llama", return_value=mock_llama_instance) as mock_llama_cls:
            provider = QwenLocalProvider(model_path=model_file)
            result = provider._get_llm()
        # Llama should have been called exactly once with correct params
        mock_llama_cls.assert_called_once_with(
            model_path=str(model_file),
            n_ctx=4096,
            n_gpu_layers=0,
            verbose=False,
        )
        assert result is mock_llama_instance
        assert provider._llm is mock_llama_instance

    def test_get_llm_returns_cached_instance_on_second_call(self, tmp_path):
        """_get_llm() returns the same cached instance on repeated calls."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake-model")
        mock_llama_instance = MagicMock()
        with patch("llama_cpp.Llama", return_value=mock_llama_instance) as mock_llama_cls:
            provider = QwenLocalProvider(model_path=model_file)
            first = provider._get_llm()
            second = provider._get_llm()
        # Llama constructor called only once (cached after first call)
        mock_llama_cls.assert_called_once()
        assert first is second

    async def test_stream_complete_yields_tokens(self, tmp_path):
        """stream_complete yields tokens from the background thread streaming."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake")
        provider = QwenLocalProvider(model_path=model_file)

        # Build mock llama that yields streaming chunks
        chunks = [
            {"choices": [{"delta": {"content": "Hola"}}]},
            {"choices": [{"delta": {"content": " mundo"}}]},
            {"choices": [{"delta": {}}]},  # empty token — should be skipped
        ]
        mock_llama = MagicMock()
        mock_llama.create_chat_completion.return_value = iter(chunks)
        provider._llm = mock_llama

        tokens = []
        async for token in provider.stream_complete([{"role": "user", "content": "translate"}]):
            tokens.append(token)

        assert tokens == ["Hola", " mundo"]

    async def test_stream_complete_propagates_thread_exception(self, tmp_path):
        """Exception raised in the background thread is propagated to the async caller."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake")
        provider = QwenLocalProvider(model_path=model_file)

        mock_llama = MagicMock()
        mock_llama.create_chat_completion.side_effect = RuntimeError("GGUF format error")
        provider._llm = mock_llama

        with pytest.raises(RuntimeError, match="GGUF format error"):
            async for _ in provider.stream_complete([{"role": "user", "content": "test"}]):
                pass

    async def test_complete_raises_on_empty_choices(self, tmp_path):
        """complete() raises RuntimeError when Qwen returns an empty choices list."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake")
        provider = QwenLocalProvider(model_path=model_file)
        mock_llama = MagicMock()
        mock_llama.create_chat_completion.return_value = {"choices": []}
        provider._llm = mock_llama

        with pytest.raises(RuntimeError, match="empty choices"):
            await provider.complete([{"role": "user", "content": "test"}])
