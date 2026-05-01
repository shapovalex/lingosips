"""Provider registry — the ONLY location for cloud → local fallback logic.

Rules:
- get_llm_provider() is the SOLE source of AbstractLLMProvider instances
- No other module instantiates OpenRouterProvider or QwenLocalProvider directly
- This is the ONLY services/ file that may import fastapi (for HTTPException on model-not-ready)
"""

from fastapi import HTTPException

from lingosips.services.credentials import (
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    get_credential,
)
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.llm.openrouter import OpenRouterProvider
from lingosips.services.llm.qwen_local import QwenLocalProvider
from lingosips.services.models.manager import ModelManager
from lingosips.services.speech.azure import AzureSpeechProvider
from lingosips.services.speech.base import AbstractSpeechProvider
from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider

DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"  # fallback when key set but model not configured

_model_manager = ModelManager()  # module-level singleton
_qwen_provider: QwenLocalProvider | None = None  # cached after first creation
_pyttsx3_provider: Pyttsx3Provider | None = None  # module-level singleton


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


def get_speech_provider() -> AbstractSpeechProvider:
    """Return the appropriate speech provider based on configured credentials.

    AzureSpeechProvider preferred when BOTH key and region are present.
    Falls back to Pyttsx3Provider when either is missing.

    NOTE: This function covers TTS (synthesize). Speech evaluation routing
    (WhisperLocalProvider or AzureSpeechProvider for evaluate_pronunciation)
    is added in Story 4.1 as get_speech_evaluator().

    Used exclusively via FastAPI Depends(get_speech_provider) in api/ routers.
    """
    global _pyttsx3_provider

    api_key = get_credential(AZURE_SPEECH_KEY)
    region = get_credential(AZURE_SPEECH_REGION)
    if api_key and region:
        return AzureSpeechProvider(api_key=api_key, region=region)

    # Local TTS fallback
    if _pyttsx3_provider is None:
        _pyttsx3_provider = Pyttsx3Provider()

    return _pyttsx3_provider
