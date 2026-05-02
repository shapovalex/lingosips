"""Services API router — provider status, connection testing, and credential management.

Provides:
  GET  /services/status           — active provider status (no DB, no credentials saved)
  POST /services/test-connection  — test provider credentials WITHOUT saving
  POST /services/credentials      — save credentials to OS keychain via services/credentials.py
  DELETE /services/credentials/{provider} — remove credentials from keychain

SECURITY:
- Credential values are NEVER logged — only key names.
- test-connection NEVER calls set_credential — ephemeral test only.
- All credential storage goes through services/credentials.py → keyring.
"""

import asyncio

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, field_validator, model_validator

from lingosips.services.credentials import (
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    IMAGE_ENDPOINT_KEY,
    IMAGE_ENDPOINT_URL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    delete_credential,
    set_credential,
)
from lingosips.services.llm.openrouter import OpenRouterProvider
from lingosips.services.registry import get_service_status_info, invalidate_provider_cache
from lingosips.services.speech.azure import AzureSpeechProvider

router = APIRouter()
logger = structlog.get_logger(__name__)


# ── Existing status endpoint ──────────────────────────────────────────────────


class LLMServiceStatus(BaseModel):
    provider: str  # "openrouter" | "qwen_local"
    model: str | None  # model name for openrouter; null for local
    last_latency_ms: float | None = None
    last_success_at: str | None = None


class SpeechServiceStatus(BaseModel):
    provider: str  # "azure" | "pyttsx3"
    last_latency_ms: float | None = None
    last_success_at: str | None = None


class ImageServiceStatus(BaseModel):
    configured: bool  # True when IMAGE_ENDPOINT_URL is set in keyring


class ServiceStatusResponse(BaseModel):
    llm: LLMServiceStatus
    speech: SpeechServiceStatus
    image: ImageServiceStatus


@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status() -> ServiceStatusResponse:
    """Return active LLM, speech, and image provider status.

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
        image=ImageServiceStatus(configured=info.image_endpoint_configured),
    )


# ── Connection test ───────────────────────────────────────────────────────────


class ConnectionTestRequest(BaseModel):
    provider: str  # "openrouter" | "azure" | "image"
    # OpenRouter
    api_key: str | None = None
    model: str | None = None
    # Azure Speech
    azure_key: str | None = None
    azure_region: str | None = None
    # Image endpoint
    endpoint_url: str | None = None
    endpoint_key: str | None = None

    @field_validator("provider")
    @classmethod
    def valid_provider(cls, v: str) -> str:
        if v not in ("openrouter", "azure", "image"):
            raise ValueError("provider must be 'openrouter', 'azure', or 'image'")
        return v


class ConnectionTestResponse(BaseModel):
    success: bool
    sample_translation: str | None = None
    error_code: str | None = None  # "invalid_api_key" | "network_error" | "quota_exceeded"
    error_message: str | None = None


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    request: ConnectionTestRequest,
) -> ConnectionTestResponse:
    """Test provider credentials WITHOUT saving. Returns 200 always (soft errors in body).

    CRITICAL: set_credential must NEVER be called here. This endpoint is test-only.
    """
    if request.provider == "openrouter":
        if not request.api_key or not request.model:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "/errors/validation",
                    "title": "api_key and model required for openrouter",
                    "status": 422,
                },
            )
        try:
            provider = OpenRouterProvider(api_key=request.api_key, model=request.model)
            result = await asyncio.wait_for(
                provider.complete(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Translate 'hello' to Spanish. "
                                "Reply with only the single word translation."
                            ),
                        }
                    ]
                ),
                timeout=15.0,
            )
            return ConnectionTestResponse(success=True, sample_translation=result.strip()[:100])
        except TimeoutError:
            return ConnectionTestResponse(
                success=False,
                error_code="network_error",
                error_message="Connection timed out",
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "401" in msg or "Unauthorized" in msg.lower():
                return ConnectionTestResponse(
                    success=False,
                    error_code="invalid_api_key",
                    error_message="Invalid API key · Check your OpenRouter dashboard",
                )
            if "429" in msg:
                return ConnectionTestResponse(
                    success=False,
                    error_code="quota_exceeded",
                    error_message="Quota exceeded · Check your OpenRouter usage limits",
                )
            return ConnectionTestResponse(
                success=False,
                error_code="network_error",
                error_message="Connection failed · Check your network",
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            return ConnectionTestResponse(
                success=False,
                error_code="network_error",
                error_message="Cannot reach OpenRouter · Check your network",
            )
        except Exception:  # noqa: BLE001
            return ConnectionTestResponse(
                success=False,
                error_code="network_error",
                error_message="Connection failed",
            )

    if request.provider == "azure":
        if not request.azure_key or not request.azure_region:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "/errors/validation",
                    "title": "azure_key and azure_region required",
                    "status": 422,
                },
            )
        try:
            provider_az = AzureSpeechProvider(
                api_key=request.azure_key, region=request.azure_region
            )
            await asyncio.wait_for(
                asyncio.to_thread(provider_az.synthesize, "hello", "es"),
                timeout=10.0,
            )
            return ConnectionTestResponse(success=True, sample_translation="Azure Speech connected")
        except TimeoutError:
            return ConnectionTestResponse(
                success=False,
                error_code="network_error",
                error_message="Azure Speech timed out",
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "auth" in msg or "403" in msg or "401" in msg:
                return ConnectionTestResponse(
                    success=False,
                    error_code="invalid_api_key",
                    error_message=("Invalid Azure Speech credentials · Check key and region"),
                )
            return ConnectionTestResponse(
                success=False,
                error_code="network_error",
                error_message="Azure Speech connection failed",
            )

    # provider == "image"
    if not request.endpoint_url:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/validation",
                "title": "endpoint_url required for image",
                "status": 422,
            },
        )
    try:
        headers: dict[str, str] = {}
        if request.endpoint_key:
            headers["Authorization"] = f"Bearer {request.endpoint_key}"
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            resp = await client_http.get(
                request.endpoint_url.rstrip("/") + "/models", headers=headers
            )
        if resp.status_code in (200, 404):  # 404 is OK — endpoint reachable
            return ConnectionTestResponse(
                success=True, sample_translation="Image endpoint reachable"
            )
        if resp.status_code in (401, 403):
            return ConnectionTestResponse(
                success=False,
                error_code="invalid_api_key",
                error_message="Invalid API key for image endpoint",
            )
        return ConnectionTestResponse(
            success=False,
            error_code="network_error",
            error_message=f"Endpoint returned {resp.status_code}",
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        return ConnectionTestResponse(
            success=False,
            error_code="network_error",
            error_message="Cannot reach image endpoint · Verify the URL",
        )
    except Exception:  # noqa: BLE001
        return ConnectionTestResponse(
            success=False,
            error_code="network_error",
            error_message="Image endpoint connection failed",
        )


# ── Save credentials ──────────────────────────────────────────────────────────


class SaveCredentialsRequest(BaseModel):
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    azure_speech_key: str | None = None
    azure_speech_region: str | None = None
    image_endpoint_url: str | None = None
    image_endpoint_key: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "SaveCredentialsRequest":
        if all(v is None for v in self.model_dump().values()):
            raise ValueError("At least one credential field must be provided")
        return self


class SaveCredentialsResponse(BaseModel):
    saved: bool


@router.post("/credentials", response_model=SaveCredentialsResponse)
async def save_credentials(
    request: SaveCredentialsRequest,
) -> SaveCredentialsResponse:
    """Save credentials to OS keychain via services/credentials.py.

    SECURITY: Credential values are NEVER logged — only key names.
    After saving, provider cache is invalidated so next request uses new credentials.
    """
    credential_map = {
        "openrouter_api_key": OPENROUTER_API_KEY,
        "openrouter_model": OPENROUTER_MODEL,
        "azure_speech_key": AZURE_SPEECH_KEY,
        "azure_speech_region": AZURE_SPEECH_REGION,
        "image_endpoint_url": IMAGE_ENDPOINT_URL,
        "image_endpoint_key": IMAGE_ENDPOINT_KEY,
    }
    for field_name, cred_key in credential_map.items():
        value = getattr(request, field_name)
        if value is not None:
            set_credential(cred_key, value)
            logger.info("credential.saved", key=cred_key)  # NEVER log value
    invalidate_provider_cache()
    return SaveCredentialsResponse(saved=True)


# ── Delete credentials ────────────────────────────────────────────────────────

_PROVIDER_CREDENTIAL_KEYS: dict[str, list[str]] = {
    "openrouter": [OPENROUTER_API_KEY, OPENROUTER_MODEL],
    "azure": [AZURE_SPEECH_KEY, AZURE_SPEECH_REGION],
    "image": [IMAGE_ENDPOINT_URL, IMAGE_ENDPOINT_KEY],
}


@router.delete("/credentials/{provider}", status_code=204)
async def remove_credentials(provider: str) -> Response:
    """Remove credentials for a provider from the OS keychain.

    Returns 204 on success, 422 on unknown provider.
    """
    if provider not in _PROVIDER_CREDENTIAL_KEYS:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/validation",
                "title": (f"Unknown provider '{provider}'. Must be: openrouter, azure, image"),
                "status": 422,
            },
        )
    for key in _PROVIDER_CREDENTIAL_KEYS[provider]:
        delete_credential(key)
        logger.info("credential.deleted", key=key)
    invalidate_provider_cache()
    return Response(status_code=204)
