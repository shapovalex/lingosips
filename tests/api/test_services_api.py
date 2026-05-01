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

    async def test_returns_qwen_local_when_no_openrouter_key(self, client: AsyncClient) -> None:
        """Mock qwen status → 200, llm.provider='qwen_local', llm.model=null."""
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["llm"]["provider"] == "qwen_local"
        assert body["llm"]["model"] is None

    async def test_returns_openrouter_when_key_configured(self, client: AsyncClient) -> None:
        """Mock openrouter status → 200, llm.provider='openrouter', llm.model set."""
        with patch(_PATCH_TARGET, return_value=_openrouter_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["llm"]["provider"] == "openrouter"
        assert body["llm"]["model"] == "openai/gpt-4o-mini"

    async def test_returns_pyttsx3_for_speech_when_no_azure(self, client: AsyncClient) -> None:
        """No Azure credentials → speech.provider='pyttsx3'."""
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        assert body["speech"]["provider"] == "pyttsx3"

    async def test_returns_azure_for_speech_when_configured(self, client: AsyncClient) -> None:
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

    async def test_always_returns_200_even_without_db(self, client: AsyncClient) -> None:
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

    async def test_response_shape_matches_rfc7807_not_wrapped(self, client: AsyncClient) -> None:
        """Response is direct model — no 'data' wrapper envelope."""
        with patch(_PATCH_TARGET, return_value=_openrouter_status()):
            response = await client.get("/services/status")

        assert response.status_code == 200
        body = response.json()
        # Must NOT be wrapped in {"data": ...} envelope
        assert "data" not in body
        assert "status" not in body

    async def test_llm_status_has_all_required_fields(self, client: AsyncClient) -> None:
        """llm object must include provider, model, last_latency_ms, last_success_at."""
        with patch(_PATCH_TARGET, return_value=_openrouter_status()):
            response = await client.get("/services/status")

        llm = response.json()["llm"]
        assert "provider" in llm
        assert "model" in llm
        assert "last_latency_ms" in llm
        assert "last_success_at" in llm

    async def test_speech_status_has_all_required_fields(self, client: AsyncClient) -> None:
        """speech object must include provider, last_latency_ms, last_success_at."""
        with patch(_PATCH_TARGET, return_value=_qwen_status()):
            response = await client.get("/services/status")

        speech = response.json()["speech"]
        assert "provider" in speech
        assert "last_latency_ms" in speech
        assert "last_success_at" in speech


# ── TestConnectionTest ────────────────────────────────────────────────────────

from unittest.mock import AsyncMock  # noqa: E402

from lingosips.services.credentials import (  # noqa: E402
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    IMAGE_ENDPOINT_URL,
    IMAGE_ENDPOINT_KEY,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
)


class TestConnectionTest:
    """Tests for POST /services/test-connection — credentials NOT saved."""

    async def test_openrouter_bad_key_returns_success_false_with_error_code(
        self, client: AsyncClient
    ) -> None:
        """Bad API key → 200 {"success": false, "error_code": "invalid_api_key"}"""
        with patch("lingosips.api.services.OpenRouterProvider") as mock_cls:
            instance = mock_cls.return_value
            instance.complete = AsyncMock(
                side_effect=RuntimeError("OpenRouter error 401: Unauthorized")
            )
            response = await client.post(
                "/services/test-connection",
                json={
                    "provider": "openrouter",
                    "api_key": "sk-bad",
                    "model": "openai/gpt-4o-mini",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "invalid_api_key"
        assert "Invalid API key" in body["error_message"]

    async def test_openrouter_success_returns_sample_translation(
        self, client: AsyncClient
    ) -> None:
        """Valid key → 200 {"success": true, "sample_translation": "hola"}"""
        with patch("lingosips.api.services.OpenRouterProvider") as mock_cls:
            instance = mock_cls.return_value
            instance.complete = AsyncMock(return_value="hola")
            response = await client.post(
                "/services/test-connection",
                json={
                    "provider": "openrouter",
                    "api_key": "sk-valid",
                    "model": "openai/gpt-4o-mini",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["sample_translation"] == "hola"
        assert body["error_code"] is None

    async def test_openrouter_missing_api_key_returns_422(
        self, client: AsyncClient
    ) -> None:
        """provider=openrouter without api_key → 422."""
        response = await client.post(
            "/services/test-connection",
            json={"provider": "openrouter"},  # api_key missing
        )
        assert response.status_code == 422

    async def test_missing_provider_returns_422(self, client: AsyncClient) -> None:
        """Empty body — provider is required → 422."""
        response = await client.post("/services/test-connection", json={})
        assert response.status_code == 422

    async def test_does_not_save_credentials_to_keyring(
        self, client: AsyncClient
    ) -> None:
        """Connection test must NEVER persist credentials."""
        with patch("lingosips.api.services.OpenRouterProvider") as mock_cls:
            instance = mock_cls.return_value
            instance.complete = AsyncMock(return_value="hola")
            with patch("lingosips.api.services.set_credential") as mock_save:
                await client.post(
                    "/services/test-connection",
                    json={
                        "provider": "openrouter",
                        "api_key": "sk-x",
                        "model": "openai/gpt-4o-mini",
                    },
                )
                mock_save.assert_not_called()

    async def test_network_error_returns_error_body(
        self, client: AsyncClient
    ) -> None:
        """ConnectError → 200 with error_code=network_error."""
        import httpx as _httpx

        with patch("lingosips.api.services.OpenRouterProvider") as mock_cls:
            instance = mock_cls.return_value
            instance.complete = AsyncMock(
                side_effect=_httpx.ConnectError("timeout")
            )
            response = await client.post(
                "/services/test-connection",
                json={
                    "provider": "openrouter",
                    "api_key": "sk-x",
                    "model": "openai/gpt-4o-mini",
                },
            )
        assert response.status_code == 200
        assert response.json()["error_code"] == "network_error"

    async def test_quota_exceeded_returns_specific_error(
        self, client: AsyncClient
    ) -> None:
        """429 error → 200 with error_code=quota_exceeded."""
        with patch("lingosips.api.services.OpenRouterProvider") as mock_cls:
            instance = mock_cls.return_value
            instance.complete = AsyncMock(
                side_effect=RuntimeError("OpenRouter error 429: quota exceeded")
            )
            response = await client.post(
                "/services/test-connection",
                json={
                    "provider": "openrouter",
                    "api_key": "sk-x",
                    "model": "openai/gpt-4o-mini",
                },
            )
        assert response.status_code == 200
        assert response.json()["error_code"] == "quota_exceeded"


# ── TestSaveCredentials & TestDeleteCredentials ───────────────────────────────


class TestSaveCredentials:
    """Tests for POST /services/credentials."""

    async def test_save_openrouter_credentials_returns_200(
        self, client: AsyncClient
    ) -> None:
        with patch("lingosips.api.services.set_credential") as mock_set, patch(
            "lingosips.api.services.invalidate_provider_cache"
        ) as mock_inv:
            response = await client.post(
                "/services/credentials",
                json={
                    "openrouter_api_key": "sk-test",
                    "openrouter_model": "openai/gpt-4o-mini",
                },
            )
        assert response.status_code == 200
        assert response.json()["saved"] is True
        mock_set.assert_any_call(OPENROUTER_API_KEY, "sk-test")
        mock_set.assert_any_call(OPENROUTER_MODEL, "openai/gpt-4o-mini")
        mock_inv.assert_called_once()

    async def test_save_credentials_empty_body_returns_422(
        self, client: AsyncClient
    ) -> None:
        """Body with all None values → 422 (at_least_one_field validator)."""
        response = await client.post("/services/credentials", json={})
        assert response.status_code == 422

    async def test_save_azure_credentials_stores_both_fields(
        self, client: AsyncClient
    ) -> None:
        with patch("lingosips.api.services.set_credential") as mock_set, patch(
            "lingosips.api.services.invalidate_provider_cache"
        ):
            response = await client.post(
                "/services/credentials",
                json={"azure_speech_key": "key123", "azure_speech_region": "eastus"},
            )
        assert response.status_code == 200
        mock_set.assert_any_call(AZURE_SPEECH_KEY, "key123")
        mock_set.assert_any_call(AZURE_SPEECH_REGION, "eastus")


class TestDeleteCredentials:
    """Tests for DELETE /services/credentials/{provider}."""

    async def test_delete_openrouter_credentials_returns_204(
        self, client: AsyncClient
    ) -> None:
        with patch("lingosips.api.services.delete_credential") as mock_del, patch(
            "lingosips.api.services.invalidate_provider_cache"
        ):
            response = await client.delete("/services/credentials/openrouter")
        assert response.status_code == 204
        mock_del.assert_any_call(OPENROUTER_API_KEY)
        mock_del.assert_any_call(OPENROUTER_MODEL)

    async def test_delete_unknown_provider_returns_422(
        self, client: AsyncClient
    ) -> None:
        response = await client.delete("/services/credentials/unknown")
        assert response.status_code == 422
