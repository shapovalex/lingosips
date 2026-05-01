"""Tests for GET /services/status endpoint — written BEFORE implementation (TDD).

Tests use mock of get_service_status_info() (not get_credential) to avoid keyring dependency
in API-layer tests. Follows same async test client pattern as other api tests.
"""

from unittest.mock import patch

from httpx import AsyncClient

from lingosips.services.registry import ServiceStatusInfo


def _qwen_status() -> ServiceStatusInfo:
    """Helper: ServiceStatusInfo for qwen_local + pyttsx3."""
    return ServiceStatusInfo(
        llm_provider="qwen_local",
        llm_model=None,
        speech_provider="pyttsx3",
    )


def _openrouter_status(model: str = "openai/gpt-4o-mini") -> ServiceStatusInfo:
    """Helper: ServiceStatusInfo for openrouter + pyttsx3."""
    return ServiceStatusInfo(
        llm_provider="openrouter",
        llm_model=model,
        speech_provider="pyttsx3",
    )


def _azure_status() -> ServiceStatusInfo:
    """Helper: ServiceStatusInfo for qwen_local + azure speech."""
    return ServiceStatusInfo(
        llm_provider="qwen_local",
        llm_model=None,
        speech_provider="azure",
    )


_PATCH_TARGET = "lingosips.api.services.get_service_status_info"


class TestGetServiceStatus:
    """Tests for GET /services/status (AC: 1, 2, 4)."""

    async def test_returns_qwen_local_when_no_openrouter_key(
        self, client: AsyncClient
    ) -> None:
        """Mock qwen status → 200, llm.provider='qwen_local', llm.model=null."""
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["llm"]["provider"] == "qwen_local"
        assert body["llm"]["model"] is None

    async def test_returns_openrouter_when_key_configured(
        self, client: AsyncClient
    ) -> None:
        """Mock openrouter status → 200, llm.provider='openrouter', llm.model set."""
        with patch(_PATCH_TARGET, return_value=_openrouter_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["llm"]["provider"] == "openrouter"
        assert body["llm"]["model"] == "openai/gpt-4o-mini"

    async def test_returns_pyttsx3_for_speech_when_no_azure(
        self, client: AsyncClient
    ) -> None:
        """No Azure credentials → speech.provider='pyttsx3'."""
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["speech"]["provider"] == "pyttsx3"

    async def test_returns_azure_for_speech_when_configured(
        self, client: AsyncClient
    ) -> None:
        """Azure configured → speech.provider='azure'."""
        with patch(_PATCH_TARGET, return_value=_azure_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["speech"]["provider"] == "azure"

    async def test_latency_and_timestamp_are_null_when_not_tracked(
        self, client: AsyncClient
    ) -> None:
        """Reserved fields (latency, timestamp) must be null when not yet tracked."""
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["llm"]["last_latency_ms"] is None
        assert body["llm"]["last_success_at"] is None
        assert body["speech"]["last_latency_ms"] is None
        assert body["speech"]["last_success_at"] is None

    async def test_always_returns_200_even_without_db(
        self, client: AsyncClient
    ) -> None:
        """Endpoint must NOT have Depends(get_session) — no DB access needed.

        Verifies by calling without seeding any DB state and confirming 200.
        Also verifies the response has the correct top-level structure.
        """
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        # Response must have exactly 'llm' and 'speech' top-level keys (no wrapper envelope)
        assert "llm" in body
        assert "speech" in body
        # No extra wrapper keys
        assert set(body.keys()) == {"llm", "speech"}

    async def test_response_shape_matches_rfc7807_not_wrapped(
        self, client: AsyncClient
    ) -> None:
        """Response is direct model — no 'data' wrapper envelope."""
        with patch(_PATCH_TARGET, return_value=_openrouter_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        # Must NOT be wrapped in {"data": ...} envelope
        assert "data" not in body
        assert "status" not in body

    async def test_llm_status_has_all_required_fields(
        self, client: AsyncClient
    ) -> None:
        """llm object must include provider, model, last_latency_ms, last_success_at."""
        with patch(_PATCH_TARGET, return_value=_openrouter_status()):
            response = await client.get("/services/status")

        llm = response.json()["llm"]
        assert "provider" in llm
        assert "model" in llm
        assert "last_latency_ms" in llm
        assert "last_success_at" in llm

    async def test_speech_status_has_all_required_fields(
        self, client: AsyncClient
    ) -> None:
        """speech object must include provider, last_latency_ms, last_success_at."""
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        speech = response.json()["speech"]
        assert "provider" in speech
        assert "last_latency_ms" in speech
        assert "last_success_at" in speech
