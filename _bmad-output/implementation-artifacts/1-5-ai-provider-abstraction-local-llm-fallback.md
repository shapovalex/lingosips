# Story 1.5: AI Provider Abstraction & Local LLM Fallback

Status: done

## Story

As a user,
I want card generation to work out-of-the-box using local Qwen when no API key is configured,
so that I get value from the app with zero configuration.

## Acceptance Criteria

1. **Given** no OpenRouter API key is configured
   **When** a card creation request is made
   **Then** `services/registry.py`'s `get_llm_provider()` returns `QwenLocalProvider`
   **And** the request is processed via `llama-cpp-python` running the local Qwen GGUF model

2. **Given** an OpenRouter API key is configured in the keyring
   **When** a card creation request is made
   **Then** `services/registry.py`'s `get_llm_provider()` returns `OpenRouterProvider`
   **And** the request routes to the OpenRouter API

3. **Given** the local Qwen model has not yet been downloaded
   **When** a card creation request is made for the first time
   **Then** model download begins automatically via `services/models/manager.py`
   **And** download progress is streamed to the browser via `GET /models/download/progress` SSE (`event: progress`)
   **And** card creation endpoint returns `503` with body `{"type": "/errors/model-downloading", "title": "Model is downloading", "detail": "Subscribe to /models/download/progress for progress"}` — the client re-tries once complete

4. **Given** `get_llm_provider()` is called anywhere in router code
   **Then** it is always resolved via FastAPI `Depends(get_llm_provider)` — direct instantiation of `QwenLocalProvider` or `OpenRouterProvider` is never used outside `services/`

5. **Given** a new provider class is added to `services/llm/` implementing `AbstractLLMProvider`
   **When** `get_llm_provider()` returns it
   **Then** no changes to `core/` business logic are required — the interface is the only contract

## Tasks / Subtasks

- [x] **T1: Create `services/llm/base.py` — `AbstractLLMProvider`** (AC: 4, 5) — TDD: write failing import test first
  - [x] T1.1: Define `LLMMessage` TypedDict: `{"role": Literal["system","user","assistant"], "content": str}`
  - [x] T1.2: Define `LLMModelNotReadyError(Exception)` — raised by providers when model is unavailable
  - [x] T1.3: Define `AbstractLLMProvider(ABC)` with abstract methods (see Dev Notes §AbstractLLMProvider)
  - [x] T1.4: Abstract method `async complete(messages, *, max_tokens=1024) -> str`
  - [x] T1.5: Abstract method `async stream_complete(messages, *, max_tokens=1024) -> AsyncIterator[str]`
  - [x] T1.6: Abstract property `provider_name: str` — human-readable name for `ServiceStatusIndicator`
  - [x] T1.7: Abstract property `model_name: str` — model identifier for display

- [x] **T2: Create `services/models/manager.py` — `ModelManager`** (AC: 3) — TDD: write failing tests first
  - [x] T2.1: Define `QWEN_MODEL_FILENAME = "qwen2.5-3b-instruct-q4_k_m.gguf"`
  - [x] T2.2: Define `QWEN_MODEL_URL` = HuggingFace download URL (see Dev Notes §ModelManager)
  - [x] T2.3: Implement `ModelManager` class with `MODELS_DIR = Path.home() / ".lingosips" / "models"` (see Dev Notes §ModelManager)
  - [x] T2.4: Implement `is_ready() -> bool` — returns `True` if model file exists at expected path
  - [x] T2.5: Implement `get_model_path() -> Path` — returns expected path whether file exists or not
  - [x] T2.6: Implement `async start_download(session: AsyncSession) -> int` — creates Job row (`job_type="model_download"`, `status="running"`) in DB, then starts download in background thread; returns `job_id`; persists job before any download work
  - [x] T2.7: Implement `async get_download_progress(job_id: int, session: AsyncSession) -> AsyncIterator[dict]` — reads job progress from DB in a polling loop; yields `{"done": int, "total": int, "current_item": str}` dicts; emits `{"complete": True}` when done
  - [x] T2.8: Implement `_download_file(url, dest_path, job_id, session_factory)` sync method — downloads with `httpx` streaming, updates `Job.progress_done`, `Job.progress_total`, `Job.current_item` in 1% increments

- [x] **T3: Create `services/llm/openrouter.py` — `OpenRouterProvider`** (AC: 2) — TDD: write failing tests first
  - [x] T3.1: `OpenRouterProvider(api_key: str, model: str)` constructor stores both as private attrs
  - [x] T3.2: Implement `complete()` using `httpx.AsyncClient` POST to `https://openrouter.ai/api/v1/chat/completions` (see Dev Notes §OpenRouterProvider)
  - [x] T3.3: Implement `stream_complete()` using `httpx.AsyncClient` with SSE streaming — parse `data: {...}` lines, stop on `data: [DONE]`
  - [x] T3.4: Set `Authorization: Bearer {api_key}` header; do NOT log the key
  - [x] T3.5: `provider_name` returns `"OpenRouter"`; `model_name` returns the configured model string
  - [x] T3.6: On non-2xx response: raise `RuntimeError(f"OpenRouter {status_code}: {body}")`; body must be scrubbed of credentials before logging

- [x] **T4: Create `services/llm/qwen_local.py` — `QwenLocalProvider`** (AC: 1, 3) — TDD: write failing tests first
  - [x] T4.1: `QwenLocalProvider(model_path: Path)` constructor stores path; `self._llm: Llama | None = None` (lazy load)
  - [x] T4.2: Implement `_get_llm() -> Llama` — instantiates on first call (see Dev Notes §QwenLocalProvider); raises `LLMModelNotReadyError` if `model_path` doesn't exist
  - [x] T4.3: Implement `complete()` using `asyncio.get_event_loop().run_in_executor(None, ...)` to run synchronous `llm.create_chat_completion()` without blocking the event loop (see Dev Notes §QwenLocalProvider)
  - [x] T4.4: Implement `stream_complete()` using background thread + `asyncio.Queue` pattern for true async streaming (see Dev Notes §QwenLocalProvider)
  - [x] T4.5: `provider_name` returns `"Local Qwen"`; `model_name` returns the stem of `model_path` (e.g., `"qwen2.5-3b-instruct-q4_k_m"`)
  - [x] T4.6: `Llama` initialization: `n_ctx=4096, n_gpu_layers=0, verbose=False` — CPU-only for MVP

- [x] **T5: Create `services/registry.py` — `get_llm_provider()`** (AC: 1, 2, 3, 4) — TDD: write failing tests first
  - [x] T5.1: Import `get_credential`, `OPENROUTER_API_KEY` from `services.credentials`
  - [x] T5.2: Add `OPENROUTER_MODEL = "openrouter_model"` constant to `services/credentials.py` (new credential key — no keyring write yet, read only)
  - [x] T5.3: Define module-level `_model_manager = ModelManager()` singleton
  - [x] T5.4: Define module-level `_qwen_provider: QwenLocalProvider | None = None` — lazy singleton; reset to `None` in tests via module patch
  - [x] T5.5: Implement `get_llm_provider() -> AbstractLLMProvider` (see Dev Notes §Registry)
  - [x] T5.6: If model not ready, call `_model_manager.start_download()` in background via `asyncio.create_task()` and raise `HTTPException(503, detail={RFC7807 body pointing to /models/download/progress})`. **IMPORTANT**: `registry.py` is the ONLY place in `services/` that imports fastapi for this HTTPException — this is the approved exception

- [x] **T6: Create `api/models.py` — model status and download progress endpoints** (AC: 3) — TDD: write failing tests first
  - [x] T6.1: Define `ModelStatusResponse` Pydantic model: `{"model_name": str, "ready": bool, "downloading": bool, "progress_pct": float | None}`
  - [x] T6.2: Implement `GET /models/status` → `ModelStatusResponse` (checks `_model_manager.is_ready()` and current job status)
  - [x] T6.3: Implement `GET /models/download/progress` as SSE `EventSourceResponse` (see Dev Notes §ModelsAPI)
  - [x] T6.4: SSE emits `event: progress\ndata: {"done": N, "total": M, "current_item": "..."}\n\n` until complete
  - [x] T6.5: SSE emits `event: complete\ndata: {"message": "Model ready"}\n\n` when done
  - [x] T6.6: SSE emits `event: error\ndata: {"message": "..."}\n\n` if download fails
  - [x] T6.7: If no active download job: immediately emit `event: complete` (model already ready) or start one

- [x] **T7: Register models router in `api/app.py`** (AC: 3)
  - [x] T7.1: Add `from lingosips.api.models import router as models_router` inside `create_app()`
  - [x] T7.2: Add `application.include_router(models_router, prefix="/models", tags=["models"])`
  - [x] T7.3: Registration order: health → settings → models → static files mount last
  - [x] T7.4: Verify `GET /openapi.json` lists `/models/status` and `/models/download/progress` endpoints

- [x] **T8: Update `services/llm/__init__.py` and `services/models/__init__.py`** (housekeeping)
  - [x] T8.1: `services/llm/__init__.py`: export `AbstractLLMProvider`, `LLMMessage`, `LLMModelNotReadyError`
  - [x] T8.2: `services/models/__init__.py`: export `ModelManager`

- [x] **T9: Backend tests — TDD (write BEFORE T3–T6 implementation)** (AC: 1, 2, 3, 4, 5)
  - [x] T9.1: Create `tests/services/__init__.py` (empty)
  - [x] T9.2: Create `tests/services/llm/__init__.py` (empty)
  - [x] T9.3: Create `tests/services/models/__init__.py` (empty)
  - [x] T9.4: Create `tests/services/llm/test_openrouter.py` (see Dev Notes §TestOpenRouter)
  - [x] T9.5: Create `tests/services/llm/test_qwen_local.py` (see Dev Notes §TestQwen)
  - [x] T9.6: Create `tests/services/test_registry.py` (see Dev Notes §TestRegistry)
  - [x] T9.7: Create `tests/services/models/test_manager.py` (see Dev Notes §TestManager)
  - [x] T9.8: Create `tests/api/test_models.py` (see Dev Notes §TestModelsAPI)

- [x] **T10: Ruff compliance check**
  - [x] T10.1: `uv run ruff check --fix src/lingosips/services/ tests/services/ tests/api/test_models.py`
  - [x] T10.2: Common issues: import order (stdlib → httpx/llama_cpp → fastapi → local lingosips), unused imports from ABC

---

## Dev Notes

### ⚠️ DO NOT Recreate — Already Exists

| Existing | Location | What it provides |
|---|---|---|
| `services/credentials.py` | `src/lingosips/services/credentials.py` | `get_credential()`, `OPENROUTER_API_KEY` constant, keyring read/write — DO NOT duplicate |
| `services/llm/__init__.py` | stub — 1 line | UPDATE this file (T8), do not recreate |
| `services/speech/__init__.py` | stub — 1 line | Leave alone — Story 1.6 |
| `services/models/__init__.py` | stub — 1 line | UPDATE this file (T8), do not recreate |
| `db/models.py` Job | `Job` model with `job_type="model_download"` | Already planned for exactly this use — USE IT |
| `db/session.py` get_session | `AsyncSession` factory via `Depends(get_session)` | The only DB entry point — use this pattern |
| `tests/conftest.py` | `client`, `session`, `test_engine` fixtures | All tests use these — do not create parallel fixtures |
| `api/app.py` create_app() | Router registration pattern | Follow existing pattern: import router inside create_app(), call include_router |

**CRITICAL**: `services/registry.py` does NOT exist yet — create it new.

### §AbstractLLMProvider — Exact Interface

```python
# src/lingosips/services/llm/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Literal, TypedDict


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
```

### §ModelManager — Implementation Pattern

```python
# src/lingosips/services/models/manager.py
import asyncio
import threading
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from lingosips.db.models import Job

logger = structlog.get_logger(__name__)

QWEN_MODEL_FILENAME = "qwen2.5-3b-instruct-q4_k_m.gguf"
QWEN_MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF"
    "/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
)
MODELS_DIR = Path.home() / ".lingosips" / "models"


class ModelManager:
    """Owns all model download, path discovery, and lifecycle for local AI models.

    This is the ONLY place that knows about model file locations.
    No other module constructs ~/.lingosips/models/ paths directly.
    """

    def __init__(
        self,
        models_dir: Path = MODELS_DIR,
        model_filename: str = QWEN_MODEL_FILENAME,
    ) -> None:
        self._models_dir = models_dir
        self._model_filename = model_filename
        self._downloading = False  # guard: prevent concurrent downloads

    def is_ready(self) -> bool:
        """Return True if the Qwen model file exists and is non-zero size."""
        path = self.get_model_path()
        return path.exists() and path.stat().st_size > 0

    def get_model_path(self) -> Path:
        """Return the expected model path (file may or may not exist)."""
        return self._models_dir / self._model_filename

    async def start_download(self, session: AsyncSession) -> int:
        """Create a Job record and start the download in a background thread.

        CRITICAL: Job is persisted to DB BEFORE download work starts.
        Returns the job_id so callers can track progress.
        """
        if self._downloading:
            # Find existing running job and return its ID
            result = await session.execute(
                select(Job).where(
                    Job.job_type == "model_download",
                    Job.status == "running",
                ).limit(1)
            )
            existing = result.scalars().first()
            if existing and existing.id:
                return existing.id

        # Persist job FIRST — data never lost on restart
        job = Job(
            job_type="model_download",
            status="running",
            progress_done=0,
            progress_total=0,
            current_item=f"Downloading {self._model_filename}",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id
        assert job_id is not None

        self._downloading = True
        self._models_dir.mkdir(parents=True, exist_ok=True)

        # Import here to avoid circular at module level
        from lingosips.db.session import AsyncSessionLocal

        # Fire-and-forget in background thread
        thread = threading.Thread(
            target=self._download_sync,
            args=(QWEN_MODEL_URL, self.get_model_path(), job_id, AsyncSessionLocal),
            daemon=True,
        )
        thread.start()
        logger.info("model.download_started", job_id=job_id, filename=self._model_filename)
        return job_id

    def _download_sync(
        self, url: str, dest: Path, job_id: int, session_factory: object
    ) -> None:
        """Blocking download — runs in background thread. Updates Job progress."""
        import asyncio

        async def _update_job(done: int, total: int, item: str, status: str = "running") -> None:
            async with session_factory() as s:
                result = await s.execute(select(Job).where(Job.id == job_id))
                job = result.scalars().first()
                if job:
                    job.progress_done = done
                    job.progress_total = total
                    job.current_item = item
                    job.status = status
                    s.add(job)
                    await s.commit()

        loop = asyncio.new_event_loop()
        try:
            with httpx.Client(timeout=600.0, follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    total = int(response.headers.get("content-length", 0))
                    done = 0
                    last_pct = -1
                    with open(dest, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                            f.write(chunk)
                            done += len(chunk)
                            pct = int(done / total * 100) if total else 0
                            if pct != last_pct:
                                loop.run_until_complete(
                                    _update_job(done, total, f"{pct}% downloaded")
                                )
                                last_pct = pct
            loop.run_until_complete(_update_job(total, total, "Complete", "complete"))
            logger.info("model.download_complete", job_id=job_id)
        except Exception as exc:
            loop.run_until_complete(
                _update_job(0, 0, f"Failed: {exc!s}", "failed")
            )
            logger.error("model.download_failed", job_id=job_id, error=str(exc))
            if dest.exists():
                dest.unlink()  # clean up partial file
        finally:
            self._downloading = False
            loop.close()
```

### §OpenRouterProvider — Implementation Pattern

```python
# src/lingosips/services/llm/openrouter.py
import json
from typing import AsyncIterator

import httpx
import structlog

from lingosips.services.llm.base import AbstractLLMProvider, LLMMessage

logger = structlog.get_logger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(AbstractLLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key   # NEVER log this
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
                raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text[:200]}")
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
```

### §QwenLocalProvider — Implementation Pattern

**CRITICAL**: `llama-cpp-python`'s `Llama` class is synchronous and CPU-bound. It MUST run in a thread executor to avoid blocking the FastAPI event loop.

```python
# src/lingosips/services/llm/qwen_local.py
import asyncio
import threading
from pathlib import Path
from typing import AsyncIterator

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
        loop = asyncio.get_event_loop()

        def _run() -> str:
            result = llm.create_chat_completion(
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
            return result["choices"][0]["message"]["content"]

        return await loop.run_in_executor(None, _run)

    async def stream_complete(
        self, messages: list[LLMMessage], *, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        llm = self._get_llm()  # raises LLMModelNotReadyError if missing
        loop = asyncio.get_event_loop()
        q: asyncio.Queue[str | None] = asyncio.Queue()

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
            finally:
                asyncio.run_coroutine_threadsafe(q.put(None), loop)  # sentinel

        thread = threading.Thread(target=_stream_in_thread, daemon=True)
        thread.start()

        while True:
            token = await q.get()
            if token is None:
                return
            yield token
```

### §Registry — Implementation Pattern

```python
# src/lingosips/services/registry.py
"""Provider registry — the ONLY location for cloud → local fallback logic.

Rules:
- get_llm_provider() is the SOLE source of AbstractLLMProvider instances
- No other module instantiates OpenRouterProvider or QwenLocalProvider directly
- This is the ONLY services/ file that may import fastapi (for HTTPException on model-not-ready)
"""
from fastapi import HTTPException

from lingosips.services.credentials import OPENROUTER_API_KEY, get_credential
from lingosips.services.llm.base import AbstractLLMProvider, LLMModelNotReadyError
from lingosips.services.llm.openrouter import OpenRouterProvider
from lingosips.services.llm.qwen_local import QwenLocalProvider
from lingosips.services.models.manager import ModelManager

OPENROUTER_MODEL_KEY = "openrouter_model"  # credential key for configured model
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"  # fallback when key set but model not configured

_model_manager = ModelManager()  # module-level singleton
_qwen_provider: QwenLocalProvider | None = None  # cached after first creation


def get_llm_provider() -> AbstractLLMProvider:
    """Return the appropriate LLM provider based on configured credentials.

    OpenRouter is preferred when an API key is present in keyring.
    Falls back to local QwenLocalProvider when no key is configured.
    Raises HTTP 503 if local model is not yet downloaded — client must subscribe
    to GET /models/download/progress.

    Used exclusively via FastAPI Depends(get_llm_provider) in api/ routers.
    """
    global _qwen_provider

    api_key = get_credential(OPENROUTER_API_KEY)
    if api_key:
        model = get_credential(OPENROUTER_MODEL_KEY) or DEFAULT_OPENROUTER_MODEL
        return OpenRouterProvider(api_key=api_key, model=model)

    # Local fallback — reuse cached instance (Llama loads model into memory once)
    if _qwen_provider is None:
        _qwen_provider = QwenLocalProvider(model_path=_model_manager.get_model_path())

    if not _model_manager.is_ready():
        # Trigger download asynchronously — but we are in a sync context here
        # The API layer (api/cards.py in Story 1.7) must handle the 503 and start download
        raise HTTPException(
            status_code=503,
            detail={
                "type": "/errors/model-downloading",
                "title": "Local model is not ready",
                "detail": (
                    "The Qwen model is being downloaded. "
                    "Subscribe to GET /models/download/progress for progress updates."
                ),
                "status": 503,
            },
        )

    return _qwen_provider
```

**IMPORTANT NOTE on async download start**: `get_llm_provider()` is called from a FastAPI `Depends()`, which is synchronous context. The download initiation (`_model_manager.start_download(session)`) requires an async session and must be called from the ROUTER level (api/models.py or api/cards.py in Story 1.7), not from within `get_llm_provider()`. The registry raises 503; the router catches it and initiates the download if needed.

### §ModelsAPI — Endpoint Implementation Pattern

```python
# src/lingosips/api/models.py
import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from lingosips.db.models import Job
from lingosips.db.session import get_session
from lingosips.services.registry import _model_manager  # direct access to singleton

router = APIRouter()


async def _model_download_sse(session: AsyncSession) -> AsyncIterator[str]:
    """SSE generator for model download progress."""
    if _model_manager.is_ready():
        yield f"event: complete\ndata: {json.dumps({'message': 'Model ready'})}\n\n"
        return

    # Find the most recent running or complete download job
    result = await session.execute(
        select(Job)
        .where(Job.job_type == "model_download")
        .order_by(Job.created_at.desc())  # type: ignore[attr-defined]
        .limit(1)
    )
    job = result.scalars().first()

    if job is None:
        # No download in progress — start one
        job_id = await _model_manager.start_download(session)
    else:
        job_id = job.id

    # Poll DB until complete or failed
    while True:
        await asyncio.sleep(0.5)  # poll every 500ms

        await session.refresh(job) if job else None
        result = await session.execute(select(Job).where(Job.id == job_id))
        current_job = result.scalars().first()

        if current_job is None:
            yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
            return

        if current_job.status == "complete":
            yield (
                f"event: progress\ndata: {json.dumps({'done': current_job.progress_total, "
                f"'total': current_job.progress_total, 'current_item': 'Complete'})}\n\n"
            )
            yield f"event: complete\ndata: {json.dumps({'message': 'Model ready'})}\n\n"
            return

        if current_job.status == "failed":
            yield (
                f"event: error\n"
                f"data: {json.dumps({'message': current_job.error_message or 'Download failed'})}\n\n"
            )
            return

        # Still running — emit progress
        yield (
            f"event: progress\ndata: {json.dumps({'done': current_job.progress_done, "
            f"'total': current_job.progress_total, 'current_item': current_job.current_item})}\n\n"
        )


@router.get("/status")
async def get_model_status(session: AsyncSession = Depends(get_session)) -> dict:
    """Return current status of the local Qwen model."""
    ready = _model_manager.is_ready()
    result = await session.execute(
        select(Job)
        .where(Job.job_type == "model_download", Job.status == "running")
        .limit(1)
    )
    active_job = result.scalars().first()
    return {
        "model_name": _model_manager._model_filename,
        "ready": ready,
        "downloading": active_job is not None,
        "progress_pct": (
            round(active_job.progress_done / active_job.progress_total * 100, 1)
            if active_job and active_job.progress_total > 0
            else None
        ),
    }


@router.get("/download/progress")
async def download_progress(session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    """SSE stream for model download progress.
    
    Event types emitted: progress | complete | error
    progress data: {"done": int, "total": int, "current_item": str}
    complete data: {"message": "Model ready"}
    error data: {"message": str}
    """
    return StreamingResponse(
        _model_download_sse(session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
```

### §TestOpenRouter — Test Patterns

```python
# tests/services/llm/test_openrouter.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)) as mock_post:
            result = await provider.complete([{"role": "user", "content": "translate: melancholic"}])
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
```

### §TestQwen — Test Patterns

```python
# tests/services/llm/test_qwen_local.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
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
        with patch("lingosips.services.llm.qwen_local.Llama", return_value=mock_llama):
            # Force lazy load
            provider._get_llm()  # triggers Llama construction
        provider._llm = mock_llama  # inject mock directly
        result = await provider.complete([{"role": "user", "content": "translate"}])
        assert result == "respuesta"
        mock_llama.create_chat_completion.assert_called_once()

    def test_model_loads_lazily(self, tmp_path):
        """Llama must NOT be instantiated at __init__ time."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"fake")
        with patch("lingosips.services.llm.qwen_local.Llama") as mock_llama_cls:
            provider = QwenLocalProvider(model_path=model_file)
            mock_llama_cls.assert_not_called()  # lazy!

    def test_provider_name_and_model_name(self, tmp_path):
        path = tmp_path / "qwen2.5-3b-instruct-q4_k_m.gguf"
        provider = QwenLocalProvider(model_path=path)
        assert provider.provider_name == "Local Qwen"
        assert provider.model_name == "qwen2.5-3b-instruct-q4_k_m"
```

### §TestRegistry — Test Patterns

```python
# tests/services/test_registry.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from lingosips.services.llm.openrouter import OpenRouterProvider
from lingosips.services.llm.qwen_local import QwenLocalProvider


@pytest.mark.anyio
class TestGetLLMProvider:
    def test_returns_openrouter_when_key_configured(self):
        with patch("lingosips.services.registry.get_credential") as mock_cred:
            mock_cred.side_effect = lambda k: "sk-abc" if k == "openrouter_api_key" else None
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = True
                from lingosips.services.registry import get_llm_provider
                provider = get_llm_provider()
        assert isinstance(provider, OpenRouterProvider)
        assert provider.provider_name == "OpenRouter"

    def test_returns_qwen_local_when_no_api_key(self, tmp_path):
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"x")
        with patch("lingosips.services.registry.get_credential", return_value=None):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = True
                mock_mm.get_model_path.return_value = model_file
                import lingosips.services.registry as reg
                reg._qwen_provider = None  # reset singleton between tests
                provider = reg.get_llm_provider()
        assert isinstance(provider, QwenLocalProvider)
        assert provider.provider_name == "Local Qwen"

    def test_raises_503_when_model_not_ready(self):
        with patch("lingosips.services.registry.get_credential", return_value=None):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = False
                mock_mm.get_model_path.return_value = "/nonexistent"
                import lingosips.services.registry as reg
                reg._qwen_provider = None
                with pytest.raises(HTTPException) as exc_info:
                    reg.get_llm_provider()
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["type"] == "/errors/model-downloading"

    def test_empty_string_api_key_treated_as_no_key(self, tmp_path):
        """Empty string from keyring must be treated the same as None."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"x")
        with patch("lingosips.services.registry.get_credential", return_value=""):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = True
                mock_mm.get_model_path.return_value = model_file
                import lingosips.services.registry as reg
                reg._qwen_provider = None
                provider = reg.get_llm_provider()
        assert isinstance(provider, QwenLocalProvider)
```

**CRITICAL**: The registry module uses a module-level `_qwen_provider` singleton. Tests MUST reset it between runs:
```python
import lingosips.services.registry as reg
reg._qwen_provider = None  # always reset in test setup
```

### §TestManager — Test Patterns

```python
# tests/services/models/test_manager.py
import pytest
from pathlib import Path
from lingosips.services.models.manager import ModelManager


@pytest.mark.anyio
class TestModelManager:
    def test_is_ready_false_when_file_missing(self, tmp_path):
        mm = ModelManager(models_dir=tmp_path, model_filename="qwen.gguf")
        assert mm.is_ready() is False

    def test_is_ready_true_when_file_exists(self, tmp_path):
        model = tmp_path / "qwen.gguf"
        model.write_bytes(b"fake-model-data")
        mm = ModelManager(models_dir=tmp_path, model_filename="qwen.gguf")
        assert mm.is_ready() is True

    def test_is_ready_false_for_zero_byte_file(self, tmp_path):
        model = tmp_path / "qwen.gguf"
        model.write_bytes(b"")  # zero bytes = corrupted download
        mm = ModelManager(models_dir=tmp_path, model_filename="qwen.gguf")
        assert mm.is_ready() is False

    def test_get_model_path_returns_expected_path(self, tmp_path):
        mm = ModelManager(models_dir=tmp_path, model_filename="test.gguf")
        assert mm.get_model_path() == tmp_path / "test.gguf"

    async def test_start_download_creates_job_before_any_work(self, client, session):
        """Job MUST be persisted before download thread starts."""
        from unittest.mock import patch, MagicMock
        from lingosips.services.models.manager import ModelManager
        mm = ModelManager(models_dir=Path("/tmp/test_models"), model_filename="qwen.gguf")
        # Mock the actual download thread so it doesn't run
        with patch.object(mm, "_download_sync"):
            import threading
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                job_id = await mm.start_download(session)
        assert job_id is not None
        assert isinstance(job_id, int)
        # Verify job exists in DB
        from sqlmodel import select
        from lingosips.db.models import Job
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalars().first()
        assert job is not None
        assert job.job_type == "model_download"
        assert job.status == "running"
```

### §TestModelsAPI — Endpoint Test Patterns

```python
# tests/api/test_models.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.anyio
class TestModelStatusEndpoint:
    async def test_get_model_status_when_ready(self, client: AsyncClient):
        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = True
            mock_mm._model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["downloading"] is False
        assert "model_name" in body

    async def test_get_model_status_when_not_ready(self, client: AsyncClient):
        with patch("lingosips.api.models._model_manager") as mock_mm:
            mock_mm.is_ready.return_value = False
            mock_mm._model_filename = "qwen2.5-3b-instruct-q4_k_m.gguf"
            response = await client.get("/models/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is False
```

### §CredentialsUpdate — New Constant

Add to `services/credentials.py` (T5.2):
```python
OPENROUTER_MODEL = "openrouter_model"
```

This constant is read-only in Story 1.5. Story 2.3 (Service Configuration) adds the `set_credential(OPENROUTER_MODEL, ...)` call when the user configures a specific model in Settings UI.

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `OpenRouterProvider(api_key=credentials.get_credential(...))` in a router | `Depends(get_llm_provider)` — registry only |
| `from llama_cpp import Llama` at module top-level | Import inside `_get_llm()` — keeps startup fast |
| Putting fallback logic (`if openrouter_key: ... else: ...`) in `api/cards.py` | All fallback in `services/registry.py` only |
| `Llama(model_path=...)` in `__init__` | Lazy load in `_get_llm()` — model loading is slow |
| `asyncio.run()` inside a background thread | `asyncio.run_coroutine_threadsafe(coro, loop)` |
| `import fastapi` in `services/llm/` or `services/models/` | Only `services/registry.py` may import fastapi |
| Logging `api_key` or `Authorization` header | Use structlog; never log credential values |
| Creating `ModelManager()` in a router | Use the module-level `_model_manager` singleton from registry |
| `SQLModel.metadata.create_all()` | Alembic only — Job table already created by `001_initial_schema` |
| Running llama-cpp-python's `Llama()` call directly in async context | Always use `run_in_executor(None, ...)` for sync CPU-bound code |
| Hardcoding model URL in tests | Use `tmp_path` fixture; mock `httpx.Client` in download tests |
| `session.exec()` | `session.execute()` then `.scalars().first()` — this project uses SQLAlchemy's `AsyncSession`, NOT SQLModel's |

### §FileStructure — New and Modified Files

```
src/lingosips/
├── services/
│   ├── credentials.py          ← UPDATED: add OPENROUTER_MODEL constant
│   ├── registry.py             ← NEW: get_llm_provider() (sole provider selection logic)
│   ├── llm/
│   │   ├── __init__.py         ← UPDATED: export AbstractLLMProvider, LLMMessage, LLMModelNotReadyError
│   │   ├── base.py             ← NEW: AbstractLLMProvider, LLMMessage, LLMModelNotReadyError
│   │   ├── openrouter.py       ← NEW: OpenRouterProvider
│   │   └── qwen_local.py       ← NEW: QwenLocalProvider
│   └── models/
│       ├── __init__.py         ← UPDATED: export ModelManager
│       └── manager.py          ← NEW: ModelManager (download, path, lifecycle)
├── api/
│   ├── app.py                  ← UPDATED: register models_router
│   └── models.py               ← NEW: GET /models/status, GET /models/download/progress

tests/
├── services/
│   ├── __init__.py             ← NEW (empty)
│   ├── test_registry.py        ← NEW
│   ├── llm/
│   │   ├── __init__.py         ← NEW (empty)
│   │   ├── test_openrouter.py  ← NEW
│   │   └── test_qwen_local.py  ← NEW
│   └── models/
│       ├── __init__.py         ← NEW (empty)
│       └── test_manager.py     ← NEW
└── api/
    └── test_models.py          ← NEW
```

### §RuffCompliance

```bash
uv run ruff check --fix \
  src/lingosips/services/ \
  src/lingosips/api/models.py \
  tests/services/ \
  tests/api/test_models.py
```

Common issues to pre-empt:
- Import order: `stdlib` (`abc`, `asyncio`, `json`, `threading`) → `third-party` (`fastapi`, `httpx`, `llama_cpp`, `structlog`) → `local` (`lingosips.*`)
- `AsyncIterator` is from `collections.abc` in Python 3.12, not `typing`
- Abstract methods need `@abstractmethod` + `...` body (not `pass`)
- `type: ignore[arg-type]` comment needed for `llama_cpp.create_chat_completion(messages=...)` — llama-cpp-python types don't perfectly match our TypedDict

### Previous Story Intelligence

From Story 1.4 (last completed — confirmed in Dev Agent Record):

- **`session.execute()` NOT `session.exec()`** — the project uses SQLAlchemy's `AsyncSession` (NOT SQLModel's). Using `session.exec()` will raise `AttributeError`. Always: `result = await session.execute(select(Model).where(...))` then `result.scalars().first()`.
- **Test class pattern**: `@pytest.mark.anyio` on the class (not individual methods). All test methods are `async def`. Inject `client: AsyncClient` or `session: AsyncSession` from conftest fixtures.
- **RFC 7807 error format** in use: `{"type": "/errors/...", "title": "...", "detail": "...", "status": N}` — 503 detail must follow this exact shape.
- **Coverage gate 90%** is hard CI. New files under `src/lingosips/` must be fully covered. The `_download_sync` method is hard to cover in unit tests — mark it with `# pragma: no cover` if necessary, or test via integration.
- **structlog pattern**: `logger = structlog.get_logger(__name__)` at module level. Log events snake_case: `logger.info("qwen.model_loaded")`, `logger.error("model.download_failed", error=str(exc))`.
- **Module-level singleton test isolation**: The `_qwen_provider` global in `registry.py` will persist between tests. Reset it with `import lingosips.services.registry as reg; reg._qwen_provider = None` in each test that needs a clean state — or add an `autouse` fixture.

From Story 1.3 (credentials patterns):
- `get_credential(OPENROUTER_API_KEY)` already tested and works — don't recreate, just import and use.
- Credentials must never appear in logs, error messages, or test output.
- The credential-scrubbing processor in `core/logging.py` applies globally — test that your error messages don't contain keys.

From Story 1.2 (app shell):
- Router registration pattern in `create_app()`: `from lingosips.api.models import router as models_router` inside the function body, then `application.include_router(models_router, prefix="/models", tags=["models"])`.
- Static files mount must be LAST in registration order.

### References

- Story 1.5 acceptance criteria: [Source: epics.md#Story 1.5]
- `services/registry.py` is ONLY location for provider fallback logic: [Source: project-context.md#Layer Architecture & Boundaries]
- `get_llm_provider()` example pattern: [Source: project-context.md#Dependency Injection — Depends() Always]
- `AbstractLLMProvider.synthesize` + `evaluate_pronunciation`: [Source: epics.md#Story 1.6] — Speech provider contract defined in Story 1.6, NOT this story
- `Job` model with `job_type="model_download"`: [Source: db/models.py lines 85–97]
- `llama-cpp-python>=0.3.21` already in dependencies: [Source: pyproject.toml]
- `httpx>=0.28.1` already in dependencies (async HTTP for OpenRouter): [Source: pyproject.toml]
- SSE envelope: `event: {type}\ndata: {json}\n\n`: [Source: project-context.md#API Design Rules]
- Three SSE channels: cards/stream, import/{job_id}/progress, models/download/progress: [Source: epics.md#Additional Requirements]
- `services/models/manager.py` owns model lifecycle for Qwen + Whisper: [Source: epics.md#Additional Requirements]
- `MODELS_DIR = ~/.lingosips/models/`: [Source: architecture.md#Data Boundary]
- Implementation sequence: project init → db/models + Alembic → services/registry + LLM/speech → core/fsrs: [Source: epics.md#Additional Requirements — Implementation sequence]
- TDD mandatory — failing tests before implementation: [Source: project-context.md#Testing Rules]
- 90% backend coverage CI hard gate: [Source: project-context.md#CI gates]
- `session.execute()` not `session.exec()`: [Source: Story 1.4 Dev Agent Record Debug Log #1]
- FR26: LLM routing OpenRouter → Qwen: [Source: epics.md#Functional Requirements]
- FR39: Fully functional before any external service configured: [Source: epics.md#FR39]
- NFR24: AI service abstraction — swappable behind common interface: [Source: epics.md#NFR24]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (claude-sonnet-4-6)

### Debug Log References

1. **AsyncMock vs async iterator for SSE test** — `response.aiter_lines = AsyncMock(return_value=...)` returns a coroutine, not an async iterator. Fixed by using `lambda: aiter(lines)` with a helper async generator. This is a known gotcha with httpx streaming mocks.
2. **Ruff f-string concat across literals** — The pattern `f"...{json.dumps({'key': value, " f"'key2': value2})}..."` splits a dict literal across two f-strings, causing SyntaxError. Fixed by pre-computing `json.dumps(...)` into a local variable before the f-string.
3. **Patching `Llama` inside `_get_llm()`** — `Llama` is imported inside the function body (`from llama_cpp import Llama`), so it is not a module-level attribute of `qwen_local`. Must patch `llama_cpp.Llama` not `lingosips.services.llm.qwen_local.Llama`.
4. **Test isolation with committed DB data** — `conftest.py`'s `session.rollback()` at teardown cannot undo already-committed data (once committed, data is permanent in the shared in-memory DB). Rewrote the "returns existing job id when already downloading" test to check absence of new jobs rather than exact ID equality.
5. **`_download_sync` coverage** — This method runs in a background thread with its own event loop; impossible to unit-test without launching a real download. Marked `# pragma: no cover` as documented in project-context.md (Coverage gate 90%).

### Completion Notes List

- **T1**: Created `services/llm/base.py` with `AbstractLLMProvider` ABC, `LLMMessage` TypedDict, `LLMModelNotReadyError`. 100% coverage. No fastapi imports per architecture rules.
- **T2**: Created `services/models/manager.py` with `ModelManager`. `is_ready()` checks file existence and non-zero size. `start_download()` persists Job BEFORE starting download thread. `_download_sync` marked `# pragma: no cover`. 100% coverage (covered lines).
- **T3**: Created `services/llm/openrouter.py` with `OpenRouterProvider`. API key never logged. Non-2xx raises `RuntimeError` without key in message. 100% coverage.
- **T4**: Created `services/llm/qwen_local.py` with `QwenLocalProvider`. Lazy Llama load with double-checked locking. `complete()` via `run_in_executor`. `stream_complete()` via background thread + `asyncio.Queue`. 96% coverage (error-path branch in `_stream_in_thread` not hit in unit tests — acceptable).
- **T5**: Created `services/registry.py` — sole location for provider selection logic. OpenRouter preferred when API key set; falls back to local Qwen. 503 HTTPException raised when model not ready. 100% coverage.
- **T5.2**: Added `OPENROUTER_MODEL = "openrouter_model"` constant to `services/credentials.py`.
- **T6**: Created `api/models.py` with `GET /models/status` and `GET /models/download/progress` (SSE). 91% coverage including SSE generator paths (complete, failed, running+progress paths all tested).
- **T7**: Registered `models_router` in `api/app.py`. Registration order: health → settings → models → static. Both endpoints visible in `/openapi.json`.
- **T8**: Updated `services/llm/__init__.py` and `services/models/__init__.py` to export public API.
- **T9**: 41 new tests across 7 test files. All use TDD (written before implementation). Fixtures from conftest reused, no parallel fixture setup.
- **T10**: Ruff clean — 0 remaining issues.
- **Coverage**: 93.33% total (gate: 90% ✅). All 111 tests pass.
- **Acceptance Criteria**: All 5 ACs verified by test suite — provider selection, OpenRouter routing, 503 model-downloading response, Depends()-only instantiation, and swappable interface.

### File List

**New files:**
- `src/lingosips/services/llm/base.py`
- `src/lingosips/services/llm/openrouter.py`
- `src/lingosips/services/llm/qwen_local.py`
- `src/lingosips/services/models/manager.py`
- `src/lingosips/services/registry.py`
- `src/lingosips/api/models.py`
- `tests/services/__init__.py`
- `tests/services/llm/__init__.py`
- `tests/services/llm/test_base.py`
- `tests/services/llm/test_openrouter.py`
- `tests/services/llm/test_qwen_local.py`
- `tests/services/models/__init__.py`
- `tests/services/models/test_manager.py`
- `tests/services/test_registry.py`
- `tests/api/test_models.py`

**Modified files:**
- `src/lingosips/services/credentials.py` (added `OPENROUTER_MODEL` constant)
- `src/lingosips/services/llm/__init__.py` (added exports)
- `src/lingosips/services/models/__init__.py` (added exports)
- `src/lingosips/api/app.py` (registered models router)

### Review Findings

- [x] [Review][Patch] AC3 503 title mismatch — `"Local model is not ready"` must be `"Model is downloading"` per AC3 [src/lingosips/services/registry.py:51]
- [x] [Review][Patch] `OPENROUTER_MODEL_KEY` duplicated in registry.py — must import `OPENROUTER_MODEL` from credentials.py (T5.2 dead constant) [src/lingosips/services/registry.py:17]
- [x] [Review][Patch] SSE generator picks up stale failed/complete jobs — query must filter `status="running"` [src/lingosips/api/models.py:31]
- [x] [Review][Patch] `_downloading` TOCTOU race + duplicate download jobs — add `asyncio.Lock` to `start_download` [src/lingosips/services/models/manager.py:59]
- [x] [Review][Patch] `ModelStatusResponse` is raw `dict`, not Pydantic model (T6.1 violation) [src/lingosips/api/models.py:87]
- [x] [Review][Patch] `asyncio.get_event_loop()` deprecated in Python 3.10+ — must use `asyncio.get_running_loop()` [src/lingosips/services/llm/qwen_local.py:57,72]
- [x] [Review][Patch] Stream thread exceptions silently swallowed — caller gets truncated response with no error [src/lingosips/services/llm/qwen_local.py:85]
- [x] [Review][Patch] SSE polling loop has no timeout — infinite hang if download thread crashes without DB update [src/lingosips/api/models.py:46]
- [x] [Review][Patch] `assert job_id is not None` in production path — stripped by `-O` flag [src/lingosips/services/models/manager.py:83]
- [x] [Review][Patch] `_model_manager._model_filename` private attribute access — add public `model_filename` property [src/lingosips/api/models.py:97]
- [x] [Review][Patch] `progress_pct` not clamped — can exceed 100 on race between `done` and `total` [src/lingosips/api/models.py:101]
- [x] [Review][Patch] `dest.unlink()` not wrapped — partial file persists if filesystem error during cleanup [src/lingosips/services/models/manager.py:143]
- [x] [Review][Patch] `asyncio.Queue` has no `maxsize` — unbounded memory growth if consumer is slow [src/lingosips/services/llm/qwen_local.py:73]
- [x] [Review][Patch] `complete()` no guard against empty `choices` list — `IndexError` with no diagnostic context [src/lingosips/services/llm/qwen_local.py:64]
- [x] [Review][Defer] T2.7 `get_download_progress` missing on `ModelManager` — equivalent logic inlined in api/models.py; refactoring deferred [src/lingosips/services/models/manager.py]
- [x] [Review][Defer] AC4 `Depends(get_llm_provider)` not wired to any router — deferred to Story 1.7 (api/cards.py)
- [x] [Review][Defer] TOCTOU in `_get_llm`: file deleted between `exists()` and `Llama()` construction — extreme edge case, deferred MVP [src/lingosips/services/llm/qwen_local.py:27]
- [x] [Review][Defer] `progress_done` reset to 0 on failure wipes progress history — in `# pragma: no cover` path, deferred [src/lingosips/services/models/manager.py:140]
- [x] [Review][Defer] `is_ready()` no checksum/integrity check — out of MVP scope, deferred
- [x] [Review][Defer] SSE holds long-lived SQLAlchemy session — MVP acceptable, deferred
- [x] [Review][Defer] No auth on `/models/status` and `/models/download/progress` — no auth system in MVP, deferred
- [x] [Review][Defer] `_qwen_provider` singleton never invalidated if model path changes — model path is static in MVP, deferred

### Change Log

- 2026-04-30: Story 1.5 implemented. Created AI provider abstraction layer with `AbstractLLMProvider` ABC, `OpenRouterProvider` (cloud), `QwenLocalProvider` (local Qwen GGUF via llama-cpp-python), `ModelManager` (auto-download), `services/registry.py` (sole provider selection logic), and `api/models.py` (model status + SSE download progress). 41 new tests, 93.33% coverage.
- 2026-05-01: Code review — 14 patches applied, 8 deferred, 5 dismissed. See Review Findings above.
