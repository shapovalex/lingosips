"""Provider registry — the ONLY location for cloud → local fallback logic.

Rules:
- get_llm_provider() is the SOLE source of AbstractLLMProvider instances
- No other module instantiates OpenRouterProvider or QwenLocalProvider directly
- This is the ONLY services/ file that may import fastapi (for HTTPException on model-not-ready)
"""

from fastapi import HTTPException

from lingosips.services.credentials import OPENROUTER_API_KEY, OPENROUTER_MODEL, get_credential
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.llm.openrouter import OpenRouterProvider
from lingosips.services.llm.qwen_local import QwenLocalProvider
from lingosips.services.models.manager import ModelManager

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
        model = get_credential(OPENROUTER_MODEL) or DEFAULT_OPENROUTER_MODEL
        return OpenRouterProvider(api_key=api_key, model=model)

    # Local fallback — reuse cached instance (Llama loads model into memory once)
    if _qwen_provider is None:
        _qwen_provider = QwenLocalProvider(model_path=_model_manager.get_model_path())

    if not _model_manager.is_ready():
        # Trigger download asynchronously — but we are in a sync context here.
        # The API layer (api/cards.py in Story 1.7) must handle the 503 and start download.
        raise HTTPException(
            status_code=503,
            detail={
                "type": "/errors/model-downloading",
                "title": "Model is downloading",
                "detail": "Subscribe to /models/download/progress for progress",
                "status": 503,
            },
        )

    return _qwen_provider
