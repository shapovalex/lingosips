"""Services status API router.

Provides GET /services/status — returns active LLM and speech provider status.
No DB access required — reads from keyring only via get_service_status_info().
Always returns 200 — never raises on provider misconfiguration.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from lingosips.services.registry import get_service_status_info

router = APIRouter()


class LLMServiceStatus(BaseModel):
    provider: str  # "openrouter" | "qwen_local"
    model: str | None  # model name for openrouter; null for local
    last_latency_ms: float | None = None
    last_success_at: str | None = None


class SpeechServiceStatus(BaseModel):
    provider: str  # "azure" | "pyttsx3"
    last_latency_ms: float | None = None
    last_success_at: str | None = None


class ServiceStatusResponse(BaseModel):
    llm: LLMServiceStatus
    speech: SpeechServiceStatus


@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status() -> ServiceStatusResponse:
    """Return active LLM and speech provider status.

    Does NOT require DB session — reads from keyring only.
    Always returns 200 — never raises on provider misconfiguration.
    """
    info = get_service_status_info()
    return ServiceStatusResponse(
        llm=LLMServiceStatus(
            provider=info.llm_provider,
            model=info.llm_model,
            last_latency_ms=info.last_llm_latency_ms,
            last_success_at=info.last_llm_success_at,
        ),
        speech=SpeechServiceStatus(
            provider=info.speech_provider,
            last_latency_ms=info.last_speech_latency_ms,
            last_success_at=info.last_speech_success_at,
        ),
    )
