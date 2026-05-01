"""Local Qwen LLM provider — runs GGUF model via llama-cpp-python.

CRITICAL: llama-cpp-python's Llama class is synchronous and CPU-bound.
It MUST run in a thread executor to avoid blocking the FastAPI event loop.
"""

import asyncio
import threading
from collections.abc import AsyncIterator
from pathlib import Path

import structlog

from lingosips.services.llm.base import AbstractLLMProvider, LLMMessage, LLMModelNotReadyError

logger = structlog.get_logger(__name__)


class QwenLocalProvider(AbstractLLMProvider):
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._llm = None  # lazy: loaded on first request
        self._load_lock = threading.Lock()  # prevent double-init in concurrent requests

    def _get_llm(self):
        """Lazy-load Llama model. Thread-safe. Raises LLMModelNotReadyError if file missing."""
        if not self._model_path.exists():
            raise LLMModelNotReadyError(
                f"Qwen model not found at {self._model_path}. "
                "Subscribe to GET /models/download/progress"
            )
        if self._llm is None:
            with self._load_lock:
                if self._llm is None:  # double-checked locking
                    from llama_cpp import Llama  # import here to keep startup fast

                    logger.info("qwen.loading_model", path=str(self._model_path))
                    self._llm = Llama(
                        model_path=str(self._model_path),
                        n_ctx=4096,
                        n_gpu_layers=0,  # CPU-only for MVP
                        verbose=False,
                    )
                    logger.info("qwen.model_loaded")
        return self._llm

    @property
    def provider_name(self) -> str:
        return "Local Qwen"

    @property
    def model_name(self) -> str:
        return self._model_path.stem  # "qwen2.5-3b-instruct-q4_k_m"

    async def complete(self, messages: list[LLMMessage], *, max_tokens: int = 1024) -> str:
        llm = self._get_llm()  # raises LLMModelNotReadyError if missing
        loop = asyncio.get_running_loop()

        def _run() -> str:
            result = llm.create_chat_completion(
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
            choices = result.get("choices", [])
            if not choices:
                raise RuntimeError("Qwen returned empty choices list")
            return choices[0]["message"]["content"]

        return await loop.run_in_executor(None, _run)

    async def stream_complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        llm = self._get_llm()  # raises LLMModelNotReadyError if missing
        loop = asyncio.get_running_loop()
        q: asyncio.Queue[str | Exception | None] = asyncio.Queue(maxsize=100)

        def _stream_in_thread() -> None:
            try:
                for chunk in llm.create_chat_completion(
                    messages=messages,  # type: ignore[arg-type]
                    max_tokens=max_tokens,
                    stream=True,
                ):
                    token = chunk["choices"][0]["delta"].get("content", "")
                    if token:
                        asyncio.run_coroutine_threadsafe(q.put(token), loop)
            except Exception as exc:
                logger.error("qwen.stream_error", error=str(exc))
                asyncio.run_coroutine_threadsafe(q.put(exc), loop)  # propagate to caller
            finally:
                asyncio.run_coroutine_threadsafe(q.put(None), loop)  # sentinel

        thread = threading.Thread(target=_stream_in_thread, daemon=True)
        thread.start()

        while True:
            item = await q.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item
